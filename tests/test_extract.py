"""抽取与流水线的回归防线（S3.1/S3.2 门禁用）。

这里的断言分两类：
1. **能力下限**：50 条案例上的准确率不能低于当前实测值——规则一改就掉，说明改坏了。
2. **行为约定**：缺字段必须不硬算、相对时间必须标注、金额依据必须能核。
"""
import json
import os
from datetime import date

import pytest

from arb.extract import extract
from arb.pipeline import analyze

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = date(2025, 1, 1)


def load_cases():
    with open(os.path.join(ROOT, "data", "cases.jsonl"), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


CASES = load_cases()


def norm(v):
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return v
    return v


def acc(field: str) -> float:
    hit = n = 0
    for c in CASES:
        gold = c["gold"].get(field)
        if gold is None:
            continue
        got = extract(c["story"], today=TODAY)["fields"].get(field)
        n += 1
        if field in ("monthly_wage", "unpaid_wages"):
            ok = got is not None and abs(float(got) - float(gold)) <= max(1.0, 0.01 * float(gold))
        else:
            ok = norm(got) == norm(gold)
        hit += ok
    return hit / n if n else 0.0


@pytest.mark.parametrize("field,floor", [
    ("hire_date", 1.00),
    ("monthly_wage", 1.00),
    ("end_date", 0.85),
    ("termination", 0.58),  # 另 20 条本就没说清谁提的，按设计留空
    ("has_written_contract", 1.00),
])
def test_field_accuracy_floor(field, floor):
    assert acc(field) >= floor, f"{field} 准确率掉到 {acc(field):.0%}（下限 {floor:.0%}）"


def test_amount_accuracy_floor():
    from arb.evalkit import amount_matches

    ok = 0
    for c in CASES:
        r = analyze(c["story"], today=TODAY, mode="best_effort")
        ok += r["status"] == "ok" and amount_matches(c["story"], r, c["expected"])
    rate = ok / len(CASES)
    assert rate >= 0.90, f"端到端金额命中率掉到 {rate:.0%}（下限 90%）"


def test_missing_fields_do_not_compute():
    r = analyze("公司把我辞了，我很生气。", today=TODAY)
    assert r["status"] == "need_more"
    assert "total" not in r
    assert r["questions"], "缺字段时必须给追问问题"


def test_best_effort_marks_assumptions():
    r = analyze("2021年3月1日入职，月薪9000，2024年3月1日公司把我辞了。", today=TODAY, mode="best_effort")
    assert r["status"] == "ok"
    assert r["fields"]["termination"] == "illegal_dismissal"
    assert r["total"] > 0


def test_relative_date_is_flagged():
    out = extract("2021年3月进厂，去年5月20号让我走人，月薪9000。", today=TODAY)
    assert out["fields"]["end_date"] == date(2024, 5, 20)
    assert out["relative"], "相对时间必须写进 relative，让前端提示用户确认"


def test_month_only_end_date_uses_month_end():
    out = extract("2020年8月入职，月薪13000，2024年5月协商一致解除。", today=TODAY)
    assert out["fields"]["end_date"] == date(2024, 5, 31)


def test_evidence_points_to_story():
    story = "2021年3月1日入职，月薪9000，2024年3月1日公司把我辞了。"
    out = extract(story, today=TODAY)
    for k, v in out["evidence"].items():
        if v.startswith("（"):
            continue
        assert v in story, f"{k} 的 evidence 不在原文里：{v}"


def test_all_item_citations_are_real():
    story = "2019年3月1日入职，月薪12000，2024年3月1日公司以组织架构调整解除，没签合同。"
    r = analyze(story, today=TODAY)
    assert r["status"] == "ok"
    assert r["items"]
    assert r["citation_problems"] == [], f"有法条引不对：{r['citation_problems']}"
    for it in r["items"]:
        assert it["cite_texts"], f"{it['name']} 没有可展示的法条原文"


def test_deadlines_present():
    r = analyze("2019年3月1日入职，月薪12000，2024年3月1日公司把我辞了。", today=TODAY)
    ds = r["deadlines"]
    assert len(ds) >= 3
    assert all(d["deadline"] for d in ds)

# ---- 2026-11-04 三条修复的回归测试 ----

def test_daigang_shifts_to_next_month_end():
    """待岗一个月后解除：从原始月份推下月月末，不能落回本月。"""
    f = extract("2018年10月入职，月薪9800，2024年2月公司说项目结束，安排待岗一个月后解除。", today=TODAY)["fields"]
    assert str(f["end_date"]) == "2024-03-31"


def test_no_renewal_is_not_signed_contract():
    """"不续签了"里的"签了"不能被当成"签了合同"。"""
    f = extract("2019年4月1日入职，合同2024年3月31日到期，公司说不续签了，月薪9000。", today=TODAY)["fields"]
    assert f["has_written_contract"] is None


def test_settlement_agreement_is_not_labor_contract():
    """"签了协议"是协商解除协议，不是劳动合同。"""
    f = extract("2020年8月入职，月薪13000，2024年5月公司跟我谈好，双方协商一致解除，签了协议。", today=TODAY)["fields"]
    assert f["has_written_contract"] is None


def test_month_level_end_date_takes_month_end():
    """只说"3月底离职"时取月末。"""
    f = extract("2023年3月入职，月薪7800，工作日加班120小时，2024年3月底我离职了。", today=TODAY)["fields"]
    assert str(f["end_date"]) == "2024-03-31"

# ---- 口语说法补齐（演示脚本踩到）----

def test_colloquial_monthly_wage():
    """"一个月9000"这种口语，工资不能抽空。"""
    f = extract("我2020年3月1日进的这家厂，一个月9000，2024年5月20号被辞了。", today=TODAY)["fields"]
    assert f["monthly_wage"] == 9000


def test_colloquial_no_contract():
    """"一直没跟我签书面合同"要判成未签。"""
    f = extract("2020年3月1日入职，一直没跟我签书面合同，月薪9000，2024年5月20号被辞了。", today=TODAY)["fields"]
    assert f["has_written_contract"] is False
