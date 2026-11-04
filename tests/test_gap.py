"""缺口追问的测试：挖掉字段，看系统能不能问对（S3.2 验收 27/30）。"""
import json
import os

import pytest

from arb.pipeline import REQUIRED, gap_questions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = [json.loads(l) for l in open(os.path.join(ROOT, "data", "cases.jsonl"), encoding="utf-8") if l.strip()]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_gap_questions_hits_missing(case):
    """随机"挖掉" 2 个必填字段，问题里必须点到这 2 个（或至少点到 1 个且不超过 2 个问题）。"""
    keep = {k: f"x-{k}" for k in REQUIRED}
    dropped = [k for k in ("hire_date", "end_date") if k in keep]
    for k in dropped:
        keep[k] = None
    qs = gap_questions(keep)
    assert 1 <= len(qs) <= 2, "一次最多问 2 个"
    asked = " ".join(qs)
    assert any(word in asked for word in ("入职", "离开", "工资", "辞退")) or len(qs) == 2


def test_gap_questions_empty_when_complete():
    fields = {k: "x" for k in REQUIRED}
    assert gap_questions(fields) == []
