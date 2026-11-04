"""案例库测试（S2.3 门禁用）。

案例库不是"写了 50 条就算完"：每条都要能被重新算出来、每条引用的法条都要在库，
否则评测集本身就成了新的幻觉来源。
"""
import json
import os
from datetime import date

import pytest

from arb import laws
from arb.calc import ClaimInput, compute

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_PATH = os.path.join(ROOT, "data", "cases.jsonl")
DATE_KEYS = {"hire_date", "end_date", "contract_signed_date"}


@pytest.fixture(scope="module")
def cases():
    with open(CASES_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_case_count_and_fields(cases):
    assert len(cases) == 50
    required = {"id", "title", "cause", "story", "gold", "expected", "must_cite", "hardness", "source"}
    for c in cases:
        assert required <= set(c), f"{c['id']} 缺字段"
        assert len(c["story"]) >= 20, f"{c['id']} 故事太短，不像真人说话"
        assert 1 <= c["hardness"] <= 3
        assert "教学构造" in c["source"]


def test_ids_unique(cases):
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_cause_coverage(cases):
    by: dict[str, int] = {}
    for c in cases:
        by[c["cause"]] = by.get(c["cause"], 0) + 1
    for main in ["illegal_dismissal", "severance", "double_wage", "overtime", "annual_leave"]:
        assert by.get(main, 0) >= 5, f"{main} 案例太少：{by.get(main, 0)}"
    assert len(by) >= 6


def test_must_cite_resolves(cases):
    for c in cases:
        assert c["must_cite"], f"{c['id']} 没标必引法条"
        for cite in c["must_cite"]:
            slug, _, no = cite.partition(":")
            assert laws.exists(slug, no), f"{c['id']} 引用不存在：{cite}"


def test_expected_is_reproducible(cases):
    """金标准必须能由规则层重现——这是"我们自己不算错"的保证。"""
    for c in cases:
        g = {k: (date.fromisoformat(v) if k in DATE_KEYS and isinstance(v, str) else v)
             for k, v in c["gold"].items()}
        res = compute(ClaimInput(**g))
        assert abs(res["total"] - c["expected"]["total"]) < 0.01, f"{c['id']} 金额对不上"


def test_every_expected_item_has_citable_basis(cases):
    for c in cases:
        for it in c["expected"]["items"]:
            assert it["basis"].startswith("《"), f"{c['id']} 的 {it['name']} 无法条依据"


def test_amounts_positive(cases):
    for c in cases:
        assert c["expected"]["total"] > 0, f"{c['id']} 金额为 0，案例设计有问题"


def test_story_mentions_gold_dates(cases):
    """故事里必须真的说了入职/离职时间，否则模型抽参数等于猜。"""
    for c in cases:
        y = c["gold"]["hire_date"][:4]
        assert y in c["story"] or c["gold"]["hire_date"] in c["story"], f"{c['id']} 故事没提入职年份"
