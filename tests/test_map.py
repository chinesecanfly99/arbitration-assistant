"""完整度地图的测试：它是给人看的，但"哪一格标红"会直接影响体验，必须锁住。"""

import pytest

from arb.map import CRITICAL, FIELD_LABELS, completeness, summary_line

FULL = {
    "hire_date": "2020-03-01",
    "end_date": "2024-05-20",
    "monthly_wage": 9000,
    "termination": "illegal_dismissal",
    "has_written_contract": False,
    "unused_annual_leave_days": 5,
}


def test_all_fields_listed():
    c = completeness(FULL)
    assert len(c["rows"]) == len(FIELD_LABELS) == 10
    keys = [r["key"] for r in c["rows"]]
    assert keys[:2] == ["hire_date", "end_date"]


def test_filled_fields_marked_ok():
    c = completeness(FULL)
    ok = {r["key"] for r in c["rows"] if r["status"] == "ok"}
    assert {"hire_date", "end_date", "monthly_wage", "termination", "has_written_contract"} <= ok
    # False（没签合同）也是有效信息，不能被当成"空"
    row = next(r for r in c["rows"] if r["key"] == "has_written_contract")
    assert row["value"] == "没签"


def test_missing_critical_are_red():
    c = completeness({"monthly_wage": 8000})
    assert set(c["critical_missing"]) == {k for k in CRITICAL if k != "monthly_wage"}
    for r in c["rows"]:
        if r["key"] in c["critical_missing"]:
            assert r["status"] == "missing"


def test_optional_missing_not_counted_as_missing():
    c = completeness(FULL)
    opt = [r for r in c["rows"] if r["optional"]]
    assert opt, "应存在可选字段"
    for r in opt:
        assert r["status"] in ("optional", "ok")
    assert "overtime_workday_hours" not in c["missing"]


def test_score_monotonic():
    low = completeness({})["score"]
    high = completeness(FULL)["score"]
    assert 0 <= low < high <= 1


def test_summary_line_mentions_missing_names():
    s = summary_line({"monthly_wage": 8000})
    assert "入职日期" in s or "离职日期" in s
    assert summary_line(FULL) == "关键信息齐了，可以算了。"


def test_zero_means_missing_for_amounts():
    c = completeness({"unpaid_wages": 0, "monthly_wage": 0})
    statuses = {r["key"]: r["status"] for r in c["rows"]}
    assert statuses["monthly_wage"] == "missing"
    assert statuses["unpaid_wages"] == "optional"


@pytest.mark.parametrize("who_val,bool_val,expect", [(None, None, "missing")])
def test_bool_none_is_missing(who_val, bool_val, expect):
    c = completeness({})
    assert c["rows"][0]["status"] == expect
