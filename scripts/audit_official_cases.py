"""Run the rules against published-case probes and their dictation variants."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from arb.pipeline import analyze

ROOT = Path(__file__).resolve().parents[1]
CASE_FILE = ROOT / "data" / "official_case_probes.jsonl"
AS_OF = date(2026, 11, 18)
ADMIN_TOPICS = {"工伤": "work_injury", "社保补缴": "social_insurance", "公积金": "housing_fund"}


def variant_texts(text: str) -> list[str]:
    """Make deterministic stress inputs; these are not additional cases."""
    clauses = text.split("。")
    spaced = "。\n".join(clauses)
    spoken = text.replace("工资", "工钱").replace("劳动仲裁", "劳动仲裁那边")
    hesitant = "。嗯，".join(clauses).removesuffix("嗯，")
    return [
        text, spaced, "你好，我说一下情况。" + text, "呃，" + hesitant,
        "我想问一下。" + spoken, "是这样的，" + text.replace("，", "，呃，"),
        "我按实际情况说：" + text.replace("公司", "单位"), "你好。\n" + spoken.replace("。", "。\n"),
        text + "\n这些是我记得的情况。",
        "我记得是这样：" + text.replace("，", "。\n"),
        "想请教个事。" + text.replace("发工资", "发工钱"),
        "大概情况如下。\n" + text.replace("。", "，然后。"),
    ]


def violations(case: dict, story: str) -> list[str]:
    report = analyze(story, today=AS_OF, mode="best_effort")
    assessment = report.get("scope_assessment", {})
    topics = set(assessment.get("causes", []))
    review = report.get("issue_review") or {}
    admin = review.get("administrative") or report.get("scope", {}).get("cause")
    if admin in ADMIN_TOPICS:
        topics.add(ADMIN_TOPICS[admin])
    if review.get("injury"):
        topics.add("work_injury")
    if review.get("employment"):
        topics.add("employment_relationship")
    errors = [f"漏识别 {topic}" for topic in case["topics"] if topic not in topics]
    check = case.get("review")
    if check and not review.get(check):
        errors.append(f"缺少专项核对 {check}")
    if case.get("hold_amount") and "total" in report:
        errors.append("前置条件待确认时给出确定总额")
    return errors


def run(infile: Path = CASE_FILE) -> dict:
    rows = [json.loads(line) for line in infile.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = {}
    for split in ("development", "holdout"):
        selected = [row for row in rows if row["split"] == split]
        failing = []
        counts = Counter()
        for case in selected:
            variants = variant_texts(case["story"])
            errors = [violations(case, text) for text in variants]
            counts["case_pass"] += not errors[0]
            counts["variant_pass"] += sum(not error for error in errors[1:])
            for issues in errors:
                counts.update(issues)
            if any(errors):
                failing.append({"id": case["id"], "title": case["title"], "source": case["source"],
                                "baseline_violations": errors[0], "variant_failures": sum(bool(error) for error in errors[1:])})
        summary[split] = {
            "cases": len(selected), "case_pass": counts.pop("case_pass", 0),
            "variants": sum(len(variant_texts(case["story"])) - 1 for case in selected),
            "variant_pass": counts.pop("variant_pass", 0),
            "violations": dict(counts), "failing": failing,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(run(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
