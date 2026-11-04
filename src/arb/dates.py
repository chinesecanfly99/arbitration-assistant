"""日期工具：不依赖第三方库（避免三周项目被 requirements 拖死）。"""
from __future__ import annotations

import calendar
from datetime import date


def add_months(d: date, n: int) -> date:
    """按日历月加减，自动处理月末（1/31 + 1 月 -> 2/28 或 2/29）。"""
    total = d.month - 1 + n
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_years(d: date, n: int) -> date:
    return add_months(d, 12 * n)


def months_between(start: date, end: date) -> int:
    """start 到 end 之间的**整月数**；不满一整月不计。允许 end<start 时返回 0。"""
    if end < start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def days_inclusive(start: date, end: date) -> int:
    """闭区间天数；end < start 返回 0。"""
    if end < start:
        return 0
    return (end - start).days + 1


def days_elapsed_in_year(d: date) -> int:
    """d 在当年已过多少天（含当日）。"""
    return d.timetuple().tm_yday
