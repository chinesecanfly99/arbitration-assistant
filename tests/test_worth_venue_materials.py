"""材料清单 / 证据强度 / 立案路径 / 值得性六维的测试。

这四块都是"纯规则、可枚举"的部件——正因为不调模型，才必须被单测钉死：
权重改了分数就变，清单漏一项用户就白跑一趟，路径写错城市就是给错地址。
"""
from datetime import date

import pytest

from arb import materials as mat
from arb import venue as ven
from arb import worth as w
from arb.city import get as get_city
from arb.evidence import score as ev_score


# ---------------------------------------------------------------- 材料清单
def test_base_materials_always_present():
    items = mat.build_materials(set())
    keys = {i["key"] for i in items}
    assert {"application", "id_card", "company_registry", "relation"} <= keys
    assert all(i["required"] for i in items)


def test_materials_added_by_dispute_type():
    only_base = mat.build_materials(set())
    with_wage = mat.build_materials({"unpaid_wage"})
    assert len(with_wage) > len(only_base)
    assert "wage_owed" in {i["key"] for i in with_wage}
    assert "wage_owed" not in {i["key"] for i in only_base}


def test_duplicate_material_not_repeated():
    """termination + no_contract 都要"劳动关系证明"，不能在同一份清单里出现两次。"""
    items = mat.build_materials({"termination", "no_contract", "unpaid_wage"})
    names = [i["name"] for i in items]
    assert len(names) == len(set(names))


def test_have_is_inferred_only_from_explicit_mentions():
    items = mat.build_materials({"termination"}, "我有工资条，银行流水也导出来了")
    by_key = {i["key"]: i for i in items}
    assert by_key["wage_standard"]["have"] is True
    assert by_key["termination_notice"]["have"] is False
    assert by_key["application"]["have"] is False


def test_relation_satisfied_by_any_one_proof():
    """劳动关系证明是"四选一"，不是"全套都要"。"""
    for story in ("我有劳动合同", "我有银行流水", "我社保记录能查到", "我有工作群"):
        items = mat.build_materials(set(), story)
        relation = next(i for i in items if i["key"] == "relation")
        assert relation["have"] is True, story


def test_material_summary_counts():
    items = mat.build_materials({"unpaid_wage"}, "我有工资条")
    s = mat.summary(items)
    assert "共" in s and "项" in s
    assert "初步举证" in s


def test_material_summary_empty():
    assert mat.summary([]) == ""


def test_every_material_has_purpose_burden_how():
    for t in [*mat.BY_TYPE, None]:
        for i in mat.build_materials({t} if t else set()):
            assert i["purpose"] and i["burden"] and i["how"], i["name"]


def test_dispute_types_from_causes_and_items():
    types = mat.dispute_types(["illegal_dismissal", "double_wage"],
                              [{"name": "未签书面劳动合同二倍工资"}])
    assert types == {"termination", "no_contract"}
    # 案由没说，但内核算出了加班费 → 也要出现加班材料
    assert "overtime" in mat.dispute_types([], [{"name": "加班费"}])


# ---------------------------------------------------------------- 证据强度
def test_evidence_unknown_is_neutral_not_zero():
    r = ev_score(set(), {"termination"})
    assert r["known"] is False
    assert r["score"] == 55, "没上传材料不等于没证据，不能直接判 0 分"
    assert r["gaps"]


def test_evidence_strong_with_contract_and_notice():
    r = ev_score({"contract", "termination_notice", "bank_flow"}, {"termination"})
    assert r["known"] is True
    assert r["score"] >= 75
    assert r["level"] == "强"


def test_evidence_weak_with_nothing():
    r = ev_score({"badge"}, {"termination"})
    assert r["score"] < 50
    assert r["level"] == "弱"
    assert any("解除通知" in g for g in r["gaps"])


def test_evidence_non_termination_case_not_penalized():
    """不是解除类案件，不该因为"没有解除通知"被扣一维。"""
    flat = ev_score({"contract"}, set())
    term = ev_score({"contract"}, {"termination"})
    assert flat["score"] > term["score"]


def test_evidence_specific_gaps_by_type():
    r = ev_score({"contract"}, {"overtime", "annual_leave"})
    joined = " ".join(r["gaps"])
    assert "考勤" in joined
    assert "年假" in joined or "年休" in joined


# ---------------------------------------------------------------- 立案路径
def test_venue_has_six_stages_with_city():
    blocks = ven.build(get_city("深圳").as_dict(), days_left=120, total=50000)
    assert len(blocks) == 6
    assert "深圳市劳动人事争议仲裁院" in blocks[0]["name"]
    assert "深南大道" in blocks[0]["where"]
    stages = [b["stage"] for b in blocks]
    assert any("仲裁申请" in s for s in stages)
    assert any("撤销" in s for s in stages)


def test_venue_actions_are_clickable():
    blocks = ven.build(get_city("北京市").as_dict(), days_left=None, total=0)
    acts = blocks[0]["actions"]
    kinds = {a["kind"] for a in acts}
    assert "tel" in kinds and "copy" in kinds and "map" in kinds


def test_venue_without_city_still_gives_uniform_hotlines():
    blocks = ven.build(None)
    assert len(blocks) >= 4
    assert "12333" in blocks[0]["actions"][0]["value"]
    joined = " ".join(b["note"] for b in blocks)
    assert "不写具体窗口" in joined, "没覆盖的城市要明说，不能给错地址"


def test_venue_does_not_borrow_other_city_address():
    blocks = ven.build(None)
    for b in blocks:
        assert "深圳" not in b["name"] and "北京" not in b["name"]


def test_venue_mentions_days_left_when_known():
    blocks = ven.build(get_city("杭州").as_dict(), days_left=9, total=1000)
    assert any("还剩 9 天" in b["note"] for b in blocks)


def test_venue_summary():
    blocks = ven.build(None)
    assert f"{len(blocks)} 条路径" in ven.summary(blocks)
    assert ven.summary([]) == ""


# ---------------------------------------------------------------- 值得性
def _worth(total, **kw):
    return w.compute({"termination": "illegal_dismissal", **kw}, total,
                     kw.pop("types", {"termination"}), kw.pop("evidence", None),
                     kw.pop("city", None), kw.pop("days_left", None))


def test_weights_sum_to_one():
    assert pytest.approx(sum(w.WEIGHTS.values())) == 1.0


def test_six_dimensions_present_and_weighted():
    r = w.compute({"termination": "illegal_dismissal"}, 30000, {"termination"}, None, None, 300)
    assert [d["key"] for d in r["dimensions"]] == list(w.WEIGHTS)
    expect = round(sum(d["score"] * d["weight"] for d in r["dimensions"]))
    assert r["score"] == expect


def test_amount_dimension_is_monotonic():
    """金额越大，这一维越不该拦住你（0 元单独处理：算不出来 ≠ 不值得）。"""
    scores = [w.compute({}, t, {"termination"}, None, None, None)["dimensions"][0]["score"]
              for t in (1, 1000, 5000, 10000, 30000, 80000)]
    assert scores == sorted(scores)
    assert w.compute({}, 0, {"termination"}, None, None, None)["dimensions"][0]["score"] == 50


def test_employee_resign_is_not_recommended():
    r = w.compute({"termination": "employee_resign"}, 50000, {"termination"}, None, None, 300)
    assert r["decision"] == "not_recommended"
    assert "主动辞职" in r["decision_label"]


def test_zero_amount_is_not_recommended():
    r = w.compute({"termination": "illegal_dismissal"}, 0, set(), None, None, None)
    assert r["decision"] == "not_recommended"


def test_small_unpaid_wage_prefers_supervision():
    """欠薪金额不大时，监察投诉比仲裁快——这是"有更好的路"，不是"别去"。"""
    r = w.compute({"termination": "illegal_dismissal"}, 4000, {"unpaid_wage", "termination"},
                  None, None, 300)
    assert r["alternative"] and r["alternative"]["key"] == "supervision"
    assert r["decision"] in ("better_alternative", "recommend")


def test_large_amount_recommends_arbitration():
    city = get_city("深圳").as_dict()
    r = w.compute({"termination": "illegal_dismissal"}, 120000, {"termination"},
                  {"score": 80, "level": "强", "known": True}, city, 300)
    assert r["decision"] == "recommend"


def test_urgency_is_highest_near_deadline():
    for left, floor in ((10, 85), (100, 65), (300, 50)):
        r = w.compute({"termination": "illegal_dismissal"}, 30000, {"termination"}, None, None, left)
        urgency = next(d for d in r["dimensions"] if d["key"] == "urgency")
        assert urgency["score"] >= floor


def test_reasons_always_three_and_citable():
    r = w.compute({"termination": "illegal_dismissal"}, 30000, {"termination"},
                  None, get_city("深圳市").as_dict(), 30)
    assert len(r["reasons"]) == 3
    for reason in r["reasons"]:
        assert reason["text"] and reason["cites"]


def test_one_final_dimension_uses_city_threshold():
    city = get_city("深圳市").as_dict()
    small = w.compute({"termination": "illegal_dismissal"}, 10000, {"termination"}, None, city, 300)
    big = w.compute({"termination": "illegal_dismissal"}, 200000, {"termination"}, None, city, 300)
    dim = lambda r: next(d for d in r["dimensions"] if d["key"] == "one_final")["score"]  # noqa: E731
    assert dim(small) > dim(big)
