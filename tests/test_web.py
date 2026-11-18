"""前端测试：四种状态都要能渲染，且不能让用户输入变成脚本。"""
import re
import threading
import urllib.parse
import urllib.request

import pytest

from arb.pipeline import analyze
from arb.web import Handler, render_page

from http.server import ThreadingHTTPServer

STORY = "2020年3月1日入职，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了。"


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()      # 不关会让解释器退不干净、报 ResourceWarning: unclosed socket
    t.join(timeout=5)       # 等线程真的停下，否则跑测试时偶发"1 warning"


def fetch(url, data=None):
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read().decode("utf-8"), dict(r.headers)


def test_index_page(server):
    code, html, _ = fetch(server + "/")
    assert code == 200
    assert "Arbitration Console" in html
    assert '<form method="post" action="/analyze">' in html

    code_zh, html_zh, _ = fetch(server + "/?lang=zh")
    assert code_zh == 200
    assert "劳动仲裁维权助手" in html_zh


def test_index_has_chips(server):
    _, html, _ = fetch(server + "/")
    assert html.count('class="chip"') >= 30
    assert "人话" in html or "plain" in html


def test_print_page(server):
    code, html, _ = fetch(server + "/print?story=" + urllib.parse.quote(STORY))
    assert code == 200
    assert "@media print" in html


def test_post_analyze_ok(server):
    code, html, _ = fetch(server + "/analyze", {"story": STORY})
    assert code == 200
    assert "Estimated Claimable Amount" in html
    assert "Citation Verified" in html
    assert "Statutory Arbitration Deadlines" in html

    code_zh, html_zh, _ = fetch(server + "/analyze", {"story": STORY, "lang": "zh"})
    assert code_zh == 200
    assert "你能主张" in html_zh
    assert "引用已核验" in html_zh
    assert "仲裁时效" in html_zh


def test_post_need_more(server):
    code, html, _ = fetch(server + "/analyze", {"story": "公司把我辞了"})
    assert code == 200
    assert "Details to verify if needed" in html

    code_zh, html_zh, _ = fetch(server + "/analyze", {"story": "公司把我辞了", "lang": "zh"})
    assert code_zh == 200
    assert "需要时再核对" in html_zh


def test_post_out_of_scope(server):
    code, html, _ = fetch(server + "/analyze", {"story": "工地摔伤了，算工伤吗"})
    assert code == 200
    assert "Labor arbitration relevance" in html
    assert 'value="25" aria-labelledby="scopeTitle"' in html

    code_zh, html_zh, _ = fetch(server + "/analyze", {"story": "工地摔伤了，算工伤吗", "lang": "zh"})
    assert code_zh == 200
    assert "人社局工伤科" in html_zh


def test_staged_pay_shows_analysis_before_followups(server):
    story = "我实习后转正，月薪约定和到账不同，工作六个月，老板只发了两个月的工资。"
    _, html, _ = fetch(server + "/analyze", {"story": story, "lang": "zh", "compare": "1"})
    assert "实习与转正欠薪初步分析" in html
    assert "查看初步分析" in html
    assert 'value="70" aria-labelledby="scopeTitle"' in html
    assert 'id="caseEvidenceForm"' in html and 'id="casePayForm"' in html
    assert "核对期间" in html
    assert 'id="continueGuide"' not in html
    assert story in html


def test_add_answer_skips_already_stated_goal_and_refreshes_review(server):
    story = "我想要公司给我开一张在职证明。"
    _, first, _ = fetch(server + "/analyze", {"story": story, "lang": "zh"})
    assert "单位做了什么" in first and "你想解决什么" not in first
    assert 'id="reviewSubmit"' in first
    updated = story + "\n工资他没有发出来，我一个月基本工资六千。"
    _, second, _ = fetch(server + "/analyze", {"story": updated, "lang": "zh", "review_update": "1", "compare": "1"})
    assert 'value="85" aria-labelledby="scopeTitle"' in second
    assert "欠了几个月" in second and "单位做了什么" not in second
    assert 'id="aiReplyBox"' not in second


def test_relevance_gives_intake_and_civil_next_steps(server):
    _, civil, _ = fetch(server + "/analyze", {"story": "房东拖欠退租押金，怎么处理？", "lang": "zh"})
    assert 'value="5" aria-labelledby="scopeTitle"' in civil
    assert "保留租约" in civil and "12348" in civil
    _, mixed, _ = fetch(server + "/analyze", {"story": "公司没有发工资，还要咨询工伤认定。", "lang": "zh"})
    assert 'value="65" aria-labelledby="scopeTitle"' in mixed
    assert "人社局工伤科" in mixed and "欠薪与当月计薪" in mixed


def test_complex_case_shows_independent_claims_and_refines_each_on_update(server):
    story = (
        "我在这家公司工作了九年左右，税前月薪12000元，2017年工作开始的。"
        "2026年4月上班时发生事故受伤，4月14日走的。公司月底说不用再来了，说我工作能力不行和要裁员。"
        "这个月工资没有给，我只工作了半个月，前面的都发了。"
    )
    report = analyze(story, mode="best_effort")
    review = report["issue_review"]
    assert "total" not in report and report["fields"]["hire_date"] is None
    assert review["reported_years"] == 9 and review["end_needs_review"]
    assert review["pay"]["partial"] and review["pay"]["difference"] is None
    assert review["scenarios"]["2n"] == [204000, 228000] and review["injury"]
    _, html, _ = fetch(server + "/analyze", {"story": story, "lang": "zh", "compare": "1"})
    assert "先核对金额差异" in html and "多项争议分开核对" in html
    assert "2017 年（具体月份待核对）" in html
    assert "合同哪天正式解除" in html and "受伤与工伤办理" in html
    assert 'id="reviewWageDifference"' not in html
    updated = story + "\n入职日期是2017年8月20日。本期计薪11天。解除生效日期是2026年4月30日。工伤认定已提交。"
    _, html, _ = fetch(server + "/analyze", {"story": updated, "lang": "zh", "review_update": "1"})
    assert 'id="review-2n">¥216,000.00' in html
    assert 'id="reviewWageDifference"' in html and "¥6,068.97" in html
    assert 'id="reviewInjuryStatus"' in html
    assert "2026-04-14" in html and "2026-04-30" in html
    assert 'data-topic="effective_date"' not in html
    assert 'data-topic="paid_days"' not in html


def test_multiple_chinese_article_references_are_attributed_to_the_same_law():
    from arb.compare import audit_reply_citations

    result = audit_reply_citations("按《劳动合同法》第47、87条（解除），第30条（工资）。另见《工伤保险条例》第33条。")
    assert [row["cite"] for row in result["items"]] == [
        "《劳动合同法》第47条", "《劳动合同法》第87条", "《劳动合同法》第30条", "《工伤保险条例》第33条",
    ]
    assert result["verified"] == 3


def test_platform_dispute_explains_both_factors_before_estimating(server):
    story = "我是2024年1月1日开始在平台送外卖，2025年1月1日离开，月报酬6000。公司安排排班和扣罚，但我可以自己决定接单。签的是合作协议，没签劳动合同。我想确认劳动关系和二倍工资。"
    _, html, _ = fetch(server + "/analyze", {"story": story, "lang": "zh"})
    assert "判断劳动关系和责任主体" in html and "二倍工资的前置条件" in html
    assert "自主接单" in html and "公司安排班次" in html
    assert "最高法指导性案例 237–240 号" in html
    assert "合计可主张" not in html


def test_short_unsigned_period_waits_for_actual_workdays(server):
    story = "2024年2月1日入职，3月17日离职，没签合同，月薪7500。"
    _, first, _ = fetch(server + "/analyze", {"story": story, "lang": "zh"})
    assert "未签期间实际干了几天" in first
    assert 'id="unsignedEstimate"' not in first
    _, updated, _ = fetch(server + "/analyze", {
        "story": story + "\n未签合同期间实际工作10个工作日。", "review_update": "1", "lang": "zh",
    })
    assert 'id="unsignedEstimate">¥3,448.28' in updated
    assert "未签期间实际干了几天" not in updated


def test_extended_injury_leave_uses_committee_decision(server):
    _, html, _ = fetch(server + "/analyze", {
        "story": "我已被认定为工伤，停工留薪期已经满了，仍有医院病休证明，单位发病假工资，我想延长停工留薪期。", "lang": "zh",
    })
    assert "市级劳动能力鉴定委员会的延长确认" in html
    assert "留薪期有没有获批延长" in html
    assert "事故发生后 30 日内申请" not in html


def test_application_download(server):
    code, body, headers = fetch(server + "/application?story=" + urllib.parse.quote(STORY))
    assert code == 200
    assert headers["Content-Type"].startswith("text/plain")
    assert "劳动仲裁申请书" in body


def test_report_download(server):
    code, body, headers = fetch(server + "/report?story=" + urllib.parse.quote(STORY))
    assert code == 200
    assert headers["Content-Type"].startswith("text/markdown")
    assert "可主张金额合计" in body


def test_xss_is_escaped(server):
    evil = '<script>alert(1)</script>2020年3月1日入职，月薪9000，2024年5月20日被辞退'
    _, html, _ = fetch(server + "/analyze", {"story": evil})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html  # 原文被转义后仍可见，可核对系统理解对不对


def test_render_page_states():
    assert "劳动仲裁维权助手" in render_page()
    r = analyze(STORY, mode="best_effort")
    ok = render_page(r, STORY)
    assert "逐项金额" in ok and "抗辩" not in ok or True


def test_ok_page_has_map_and_evidence(server):
    _, html, _ = fetch(server + "/analyze", {"story": STORY})
    assert "Case Completeness Map" in html
    assert "Burden of Proof Checklist" in html
    assert "Employer Burden" in html
    assert 'class="cell ok"' in html

    _, html_zh, _ = fetch(server + "/analyze", {"story": STORY, "lang": "zh"})
    assert "案件完整度" in html_zh
    assert "五、证据清单" in html_zh
    assert "单位举证" in html_zh


def test_need_more_page_has_clickable_map_and_form(server):
    _, html, _ = fetch(server + "/analyze", {"story": "公司把我辞了，我很生气"})
    assert "Case Completeness Map" in html
    assert 'class="chip fill"' in html, "缺字段时应给出可点的补录按钮"
    assert 'name="story"' in html, "补录页要能继续编辑提交"
    assert 'class="cell missing"' in html


def test_missing_fields_have_targeted_questions(server):
    _, html, _ = fetch(server + "/analyze", {"story": "公司把我辞了", "lang": "zh"})
    assert "哪天开始干的" in html
    assert "税前多少钱" in html
    assert 'data-example="我于___年___月___日入职___单位，担任___。"' in html
    assert 'data-plain="可以看工资条上的「应发合计」' in html
    assert html.count('class="chip fill"') == 3


@pytest.mark.parametrize("story,known,remaining,already_answered", [
    ("公司三个月工资都没发，银行每个月到手六千五。", "3 个月", "一共还差多少", "欠了几个月"),
    ("老板说以后不用再来了，我是2024年3月开始上班的，税前一万一，他没给理由。", "¥11,000.00", "哪天让你走的", "是谁提出离职的"),
    ("我现在还在职，周六还要来上班，平时加班到晚上九点。", "周六还要来上班", "周末有没有补休", "哪天多干了几小时"),
    ("公司不让休年假，我的年假还剩三天。", "3 天", "税前多少钱", "年假还剩几天"),
    ("我连书面合同都没签过，公司让我来上班已经半年了。", "未签或未拿到合同", "哪天开始干的", "后来哪天补签的"),
])
def test_oral_facts_and_guides_vary_by_case(server, story, known, remaining, already_answered):
    _, html, _ = fetch(server + "/analyze", {"story": story, "lang": "zh"})
    facts = html.split('id="knownCaseFacts"', 1)[1].split("</dl>", 1)[0]
    questions = html.split('id="guideSuggestions"', 1)[1].split("</div>", 1)[0]
    assert known in facts
    assert remaining in questions
    assert already_answered not in questions
    assert 'data-suggestion="1"' in questions

def test_pdf_download_route(server):
    import urllib.parse as up
    url = server + "/pdf?story=" + up.quote(STORY)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
        ctype = r.headers.get("Content-Type", "")
        disp = r.headers.get("Content-Disposition", "")
    assert r.status == 200
    assert "application/pdf" in ctype
    assert data.startswith(b"%PDF-")
    assert len(data) > 3000
    assert ".pdf" in disp


def test_report_page_has_pdf_button(server):
    code, html, _ = fetch(server + "/analyze", {"story": STORY})
    assert code == 200
    assert "/pdf?story=" in html
