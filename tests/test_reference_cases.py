"""类案需要跟随案情变化，并保留可以独立复核的来源。"""
from datetime import date

from arb.cli import render_markdown
from arb.pipeline import analyze
from arb.reference_cases import recommend
from arb.web import render_page


def test_overtime_reference_follows_evidence():
    assert recommend({"overtime"}, "我有实名打卡和工资流水")[0]["id"] == "spc-319151-6"
    assert recommend({"overtime"}, "下班后在微信处理工作")[0]["id"] == "spc-423922-6"


def test_specialized_annual_leave_case_requires_service_history():
    assert recommend({"annual_leave"}, "离职时有年休假没休完") == []
    assert recommend({"annual_leave"}, "退役以后入职，年休假没计军龄")[0]["id"] == "spc-507531-3"


def test_report_displays_source_and_distinction_without_changing_amount():
    story = (
        "2020年3月1日入职，月薪9000，一直没签书面合同。"
        "2024年5月20日主管口头说不要我了，还有5天年假没休。"
    )
    report = analyze(story, today=date(2024, 6, 1))
    assert report["status"] == "ok"
    assert round(report["total"], 2) == 184137.93
    assert {case["id"] for case in report["reference_cases"]} == {
        "spc-319151-1", "spc-472681-3",
    }
    for rendered in (render_markdown(report), render_page(report, story)):
        assert "类案参考" in rendered and "区别" in rendered
        assert "https://www.court.gov.cn/zixun/xiangqing/472681.html" in rendered


def test_out_of_scope_report_does_not_suggest_cases():
    report = analyze("公司没有发工资，还要咨询工伤认定")
    assert report["status"] == "out_of_scope"
    assert "reference_cases" not in report
    assert "类案参考" not in render_page(report)
