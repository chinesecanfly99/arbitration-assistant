"""端到端流水线：一段大白话 → 能算的钱 + 能核的法条 + 还缺什么（S3.2）。

设计上的硬约定：
- **模型只负责抽参数，钱一律由 calc.py 算**。这里的输入必须是已经结构化的字段。
- 缺关键字段就**不硬算**，返回 need_more 并列出要问的问题（负功能：宁可问，不猜）。
- 每条金额都带 basis，并且 basis 里引用的法条要能过 laws.exists —— 单测里扫源码强制这一点。
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from . import laws
from .calc import ClaimInput, compute
from .deadline import analyze as analyze_deadlines
from .extract import extract
from .mock_hr import rehearsal
from .scope import judge

# 这些字段的 None 表示"用户没说"，不能直接喂给 ClaimInput（None 会顶掉默认值，
# 例如 has_written_contract=None 会让二倍工资被误触发）。缺失时用规则的默认值。
OPTIONAL_WITH_DEFAULT = {
    "has_written_contract": True,
    "taken_annual_leave_days": None,
    "unused_annual_leave_days": None,
    "contract_signed_date": None,
    "total_work_years": None,
    "social_avg_wage": None,
    "restday_compensated_by_leave": False,
    "overtime_workday_hours": 0,
    "overtime_restday_hours": 0,
    "overtime_holiday_hours": 0,
    "unpaid_wages": 0,
}
REQUIRED = ("hire_date", "end_date", "monthly_wage", "termination")

QUESTIONS = {
    "hire_date": "您是哪一天入职的？（精确到月就行）",
    "end_date": "您是哪一天离开公司的？（劳动合同哪天解除/终止？）",
    "monthly_wage": "您离职前 12 个月平均每月工资多少？（含奖金、补贴，税前）",
    "termination": "是公司辞退、还是您自己辞职、还是合同到期不续签？",
    "contract_signed_date": "如果是后来补签的合同，是哪一天补签的？",
}


def gap_questions(fields: dict) -> list[str]:
    """缺口检测：必填项缺哪个就问哪个（一次最多问 2 个，别把当事人问烦）。"""
    missing = [k for k in REQUIRED if fields.get(k) is None]
    return [QUESTIONS.get(k, f"请补充 {k}") for k in missing[:2]]


def fields_to_input(fields: dict) -> dict:
    """把抽取结果收敛成 ClaimInput 的合法入参。"""
    out: dict[str, Any] = {}
    for k, default in OPTIONAL_WITH_DEFAULT.items():
        v = fields.get(k)
        out[k] = default if v is None else v
    for k in REQUIRED:
        out[k] = fields.get(k)
    return out


def analyze(story: str, today: date | None = None, hints: dict | None = None, mode: str = "strict") -> dict:
    """story → 结构化结论。返回 dict，前端/CLI 直接用。"""
    today = today or date.today()
    ex = extract(story, today=today)
    fields = dict(ex["fields"])
    hints = dict(hints or {})
    # 模型层的输出优先于规则层（规则层是兜底），但 None 不覆盖已抽到的值
    for k, v in hints.items():
        if v is not None:
            fields[k] = v

    # 缺字段：mode="best_effort" 时按最保守的默认值试算，并在 assumptions 里明说
    assumptions = []
    if mode == "best_effort":
        if fields.get("termination") is None:
            assumptions.append("解除方式没说明（是公司辞退、还是自己辞职？），暂不计经济补偿/赔偿金；确认后可能再加 N 或 2N")
        if fields.get("end_date") is None and fields.get("hire_date"):
            fields["end_date"] = today
            assumptions.append("未说明离职日期，暂按今天计（工龄会算多，务必确认）")

    verdict = judge(story, fields)
    if not verdict.in_scope:
        return {
            "status": "out_of_scope",
            "story": story,
            "fields": fields,
            "scope": {"cause": verdict.cause, "reason": verdict.refusal_reason},
            "redirect": verdict.redirect,
            "hints": verdict.hints,
        }

    missing = [k for k in REQUIRED if fields.get(k) is None]
    if mode == "best_effort":
        missing = [k for k in missing if k != "termination"]  # 未说明就不猜，照样先算别的
    base = {
        "status": "ok",
        "story": story,
        "fields": fields,
        "evidence": ex["evidence"],
        "relative": ex["relative"],
        "missing": missing,
        "questions": gap_questions(fields),
        "assumptions": assumptions,
        "scope": {"cause": verdict.cause, "causes": verdict.causes, "hints": verdict.hints},
    }
    if missing:
        base["status"] = "need_more"
        return base

    inp = ClaimInput(**fields_to_input(fields))
    res = compute(inp)
    items = []
    for it in res["items"]:
        items.append({**it, "cite_ok": basis_cites_ok(it["basis"]), "cite_texts": cite_texts(it["basis"])})
    d = inp.end_date
    deadlines = [asdict(x) for x in analyze_deadlines(d, today, employment_ongoing=False)]
    return {
        **base,
        "total": res["total"],
        "items": items,
        "warnings": res["warnings"],
        "service_months": res["service_months"],
        "severance_months": res["severance_months"],
        "deadlines": deadlines,
        "citation_problems": [i["name"] for i in items if not i["cite_ok"]],
        "rehearsal": rehearsal(verdict.cause, fields),
    }


def _basis_list(basis: str) -> list[tuple[str, str]]:
    """'《劳动合同法》第 47 条' → [('labor_contract_law','47')]"""
    import re

    out = []
    for m in re.finditer(r"《([^》]+)》第\s*([零一二三四五六七八九十百\d]+)\s*条", basis or ""):
        slug = laws.resolve_name(m.group(1))
        no = str(laws.cn_to_int(m.group(2))) if not m.group(2).isdigit() else m.group(2)
        if slug:
            out.append((slug, no))
    return out


def basis_cites_ok(basis: str) -> bool:
    pairs = _basis_list(basis)
    return bool(pairs) and all(laws.exists(slug, no) for slug, no in pairs)


def cite_texts(basis: str) -> list[dict]:
    out = []
    for slug, no in _basis_list(basis):
        a = laws.get(slug, no)
        if a:
            out.append({"law": a.law, "article_no": a.article_no, "cite": a.cite, "text": a.text[:120]})
    return out
