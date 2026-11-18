"""Train and evaluate the optional consultation-topic classifier on local STARD data."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path

from arb.labor_topic import FEATURE_COUNT, MODEL_PATH, features, model_score, question_key, score_labor_topic
from arb.scope import assess_scope, judge
from scripts.audit_official_cases import CASE_FILE

ROOT = Path(__file__).resolve().parents[1]
STARD_REPO = "https://github.com/oneal2000/STARD"
LABOR_REFERENCES = (
    "劳动合同法", "劳动法第", "劳动争议", "工伤保险", "社会保险法", "工资支付", "带薪年休假",
)


def labeled_questions(path: Path) -> list[tuple[str, str, bool]]:
    buckets: dict[str, tuple[str, set[bool]]] = {}
    for row in json.loads(path.read_bytes()):
        question = row["问题"].strip()
        key = question_key(question)
        is_labor = any(term in law for law in row["match_name"] for term in LABOR_REFERENCES)
        buckets.setdefault(key, (question, set()))[1].add(is_labor)
    return [(key, value[0], value[1].pop()) for key, value in sorted(buckets.items()) if len(value[1]) == 1]


def split_questions(rows: list[tuple[str, str, bool]]) -> list[list[tuple[str, bool]]]:
    train, dev, test = [], [], []
    for label in (False, True):
        subset = [(question, wanted) for _, question, wanted in rows if wanted == label]
        first, second = len(subset) * 7 // 10, len(subset) * 85 // 100
        train.extend(subset[:first])
        dev.extend(subset[first:second])
        test.extend(subset[second:])
    return [train, dev, test]


def train_weights(train: list[tuple[str, bool]]) -> tuple[list[float], float]:
    encoded = [(features(question), label) for question, label in train]
    sizes = Counter(label for _, label in encoded)
    weights = [0.0] * FEATURE_COUNT
    bias = 0.0
    rng = random.Random(20261118)
    for epoch in range(38):
        rng.shuffle(encoded)
        step = 0.55 / (1 + epoch / 12)
        for vector, label in encoded:
            if not vector:
                continue
            class_weight = len(encoded) / (2 * sizes[label])
            delta = step * class_weight * (float(label) - model_score(vector, weights, bias))
            bias += delta
            scaled = delta / math.sqrt(len(vector))
            for index in vector:
                weights[index] = weights[index] * 0.9998 + scaled
    return weights, bias


def metrics(wanted: list[bool], predicted: list[bool]) -> dict:
    tp = sum(a and b for a, b in zip(wanted, predicted))
    fp = sum(not a and b for a, b in zip(wanted, predicted))
    fn = sum(a and not b for a, b in zip(wanted, predicted))
    return {
        "total": len(wanted), "positive": sum(wanted), "tp": tp, "fp": fp, "fn": fn,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
    }


def baseline_prediction(text: str) -> bool:
    return assess_scope(text, judge(text))["kind"] in {"labor", "unclear", "mixed", "administrative"}


def run(path: Path, model_path: Path, revision: str, summary_path: Path | None) -> dict:
    rows = labeled_questions(path)
    train, dev, test = split_questions(rows)
    court_train = [
        (row["story"], True)
        for line in CASE_FILE.read_text(encoding="utf-8").splitlines()
        if line and (row := json.loads(line))["split"] == "development"
    ]
    coefficients, bias = train_weights(train + court_train)
    dev_labels = [label for _, label in dev]
    dev_scores = [model_score(features(text), coefficients, bias) for text, _ in dev]
    thresholds = [(threshold, metrics(dev_labels, [score >= threshold for score in dev_scores]))
                  for threshold in (n / 100 for n in range(50, 100))]
    eligible = [(threshold, score) for threshold, score in thresholds
                if (score["precision"] or 0) >= 0.90 and score["tp"] >= 3]
    threshold, validation = max(eligible, key=lambda item: (item[1]["tp"], -item[1]["fp"], item[0]),
                                default=(1.0, metrics(dev_labels, [False] * len(dev))))
    labels = [label for _, label in test]
    predictions = [model_score(features(text), coefficients, bias) >= threshold for text, _ in test]
    baseline = [baseline_prediction(text) for text, _ in test]
    held_out = metrics(labels, predictions)
    added = metrics(labels, [a or b for a, b in zip(baseline, predictions)])
    enabled = bool(eligible and (held_out["precision"] or 0) >= 0.85
                   and added["tp"] > metrics(labels, baseline)["tp"]
                   and added["fp"] <= metrics(labels, baseline)["fp"] + 1)
    provenance = {"url": STARD_REPO, "revision": revision, "license": "MIT",
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    model = {
        "version": 1, "source": provenance, "enabled": enabled, "threshold": threshold,
        "bias": round(bias, 7), "coefficients": [round(value, 7) for value in coefficients],
    }
    model_path.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    summary = {
        "source": provenance, "input_rows": len(json.loads(path.read_bytes())), "deduplicated": len(rows),
        "train": {"total": len(train) + len(court_train), "stard": len(train),
                  "positive": sum(label for _, label in train) + len(court_train), "court_cases": len(court_train)},
        "validation": validation, "held_out_model": held_out, "held_out_rules": metrics(labels, baseline),
        "held_out_combined": added, "threshold": threshold, "enabled": enabled,
    }
    if summary_path:
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", type=Path, nargs="?")
    parser.add_argument("--revision")
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--query")
    args = parser.parse_args()
    if args.query:
        print(json.dumps(score_labor_topic(args.query), ensure_ascii=False))
        return
    if args.queries is None or not args.revision:
        parser.error("training requires a queries file and an upstream revision")
    print(json.dumps(run(args.queries, args.model, args.revision, args.summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
