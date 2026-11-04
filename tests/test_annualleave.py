"""S1.6 未休年休假：档位 5/10/15 天，按当年已过天数折算，额外 200%。"""
from datetime import date

import pytest

from arb.calc import ClaimInput, Policy, annual_leave_entitlement, annual_leave_pay


def make(**kw) -> ClaimInput:
    base = dict(
        hire_date=date(2020, 1, 1),
        end_date=date(2025, 12, 31),
        monthly_wage=10000.0,
        termination="legal_termination",
    )
    base.update(kw)
    return ClaimInput(**base)


DAILY = 10000.0 / 21.75  # 459.7701...


@pytest.mark.parametrize(
    "years,days",
    [(0.5, 0), (0.99, 0), (1, 5), (9.9, 5), (10, 10), (19.9, 10), (20, 15), (35, 15)],
)
def test_entitlement_tiers(years, days):
    assert annual_leave_entitlement(years) == days


def test_full_year_five_days():
    item = annual_leave_pay(make(total_work_years=3), Policy())
    assert item.amount == pytest.approx(5 * DAILY * 2.0, rel=1e-9)
    assert round(item.amount, 2) == 4597.70


def test_prorated_by_elapsed_days():
    item = annual_leave_pay(make(end_date=date(2025, 7, 2), total_work_years=11), Policy())
    # 10 天 * 183/365 = 5.01 -> 5 天
    assert item.amount == pytest.approx(5 * DAILY * 2.0, rel=1e-9)


def test_twenty_years_fifteen_days():
    item = annual_leave_pay(make(total_work_years=21), Policy())
    assert item.amount == pytest.approx(15 * DAILY * 2.0, rel=1e-9)


def test_less_than_one_year_no_entitlement():
    assert annual_leave_pay(make(total_work_years=0.5), Policy()) is None


def test_taken_days_subtracted():
    item = annual_leave_pay(make(total_work_years=3, taken_annual_leave_days=2), Policy())
    assert item.amount == pytest.approx(3 * DAILY * 2.0, rel=1e-9)


def test_explicit_unused_days_wins():
    item = annual_leave_pay(make(unused_annual_leave_days=3), Policy())
    assert item.amount == pytest.approx(3 * DAILY * 2.0, rel=1e-9)
    assert "按用户提供" in item.note


def test_zero_unused_returns_none():
    assert annual_leave_pay(make(total_work_years=3, taken_annual_leave_days=5), Policy()) is None
