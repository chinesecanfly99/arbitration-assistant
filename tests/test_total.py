"""S1.7 汇总：各项相加、顺序稳定、struct 可被前端直接吃。"""
from datetime import date

import pytest

from arb.calc import ClaimInput, compute


def test_total_is_sum_of_items():
    inp = ClaimInput(
        hire_date=date(2020, 1, 1),
        end_date=date(2021, 1, 1),
        monthly_wage=10000.0,
        termination="illegal_dismissal",
        has_written_contract=False,
        overtime_workday_hours=10,
        unpaid_wages=5000.0,
    )
    res = compute(inp)
    names = [i["name"] for i in res["items"]]
    # 2N(20000) + 二倍工资(110000) + 加班费(862.07) + 欠薪(5000)
    assert names == ["违法解除赔偿金（2N）", "未签书面劳动合同二倍工资", "加班费", "拖欠工资"]
    assert res["total"] == 135862.07
    assert pytest.approx(res["total"]) == sum(i["amount"] for i in res["items"])


def test_illegal_2n_plus_unpaid():
    inp = ClaimInput(
        hire_date=date(2020, 1, 1),
        end_date=date(2023, 1, 1),
        monthly_wage=10000.0,
        termination="illegal_dismissal",
        unpaid_wages=5000.0,
    )
    res = compute(inp)
    assert res["total"] == 65000.0


def test_every_item_carries_formula_and_basis():
    inp = ClaimInput(
        hire_date=date(2020, 1, 1),
        end_date=date(2023, 1, 1),
        monthly_wage=10000.0,
        termination="legal_termination",
        overtime_holiday_hours=5,
        unpaid_wages=1000.0,
    )
    res = compute(inp)
    assert res["items"], "至少要算出一项"
    for item in res["items"]:
        assert item["formula"], f"{item['name']} 缺计算过程"
        assert "第" in item["basis"], f"{item['name']} 缺法条依据"
        assert item["amount"] >= 0


def test_result_shape_is_json_safe():
    import json

    inp = ClaimInput(
        hire_date=date(2020, 1, 1), end_date=date(2020, 4, 30), monthly_wage=8000.0
    )
    res = compute(inp)
    text = json.dumps(res, ensure_ascii=False)  # 不能有 date 对象漏出来
    assert "经济补偿金" in text
    assert res["total"] == 4000.0  # 3 个月工龄 -> 半个月
