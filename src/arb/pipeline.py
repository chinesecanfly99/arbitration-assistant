"""端到端流水线：一段大白话 → 能不能申请 + 能算多少钱 + 该带什么 + 值不值得去。

设计上的硬约定：
1. **模型只负责抽参数，钱一律由 calc.py 算**。这里的输入必须是已经结构化的字段。
2. **没被确认的外来读数不进计算**。规则从用户原话里抽出来的字段可以直接用；
   模型或图片给的字段先落进 `pending`，用户点头（`confirmed`）之后才写进 `fields`。
   口述与外来读数冲突时**不擅自择一**，两条都摆出来让用户选。
3. 缺关键字段就**不硬算**，返回 need_more 并列出要问的问题（负功能：宁可问，不猜）。
4. 资格闸门判定"不能申请"时返回 blocked，**不再往下算钱**——屏幕上那个总额会误导人。
5. 每条金额都带 basis，且 basis 引用的法条要能过 laws.exists（单测扫源码强制）。

返回结构（前端/CLI/PDF 共用）：
    status: ok | need_more | out_of_scope | blocked
    fields / sources / pending / assumptions
    gates   三层闸门（受案范围 / 资格 / 口径）
    items / total / deadlines / citation_problems
    evidence_score / materials / venue / worth / one_final_note
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from . import city as city_store
from . import laws, materials as materials_kb, venue as venue_kb, worth as worth_kb
from .calc import ClaimInput, compute
from .deadline import analyze as analyze_deadlines
from .evidence import score as evidence_score
from .extract import extract
from .gates import one_final_award_note, qualify
from .map import FIELD_LABELS
from .reference_cases import recommend
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

LABELS = {k: label for k, label, _hint in FIELD_LABELS}


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


def _absent(v: Any) -> bool:
    """字段算不算"用户没说"。

    规则抽取对没提到的数值字段会给 0（加班 0 小时、欠薪 0 元），这是计算用的默认值，
    不是用户的主张。所以判冲突时要把 0 当成"没说"，否则模型给一个真实读数就会被
    误判成"和你说的不一致"，白白多问一轮。
    """
    if v is None:
        return True
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v == 0
    return False


def merge_hints(fields: dict, hints: dict | None, confirmed: set[str]) -> tuple[list[dict], dict]:
    """把外来读数（模型/图片）与口述事实合并，**未确认的不写进 fields**。

    三种情形：
    - 用户已确认（key 在 confirmed 里）→ 写入，来源标 confirmed；
    - 口述里没有、也没确认 → 进 pending，等确认，**不参与计算**；
    - 口述里已有不同值 → 进 pending 并标 conflict，**保留口述值**，不擅自择一。

    外来读数与口述完全一致时不打扰用户，直接用。
    """
    sources = {k: "story" for k, v in fields.items() if not _absent(v)}
    pending: list[dict] = []
    for k, v in dict(hints or {}).items():
        if v is None:
            continue
        if k in confirmed:
            fields[k] = v
            sources[k] = "confirmed"
            continue
        story_val = fields.get(k)
        if not _absent(story_val) and story_val == v:
            continue
        pending.append({
            "key": k,
            "label": LABELS.get(k, k),
            "suggested": v,
            "from_story": None if _absent(story_val) else story_val,
            "reason": "unconfirmed" if _absent(story_val) else "conflict",
        })
    return pending, sources


def _min_days_left(deadlines: list[dict]) -> int | None:
    lefts = [d["days_left"] for d in deadlines
             if d.get("applicable") and d.get("days_left") is not None]
    return min(lefts) if lefts else None


def analyze(
    story: str,
    today: date | None = None,
    hints: dict | None = None,
    confirmed: Any = (),
    mode: str = "strict",
    city: str | None = None,
) -> dict:
    """story → 结构化结论。返回 dict，前端/CLI/PDF 直接用。"""
    today = today or date.today()
    ex = extract(story, today=today)
    fields = dict(ex["fields"])
    pending, sources = merge_hints(fields, hints, {str(c) for c in (confirmed or ())})

    # 缺字段：mode="best_effort" 时按最保守的默认值试算，并在 assumptions 里明说
    assumptions: list[str] = []
    if pending:
        n = len(pending)
        assumptions.append(
            f"有 {n} 项来自模型/图片的读数还没有你确认，本单**没有**用它们算钱"
            "（确认后我再重算，避免一个没核对过的数字被当成结论）"
        )
    if mode == "best_effort":
        if fields.get("termination") is None:
            assumptions.append("解除方式没说明（是公司辞退、还是自己辞职？），暂不计经济补偿/赔偿金；确认后可能再加 N 或 2N")
        if fields.get("end_date") is None and fields.get("hire_date"):
            fields["end_date"] = today
            sources["end_date"] = "assumed"
            assumptions.append("未说明离职日期，暂按今天计（工龄会算多，务必确认）")

    verdict = judge(story, fields)
    if not verdict.in_scope:
        return {
            "status": "out_of_scope",
            "story": story,
            "fields": fields,
            "sources": sources,
            "pending": pending,
            "scope": {"cause": verdict.cause, "reason": verdict.refusal_reason},
            "redirect": verdict.redirect,
            "hints": verdict.hints,
        }

    # ---------- 三层闸门：能不能进门 ----------
    gates = qualify(story, fields, verdict, today=today, city=city)
    base = {
        "status": "ok",
        "story": story,
        "fields": fields,
        "sources": sources,
        "pending": pending,
        "evidence": ex["evidence"],
        "relative": ex["relative"],
        "gates": gates,
        "scope": {"cause": verdict.cause, "causes": verdict.causes, "hints": verdict.hints},
        "assumptions": assumptions,
    }

    if gates["blockers"]:
        return {
            **base,
            "status": "blocked",
            "blockers": gates["blockers"],
            "questions": [],
            "missing": [],
        }

    missing = [k for k in REQUIRED if fields.get(k) is None]
    if mode == "best_effort":
        missing = [k for k in missing if k != "termination"]  # 未说明就不猜，照样先算别的
    base["missing"] = missing
    base["questions"] = gap_questions(fields)
    if missing:
        base["status"] = "need_more"
        return base

    # ---------- 城市口径：3 倍封顶的基数 ----------------
    city_info = gates.get("city")
    if city_info and fields.get("social_avg_wage") is None:
        avg = (city_info.get("params") or {}).get("avg_wage_monthly")
        if avg:
            fields["social_avg_wage"] = avg
            sources["social_avg_wage"] = "city"
            assumptions.append(
                f"3 倍封顶按{city_info['city']}上年度职工月平均工资 {avg:,.0f} 元算"
                f"（数据核验日 {city_info.get('verified_at') or '未标注'}）；该数字每年调整，立案前请再核一次"
            )
    elif gates.get("city_name") and not city_info:
        assumptions.append(
            f"{gates['city_name']}的口径还没收录，**没有**套用任何城市的社平工资，3 倍封顶这一项按未启用处理"
        )

    # ---------- 算钱 ----------
    inp = ClaimInput(**fields_to_input(fields))
    res = compute(inp)
    items = [
        {**it, "cite_ok": basis_cites_ok(it["basis"]), "cite_texts": cite_texts(it["basis"])}
        for it in res["items"]
    ]
    deadlines = [asdict(x) for x in analyze_deadlines(inp.end_date, today, employment_ongoing=False)]
    days_left = _min_days_left(deadlines)

    # ---------- 证据 / 材料 / 值得性 / 路径 ----------
    types = materials_kb.dispute_types(verdict.causes, items)
    have = materials_kb.what_you_have(story)
    ev = evidence_score(have, types)
    mats = materials_kb.build_materials(types, story)
    worth = worth_kb.compute(fields, res["total"], types, ev, city_info, days_left)
    venue = venue_kb.build(city_info, days_left, res["total"])

    return {
        **base,
        "total": res["total"],
        "items": items,
        "warnings": res["warnings"],
        "service_months": res["service_months"],
        "severance_months": res["severance_months"],
        "deadlines": deadlines,
        "days_left": days_left,
        "citation_problems": [i["name"] for i in items if not i["cite_ok"]],
        "rehearsal": rehearsal(verdict.cause, fields),
        "types": sorted(types),
        "reference_cases": recommend(types, story),
        "city": city_info,
        "evidence_score": ev,
        "materials": mats,
        "venue": venue,
        "worth": worth,
        "one_final_note": one_final_award_note(gates.get("city_name"), res["total"]),
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


def covered_cities() -> list[dict]:
    """给前端/CLI 展示"我们覆盖了哪几个城市"，避免用户以为全国都能算。"""
    return city_store.table()
