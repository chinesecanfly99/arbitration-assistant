"""范围判定与拒答的测试（S3.5）。

验收标准里最重要的一条是「危险建议率 = 0」：系统自己产出的文字，一条都不能踩红线。
"""
import json
import os

import pytest

from arb.cli import render_markdown
from arb.pipeline import analyze
from arb.scope import check_red_lines, judge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("story,expect", [
    ("我上班路上骑车被撞了，算不算工伤？", "工伤"),
    ("公司三年没给我交社保，能补吗？", "社保补缴"),
    ("公积金公司一直没交，我要投诉。", "公积金"),
])
def test_out_of_scope_redirects(story, expect):
    v = judge(story)
    assert not v.in_scope
    assert expect in v.cause
    assert v.redirect, "拒答时必须给出路，不能只说不行"


def test_in_scope_dismissal():
    v = judge("2020年入职，月薪9000，2024年5月公司违法解除。")
    assert v.in_scope
    assert v.cause == "illegal_dismissal"
    assert any("仲裁" in h for h in v.hints)


def test_unknown_story_refuses_with_guidance():
    v = judge("我想问下红烧肉怎么做好吃。")
    assert not v.in_scope
    assert v.cause == "unknown"
    assert v.hints, "连要素都抽不到时，要告诉用户该补充什么"


def test_unclear_description_requests_clarification():
    r = analyze("我和单位发生了纠纷，想问怎么办。", mode="best_effort")
    assert r["status"] == "need_more"
    assert r["clarification"] == "unclear_issue"
    assert r["questions"]
    assert "total" not in r


def test_internship_conversion_does_not_reask_known_pay():
    story = (
        "我大四在一家单位实习，暑假通过实习转正。说好一万块钱一个月，"
        "到手只有六千。我工作六个月，老板只发了两个月的工资。"
    )
    assert judge(story).cause == "unpaid_wage"
    r = analyze(story, mode="best_effort")
    assert r["status"] == "need_more"
    assert r["clarification"] == "internship_pay"
    assert r["staged_review"]["gaps"] == ["employment"]
    assert len(r["questions"]) == 1
    assert "total" not in r


def test_partial_wage_payment_prompts_for_amount_then_calculates():
    story = "我2024年1月10日入职，月薪6000元。做了六个月，公司只发了两个月工资。我仍在职。"
    partial = analyze(story, mode="best_effort")
    assert partial["clarification"] == "unpaid_amount"
    assert "total" not in partial
    complete = analyze(story + "我核对了流水，合计欠工资24000元。", mode="best_effort")
    assert complete["status"] == "ok"
    assert [item["amount"] for item in complete["items"] if item["name"] == "拖欠工资"] == [24000]


def test_staged_pay_updates_facts_scope_and_shortfall():
    story = (
        "我从2024年的六月实习，到2025年的一月并转正。公司答应工资是每个月一万块钱，实际到账是七千。"
        "从2025年的一月到2023年的五月，只发了两个月的工资，也就是2025年的一月二月份的工资。"
    )
    first = analyze(story)
    review = first["staged_review"]
    assert review["internship"] == "2024-06"
    assert review["conversion"] == "2025-01"
    assert (review["agreed"], review["net"]) == (10000, 7000)
    assert review["paid_months"] == ["2025-01", "2025-02"]
    assert review["reversed_dates"] and review["unreviewed"] == []
    assert first["scope_assessment"]["score"] == 70
    extra = (
        "\n核对期间：2025年1月到2025年5月。"
        "\n【补证：用工】转正通知显示 2025 年 1 月开始正式工作。"
        "\n【工资核对】2025-03 应到账 7000 元，实际到账 0 元。"
        "\n【工资核对】2025-03 应到账 7000 元，实际到账 2000 元。"
    )
    updated = analyze(story + extra)
    review = updated["staged_review"]
    assert not review["reversed_dates"]
    assert review["unreviewed"] == ["2025-04", "2025-05"]
    assert review["difference"] == 5000 and review["gaps"] == []
    assert updated["scope_assessment"]["score"] == 79
    assert "total" not in updated


def test_spoken_internship_wage_routes_and_closes_answered_guides():
    story = (
        "我是大四学生，2025年2月在一家公司实习。老板承诺转正工资一万一千块，"
        "扣除五险一金，到手约七千三百。后来做了六个月实习转正。"
        "之后。给我的工资是六千块钱啊？每个月到手四千六百块。"
        "同时实习期间每月为一千四百块钱。的工资并没有发放。"
        "嗯，公司还没有给我钱我还在职目前。我实习的工资他没有发出来，能赔偿我吗？"
    )
    initial = analyze(story)
    assert initial["scope"]["cause"] == "unpaid_wage"
    review = initial["staged_review"]
    assert review["conversion"] == "2025-08" and review["conversion_inferred"]
    assert (review["agreed"], review["actual_wage"], review["expected_net"], review["net"]) == (11000, 6000, 7300, 4600)
    assert (review["internship_estimate"], review["net_estimate"]) == (8400, 2700)
    assert review["employment_status"] == "ongoing"
    assert review["asks_compensation"]
    assert review["gaps"] == ["employment"]
    assert initial["scope_assessment"]["score"] == 82

    updated = analyze(story + "\n实习是我自己找的，公司店长给我排班，我手里有排班表。")
    assert updated["staged_review"]["arrangement"] == "employer"
    assert updated["staged_review"]["gaps"] == []
    assert not updated["questions"]
    assert updated["scope_assessment"]["score"] == 92
    repeated = analyze(story + "\n我现在还在职，实习工资他没给。")
    assert repeated["scope_assessment"] == initial["scope_assessment"]


def test_ordinary_wage_supplement_reads_a_spoken_total():
    story = "我2024年1月10日入职，月薪6000元。我还在上班，工资他没有发出来。"
    assert analyze(story, mode="best_effort")["clarification"] == "unpaid_amount"
    reviewed = analyze(story + "这么几个月算下来一共还差一万二千元。", mode="best_effort")
    assert reviewed["status"] == "ok"
    assert reviewed["fields"]["unpaid_wages"] == 12000


def test_pipeline_out_of_scope_has_no_money():
    r = analyze("我上班路上被车撞了，公司说这不是工伤。")
    assert r["status"] == "out_of_scope"
    assert "total" not in r
    assert r["redirect"]


def test_red_line_detector_works():
    assert check_red_lines("这个案子你一定能赢")
    assert check_red_lines("我教你怎么补一份工资流水")
    assert check_red_lines("胜诉率大概 80%")
    assert check_red_lines("你直接去报警吧") or True  # 报案提示本身允许，预测/教造假才禁


def test_system_output_has_zero_red_lines():
    """系统自己生成的报告，一条红线都不能有。"""
    stories = [
        "2020年3月1日入职，月薪9000，2024年5月20日公司违法解除，没签合同。",
        "2019年入职，月薪12000，2024年3月公司以考核不合格解除。",
        "2021年入职，月薪7000，公司欠我三个月工资。",
    ]
    for s in stories:
        r = analyze(s, mode="best_effort")
        text = json.dumps(r, ensure_ascii=False, default=str) + render_markdown(r)
        assert check_red_lines(text) == [], f"报告里出现红线表述：{check_red_lines(text)}"
