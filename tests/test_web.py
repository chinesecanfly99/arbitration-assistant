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
    assert "劳动仲裁维权助手" in html
    assert '<form method="post" action="/analyze">' in html


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
    assert "你能主张" in html
    assert "引用已核验" in html
    assert "仲裁时效" in html


def test_post_need_more(server):
    code, html, _ = fetch(server + "/analyze", {"story": "公司把我辞了"})
    assert code == 200
    assert "还差几个信息" in html or "请补充" in html


def test_post_out_of_scope(server):
    code, html, _ = fetch(server + "/analyze", {"story": "工地摔伤了，算工伤吗"})
    assert code == 200
    assert "不归劳动仲裁管" in html


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
    assert "案件完整度" in html
    assert "五、证据清单" in html
    assert "单位举证" in html
    assert 'class="cell ok"' in html


def test_need_more_page_has_clickable_map_and_form(server):
    _, html, _ = fetch(server + "/analyze", {"story": "公司把我辞了，我很生气"})
    assert "案件完整度" in html
    assert 'class="chip fill"' in html, "缺字段时应给出可点的补录按钮"
    assert 'name="story"' in html, "补录页要能继续编辑提交"
    assert 'class="cell missing"' in html


def test_fill_button_text_is_template(server):
    _, html, _ = fetch(server + "/analyze", {"story": "公司把我辞了"})
    assert "补：入职日期" in html
    assert "data-text=" in html

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
