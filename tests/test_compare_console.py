"""控制台模式、演示案例库与「普通 AI vs 本系统」对比测试。"""
import io
import json
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from arb import compare
from arb.pipeline import analyze
from arb.web import Handler


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()
    t.join(timeout=5)


def fetch(url, data=None):
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read().decode("utf-8")


def test_demo_cases_cover_core_scenarios():
    ids = [c["id"] for c in compare.DEMO_CASES]
    assert len(ids) >= 5
    expected_statuses = {
        "full_2n": "ok",
        "high_wage_cap": "ok",
        "gap_need_more": "need_more",
        "out_of_scope": "out_of_scope",
        "redline_winrate": "out_of_scope",
        "cross_city_gate": "ok",
    }
    for cid, want in expected_statuses.items():
        case = compare.get_demo_case(cid)
        assert case is not None, cid
        rep = analyze(case["story"], mode="best_effort")
        assert rep["status"] == want, (cid, rep["status"])


def test_audit_reply_citations_distinguishes_real_and_fake():
    txt = "依据《劳动合同法》第87条以及《劳动合同法》第999条可以主张赔偿。"
    audit = compare.audit_reply_citations(txt)
    assert audit["total"] == 2
    assert audit["verified"] == 1
    assert audit["unverified"] == 1


def test_compare_offline_preset_and_structural(monkeypatch):
    monkeypatch.delenv("ARB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    preset = compare.get_demo_case("full_2n")
    rep = analyze(preset["story"], mode="best_effort")
    res_preset = compare.compare_with_generic_ai(preset["story"], rep)
    assert res_preset["mode"] == "preset"
    assert res_preset["flaws"]

    custom = "2022年1月1日入职，月薪8000，2024年1月1日被违法辞退。"
    rep_custom = analyze(custom, mode="best_effort")
    res_struct = compare.compare_with_generic_ai(custom, rep_custom)
    assert res_struct["mode"] == "structural"


def test_compare_live_mocked(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{
                    "message": {
                        "content": "大约赔偿15万元，依据《劳动合同法》第87条和《劳动合同法》第999条。"
                    }
                }]
            }).encode("utf-8")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30: FakeResp())
    story = "2022年1月1日入职，月薪8000，2024年1月1日被违法辞退。"
    rep = analyze(story, mode="best_effort")
    res = compare.compare_with_generic_ai(story, rep, api_key="sk-test-key")
    assert res["mode"] == "live"
    assert res["cite_audit"]["verified"] == 1
    assert res["cite_audit"]["unverified"] == 1


def test_console_ui_features(server):
    code, html = fetch(server + "/")
    assert code == 200
    assert "演示案例库" in html
    assert 'id="voiceBtn"' in html
    assert 'id="chipsDrawer"' in html
    assert 'id="toggleGuideBtn"' in html
    assert html.count('class="case-btn') >= 5

    # 通过 ?case= 直接打开预设案例对比页
    code, case_html = fetch(server + "/?case=full_2n")
    assert code == 200
    assert "普通通用大模型" in case_html
    assert "本系统 · 规则 + 法条核验内核" in case_html
    assert "合计可主张" in case_html

    # compare=0 时不渲染双栏对比卡片
    code, no_cmp_html = fetch(server + "/analyze", {
        "story": compare.get_demo_case("full_2n")["story"],
        "compare": "0",
    })
    assert code == 200
    assert 'id="sec-compare"' not in no_cmp_html
