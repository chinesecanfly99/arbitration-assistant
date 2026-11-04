"""S1.2 / S1.3 经济补偿 N 与违法解除 2N。"""
from datetime import date

from arb.calc import ClaimInput, Policy, compute, economy_compensation


def make(**kw) -> ClaimInput:
    base = dict(hire_date=date(2017, 1, 1), end_date=date(2020, 1, 1), monthly_wage=10000.0)
    base.update(kw)
    return ClaimInput(**base)


def test_n_three_years():
    item = economy_compensation(make(), Policy())
    assert item.amount == 30000.0
    assert "3" in item.formula
    assert "第 47 条" in item.basis


def test_n_half_month():
    item = economy_compensation(make(hire_date=date(2020, 1, 1), end_date=date(2020, 4, 30)), Policy())
    assert item.amount == 5000.0  # 3 个月工龄 -> 半个月


def test_n_six_months_counts_as_one_year():
    item = economy_compensation(make(hire_date=date(2020, 1, 1), end_date=date(2020, 7, 1)), Policy())
    assert item.amount == 10000.0


def test_3x_cap_on_wage_and_12_year_cap():
    inp = make(
        hire_date=date(2000, 1, 1),
        end_date=date(2020, 1, 1),
        monthly_wage=30000.0,
        social_avg_wage=8000.0,
    )
    item = economy_compensation(inp, Policy())
    # 30000 > 3*8000=24000 -> 基数 24000；20 年工龄被压到 12 年
    assert item.amount == 24000.0 * 12
    assert "封顶" in item.note


def test_no_cap_when_below_3x():
    inp = make(monthly_wage=20000.0, social_avg_wage=8000.0)  # 20000 < 24000
    item = economy_compensation(inp, Policy())
    assert item.amount == 60000.0


def test_illegal_dismissal_is_2n():
    res = compute(make(termination="illegal_dismissal"))
    items = {i["name"]: i for i in res["items"]}
    assert items["违法解除赔偿金（2N）"]["amount"] == 60000.0
    assert "经济补偿金（N）" not in items, "2N 与 N 不应并用"
    assert res["total"] == 60000.0


def test_legal_termination_is_n():
    res = compute(make(termination="legal_termination"))
    names = [i["name"] for i in res["items"]]
    assert names == ["经济补偿金（N）"]
    assert res["total"] == 30000.0


def test_mutual_agreement_gets_n():
    res = compute(make(termination="mutual_agreement"))
    assert res["total"] == 30000.0


def test_employee_resign_no_compensation_and_warns():
    res = compute(make(termination="employee_resign"))
    assert res["items"] == []
    assert any("第 38 条" in w for w in res["warnings"])


def test_zero_wage_warns():
    res = compute(make(monthly_wage=0.0))
    assert any("月工资为 0" in w for w in res["warnings"])


def test_service_years_reported():
    res = compute(make())
    assert res["service_months"] == 36
    assert res["service_years"] == 3.0
    assert res["severance_months"] == 3.0
