"""Optional local classifier for contextual labour-topic hints."""
from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from zlib import crc32

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "labor_topic_model.json"
FEATURE_COUNT = 8192
TOKEN = re.compile(r"[\u3400-\u9fff]+|[a-z]+|\d+")


def normalized(text: str) -> str:
    return "".join("0" if token.isdigit() else token for token in TOKEN.findall(text.lower()))


def question_key(text: str) -> str:
    return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()


def features(text: str) -> list[int]:
    text = normalized(text[:4000])
    return sorted({
        crc32(text[i:i + size].encode("utf-8")) % FEATURE_COUNT
        for size in (2, 3) for i in range(len(text) - size + 1)
    })


def model_score(vector: list[int], coefficients: list[float], bias: float) -> float:
    linear = bias
    if vector:
        linear += sum(coefficients[i] for i in vector) / math.sqrt(len(vector))
    return 1 / (1 + math.exp(-max(-40.0, min(40.0, linear))))


@lru_cache(maxsize=1)
def _load() -> dict:
    if not MODEL_PATH.is_file():
        return {}
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if model["version"] != 1 or len(model["coefficients"]) != FEATURE_COUNT:
        return {}
    return model


def score_labor_topic(story: str) -> dict:
    """Return an offline assisted-review score from the recorded model."""
    model = _load()
    vector = features(story)
    if not model or not vector:
        return {"score": None, "suggestion": None}
    value = model_score(vector, model["coefficients"], model["bias"])
    return {"score": round(value, 4), "suggestion": value >= model["threshold"],
            "enabled_for_intake": model["enabled"]}
