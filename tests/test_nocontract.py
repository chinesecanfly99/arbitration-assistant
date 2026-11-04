"""S1.4 未签书面合同二倍工资：满一个月次日起，最多 11 个月。"""
from datetime import date

import pytest

from arb.calc import ClaimInput, Policy, compute, double_wage


def make(**kw) -> ClaimInput:
    base = dict(
        hire_date=date(2024, 1, 1),
        end_date=date(2025, 1, 1),
        monthly_wage=10000.0,
        has_written_contract=False,
        termination="legal_termination",
    )
    base.update(kw)
    return ClaimInput(**base)


def test_default_signed_contract_means_no_claim():
    inp = ClaimInput(hire_date=date(2024, 1, 1), end_date=date(2025, 1, 1), monthly_wage=10000)
    assert inp.has_written_contract is True
    assert double_wage(inp, Policy()) is None


def test_never_signed_capped_at_11_months():
    item = double_wage(make(), Policy())
    assert item.amount == 110000.0
    assert "11" in item.formula
    assert "第 82 条" in item.basis


def test_signed_after_four_months():
    item = double_wage(make(contract_signed_date=date(2024, 6, 1)), Policy())
    # 2024-02-02 ~ 2024-05-31 = 120 天 = 4 个月
    assert item.amount == 40000.0
    assert "120 天" in item.formula


def test_signed_within_first_month_no_claim():
    item = double_wage(make(contract_signed_date=date(2024, 2, 1)), Policy())
    assert item is None


def test_late_signing_after_one_year_still_capped():
    item = double_wage(make(contract_signed_date=date(2025, 6, 1)), Policy())
    assert item.amount == 110000.0


def test_partial_month_policy_switch():
    inp = make(contract_signed_date=date(2024, 6, 15))
    strict = double_wage(inp, Policy(double_wage_round_up_partial_month=False))
    loose = double_wage(inp, Policy(double_wage_round_up_partial_month=True))
    assert strict.amount == 40000.0   # 134 天 -> 4 个月
    assert loose.amount == 50000.0    # 不足一月按一月 -> 5 个月


def test_double_wage_note_is_about_the_other_multiple():
    item = double_wage(make(), Policy())
    assert "另一倍" in item.note


def test_double_wage_in_total():
    res = compute(make())
    names = [i["name"] for i in res["items"]]
    assert "未签书面劳动合同二倍工资" in names
    assert pytest.approx(res["total"]) == 110000.0 + 10000.0  # 11 个月二倍 + 1 个月 N
