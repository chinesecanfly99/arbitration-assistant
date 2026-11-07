"""城市口径 + 资格闸门的测试。

这两块最容易被"看起来能跑"骗过去：
- 城市口径错了，3 倍封顶会用错基数，金额差几十万却算得一本正经；
- 闸门漏了，一事不再理/退休返聘/跨城市这些"进门就卡"的情形会被算成一笔钱。
所以这里逐条钉住：覆盖哪几城、单字别名不许误报、四类资格情形都要能被拦到。
"""
from datetime import date

import pytest

from arb import city as city_store
from arb.gates import detect_cities, detect_city, one_final_award_note, qualify
from arb.pipeline import analyze
from arb.scope import judge


# ---------------------------------------------------------------- 城市口径
def test_five_cities_are_covered():
    names = city_store.names()
    assert len(names) == 5
    for c in ("北京市", "上海市", "广州市", "深圳市", "杭州市"):
        assert c in names, c


def test_shenzhen_average_wage_is_filled():
    """深圳社平工资曾经是 null（硬缺口）：3 倍封顶就没法算。现在必须是真数字。"""
    c = city_store.get("深圳")
    assert c is not None
    assert c.avg_wage == 16157
    assert c.cap_3x == 48471
    assert c.min_wage == 2700
    assert c.one_final_award_threshold == 32400


def test_city_params_carry_source_and_verified_date():
    """每个数字都要能说出出处和核验日，否则评审一问"这数哪来的"就答不上。"""
    for c in city_store.load_all():
        assert c.verified_at, f"{c.name} 缺核验日"
        assert c.sources.get("avg_wage"), f"{c.name} 缺社平工资出处"
        assert c.sources.get("min_wage"), f"{c.name} 缺最低工资出处"


def test_city_normalize_accepts_common_spellings():
    assert city_store.normalize("深圳市") == "深圳市"
    assert city_store.normalize("深圳") == "深圳市"
    assert city_store.normalize("鹏城") == "深圳市"
    assert city_store.normalize("北京市") == "北京市"


def test_unknown_city_is_not_guessed():
    assert city_store.get("成都") is None
    assert city_store.covered("成都") is False
    assert city_store.social_avg_wage("成都") is None


def test_city_table_for_display():
    rows = city_store.table()
    assert len(rows) == 5
    assert all(r["cap_3x"] and r["one_final_award_threshold"] for r in rows)


def test_single_char_alias_does_not_false_positive():
    """单字别名（京/沪/穗/深/杭）误报率太高：南京不能被认成北京，深刻不能被认成深圳。"""
    assert detect_cities("我在南京上班，公司把我辞了") == []
    assert detect_cities("我深受打击，公司把我辞了") == []
    assert detect_cities("我在深圳上班") == ["深圳市"]
    assert detect_cities("北京和上海都有办公室") == ["北京市", "上海市"]


def test_detect_city_explicit_argument_wins():
    assert detect_city("我在南京上班", "深圳") == "深圳市"


# ---------------------------------------------------------------- 资格闸门
def _verdict(story: str):
    return judge(story, {"monthly_wage": 9000})


def test_res_judicata_blocks_calculation():
    story = "2022年3月1日入职，月薪9000，2024年5月20日违法辞退我，仲裁裁决已经下来了"
    r = analyze(story, today=date(2025, 1, 1), mode="best_effort")
    assert r["status"] == "blocked", "有过裁决就不该再算一笔钱"
    assert r["gates"]["status"] == "fail"
    assert r["gates"]["can_arbitrate"] is False
    assert any("一事不再理" in b for b in r["blockers"])
    assert "total" not in r, "被闸门拦住时不能给出总额"


def test_pending_arbitration_warns_but_still_calculates():
    story = "2022年3月1日入职，月薪9000，2024年5月20日违法辞退我，已经申请劳动仲裁了"
    r = analyze(story, today=date(2025, 1, 1), mode="best_effort")
    assert r["status"] == "ok"
    assert r["gates"]["status"] == "warn"
    assert any("已申请仲裁" in d for layer in r["gates"]["layers"] for d in (layer.get("detail") or []))


def test_settled_agreement_warns_with_correct_citation():
    story = "2022年3月1日入职，月薪9000，2024年5月20日违法辞退我，签了和解协议"
    g = qualify(story, {"monthly_wage": 9000}, _verdict(story), today=date(2025, 1, 1))
    assert g["status"] == "warn"
    assert "sfjs1:35" in g["cites"], "协议效力要引解释（一）第 35 条，不能乱引"


def test_retiree_rule_mentions_new_judicial_interpretation():
    story = "我退休返聘，2022年3月1日入职，月薪9000，2024年5月20日被辞退"
    g = qualify(story, {"monthly_wage": 9000}, _verdict(story), today=date(2025, 1, 1))
    assert g["status"] == "warn"
    text = " ".join(d for layer in g["layers"] for d in (layer.get("detail") or []))
    assert "退休" in text
    assert "sfjs1:32" in g["cites"] and "sfjs2:21" in g["cites"], "要同时指出旧规则与它的废止"


def test_intern_rule_warns():
    story = "我大三实习，公司说不要我了，月薪3000，2024年5月20日"
    g = qualify(story, {"monthly_wage": 3000}, _verdict(story), today=date(2025, 1, 1))
    assert g["status"] == "warn"
    text = " ".join(d for layer in g["layers"] for d in (layer.get("detail") or []))
    assert "实习" in text


def test_cross_city_conflict_warns():
    story = "我在深圳上班，公司注册在北京，2022年3月1日入职，月薪9000，2024年5月20日违法辞退我"
    g = qualify(story, {"monthly_wage": 9000}, _verdict(story), today=date(2025, 1, 1))
    assert g["status"] == "warn"
    assert g["cities_seen"] == ["北京市", "深圳市"]
    assert "arbitration_law:21" in g["cites"]
    text = " ".join(d for layer in g["layers"] for d in (layer.get("detail") or []))
    assert "只能挑一个" in text


def test_covered_city_fills_social_average_wage_and_caps():
    """讲到深圳，就应该按深圳社平工资做 3 倍封顶——不能拿 null 当"不封顶"。"""
    story = ("我在深圳，2012年5月1日入职，月薪60000，2024年5月20日违法辞退我")
    r = analyze(story, today=date(2025, 1, 1), mode="best_effort")
    assert r["status"] == "ok"
    assert r["fields"]["social_avg_wage"] == 16157
    n2 = next(i for i in r["items"] if "违法解除" in i["name"])
    assert "48471" in n2["formula"], n2["formula"]
    assert any("3 倍封顶" in a for a in r["assumptions"])


def test_uncovered_city_says_so_and_does_not_borrow_numbers():
    story = "我在成都上班，2015年5月1日入职，月薪9000，2024年5月20日违法辞退我"
    r = analyze(story, today=date(2025, 1, 1), mode="best_effort")
    assert r["status"] == "ok"
    assert r["fields"].get("social_avg_wage") is None, "没覆盖的城市不许套用别人的社平工资"
    assert any("成都" in a and "没有" in a for a in r["assumptions"]), r["assumptions"]


def test_place_guess_ignores_non_place_phrases():
    """「在城市里上班」「在这家公司工作」不是地名——不许当成城市，否则会误报"口径未覆盖"。"""
    assert detect_city("我在城市里上班，公司不要我了") is None
    assert detect_city("我在公司工作三年了") is None
    assert detect_city("我在成都上班") == "成都"


def test_one_final_award_note_both_sides():
    low = one_final_award_note("深圳市", 10000)
    high = one_final_award_note("深圳市", 100000)
    assert low and "一裁终局线" in low and "不能起诉" in low
    assert high and "不能起诉" not in high
    assert one_final_award_note(None, 10000) is None
    assert one_final_award_note("成都", 10000) is None
