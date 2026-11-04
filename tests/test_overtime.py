"""S1.5 加班费：工作日 150% / 休息日 200% / 法定节假日 300%，日工资按 21.75 折算。"""
from datetime import date

import pytest

from arb.calc import ClaimInput, Policy, compute, overtime_pay


def make(**kw) -> ClaimInput:
    base = dict(
        hire_date=date(2022, 1, 1),
        end_date=date(2023, 1, 1),
        monthly_wage=10000.0,
        termination="legal_termination",
    )
    base.update(kw)
    return ClaimInput(**base)


HOURLY = 10000.0 / 21.75 / 8.0  # 57.471264...


def test_no_overtime_no_item():
    assert overtime_pay(make(), Policy()) is None


def test_workday_150():
    item = overtime_pay(make(overtime_workday_hours=10), Policy())
    assert item.amount == pytest.approx(10 * HOURLY * 1.5, rel=1e-9)
    assert "150%" in item.formula


def test_restday_200():
    item = overtime_pay(make(overtime_restday_hours=8), Policy())
    assert item.amount == pytest.approx(8 * HOURLY * 2.0, rel=1e-9)


def test_restday_with_comp_time_is_zero():
    item = overtime_pay(
        make(overtime_restday_hours=8, restday_compensated_by_leave=True), Policy()
    )
    assert item.amount == pytest.approx(0.0)
    assert "调休" in item.formula


def test_statutory_holiday_300():
    item = overtime_pay(make(overtime_holiday_hours=3), Policy())
    assert item.amount == pytest.approx(3 * HOURLY * 3.0, rel=1e-9)
    assert "300%" in item.formula


def test_all_three_combined():
    item = overtime_pay(
        make(
            overtime_workday_hours=10,
            overtime_restday_hours=8,
            overtime_holiday_hours=3,
        ),
        Policy(),
    )
    expected = 10 * HOURLY * 1.5 + 8 * HOURLY * 2.0 + 3 * HOURLY * 3.0
    assert item.amount == pytest.approx(expected, rel=1e-9)
    assert round(item.amount, 2) == 2298.85


def test_combined_rounds_in_total():
    res = compute(
        make(
            overtime_workday_hours=10,
            overtime_restday_hours=8,
            overtime_holiday_hours=3,
        )
    )
    items = {i["name"]: i for i in res["items"]}
    assert items["加班费"]["amount"] == 2298.85


def test_basis_is_labor_law_44():
    item = overtime_pay(make(overtime_workday_hours=1), Policy())
    assert "第 44 条" in item.basis
