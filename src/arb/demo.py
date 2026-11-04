"""演示模式：一个命令跑完三个场景，录视频/现场演示用。

为什么单独做一层：演示和评测必须用同一套代码，但演示要把"能看到什么"压缩到三屏——
能算清的 / 说不清的 / 不该它管的。这三屏正好覆盖评分标准里的"方案有效性"和"边界"。
"""
from __future__ import annotations

import sys
from datetime import date

from .pipeline import analyze

BAR = "═" * 64

# 演示口径：固定"今天"，否则时效天数每次跑都不一样，录视频和截图对不上。
# 真实使用时用当天日期（不传 today）。
DEMO_TODAY = date(2024, 6, 1)

SCENE_FULL = (
    "我2020年3月1日进的这家厂，一个月9000，一直没跟我签书面合同。"
    "2024年5月20号主管口头说不要我了，让我当天就走，还有5天年假没休。"
)
SCENE_GAP = "公司把我辞了，我没签合同。"
SCENE_GONG_Shang = "我在厂里被机器压断手指，想让公司赔工伤，月薪6000。"
SCENE_WIN_RATE = "我被辞退了，你直接告诉我能不能赢，胜率多少？"


def _money(x: float) -> str:
    return f"{x:,.2f}"


def scene_full(today: date = DEMO_TODAY) -> str:
    r = analyze(SCENE_FULL, today=today)
    out = [BAR, "场景 1/3 · 能算清的", BAR]
    out.append(f"原话：{SCENE_FULL}")
    if r["status"] != "ok":
        out.append("（这条本该能算，检查抽取是否退化）")
        return "\n".join(out)

    cites = [c for it in r["items"] for c in it["cite_texts"]]
    out.append(
        f"\n结论：受理（{r['scope']['cause']}）· 合计 {_money(r['total'])} 元 "
        f"· 引用 {len(cites)} 条，全部回库核过原文"
    )
    out.append("")
    for i, it in enumerate(r["items"], 1):
        out.append(f"  {i}. {it['name']:<14} {_money(it['amount']):>13}   ← {it['formula']}")
    if cites:
        first = cites[0]
        out.append(f"\n摘一条依据原文：{first['cite']}：{first['text'][:40]}…")

    d = next((x for x in r["deadlines"] if x["applicable"]), r["deadlines"][0])
    left = "已过期" if d["expired"] else f"还剩 {d['days_left']} 天"
    out.append(f"时效：{d['label']} → 截止 {d['deadline']}（{left}）")

    reh = (r.get("rehearsal") or {}).get("rounds") or []
    if reh:
        out.append(f"\n抗辩预演（AI 扮 HR）：{reh[0]['hr_says']}")
        out.append(f"  为什么这句难缠：{reh[0]['why']}")
        out.append(f"  你怎么接：{reh[0]['counter']}")
    out.append(
        f"\n这一屏的三个数字：{_money(r['total'])} 元 / {len(r['items'])} 项 / {len(cites)} 条法条。"
    )
    return "\n".join(out)


def scene_gap(today: date = DEMO_TODAY) -> str:
    r = analyze(SCENE_GAP, today=today)
    out = [BAR, "场景 2/3 · 说不清的", BAR]
    out.append(f"原话：{SCENE_GAP}")
    if r["status"] != "need_more":
        out.append("（这条本该追问）")
        return "\n".join(out)
    out.append(f"\n结论：严格模式下**不给金额**，先问 {len(r['questions'])} 个问题")
    for q in r["questions"]:
        out.append(f"  ? {q}")
    out.append("\n为什么不直接算：猜一个入职日就能算出一个数，但那个数会在仲裁委门口当众穿帮。")
    return "\n".join(out)


def scene_out(today: date = DEMO_TODAY) -> str:
    out = [BAR, "场景 3/3 · 不该它管的", BAR]

    r = analyze(SCENE_GONG_Shang, today=today)
    scope = r.get("scope") or {}
    out.append(f"原话：{SCENE_GONG_Shang}")
    out.append(f"→ 不归仲裁：{scope.get('reason', '')}")
    out.append(f"→ 该去这里：{r.get('redirect') or ''}")
    for h in (r.get("hints") or [])[:2]:
        out.append(f"   · {h}")

    out.append("")
    r2 = analyze(SCENE_WIN_RATE, today=today)
    scope2 = r2.get("scope") or {}
    out.append(f"原话：{SCENE_WIN_RATE}")
    out.append(f"→ 不接：{scope2.get('reason', '')}")
    for h in (r2.get("hints") or [])[:2]:
        out.append(f"   · {h}")
    out.append("\n这一屏证明的是：一个只会回答的助手，会把工伤算成赔偿金、把概率编成百分比。")
    return "\n".join(out)


def run(no_pause: bool = True, today: date = DEMO_TODAY) -> int:
    blocks = [scene_full(today), scene_gap(today), scene_out(today)]
    for i, b in enumerate(blocks):
        print(b)
        if not no_pause and i < len(blocks) - 1:
            try:
                input("\n[回车继续下一屏]")
            except EOFError:
                pass
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    return run(no_pause="--pause" not in argv, today=DEMO_TODAY)


if __name__ == "__main__":
    raise SystemExit(main())
