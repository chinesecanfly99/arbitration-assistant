"""抗辩预演的测试（S3.6）。重点是"不能教人伪造材料"。"""
import pytest

from arb.mock_hr import rehearsal
from arb.scope import check_red_lines


@pytest.mark.parametrize("cause", ["illegal_dismissal", "double_wage", "overtime", "annual_leave", "unpaid_wage", "severance"])
def test_rehearsal_has_three_rounds(cause):
    r = rehearsal(cause)
    assert len(r["rounds"]) == 3
    for rd in r["rounds"]:
        assert rd["hr_says"] and rd["why"] and rd["counter"]
        assert rd["need"], "每一轮都要说清楚该准备什么证据"


def test_evidence_checklist_deduped():
    r = rehearsal("illegal_dismissal")
    need = r["evidence_checklist"]
    assert len(need) == len(set(need))
    assert len(need) >= 3


def test_rehearsal_never_tells_you_to_fake():
    for cause in ["illegal_dismissal", "double_wage", "overtime", "annual_leave", "unpaid_wage", "severance"]:
        r = rehearsal(cause)
        text = " ".join(
            [rd["counter"] for rd in r["rounds"]] + [r["tip"]]
        )
        assert check_red_lines(text) == [], f"{cause} 出现红线表述"
        assert "伪造" not in text and "补一份假的" not in text
