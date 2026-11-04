"""申请书草稿：能填的都填，不确定的留空，绝不编事实。"""
from arb.application import render_application, render_notes
from arb.pipeline import analyze

STORY = "2020年3月1日入职一家电子厂，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了。还有5天年假没休。"


def test_application_contains_requests_and_total():
    r = analyze(STORY, mode="best_effort")
    txt = render_application(r)
    assert "劳动仲裁申请书" in txt
    assert "仲裁请求" in txt
    assert f"{r['total']:,.2f}" in txt
    for it in r["items"]:
        assert it["name"] in txt


def test_application_leaves_unknown_blank():
    r = analyze(STORY, mode="best_effort")
    txt = render_application(r)
    assert "____" in txt          # 公司名等不知道的必须留空
    assert "被申请人：____" in txt
    assert "此致" in txt


def test_application_has_no_fabricated_company():
    r = analyze(STORY, mode="best_effort")
    txt = render_application(r)
    for fake in ("有限公司", "科技有限公司"):
        assert fake not in txt


def test_notes_mention_deadline_and_no_forgery():
    r = analyze(STORY, mode="best_effort")
    notes = render_notes(r)
    assert "时效" in notes
    assert "12348" in notes
    assert "不要伪造" in notes
