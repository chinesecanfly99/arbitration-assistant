# -*- coding: utf-8 -*-
"""S6.2 的第三臂：纯大模型直答（有 key 才能跑）。

和"我们这套"的区别就一句话：**让模型自己算钱**，不给它规则内核、不给它法条库。
跑出来的每条都做两件事后处理：
1. 金额与金标准比（与 evalkit.amount_matches 同口径）；
2. 模型自己写的"依据"逐条拿去 laws.resolve_name / laws.exists 核 —— 核不到就是幻觉引用。

没有 key 时**不编结果**：打印"未运行"，退出码 2。这样 CI 和一键复现都不会假装跑过。

用法：
    ARB_LLM_API_KEY=sk-... PYTHONPATH=src python -m scripts.llm_baseline
    # 可选：ARB_LLM_BASE_URL / ARB_LLM_MODEL
产物：
    docs/llm_baseline.jsonl   每条一行
    stdout                    汇总（可直接贴进 docs/ablation.md）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import date

from arb import laws, llm
from arb.evalkit import amount_matches

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "cases.jsonl")
OUT = os.path.join(ROOT, "docs", "llm_baseline.jsonl")
TODAY = date(2025, 1, 1)

PROMPT = """你是劳动争议领域的律师助理。请**直接**根据当事人的话算清楚他能拿到哪些钱。
只输出 JSON：
{"items":[{"name":"项目名","amount":数字,"basis":"依据的法律与条号，例如《劳动合同法》第87条"}],"total":数字}
说明：算不清的项不要列；不要写解释；金额单位是元。
当事人原话：
"""

CITE = re.compile(r"《([^》]+)》第\s*([零一二三四五六七八九十百\d]+)\s*条")


def parse_basis_cites(basis: str) -> tuple[int, int]:
    """返回 (引用条数, 其中能在法条库里核到的条数)。"""
    total = ok = 0
    for m in CITE.finditer(basis or ""):
        total += 1
        slug = laws.resolve_name(m.group(1))
        no = str(laws.cn_to_int(m.group(2))) if not m.group(2).isdigit() else m.group(2)
        if slug and laws.exists(slug, no):
            ok += 1
    return total, ok


def ask_model(story: str) -> dict:
    """一次调用，返回解析后的 JSON；失败抛异常由上层记 fail。"""
    return llm.call(PROMPT + story)


def main() -> int:
    if not llm.available():
        print("未运行：没有配置 ARB_LLM_API_KEY / OPENAI_API_KEY。")
        print("这把'纯大模型直答'的臂留空，不编结果——配 key 后重跑同一条命令即可补齐。")
        return 2

    cases = [json.loads(l) for l in io.open(DATA, encoding="utf-8")]
    ok_amount = ok_cite_all = cite_total = cite_ok = 0
    rows = []
    for c in cases:
        try:
            out = ask_model(c["story"])
        except Exception as e:  # noqa: BLE001 网络/解析失败都记一条
            rows.append({"id": c["id"], "error": f"{type(e).__name__}: {e}"})
            continue
        items = out.get("items") or []
        tot, good = 0, 0
        for i in items:
            t, g = parse_basis_cites(str(i.get("basis", "")))
            tot += t
            good += g
        cite_total += tot
        cite_ok += good
        hit = amount_matches(c["story"], {"items": items}, c["expected"])
        ok_amount += bool(hit)
        ok_cite_all += bool(tot and good == tot)
        rows.append({"id": c["id"], "items": items, "amount_hit": hit, "cites": [tot, good]})

    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    )
    n = len(cases)
    print(f"纯大模型直答：金额命中 {ok_amount}/{n}，引用可核验 {cite_ok}/{cite_total}，"
          f"整单引用全真 {ok_cite_all}/{n}（日期口径 {TODAY}）")
    print(f"明细已写入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
