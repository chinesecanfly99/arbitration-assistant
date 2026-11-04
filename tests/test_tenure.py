"""S1.1 工龄折算：满 1 年 1 个月 / 6 个月以上不满 1 年按 1 年 / 不满 6 个月半个月。"""
from datetime import date

import pytest

from arb.calc import service_months, severance_months_by_law


@pytest.mark.parametrize(
    "hire,end,expected_months,expected_severance_months",
    [
        # 差一天满一年 -> 11 个月工龄，但"六个月以上不满一年"按一年，仍给 1 个月
        (date(2020, 1, 15), date(2021, 1, 14), 11, 1.0),
        # 正好满一年
        (date(2020, 1, 15), date(2021, 1, 15), 12, 1.0),
        # 5 个月 -> 半个月
        (date(2020, 1, 1), date(2020, 6, 30), 5, 0.5),
        # 正好 6 个月 -> 按一年，1 个月
        (date(2020, 1, 1), date(2020, 7, 1), 6, 1.0),
        # 6 个月零 30 天 -> 仍 6 个月整
        (date(2020, 1, 1), date(2020, 7, 31), 6, 1.0),
        # 5 年整
        (date(2015, 3, 1), date(2020, 3, 1), 60, 5.0),
        # 5 年 6 个月 -> 6 个月
        (date(2015, 3, 1), date(2020, 9, 1), 66, 6.0),
        # 5 年 5 个月 -> 5.5 个月
        (date(2015, 3, 1), date(2020, 8, 1), 65, 5.5),
        # 月末入职：3/31 到 9/30 只满 5 个月
        (date(2020, 3, 31), date(2020, 9, 30), 5, 0.5),
        # 闰日入职
        (date(2020, 2, 29), date(2021, 2, 28), 11, 1.0),
        # 不满一个月
        (date(2020, 1, 10), date(2020, 1, 20), 0, 0.5),
        # 10 年整
        (date(2010, 5, 1), date(2020, 5, 1), 120, 10.0),
    ],
)
def test_tenure(hire, end, expected_months, expected_severance_months):
    months = service_months(hire, end)
    assert months == expected_months
    assert severance_months_by_law(months) == expected_severance_months


def test_end_before_hire_raises():
    with pytest.raises(ValueError):
        service_months(date(2020, 5, 1), date(2020, 4, 1))
