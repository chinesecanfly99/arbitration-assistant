"""值得性六维加权：回答"这趟值不值得去"，而不是"能拿多少钱"。

为什么单独做一层：
- 金额算对只回答了"多少"。标的 2000 元、证据只有口头、单位已停业、时效只剩 7 天，
  这四个数放在一起才决定"该不该去"，而它们彼此不能相加、不能替代；
- 每个维度都给出"为什么给这个分"，用户可以逐条反驳我——可解释比准确更重要；
- 结论三选一：建议仲裁 / 可仲裁但有更好的路 / 不建议，避免只给一个"能去"的信号。

六维与权重（权重是我们定的，写在 WEIGHTS 里，改就是改一行）：
    标的额与成本比 0.25 / 证据强度 0.25 / 一裁终局 0.10
    执行可能性 0.15 / 替代路径 0.10 / 时效剩余 0.15

免责：分数只用于排序"要做的事"，不是胜诉概率，也不预测裁判结果。
"""
from __future__ import annotations

WEIGHTS = {
    "amount_cost": 0.25,
    "evidence": 0.25,
    "one_final": 0.10,
    "enforcement": 0.15,
    "alternative": 0.10,
    "urgency": 0.15,
}

LABELS = {
    "amount_cost": "标的额与成本比",
    "evidence": "证据强度",
    "one_final": "一裁终局影响",
    "enforcement": "执行可能性",
    "alternative": "替代路径优越性",
    "urgency": "时效剩余",
}

MONEY_TYPES = {"termination", "no_contract", "unpaid_wage", "overtime", "annual_leave"}


def _amount_dim(total: float, types: set[str]) -> tuple[int, str]:
    money_claim = bool(types & MONEY_TYPES)
    if total <= 0:
        if money_claim:
            return 50, "金额还算不出来（缺工资基数或离职日），但诉求本身是金钱请求，先把数算清"
        return 30, "诉求里没有可计算的金额（确认/抗辩类），金额维度按中性处理"
    if total < 3000:
        return 25, f"标的约 {total:,.0f} 元，低于一个月工资量级，请假跑一趟的时间成本可能超过收益"
    if total < 8000:
        return 45, f"标的约 {total:,.0f} 元，扣掉误工和往返成本后收益有限，但权利本身不该放弃"
    if total < 20000:
        return 65, f"标的约 {total:,.0f} 元，值得投入一次仲裁"
    if total < 50000:
        return 80, f"标的约 {total:,.0f} 元，明显高于程序成本"
    return 90, f"标的约 {total:,.0f} 元，程序成本占比很低"


def _one_final_dim(city: dict | None, total: float, types: set[str]) -> tuple[int, str]:
    if not city:
        return 60, "用工所在地未确认，看不出是否在一裁终局线内（这条只影响单位能不能起诉）"
    line = city.get("one_final_award_threshold")
    name = city.get("city") or "当地"
    if not line:
        return 60, f"{name}的一裁终局金额线未收录，这一维按中性处理"
    one_final_types = {"unpaid_wage", "termination", "overtime", "annual_leave"}
    if total and total <= line and (types & one_final_types):
        return 85, (
            f"标的 {total:,.0f} 元未超过{name}一裁终局线 {line:,.0f} 元："
            "裁决作出即生效，单位不能起诉只能申请撤销，对劳动者有利"
        )
    if total > line:
        return 60, f"标的 {total:,.0f} 元超过{name}一裁终局线 {line:,.0f} 元，单位不服可起诉，周期可能拉长"
    return 60, "金额还没算出来，确认工资与工龄后再看是否在一裁终局线内"


def _urgency_dim(days_left, still_employed: bool) -> tuple[int, str]:
    if days_left is None and still_employed:
        return 50, "仍在职：时效还没开始跑，但继续留着要考虑关系成本"
    if days_left is None:
        return 50, "时效起算点未确认（先说清哪天离职）"
    if days_left < 0:
        return 90, f"按离职日已超过一年（{abs(days_left)} 天前），需先解决时效障碍；对方不抗辩时仍可主张"
    if days_left <= 60:
        return 90, f"时效仅剩 {days_left} 天，属最高优先级，本周就该把材料备齐"
    if days_left <= 180:
        return 70, f"时效剩余 {days_left} 天，建议一个月内提交"
    return 55, f"时效剩余 {days_left} 天，时间相对充裕，可以先把材料备齐再决定"


def _enforcement_dim(total: float) -> tuple[int, str]:
    if total <= 0:
        return 50, "违约金/确认之诉类请求，执行维度按中性处理"
    return 55, (
        "单位经营状态未核实：立案前用「电子营业执照」小程序查是否注销、吊销或经营异常；"
        "已停业的，胜诉也可能执行不到钱，优先找财产线索"
    )


def _alternative_dim(total: float, types: set[str]) -> tuple[int, str, dict | None]:
    if "unpaid_wage" in types and 0 < total <= 10000:
        return 35, "欠薪金额不大：劳动保障监察投诉（12333）通常比仲裁快，且可与仲裁并行", {
            "key": "supervision",
            "title": "先走劳动保障监察投诉（欠薪快速通道）",
            "why": f"欠薪 {total:,.0f} 元，监察投诉通常比仲裁快，且两条路可并行",
            "tel": "12333",
        }
    if "termination" in types and 0 < total <= 3000:
        return 40, "标的很小：先申请调解或协商，结案更快且不伤关系", {
            "key": "mediation",
            "title": "先申请调解或协商",
            "why": "标的额很小，调解结案更快",
            "tel": "12348",
        }
    return 65, "未发现明显更优的替代路径", None


def compute(
    fields: dict,
    total: float,
    types: set[str] | None = None,
    evidence: dict | None = None,
    city: dict | None = None,
    days_left=None,
) -> dict:
    """返回 {score, decision, decision_label, dimensions, reasons, alternative}。

    fields 只用三个键：termination / still_employed / 是否有书面合同。
    其它上下文（金额、证据、城市、时效）全部由参数直接给，方便单测逐个变量固定。
    """
    types = set(types or ())
    evidence = evidence or {}
    term = fields.get("termination")
    dims = []

    a_s, a_n = _amount_dim(total, types)
    dims.append({"key": "amount_cost", "label": LABELS["amount_cost"],
                 "weight": WEIGHTS["amount_cost"], "score": a_s, "note": a_n})

    if evidence:
        known = evidence.get("known", True)
        dims.append({"key": "evidence", "label": LABELS["evidence"],
                     "weight": WEIGHTS["evidence"], "score": evidence.get("score", 0),
                     "note": (f"证据强度 {evidence.get('level', '?')}（{evidence.get('score', 0)}/100）；"
                              + ("有书证支撑关键事实" if evidence.get("score", 0) >= 70
                                 else "关键事实仍主要靠口述"))
                     if known else
                     "你还没说手上具体有哪些材料，这一维按中性分算；照清单备齐后会更准"})
    else:
        dims.append({"key": "evidence", "label": LABELS["evidence"],
                     "weight": WEIGHTS["evidence"], "score": 60,
                     "note": "材料还没上传：结论先按你口述的事实给，照清单备齐会更准"})

    for fn, key, args in (
        (_one_final_dim, "one_final", (city, total, types)),
        (_enforcement_dim, "enforcement", (total,)),
    ):
        s, n = fn(*args)
        dims.append({"key": key, "label": LABELS[key], "weight": WEIGHTS[key],
                     "score": s, "note": n})

    alt_s, alt_n, alt = _alternative_dim(total, types)
    dims.append({"key": "alternative", "label": LABELS["alternative"],
                 "weight": WEIGHTS["alternative"], "score": alt_s, "note": alt_n})

    u_s, u_n = _urgency_dim(days_left, bool(fields.get("still_employed")))
    dims.append({"key": "urgency", "label": LABELS["urgency"],
                 "weight": WEIGHTS["urgency"], "score": u_s, "note": u_n})

    score = round(sum(d["score"] * d["weight"] for d in dims))

    # ---- 三选一：先判"根本不用去"，再看总分 ----
    if term == "employee_resign":
        decision, label = "not_recommended", "主动辞职原则上没有经济补偿，不必为此单独申请仲裁"
    elif total <= 0:
        decision, label = "not_recommended", "先别急着提交：现在还算不出可主张的金额，把事实补齐再说"
    elif score >= 62 and not (alt and score < 70):
        decision, label = "recommend", "建议仲裁"
    elif alt:
        decision, label = "better_alternative", "可以仲裁，但有更快的路"
    else:
        decision, label = "not_recommended", "再等等：把材料补齐、把关键事实问清，比现在递上去强"

    return {
        "score": score,
        "decision": decision,
        "decision_label": label,
        "dimensions": dims,
        "alternative": alt,
        "reasons": _reasons(dims, fields, total, types, city, days_left),
    }


def _reasons(dims, fields, total, types, city, days_left) -> list[dict]:
    """三条最该看的理由：按"会不会翻车"排序，不看分数。"""
    by_key = {d["key"]: d for d in dims}
    out: list[dict] = []

    term = fields.get("termination")
    if term == "employee_resign":
        out.append({
            "text": "自己提出辞职、且不属于未足额发工资或未依法缴社保等被迫解除情形，"
                    "原则上没有经济补偿（N）；除非能证明是《劳动合同法》第 38 条那几种情形",
            "cites": ["labor_contract_law:46"],
        })
    elif term == "illegal_dismissal":
        out.append({
            "text": "解除由单位提出、且理由难以成立，按违法解除主张 2N（经济补偿标准的二倍），与 N 不并用",
            "cites": ["labor_contract_law:87"],
        })
    elif "no_contract" in types and fields.get("has_written_contract") is False:
        out.append({
            "text": "未订立书面劳动合同，可主张自用工满一个月次日起的二倍工资差额，最多 11 个月",
            "cites": ["labor_contract_law:82"],
        })
    elif "unpaid_wage" in types:
        out.append({
            "text": "拖欠劳动报酬属受案范围，且在职期间主张不受一年时效限制",
            "cites": ["labor_law:50"],
        })
    else:
        out.append({
            "text": "争议事项属于《劳动争议调解仲裁法》第二条受案范围，可以申请仲裁，仲裁不收费",
            "cites": ["arbitration_law:2"],
        })

    if days_left is not None and days_left <= 60:
        out.append({
            "text": f"仲裁时效仅剩 {days_left} 天，属最高优先级，先递申请保住权利，材料可以边补边交",
            "cites": ["arbitration_law:27"],
        })
    else:
        ev = by_key["evidence"]
        out.append({"text": ev["note"], "cites": ["arbitration_law:6"]})

    if total and city and (city.get("one_final_award_threshold") or 0) >= total > 0:
        out.append({"text": by_key["one_final"]["note"], "cites": ["arbitration_law:47"]})
    elif total > 0:
        out.append({"text": by_key["amount_cost"]["note"], "cites": ["labor_contract_law:47"]})
    else:
        out.append({"text": "按现在的事实算不出可主张的金额，先把入职日、离职日、月工资补齐再判断值不值得去",
                    "cites": ["arbitration_law:6"]})
    return out[:3]
