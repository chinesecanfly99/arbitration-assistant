"""关键词芯片（S3.3）：30+ 术语、每个都要有"人话解释"。"""
import pytest

from arb.chips import all_chips, groups, suggest


def test_at_least_30_terms():
    assert len(all_chips()) >= 30


def test_every_chip_is_explained_in_plain_words():
    for c in all_chips():
        assert c["term"] and c["plain"] and c["when"] and c["why"]
        assert len(c["plain"]) >= 12, c["term"]
        assert "第" not in c["plain"] or "条" not in c["plain"], f"[{c['term']}] 解释里别堆法条"


def test_terms_unique():
    terms = [c["term"] for c in all_chips()]
    assert len(terms) == len(set(terms))


def test_groups_cover_core_areas():
    g = groups()
    for name in ("离职", "工资", "合同"):
        assert name in g and len(g[name]) >= 3


def test_suggest_returns_relevant_chips():
    got = [c["term"] for c in suggest("公司没签合同就把我辞了，还欠我两个月工资")]
    assert any("二倍工资" in t for t in got)
    assert any("解除" in t or "经济补偿" in t for t in got)
    assert len(got) <= 6


def test_suggest_empty_story():
    assert suggest("") == []
