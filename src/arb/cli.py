"""命令行入口：python -m arb.cli "我被公司辞了…"

存在的意义：不用等前端做好，就能把"输入一段大白话 → 拿到一份能核的计算单"这条闭环跑通，
而且它就是评测脚本调用的同一套代码——演示和评测不脱节。
"""
from __future__ import annotations

import json
import sys
from datetime import date

from . import llm
from .application import render_application, render_notes
from .pipeline import analyze

LINE = "─" * 62


def render_markdown(r: dict) -> str:
    out = []
    out.append("# 劳动仲裁金额测算单")
    city = (r.get("city") or {}).get("city")
    out.append(
        f"\n> 生成时间：{date.today().isoformat()}　口径城市：{city or '未覆盖（未套用任何城市数字）'}"
    )
    out.append(f"\n**当事人原话**：{r['story']}\n")

    if r["status"] == "need_more":
        out.append("## 现在还不能算，需要您补充：")
        for q in r["questions"]:
            out.append(f"- {q}")
        if r.get("relative"):
            out.append("\n**相对时间已自动推定，请确认：**")
            for x in r["relative"]:
                out.append(f"- {x}")
        return "\n".join(out)

    if r["status"] == "blocked":
        out.append("## 现在还不能申请（这道门进不去）\n")
        for b in r.get("blockers") or []:
            out.append(f"- **硬性障碍**：{b}")
        out.append("\n这不是算不出来，而是这件事现在不具备申请条件，所以不给金额——")
        out.append("一个看起来很确定的总数在这里只会误导你。")
        gates = r.get("gates") or {}
        for layer in gates.get("layers") or []:
            if layer.get("status") == "fail" or (layer.get("detail") and layer.get("key") == "qualification"):
                out.append(f"\n**{layer['title']}**：{layer['message']}")
                for d in layer.get("detail") or []:
                    out.append(f"- {d}")
        out.append(f"\n{LINE}")
        out.append("本单不构成法律意见；具体怎么办建议先拨 12348 免费问一遍。")
        return "\n".join(out)

    if r["status"] == "out_of_scope":
        scope = r.get("scope") or {}
        reason = scope.get("reason") or ""
        out.append(f"## 这件事不归劳动仲裁管：{reason}\n")
        if r.get("redirect"):
            out.append(f"**该去这里办**：{r['redirect']}\n")
        if r.get("hints"):
            out.append("**几点提醒：**")
            for h in r["hints"]:
                out.append(f"- {h}")
        out.append(f"\n{LINE}")
        out.append("本单只是根据您提供的信息做的初步判断，不构成法律意见，也不能代替律师。")
        out.append("如果拿不准归属，可先拨 12348（公共法律服务热线）问一句，免费。")
        return "\n".join(out)

    worth = r.get("worth") or {}
    if worth.get("decision_label"):
        out.append(
            f"> **结论：{worth['decision_label']}**（值得性 {worth.get('score')}/100）"
        )
        out.append("> 这不是胜诉率，也不预测裁判结果；只是把六件事放在一起，告诉你先做哪件。\n")

    out.append(f"## 一、可主张金额合计：**{r['total']:,.2f} 元**\n")
    out.append("| 项目 | 金额（元） | 算法 |")
    out.append("| --- | ---: | --- |")
    for it in r["items"]:
        out.append(f"| {it['name']} | {it['amount']:,.2f} | {it['formula']} |")
    out.append(f"| **合计** | **{r['total']:,.2f}** | |")

    out.append("\n## 二、每一项的法律依据（可逐条核对）\n")
    for it in r["items"]:
        flag = "✅" if it["cite_ok"] else "⚠️ 引用未通过校验"
        out.append(f"**{it['name']}** {flag}")
        out.append(f"- 依据：{it['basis']}")
        for c in it["cite_texts"]:
            out.append(f"  - {c['cite']}：{c['text']}")
        if it.get("note"):
            out.append(f"  - 说明：{it['note']}")
        out.append("")

    if r.get("reference_cases"):
        out.append("\n### 类案参考（按案由与案情线索选取）\n")
        out.append("请结合本人证据与案件差异阅读。案例结果仅供参考。\n")
        for case in r["reference_cases"]:
            out.append(f"**{case['title']}** · [{case['source']}]({case['url']})")
            for label, key in (("争议焦点", "focus"), ("处理结果", "result"),
                               ("可比点", "compare"), ("区别", "distinguish")):
                out.append(f"- {label}：{case[key]}")
            out.append("")

    out.append("## 三、仲裁时效（别让权利睡过期）\n")
    out.append("| 请求 | 起算日 | 截止日 | 剩余天数 |")
    out.append("| --- | --- | --- | ---: |")
    for d in r["deadlines"]:
        left = "—" if d["days_left"] is None else ("已过期" if d["expired"] else f"{d['days_left']} 天")
        out.append(f"| {d['label']} | {d['anchor']} | {d['deadline']} | {left} |")

    if r.get("assumptions"):
        out.append("\n## 四、本单暂时采用的口径（请确认）\n")
        for a in r["assumptions"]:
            out.append(f"- {a}")
    if r.get("relative"):
        out.append("\n**相对时间推定（请确认）：**")
        for x in r["relative"]:
            out.append(f"- {x}")

    gates = r.get("gates") or {}
    if gates.get("layers"):
        out.append("\n## 五、能不能申请（三道闸门）\n")
        for layer in gates["layers"]:
            mark = {"pass": "✅", "warn": "⚠️", "fail": "⛔", "info": "ℹ️"}.get(layer.get("status"), "·")
            out.append(f"{mark} **{layer['title']}**：{layer['message']}")
            for d in layer.get("detail") or []:
                out.append(f"   - {d}")
            if layer.get("cites"):
                out.append(f"   - 依据：{'、'.join(layer['cites'])}")

    ev = r.get("evidence_score") or {}
    mats = r.get("materials") or []
    if mats:
        out.append("\n## 六、要带什么（材料清单 + 谁举证）\n")
        if ev:
            out.append(
                f"证据强度：**{ev.get('score')}/100**（{ev.get('level')}）"
                + ("" if ev.get("known", True) else "——你还没说手上有哪些材料，这一维按中性算")
            )
        out.append("\n| 材料 | 有/缺 | 谁举证 | 怎么拿 |")
        out.append("| --- | --- | --- | --- |")
        for m in mats:
            out.append(
                f"| {m['name']} | {'有' if m['have'] else '缺'} | {m['burden']} | {m['how']} |"
            )
        for g in (ev.get("gaps") or []):
            out.append(f"\n- {g}")

    venue = r.get("venue") or []
    if venue:
        out.append("\n## 七、去哪办（立案路径）\n")
        for b in venue:
            out.append(f"**{b['stage']}　{b['name']}**")
            if b.get("where"):
                out.append(f"- 地点：{b['where']}")
            if b.get("hours"):
                out.append(f"- 时间：{b['hours']}")
            out.append(f"- 说明：{b['note']}")
            tels = [a["value"] for a in b.get("actions") or [] if a.get("kind") == "tel"]
            if tels:
                out.append(f"- 电话：{'、'.join(tels)}")
            out.append("")

    if worth.get("dimensions"):
        out.append("## 八、值不值得去（六维加权）\n")
        out.append("| 维度 | 权重 | 分数 | 为什么 |")
        out.append("| --- | ---: | ---: | --- |")
        for d in worth["dimensions"]:
            out.append(
                f"| {d['label']} | {int(round(d['weight'] * 100))}% | {d['score']} | {d['note']} |"
            )
        out.append(f"\n**总分 {worth.get('score')}/100　结论：{worth.get('decision_label')}**")
        alt = worth.get("alternative")
        if alt:
            out.append(f"\n更快的路：**{alt['title']}**——{alt['why']}（{alt['tel']}）")
        if r.get("one_final_note"):
            out.append(f"\n一裁终局：{r['one_final_note']}")

    if r.get("warnings"):
        out.append("\n## 提醒\n")
        for w in r["warnings"]:
            out.append(f"- {w}")

    pending = r.get("pending") or []
    if pending:
        out.append("\n## 还没确认的读数（本单没有采用）\n")
        for p in pending:
            if p.get("reason") == "conflict":
                out.append(
                    f"- **{p['label']}**：你原话说的是 {p['from_story']}（本单按这个算），"
                    f"模型读到的是 {p['suggested']}——不一致，不替你选"
                )
            else:
                out.append(f"- **{p['label']}**：模型读到 {p['suggested']}，等确认后才参与计算")
        out.append("\n（网页版可以逐项勾选确认；命令行加 `--confirm` 表示全部认可）")

    out.append("\n" + LINE)
    out.append("本单只是根据您提供的信息做的初步测算，不构成法律意见，也不能代替律师。")
    out.append("正式申请前请核对工资流水、社保记录和劳动合同原件；符合条件可拨 12348 申请法律援助。")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1
    story = " ".join(a for a in argv if not a.startswith("--"))
    as_json = "--json" in argv
    mode = "best_effort" if "--best-effort" in argv else "strict"
    accept_model = "--confirm" in argv

    fields_override = {}
    if llm.available():
        try:
            got = llm.extract_fields(story)
            fields_override = got["fields"]
            for b in got["bad"]:
                print(f"[模型输出已丢弃] {b}", file=sys.stderr)
        except Exception as e:  # 网络/额度/格式问题都不该让整条流水线挂掉
            print(f"[模型层不可用，改用规则抽取] {e}", file=sys.stderr)
    else:
        print("[未配置模型：使用规则抽取，结果仅供参考]", file=sys.stderr)

    # 模型读数默认**不进计算**，要人点头。命令行用 --confirm 一次性认可全部读数；
    # 更严谨的做法是去网页版逐项勾选（那里的确认是逐字段的）。
    confirmed = list(fields_override) if accept_model else []

    r = analyze(story, mode=mode, hints=fields_override, confirmed=confirmed)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str) if as_json else render_markdown(r))
    return 0 if r["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
