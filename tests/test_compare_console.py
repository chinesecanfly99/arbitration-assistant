"""控制台模式、演示案例库、双语切换、异步对比接口与英文抽取测试。"""
import json
import threading
import urllib.parse
import urllib.request
from datetime import date
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
    assert len(compare.DEMO_CASES) == 8
    expected_statuses = {
        "full_2n": "ok",
        "overtime_unpaid": "ok",
        "mutual_severance": "ok",
        "high_wage_cap": "ok",
        "cross_city_gate": "ok",
        "gap_need_more": "need_more",
        "out_of_scope": "out_of_scope",
        "redline_winrate": "out_of_scope",
    }
    for cid, want in expected_statuses.items():
        case = compare.get_demo_case(cid)
        assert case is not None, cid
        rep = analyze(case["story"], mode="best_effort")
        assert rep["status"] == want, (cid, rep["status"])
        rep_en = analyze(case["story_en"], mode="best_effort")
        assert rep_en["status"] == want, (cid, "en", rep_en["status"])


def test_english_story_extraction_matches_exact_amount():
    en_story = compare.get_demo_case("full_2n")["story_en"]
    zh_story = compare.get_demo_case("full_2n")["story"]
    rep_en = analyze(en_story, today=date(2024, 6, 1))
    rep_zh = analyze(zh_story, today=date(2024, 6, 1))
    assert rep_en["status"] == "ok"
    assert round(rep_en["total"], 2) == round(rep_zh["total"], 2) == 184137.93


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
    res_preset = compare.compare_with_generic_ai(preset["story"], rep, lang="en")
    assert res_preset["mode"] == "preset"
    assert res_preset["flaws"]

    custom = "2022年1月1日入职，月薪8000，2024年1月1日被违法辞退。"
    rep_custom = analyze(custom, mode="best_effort")
    res_struct = compare.compare_with_generic_ai(custom, rep_custom, lang="zh")
    assert res_struct["mode"] == "structural"


def test_compare_live_mocked_and_cached(monkeypatch):
    calls = {"n": 0}

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

    def fake_open(req, timeout=25):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    compare._LIVE_CACHE.clear()
    story = "2022年1月1日入职，月薪8000，2024年1月1日被违法辞退。"
    rep = analyze(story, mode="best_effort")
    res1 = compare.compare_with_generic_ai(story, rep, api_key="sk-test-key", lang="zh")
    res2 = compare.compare_with_generic_ai(story, rep, api_key="sk-test-key", lang="zh")
    assert res1["mode"] == "live"
    assert res1["cite_audit"]["verified"] == 1
    assert res1["cite_audit"]["unverified"] == 1
    assert res2["cached"] is True
    assert calls["n"] == 1


def test_console_ui_bilingual_tabs_and_async_api(server):
    # 默认打开为英文版控制台
    code, html = fetch(server + "/")
    assert code == 200
    assert "Demo Case Library" in html
    assert 'id="voiceBtn"' in html
    assert 'id="chipsDrawer"' in html
    assert 'id="toggleGuideBtn"' in html
    assert html.count('class="case-btn') == 8

    # 切换中文版控制台
    code, zh_html = fetch(server + "/?lang=zh")
    assert code == 200
    assert "演示案例库" in zh_html

    # 通过 ?case= 直接打开预设案例（含 4 个分模块 Tab 与双栏对比）
    code, case_html = fetch(server + "/?case=full_2n")
    assert code == 200
    assert "Generic LLM" in case_html
    assert "Rule + Statute Engine" in case_html
    assert 'data-tab="tab-overview"' in case_html
    assert 'data-tab="tab-statutes"' in case_html
    assert 'data-tab="tab-defense"' in case_html
    assert 'data-tab="tab-filing"' in case_html

    # 异步对比接口 /api/compare
    code, api_body = fetch(server + "/api/compare", {
        "story": compare.get_demo_case("full_2n")["story_en"],
        "lang": "en",
    })
    assert code == 200
    payload = json.loads(api_body)
    assert payload["reply"]

    # compare=0 时不渲染双栏对比卡片
    code, no_cmp_html = fetch(server + "/analyze", {
        "story": compare.get_demo_case("full_2n")["story"],
        "compare": "0",
    })
    assert code == 200
    assert 'id="sec-compare"' not in no_cmp_html
