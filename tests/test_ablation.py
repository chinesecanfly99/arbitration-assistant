# -*- coding: utf-8 -*-
"""S6.2 消融实验的回归测试：四臂的结论必须由代码跑出来，不能是文档里编的。

守三件事：
1. 裸算臂在缺字段时确实会"猜钱"，且猜不准（这就是"该问就问"的证据）；
2. 加了范围拒答后，探针明显变好；
3. 只有接了法条库的臂，引用才可核验。
"""
import importlib.util
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


abl = _load("ablation")


def _cases(n: int = 12):
    return abl.load_cases()[:n]


def test_naked_arm_guesses_when_missing():
    """信息不全时，裸算臂照样给钱（猜），这正是最危险的失败模式。"""
    r = abl.arm_naked({"story": "公司把我辞了，我很生气。"})
    assert r["status"] == "ok" and r["total"] > 0


def test_scope_arm_refuses_out_of_scope():
    for story, kind, want in abl.PROBES:
        if want != "out_of_scope":
            continue
        assert abl.arm_scope({"story": story})["status"] == "out_of_scope", f"{kind} 没被拦住"


def test_asking_arm_does_not_guess_money():
    """缺关键字段时，C/D 臂必须不给金额。"""
    for mod in (abl.arm_ask, abl.arm_full):
        r = mod({"story": "公司把我辞了，我很生气。"})
        assert r["status"] == "need_more" and r["total"] is None


def test_citations_only_verifiable_in_full_arm():
    cases = _cases()
    assert abl.score(abl.arm_naked, cases)["verified"] == 0
    full = abl.score(abl.arm_full, cases)
    assert full["verified"] > 0 and full["verified"] == full["cited"]


def test_full_arm_beats_naked_on_amount():
    cases = _cases()
    naked = abl.score(abl.arm_naked, cases)["amount"]
    full = abl.score(abl.arm_full, cases)["amount"]
    assert full > naked, "混合系统在金额上必须好于「缺字段就猜」的裸算"


def test_probe_counts_monotonic():
    """探针判对数：A <= B <= D。"""
    a = sum(1 for _, _, ok in abl.probe(abl.arm_naked) if ok)
    b = sum(1 for _, _, ok in abl.probe(abl.arm_scope) if ok)
    d = sum(1 for _, _, ok in abl.probe(abl.arm_full) if ok)
    assert a <= b <= d
    assert d == len(abl.PROBES)


def test_ablation_doc_exists_and_matches_code():
    path = os.path.join(ROOT, "docs", "ablation.md")
    assert os.path.exists(path), "先跑 PYTHONPATH=src python -m scripts.ablation 生成"
    text = open(path, encoding="utf-8").read()
    for name in ("A 裸算", "B + 范围拒答", "C + 缺口追问", "D 全套"):
        assert name in text


# ---- 纯大模型那一臂：只测"离线也能验的部分" ----

lb = _load("llm_baseline")


def test_llm_baseline_citation_checker_catches_fake():
    """真引用能核到，编的条号核不到——这是给"纯大模型"那一臂准备的打分器。"""
    tot, ok = lb.parse_basis_cites("依据《劳动合同法》第87条、《劳动合同法》第300条")
    assert tot == 2 and ok == 1


def test_llm_baseline_without_key_exits_2(monkeypatch):
    monkeypatch.delenv("ARB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert lb.main() == 2
