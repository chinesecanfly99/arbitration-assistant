"""规则抽取基线在 50 条案例上的评测（S3.1 证据）。

用法：PYTHONPATH=src python -m scripts.eval_extract [--today 2025-01-01]
输出三块：
  1. 逐字段准确率（抽取质量）
  2. 端到端金额命中率（抽取→calc 算出来跟金标准差 <1% 才算对）——这才是用户能感知的指标
  3. 未命中清单（区分"抽错"和"故事里压根没说"）
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

from arb.extract import extract
from arb.pipeline import analyze

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "data", "cases.jsonl")


def norm(v):
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return v
    return v


def main() -> int:
    today = date(2025, 1, 1)
    if "--today" in sys.argv:
        today = date.fromisoformat(sys.argv[sys.argv.index("--today") + 1])

    rows = [json.loads(l) for l in open(CASES, encoding="utf-8") if l.strip()]
    stats: dict[str, list[int]] = {}
    fails: dict[str, list[str]] = {}
    amount_ok, amount_rows = 0, []

    for c in rows:
        out = extract(c["story"], today=today)
        got, ev = out["fields"], out["evidence"]
        for k, gold_v in c["gold"].items():
            if k not in got:
                continue
            g = norm(gold_v)
            v = got[k]
            if k in ("monthly_wage", "unpaid_wages"):
                ok = g is not None and v is not None and abs(float(v) - float(g)) <= max(1.0, 0.01 * float(g))
            elif g is None:
                ok = True
            else:
                ok = (v == g)
            s = stats.setdefault(k, [0, 0])
            s[1] += 1
            if ok:
                s[0] += 1
            else:
                fails.setdefault(k, []).append(f"{c['id']}(金={g},抽={v})")

        # 端到端：走完整流水线（含"缺字段就不硬算"的规则）
        r = analyze(c["story"], today=today, mode="best_effort")
        if r["status"] != "ok":
            amount_rows.append((c["id"], "need_more", "缺 " + ",".join(r["missing"])))
            continue
        got_total = r["total"]
        want = c["expected"]["total"]
        ok = abs(got_total - want) <= max(1.0, 0.01 * want)
        amount_ok += ok
        amount_rows.append((c["id"], ok, f"{got_total:,.2f} vs {want:,.2f}"))

    print(f"今日基准：{today}")
    print(f"\n{'字段':30s} {'命中':>4s}/{'总数':>4s}  准确率")
    print("-" * 56)
    tot_hit = tot_n = 0
    for k, (hit, n) in sorted(stats.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        tot_hit += hit
        tot_n += n
        print(f"{k:30s} {hit:4d}/{n:4d}   {hit / n:6.1%}")
    print("-" * 56)
    print(f"{'字段合计':30s} {tot_hit:4d}/{tot_n:4d}   {tot_hit / tot_n:6.1%}")
    print(f"\n端到端金额命中：{amount_ok}/{len(rows)} = {amount_ok / len(rows):.1%}")
    bad = [r for r in amount_rows if r[1] is not True]
    print(f"未命中 {len(bad)} 条：")
    for cid, ok, detail in bad[:20]:
        print(f"  {cid}  {detail}")
    for k, ids in fails.items():
        if k in ("hire_date", "end_date", "termination"):
            print(f"\n[{k}] 失败 {len(ids)}：{', '.join(ids[:6])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
