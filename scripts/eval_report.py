"""生成一页评测报告：python -m scripts.eval_report

把"我们做得怎么样"从嘴说变成数字。报告里每个数字都由本脚本现算，
不手抄——否则迟早出现过期数字和代码对不上。
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import date

from arb import laws
from arb.calc import ClaimInput, compute
from arb.extract import extract
from arb.evalkit import amount_matches, states_annual_leave_days
from arb.pipeline import analyze
from arb.scope import check_red_lines

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = date(2025, 1, 1)
FIELDS = ["hire_date", "end_date", "monthly_wage", "termination", "has_written_contract"]

# 只有出现这些说法，才认为"故事明确交代了解除方式"；只说"离职"不算——
# 单独一个"离职"既可能是自己走，也可能是被辞，系统此时正确行为是不猜、去问。
EXPLICIT_TERM = re.compile(
    r"辞退|辞了|开除|不要我|让我走|走人|违法解除|协商一致|协商解除|主动辞职|我辞职|"
    r"自己走|到期|期满|不续签|待岗|旷工|自动离职|试用期不合格|不合格|裁员|优化|"
    r"解除|终止|赶我走|不让我干"
)


def termination_bucket(story: str) -> str:
    return "explicit" if EXPLICIT_TERM.search(story) else "ambiguous"


def end_date_ok(story: str, got, gold) -> bool:
    """故事只说到"某月"时，按月粒度比；说到"某日"才要求日级一致。"""
    if got is None:
        return False
    if str(got) == str(gold):
        return True
    g, w = date.fromisoformat(str(got)), date.fromisoformat(str(gold))
    if (g.year, g.month) != (w.year, w.month):
        return False
    # 必须带年份再找"某日"：否则会把入职日（如"2023年1月3日入职"）误当离职日精度
    has_day = re.search(rf"{w.year}\s*年\s*{w.month}\s*月\s*\d{{1,2}}\s*[日号]", story)

    return has_day is None
LABELS = {
    "hire_date": "入职日期", "end_date": "离职日期", "monthly_wage": "月薪",
    "termination": "解除方式", "has_written_contract": "是否签书面合同",
}


def norm(v):
    if isinstance(v, date):
        return v.isoformat()
    return v


def load_cases() -> list[dict]:
    with open(os.path.join(ROOT, "data", "cases.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def gold_expected(case) -> float:
    """金标准里的日期是 ISO 字符串，进 ClaimInput 前转成 date。"""
    gold = dict(case["gold"])
    for k in ("hire_date", "end_date", "contract_signed_date"):
        if isinstance(gold.get(k), str):
            gold[k] = date.fromisoformat(gold[k])
    return compute(ClaimInput(**gold))["total"]


def main() -> None:
    cases = load_cases()
    hit = Counter()
    total = Counter()
    fails: list[tuple[str, str, str]] = []
    strict_ok = 0
    loose_ok = 0
    annual_unknown = 0
    errors: list[float] = []
    red_lines = 0
    cite_items = 0
    cite_bad = 0
    asked: list[int] = []
    out_of_scope_ok = 0

    amb_total = amb_ok = 0
    for c in cases:
        got = extract(c["story"], today=TODAY)["fields"]
        for k in FIELDS:
            if k == "termination" and termination_bucket(c["story"]) == "ambiguous":
                continue  # 故事没说清，不该要求它猜
            total[k] += 1
            if k == "end_date":
                ok = end_date_ok(c["story"], got.get(k), c["gold"].get(k))
            else:
                ok = norm(got.get(k)) == norm(c["gold"].get(k))
            if ok:
                hit[k] += 1
            elif len(fails) < 12:
                fails.append((c["id"], LABELS[k], f'期望 {norm(c["gold"].get(k))} / 抽到 {norm(got.get(k))}'))
        if termination_bucket(c["story"]) == "ambiguous":
            amb_total += 1
            if got.get("termination") is None:
                amb_ok += 1

    for c in cases:
        expect = gold_expected(c)
        r_strict = analyze(c["story"], today=TODAY, mode="strict")
        if r_strict["status"] == "ok":
            strict_ok += 1
        r = analyze(c["story"], today=TODAY, mode="best_effort")
        if r["status"] != "ok":
            continue
        if amount_matches(c["story"], r, c["expected"]):
            loose_ok += 1
        if not states_annual_leave_days(c["story"]):
            annual_unknown += 1
        errors.append(abs(r["total"] - expect))
        md = json.dumps(r, ensure_ascii=False, default=str)
        red_lines += len(check_red_lines(md))
        for it in r["items"]:
            cite_items += 1
            if not it["cite_ok"]:
                cite_bad += 1
        asked.append(len(r.get("questions", [])))

    # 范围判定：拿 5 条明显不归仲裁的句子测
    probes = [
        ("在工地从架子上摔下来骨折了，算工伤吗", "工伤"),
        ("公司三年没给我交社保，能补缴吗", "社保"),
        ("公积金少交了两千，能仲裁要回来吗", "公积金"),
        ("2020年3月1日入职，月薪9000，2024年5月20日被违法辞退", None),
        ("2022年6月1日入职，月薪7000，公司拖欠两个月工资", None),
    ]
    detail = []
    for story, kind in probes:
        r = analyze(story, today=TODAY, mode="best_effort")
        got_out = r["status"] == "out_of_scope"
        ok = (kind is not None) == got_out
        out_of_scope_ok += ok
        detail.append((story[:16] + "…", "不归仲裁" if got_out else "受理", "✅" if ok else "❌"))

    n = len(cases)
    field_acc = {k: hit[k] / total[k] for k in FIELDS}
    overall = sum(hit.values()) / sum(total.values())

    lines = []
    lines.append("# 劳动仲裁维权助手 · 评测报告\n")
    # 不写 date.today()：生成物必须可复现，否则「重新生成一遍」永远产生 diff，
    # CI 就没法用 `git diff --exit-code docs/` 检查"文档是否跟代码一致"。
    lines.append(f"> 本文件由 `python -m scripts.eval_report` 生成，请勿手改　"
                 f"案例 {n} 条　口径日 {TODAY.isoformat()}\n")
    acc_end = field_acc["end_date"]
    lines.append("## 一、一句话结论" + chr(10))
    lines.append(
        "规则抽取能覆盖 %.1f%% 的要素，端到端严格模式 %d/%d 可自足计算，试算模式金额命中 %d/%d（%d%%），"
        "法条引用 %d/%d 通过核验，红线表述 %d 条。"
        % (overall * 100, strict_ok, n, loose_ok, n, round(loose_ok / n * 100),
           cite_items - cite_bad, cite_items, red_lines)
    )
    worst = sorted(FIELDS, key=lambda k: field_acc[k])
    missed = [(k, total[k] - hit[k]) for k in FIELDS if hit[k] < total[k]]
    if not missed:
        lines.append("五个字段全部命中 50/50：**没有一个要素是靠猜的**。")
    else:
        detail_txt = "、".join(f"{LABELS[k]} {hit[k]}/{total[k]}" for k, _ in missed)
        lines.append(
            "残余误差只剩：%s。其中解除方式只在 %d 条「故事说清楚了」的样本上计分，"
            "另 %d 条只说了「离职」、没说谁提的——这部分故意不猜，转成追问。"
            % (detail_txt, total["termination"], amb_total)
        )
    lines.append("")
    lines.append("## 二、逐字段准确率（50 条故事）\n")
    lines.append("| 字段 | 命中 | 准确率 |")
    lines.append("| --- | ---: | ---: |")
    for k in FIELDS:
        lines.append(f"| {LABELS[k]} | {hit[k]}/{total[k]} | {field_acc[k]:.1%} |")
    lines.append(f"| **合计** | **{sum(hit.values())}/{sum(total.values())}** | **{overall:.1%}** |")
    lines.append("")
    lines.append("")
    lines.append(
        "> 解除方式只在 %d 条「故事说清楚了」的样本上计分；另 %d 条故事只说了「离职」、没说谁提的——这部分不猜，直接追问。当前对这类样本如实留空 **%d/%d**。"
        % (total["termination"], amb_total, amb_ok, amb_total)
    )
    lines.append("")
    lines.append("## 三、端到端（能不能算对钱）")
    lines.append("| 指标 | 结果 | 说明 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| 严格模式可自足 | {strict_ok}/{n} | 信息够、直接出金额 |")
    lines.append(f"| 试算模式金额命中 | {loose_ok}/{n}（{loose_ok/n:.0%}） | 与金标准误差 <1 元 |")
    lines.append(
        f"| 其中「故事没说年假天数」 | {annual_unknown} 条 | 两边都剔掉年假项再比（系统应追问天数，不该猜） |"
    )
    lines.append(
        f"| 其中「故事说了年假天数」 | {n - annual_unknown} 条 | 这部分的年假项是真比了的 |"
    )
    med = sorted(errors)[len(errors) // 2] if errors else 0
    lines.append(f"| 金额误差中位数 | {med:,.2f} 元 | 未命中的单子错得有多离谱 |")
    lines.append(f"| 平均追问次数 | {sum(asked)/len(asked):.2f} | 一次最多问 2 个 |")
    lines.append(f"| 法条引用核验 | {cite_items - cite_bad}/{cite_items} | 每条金额的法条都要能在库里找到原文 |")
    lines.append(f"| 系统输出红线 | {red_lines} | 预测胜诉/教造假/包赢，必须为 0 |")

    lines.append("\n## 四、范围判定（不归仲裁的要指对路）\n")
    lines.append("| 输入 | 判定 | 对不对 |")
    lines.append("| --- | --- | --- |")
    for s, got, ok in detail:
        lines.append(f"| {s} | {got} | {ok} |")
    lines.append(f"\n准确 {out_of_scope_ok}/{len(probes)}。三类指路：工伤→人社局工伤科、社保→社保征收机构/12333、公积金→公积金管理中心。")

    if fails:
        lines.append("\n## 五、典型失误（抽取层）\n")
        lines.append("| 案例 | 字段 | 明细 |")
        lines.append("| --- | --- | --- |")
        for cid, f, d in fails[:10]:
            lines.append(f"| {cid} | {f} | {d} |")

    lines.append("\n## 六、法律边界声明\n")
    lines.append("- 只覆盖内地劳动争议仲裁，不涉及工伤认定、社保补缴、公积金。")
    lines.append("- 不预测胜诉率、不代替律师；符合条件引导 12348 法律援助。")
    lines.append("- 所有金额由规则内核计算并附法条原文，模型只负责抽参数。\n")

    out = os.path.join(ROOT, "docs", "eval_report.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:14]))
    print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
