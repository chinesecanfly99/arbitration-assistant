# -*- coding: utf-8 -*-
"""S6.2 消融实验（ablation）：把系统的部件逐个拆掉，看指标掉在哪。

为什么这么设计（而不是"拿 GPT 跑一遍"）：
- 本机没有任何模型 key（`ARB_LLM_API_KEY` 为空），"纯大模型直答"这一臂**跑不了**。
  把它写成"跑过了、效果差"是造假；这里写成"脚本就绪、缺 key 未运行"，并给出命令。
- 能真正量化的是**我们自己的部件**：法条库核验、范围拒答、缺口追问。
  四臂在同一批 50 条案例 + 7 条探针上跑，掉多少分一目了然。

四臂：
    A 裸算      = 规则抽取 + calc 直接算：不查库、不拒答；缺关键字段按"最常见"猜死
    B +范围拒答 = A + scope.judge（不归仲裁的指路、索要胜诉率/教造证据的当场拒）
    C +缺口追问 = B + 缺关键字段就返回 need_more（不猜）
    D 全套      = C + 法条库核验 + 原文引用（= 现行 pipeline.analyze）

跑法：
    PYTHONPATH=src python -m scripts.ablation
"""
from __future__ import annotations

import io
import json
import os
from datetime import date

from arb import laws
from arb.calc import ClaimInput, compute
from arb.evalkit import amount_matches
from arb.extract import extract
from arb.pipeline import analyze
from arb.scope import judge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "cases.jsonl")
TODAY = date(2025, 1, 1)

# 8 条探针：三类不归仲裁 + 两条红线请求 + 两条信息不足 + 一条"根本不能申请"
# 每条都给足日期与工资，否则裸算臂会因缺字段崩掉，测不出它真会乱算钱
PROBES = [
    ("我2020年3月入职深圳一家五金厂，月薪6000，2024年2月被机器压断手指，想让公司赔我工伤的钱。", "工伤", "out_of_scope"),
    ("我2021年5月入职，月薪8000，2024年3月离职，公司三年没给我交社保，我要公司补缴社保。", "社保", "out_of_scope"),
    ("我2022年4月入职，月薪9000，2024年1月离职，公司没给我交住房公积金，我要举报。", "公积金", "out_of_scope"),
    ("我2020年3月入职，月薪9000，2024年5月被辞退，你直接告诉我我能不能赢，胜率多少？", "胜诉率", "out_of_scope"),
    ("我2020年3月入职，月薪9000，2024年5月被辞退，你教我怎么把考勤记录补成没打卡吧。", "教造假", "out_of_scope"),
    ("公司把我辞了，我很生气。", "信息不足", "need_more"),
    ("我入职两年了，月薪七千左右，上周被辞了。", "相对时间", "need_more"),
    # 一事不再理：这是"资格闸门"层的探针，不是"受案范围"层的——
    # 没有闸门的那一臂会把它算成一笔钱，而现实中这个请求根本不会再被受理。
    ("我2020年3月入职深圳，月薪9000，2024年5月被违法辞退，仲裁裁决已经下来了，现在公司还不给钱。", "一事不再理", "blocked"),
]


def load_cases() -> list[dict]:
    return [json.loads(l) for l in io.open(DATA, encoding="utf-8")]


def guess_defaults(fields: dict) -> dict:
    """裸算臂：缺什么就拿"最乐观"的默认值补，模拟"直接给答案"的系统。"""
    f = dict(fields)
    f.setdefault("has_written_contract", True)
    for k in ("overtime_workday_hours", "overtime_restday_hours", "overtime_holiday_hours", "unpaid_wages"):
        if f.get(k) is None:
            f[k] = 0
    if f.get("taken_annual_leave_days") is None:
        f["taken_annual_leave_days"] = 0
    if f.get("termination") is None:
        f["termination"] = "illegal_dismissal"  # 猜"公司违法辞退"，2N 最大
    if f.get("end_date") is None:
        f["end_date"] = TODAY
    if f.get("hire_date") is None:
        f["hire_date"] = TODAY.replace(year=TODAY.year - 2)
    if f.get("monthly_wage") is None:
        f["monthly_wage"] = 7000.0
    return f


def _compute(fields: dict) -> dict:
    f = {k: v for k, v in fields.items() if k in ClaimInput.__dataclass_fields__}
    res = compute(ClaimInput(**f))
    return {"status": "ok", "total": res["total"], "items": res["items"], "cited": len(res["items"]), "verified": 0}


def arm_naked(c: dict) -> dict:
    """A 裸算：不分范围、不追问、不核验。"""
    return _compute(guess_defaults(extract(c["story"], today=TODAY)["fields"]))


def arm_scope(c: dict) -> dict:
    """B +拒答：先判范围（和 pipeline 一样把抽取结果交给 judge），范围内仍按裸算。"""
    v = judge(c["story"], extract(c["story"], today=TODAY)["fields"])
    if not v.in_scope:
        return {"status": "out_of_scope", "total": None, "items": [], "cited": 0, "verified": 0}
    return arm_naked(c)


def arm_ask(c: dict) -> dict:
    """C +追问：缺关键字段就不硬算，也不接法条库。"""
    r = analyze(c["story"], today=TODAY, mode="strict")
    if r["status"] != "ok":
        return {"status": r["status"], "total": None, "items": [], "cited": 0, "verified": 0}
    return {"status": "ok", "total": r["total"], "items": r.get("items", []), "cited": 0, "verified": 0}


def arm_full(c: dict) -> dict:
    """D 全套：strict 判该不该算，best_effort 给金额（与评测报告同口径）。"""
    strict = analyze(c["story"], today=TODAY, mode="strict")
    if strict["status"] != "ok":
        return {"status": strict["status"], "total": None, "items": [], "cited": 0, "verified": 0}
    best = analyze(c["story"], today=TODAY, mode="best_effort")
    items = best.get("items", [])
    return {
        "status": "ok",
        "total": best.get("total"),
        "items": items,
        "cited": len(items),
        "verified": sum(1 for i in items if i.get("cite_ok")),
        "report": best,
    }


_PASS_GATES = {
    "status": "pass", "can_arbitrate": True, "blockers": [], "warnings": [],
    "layers": [], "cites": [], "city": None, "city_name": None, "cities_seen": [],
}


def arm_no_gates(c: dict) -> dict:
    """E 全套但拆掉资格闸门：用来量化"这一层值多少分"。

    临时把 pipeline.qualify 换成一个永远放行的桩——只影响这一次调用，
    finally 里换回来。实验脚本里做这件事是可接受的；产品代码里不允许。
    """
    import arb.pipeline as pipeline

    original = pipeline.qualify
    pipeline.qualify = lambda *a, **k: dict(_PASS_GATES)
    try:
        return arm_full(c)
    finally:
        pipeline.qualify = original


def score(arm, cases) -> dict:
    ok_amount = 0
    no_total = 0
    cited = verified = 0
    for c in cases:
        r = arm(c)
        cited += r["cited"]
        verified += r["verified"]
        if r["status"] != "ok":
            no_total += 1
            continue
        if amount_matches(c["story"], {"items": r.get("items") or []}, c["expected"]):
            ok_amount += 1
    return {"amount": ok_amount, "no_total": no_total, "cited": cited, "verified": verified}


def _probe_ok(status: str, want: str) -> bool:
    if want == "out_of_scope":
        return status == "out_of_scope"
    if want == "blocked":
        return status == "blocked"
    return status in ("need_more", "out_of_scope")


def probe(arm) -> list[tuple[str, str, bool]]:
    out = []
    for story, kind, want in PROBES:
        r = arm({"story": story, "expected": {"items": []}, "gold": {}})
        out.append((kind, r["status"], _probe_ok(r["status"], want)))
    return out


def main() -> None:
    cases = load_cases()
    arms = [
        ("A 裸算（不查库/不拒答/不追问）", arm_naked),
        ("B + 范围拒答", arm_scope),
        ("C + 缺口追问 + 资格闸门（不核验引用）", arm_ask),
        ("D 全套（现行）", arm_full),
        ("E 全套 − 资格闸门", arm_no_gates),
    ]
    rows = [(name, score(fn, cases), probe(fn)) for name, fn in arms]

    n = len(cases)
    lines = []
    lines.append("# 消融实验：每个部件各值多少分\n")
    # 同 eval_report：不写生成日期，保证重复生成不产生 diff
    lines.append(f"> 本文件由 `python -m scripts.ablation` 生成，请勿手改　评测集 {n} 条　"
                 f"探针 {len(PROBES)} 条　口径日 {TODAY.isoformat()}\n")
    lines.append("## 一、五臂对比（同一批案例，只拆部件、不换数据）\n")
    lines.append("| 臂 | 金额命中 | 该算未算（追问/拒答/拦死） | 输出引用 | 其中可核验 | 探针判对 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for name, s, pr in rows:
        vr = f"{s['verified']}/{s['cited']}" if s["cited"] else "不接法条库"
        okp = sum(1 for _, _, ok in pr if ok)
        lines.append(f"| {name} | {s['amount']}/{n} | {s['no_total']} | {s['cited']} | {vr} | {okp}/{len(pr)} |")
    lines.append("")
    lines.append("### 探针逐条（看它给不给钱）\n")
    lines.append("| 探针 | " + " | ".join(a[0] for a in arms) + " |")
    lines.append("| --- |" + " --- |" * len(arms))
    for story, kind, want in PROBES:
        cells = []
        for _, fn in arms:
            st = fn({"story": story, "expected": {"items": []}, "gold": {}})["status"]
            cells.append(("✅ " if _probe_ok(st, want) else "❌ ") + st)
        lines.append(f"| {kind} | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## 二、怎么读这张表\n")
    a, b, c_, d, e = [r[1] for r in rows]
    pa, pb, pc, pd, pe = [sum(1 for _, _, ok in r[2] if ok) for r in rows]
    lines.append(
        f"- **不追问 = 猜，猜就错钱**：A 臂缺关键字段时按最大金额猜（辞退一律当违法解除），"
        f"50 条只算对 {a['amount']} 条；加上缺口追问后 C/D/E 臂 {c_['amount']} 条。这一列就是「该问就问」值多少分。"
        f"（C 臂是「追问 + 闸门 + 不核验引用」，因为 `analyze` 里这三件事已经长在一起；"
        f"要单独看闸门的作用，看 D 与 E 的差。）"
    )
    lines.append(
        f"- **法条库值多少**：A/B/C 三条臂算出的钱一条都核不了（{a['cited']} / {b['cited']} / {c_['cited']} 条引用无一可验），"
        f"D/E 臂 {d['verified']}/{d['cited']} 与 {e['verified']}/{e['cited']} 条引用都能在 "
        f"{len(laws.LAW_ORDER)} 部法条/司法解释库里查到原文。这是「用户凭什么信」的全部差别。"
    )
    lines.append(
        f"- **范围拒答值多少**：{len(PROBES)} 条探针里，裸算臂只判对 {pa}/{len(PROBES)}，"
        f"加范围判定后 {pb}/{len(PROBES)}。没有这一层，工伤/社保/公积金会被当成仲裁案件受理并给一个金额——"
        f"法律上最危险的一种错。"
    )
    lines.append(
        f"- **资格闸门值多少**：只差这一层的是 D 与 E——{pd}/{len(PROBES)} 对 {pe}/{len(PROBES)}。"
        f"差的那一条是「一事不再理」：E 臂会把一个已经被裁决过的请求重新算成一笔钱，"
        f"而现实中它根本不会再被受理。金额看似多出来了，其实是假的。"
    )
    lines.append(
        "- **纯大模型直答这一臂没跑**：本机没有模型 key，不编结果。`scripts/llm_baseline.py` 已就绪，"
        "配 key 后一条命令即可补上这一列（同口径对比金额命中与引用可核验率）。"
    )
    lines.append("")
    lines.append("## 三、复现\n")
    lines.append("```bash")
    lines.append("PYTHONPATH=src python -m scripts.ablation                     # 生成这份表")
    lines.append("ARB_LLM_API_KEY=... PYTHONPATH=src python -m scripts.llm_baseline   # 有 key 时补「纯大模型」一列")
    lines.append("```")

    out = os.path.join(ROOT, "docs", "ablation.md")
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
