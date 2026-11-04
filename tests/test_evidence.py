"""证据清单的测试：核心是"谁举证"不能标错。

标错方向的代价不对称：把该单位出的证据标成"你自己准备"，用户会白跑一趟；
反过来把该自己准备的标成"单位出"，用户会在庭上被问住。
"""

import pytest

from arb.evidence import ME_HINTS, UNIT_HINTS, rows, summary, who


def test_unit_held_evidence_goes_to_unit():
    for name in ["考勤记录", "工资发放记录", "解除通知书", "规章制度公示记录", "打卡记录"]:
        assert who(name) == "单位", name


def test_my_evidence_goes_to_me():
    for name in ["劳动合同", "聊天记录", "录音", "工作群通知", "邮件"]:
        assert who(name) in ("你", "双方"), name


def test_unknown_defaults_to_me():
    assert who("一张我也不知道是什么的表") == "你"


def test_both_sides():
    assert who("劳动合同原件与单位存档") == "双方"


def test_rows_shape_and_why():
    out = rows(["考勤记录", "劳动合同"])
    assert [r["name"] for r in out] == ["考勤记录", "劳动合同"]
    assert out[0]["who"] == "单位" and "第六条" not in out[0]["why"]
    assert "单位承担不利后果" in out[0]["why"]
    assert "自己准备并提交" in out[1]["why"]
    for r in out:
        assert set(r) == {"name", "who", "why"}


def test_summary_counts():
    out = rows(["考勤记录", "工资发放记录", "劳动合同"])
    s = summary(out)
    assert "共 3 项" in s
    assert "2 项可要求单位提供" in s
    assert "1 项需要你自己准备" in s


def test_summary_empty():
    assert summary([]) == ""


def test_rehearsal_checklist_has_unit_items():
    """每个案由的抗辩预演都要至少给出 1 条"单位举证"项，否则用户会被问住。"""
    from arb.mock_hr import rehearsal

    for cause in [
        "illegal_dismissal",
        "severance",
        "double_wage",
        "overtime",
        "annual_leave",
        "unpaid_wage",
        "mixed",
    ]:
        r = rehearsal(cause)
        out = rows(r["evidence_checklist"])
        assert any(x["who"] == "单位" for x in out), f"{cause} 没有单位举证项"
        assert r["evidence_checklist"], f"{cause} 证据清单为空"


@pytest.mark.parametrize("hint", UNIT_HINTS)
def test_unit_hint_recognized(hint):
    assert who(hint + "（单位保存）") == "单位"


@pytest.mark.parametrize("hint", ME_HINTS)
def test_me_hint_recognized(hint):
    assert who(hint) in ("你", "双方")
