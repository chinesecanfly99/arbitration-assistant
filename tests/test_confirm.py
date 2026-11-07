"""确认链的测试：没经过用户点头的读数，一律不进计算。

这条规则是"负功能"里最值钱的一条：
模型把 9000 读成 12000、把 5 天年假读成 15 天，如果直接进 calc，
屏幕上就会出来一个**看起来很确定**的错数字——比"算不出来"危险得多。
所以这里钉三种行为：未确认 → 不用；确认 → 才用；口述与读数冲突 → 不擅自择一。
"""
from datetime import date

from arb.pipeline import analyze, merge_hints
from arb.web import pending_html

STORY = "2020年3月1日入职，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了。"
TODAY = date(2025, 1, 1)


def _names(r):
    return [i["name"] for i in r["items"]]


def test_unconfirmed_reading_is_not_used():
    r = analyze(STORY, today=TODAY, hints={"unpaid_wages": 5000}, mode="best_effort")
    assert r["status"] == "ok"
    assert [p["key"] for p in r["pending"]] == ["unpaid_wages"]
    assert r["pending"][0]["reason"] == "unconfirmed"
    # 规则抽取给的是占位 0，未确认的读数不许把它改成 5000
    assert r["fields"]["unpaid_wages"] == 0, "未确认的读数不许写进字段"
    assert "拖欠工资" not in _names(r)
    assert any("没有**用它们算钱" in a or "没有" in a for a in r["assumptions"])


def test_confirmed_reading_changes_the_money():
    base = analyze(STORY, today=TODAY, hints={"unpaid_wages": 5000}, mode="best_effort")
    ok = analyze(STORY, today=TODAY, hints={"unpaid_wages": 5000},
                 confirmed=["unpaid_wages"], mode="best_effort")
    assert ok["pending"] == []
    assert "拖欠工资" in _names(ok)
    assert round(ok["total"] - base["total"], 2) == 5000.0


def test_conflict_keeps_story_value_and_does_not_pick_a_side():
    r = analyze(STORY, today=TODAY, hints={"monthly_wage": 12000}, mode="best_effort")
    p = next(x for x in r["pending"] if x["key"] == "monthly_wage")
    assert p["reason"] == "conflict"
    assert p["from_story"] == 9000 and p["suggested"] == 12000
    assert r["fields"]["monthly_wage"] == 9000, "冲突时按口述算，且必须让用户看见两个值"


def test_confirmed_conflict_overrides_story():
    r = analyze(STORY, today=TODAY, hints={"monthly_wage": 12000},
                confirmed=["monthly_wage"], mode="best_effort")
    assert r["fields"]["monthly_wage"] == 12000
    assert r["pending"] == []


def test_equal_reading_does_not_bother_the_user():
    r = analyze(STORY, today=TODAY, hints={"monthly_wage": 9000}, mode="best_effort")
    assert r["pending"] == []


def test_merge_hints_returns_sources():
    fields = {"monthly_wage": 9000}
    pending, sources = merge_hints(fields, {"unpaid_wages": 3000}, set())
    assert pending and sources == {"monthly_wage": "story"}
    pending, sources = merge_hints({"monthly_wage": 9000}, {"unpaid_wages": 3000},
                                   {"unpaid_wages"})
    assert pending == [] and sources["unpaid_wages"] == "confirmed"


def test_none_hints_are_ignored():
    pending, _ = merge_hints({}, {"monthly_wage": None}, set())
    assert pending == []


def test_pending_html_renders_checkboxes_and_both_values():
    html = pending_html(
        [{"key": "monthly_wage", "label": "月工资", "suggested": 12000,
          "from_story": 9000, "reason": "conflict"}],
        STORY,
    )
    assert 'name="confirm"' in html
    assert 'value="monthly_wage"' in html
    assert "12000" in html and "9000" in html
    assert "说法不一致" in html
    assert pending_html([], STORY) == ""


def test_pending_html_escapes_story():
    html = pending_html(
        [{"key": "unpaid_wages", "label": "欠薪", "suggested": 1,
          "from_story": None, "reason": "unconfirmed"}],
        '<script>alert(1)</script>',
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
