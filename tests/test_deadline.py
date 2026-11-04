"""S1.8 仲裁时效：1 年、三种起算点、欠薪存续期间例外、中断重算。"""
from datetime import date

from arb.deadline import (
    CLAIM_DISMISSAL,
    CLAIM_WAGE,
    analyze,
    limitation,
)


def test_one_year_deadline():
    r = limitation(CLAIM_DISMISSAL, date(2025, 3, 1), today=date(2025, 9, 1))
    assert r.applicable is True
    assert r.deadline == date(2026, 3, 1)
    assert r.days_left == 181
    assert r.expired is False
    assert r.urgent is False


def test_expired():
    r = limitation(CLAIM_DISMISSAL, date(2025, 3, 1), today=date(2026, 4, 1))
    assert r.expired is True
    assert r.days_left == -31
    assert "已超过仲裁时效" in r.note
    assert "12348" in r.note


def test_urgent_within_30_days():
    r = limitation(CLAIM_DISMISSAL, date(2025, 3, 1), today=date(2026, 2, 10))
    assert r.days_left == 19
    assert r.urgent is True and r.expired is False
    assert "立即" in r.note


def test_boundary_30_days_is_urgent():
    r = limitation(CLAIM_DISMISSAL, date(2025, 3, 1), today=date(2026, 1, 30))
    assert r.days_left == 30
    assert r.urgent is True


def test_boundary_31_days_not_urgent():
    r = limitation(CLAIM_DISMISSAL, date(2025, 3, 1), today=date(2026, 1, 29))
    assert r.days_left == 31
    assert r.urgent is False


def test_wage_while_employed_is_not_time_barred():
    r = limitation(CLAIM_WAGE, date(2024, 1, 1), today=date(2026, 1, 1), employment_ongoing=True)
    assert r.applicable is False
    assert r.deadline is None
    assert "不受一年时效限制" in r.note


def test_wage_after_termination_runs_from_end():
    r = limitation(CLAIM_WAGE, date(2024, 6, 1), today=date(2024, 12, 1), employment_ongoing=False)
    assert r.applicable is True
    assert r.deadline == date(2025, 6, 1)
    assert r.days_left == 182


def test_missing_anchor_asks_for_info():
    r = limitation(CLAIM_DISMISSAL, None, today=date(2025, 1, 1))
    assert r.deadline is None
    assert "补全" in r.note


def test_interruption_restarts_clock():
    r = limitation(
        CLAIM_DISMISSAL,
        date(2024, 1, 1),
        today=date(2025, 6, 1),
        interrupted_on=date(2025, 1, 1),
    )
    assert r.anchor == date(2025, 1, 1)
    assert r.deadline == date(2026, 1, 1)
    assert r.days_left == 214
    assert "重新起算" in r.note


def test_leap_day_anchor():
    r = limitation(CLAIM_DISMISSAL, date(2024, 2, 29), today=date(2024, 6, 1))
    assert r.deadline == date(2025, 2, 28)


def test_analyze_covers_all_claims():
    results = analyze(end_date=date(2025, 3, 1), today=date(2025, 6, 1))
    assert len(results) == 5
    d = {r.claim_type: r for r in results}
    assert d[CLAIM_DISMISSAL].anchor == date(2025, 3, 1)
    assert all(r.as_dict()["deadline"] is not None for r in results)


def test_analyze_ongoing_job_keeps_wage_unlimited():
    results = analyze(end_date=None, today=date(2025, 6, 1), employment_ongoing=True)
    d = {r.claim_type: r for r in results}
    assert d[CLAIM_WAGE].applicable is False
    assert d[CLAIM_DISMISSAL].deadline is None  # 未离职，无解除日


def test_anchor_override():
    results = analyze(
        end_date=date(2025, 3, 1),
        today=date(2025, 6, 1),
        anchors={CLAIM_WAGE: date(2024, 1, 1)},
    )
    d = {r.claim_type: r for r in results}
    assert d[CLAIM_WAGE].anchor == date(2024, 1, 1)
