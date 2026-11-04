"""评测口径工具：金额是否命中，以及"年假没说就不计入"的处理。

为什么需要它：
有些案例的金标准里带了"未休年假 5 天"这类故事里根本没说的数字。
系统此时正确行为是**追问**，不是猜一个年假天数出来——猜对了是运气，猜错了是误导。
所以这类案例比金额时，两边都把"未休年休假工资"这一项剔掉，单独记一笔"待确认"。
"""
from __future__ import annotations

import re

ANNUAL_LEAVE_ITEM = "未休年休假工资"
ANNUAL_HINT = re.compile(r"年假|年休假")
# 故事里要出现具体天数才算"用户告诉了天数"，否则系统只能追问
ANNUAL_DAYS = re.compile(r"\d+\s*天[^。；，]{0,6}年假|年假[^。；，]{0,6}\d+\s*天")


def mentions_annual_leave(story: str) -> bool:
    return bool(ANNUAL_HINT.search(story or ""))


def states_annual_leave_days(story: str) -> bool:
    return bool(ANNUAL_DAYS.search(story or ""))


def _sum_without(items, names_to_drop) -> float:
    return sum(float(i.get("amount") or 0) for i in items if i.get("name") not in names_to_drop)


def amount_matches(story: str, report: dict, expected: dict, tol: float = 1.0) -> bool:
    """True 表示系统算出的金额与金标准一致（口径见模块 docstring）。"""
    drop = set()
    if not states_annual_leave_days(story):
        drop.add(ANNUAL_LEAVE_ITEM)
    got = _sum_without(report.get("items") or [], drop)
    want = _sum_without(expected.get("items") or [], drop)
    return abs(got - want) < tol
