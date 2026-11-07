"""按案由和案情线索检索本地公开类案。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CASE_FILE = Path(__file__).resolve().parents[2] / "data" / "reference_cases.json"


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    return json.loads(CASE_FILE.read_text(encoding="utf-8"))


def recommend(issues: set[str], story: str, limit: int = 3) -> list[dict]:
    """每个案由选一个案例，优先展示与叙述线索更接近的案例。"""
    ranked = []
    for case in _load():
        if case["issue"] not in issues:
            continue
        score = sum(word in story for word in case["keywords"])
        if case.get("requires_keyword") and score == 0:
            continue
        ranked.append((score, case))

    results = []
    seen = set()
    for _, case in sorted(ranked, key=lambda item: -item[0]):
        if len(results) >= limit:
            break
        if case["issue"] in seen:
            continue
        seen.add(case["issue"])
        results.append({key: case[key] for key in
                        ("id", "title", "focus", "result", "compare", "distinguish", "source", "url")})
    return results
