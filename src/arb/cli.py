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
    out.append(f"\n> 生成时间：{date.today().isoformat()}　口径城市：深圳（示例）")
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
    if r.get("warnings"):
        out.append("\n## 提醒\n")
        for w in r["warnings"]:
            out.append(f"- {w}")

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

    r = analyze(story, mode=mode, hints=fields_override)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str) if as_json else render_markdown(r))
    return 0 if r["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
