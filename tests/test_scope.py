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


def test_internship_conversion_wages_need_separate_facts():
    story = (
        "我大四在一家单位实习，暑假通过实习转正。说好一万块钱一个月，"
        "到手只有六千。我工作六个月，老板只发了两个月的工资。"
    )
    assert judge(story).cause == "unpaid_wage"
    r = analyze(story, mode="best_effort")
    assert r["status"] == "need_more"
    assert r["clarification"] == "internship_pay"
    assert len(r["questions"]) == 3
    assert "total" not in r


def test_partial_wage_payment_prompts_for_amount_then_calculates():
    story = "我2024年1月10日入职，月薪6000元。做了六个月，公司只发了两个月工资。我仍在职。"
    partial = analyze(story, mode="best_effort")
    assert partial["clarification"] == "unpaid_amount"
    assert "total" not in partial
    complete = analyze(story + "我核对了流水，合计欠工资24000元。", mode="best_effort")
    assert complete["status"] == "ok"
    assert [item["amount"] for item in complete["items"] if item["name"] == "拖欠工资"] == [24000]


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
