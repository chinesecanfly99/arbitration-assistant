"""证据清单：每条证据标注"谁举证"。

依据
- 《劳动争议调解仲裁法》第六条：与争议事项有关的证据属于用人单位掌握管理的，
  用人单位应当提供；不提供的，由用人单位承担不利后果。
- 实务口径：用人单位作出解除决定的，由用人单位对解除的合法性承担举证责任；
  考勤记录、工资发放记录、规章制度公示记录，通常由单位举证。

这里只做**清单与举证方标注**，不给胜诉判断。
"""

from __future__ import annotations

UNIT_HINTS = (
    "考勤",
    "工资条",
    "工资发放",
    "银行流水",
    "解除通知",
    "解除决定",
    "规章制度",
    "公示",
    "打卡",
    "排班",
    "社保记录",
    "单位存档",
    "单位保存",
)
ME_HINTS = ("劳动合同", "申请书", "聊天记录", "录音", "工作群", "工牌", "邮件", "工资转账")


def who(name: str) -> str:
    """"单位" / "你" / "双方" —— 按证据名判断，没命中就按"你"（自己先备着不亏）。"""
    unit = any(h in name for h in UNIT_HINTS)
    me = any(h in name for h in ME_HINTS)
    if unit and me:
        return "双方"
    if unit:
        return "单位"
    return "你"


def rows(checklist: list[str]) -> list[dict]:
    out = []
    for name in checklist:
        w = who(name)
        out.append(
            {
                "name": name,
                "who": w,
                "why": _why(name, w),
            }
        )
    return out


def _why(name: str, w: str) -> str:
    if w == "单位":
        return "属单位掌握管理的证据，可要求单位提供；不提供由单位承担不利后果"
    if w == "双方":
        return "双方都可能有；你手上的先留好，同时可申请仲裁委调取"
    return "需要你自己准备并提交"


def summary(rows_: list[dict]) -> str:
    unit = sum(1 for r in rows_ if r["who"] == "单位")
    me = sum(1 for r in rows_ if r["who"] == "你")
    if not rows_:
        return ""
    return f"共 {len(rows_)} 项：其中 {unit} 项可要求单位提供，{me} 项需要你自己准备。"


# ---------------------------------------------------------------- 证据强度打分
# 为什么要打分：只给清单，用户不知道"我现在这点材料够不够去立案"。
# 打分不预测胜负（那是我明确拒绝的事），只回答"关键事实有没有书证撑着"。
#
# 口径（写出来是为了能被质疑，而不是显得准确）：
# - 四个维度：劳动关系、工资标准、解除事实、争议关键证据；
# - 每个维度取"手上最好的一份材料"的分，不累加——两份银行流水不比一份更管用；
# - 满分按本案类型动态算：不是"解除"类就没有解除事实这一维的 25 分，否则会被冤枉扣分。

MATERIAL_LABELS = {
    "contract": "书面劳动合同/录用通知",
    "bank_flow": "银行工资流水",
    "payslip": "工资条",
    "tax_record": "个税申报记录",
    "social_record": "社保缴纳记录",
    "termination_notice": "解除通知/辞退邮件",
    "resignation_cert": "离职证明",
    "chat_record": "微信/钉钉聊天记录",
    "attendance": "考勤/打卡/排班记录",
    "badge": "工牌/工作证/工作群",
    "wage_claim_log": "催讨记录",
}

RELATION_WEIGHTS = (("contract", 30), ("bank_flow", 24), ("social_record", 20),
                    ("attendance", 12), ("badge", 10), ("chat_record", 8))
WAGE_WEIGHTS = (("payslip", 25), ("bank_flow", 24), ("tax_record", 22), ("contract", 16))
TERMINATION_WEIGHTS = (("termination_notice", 25), ("resignation_cert", 18), ("chat_record", 13))

# 争议类型 → 该类型的"关键证据"
SPECIFIC = {
    "unpaid_wage": (("bank_flow", 22), ("payslip", 20), ("wage_claim_log", 12)),
    "overtime": (("attendance", 22), ("chat_record", 10)),
    "annual_leave": (("attendance", 22),),
    "social_insurance": (("social_record", 22),),
    "noncompete": (("contract", 22),),
    "no_contract": (("badge", 14), ("bank_flow", 14), ("social_record", 14)),
    "termination": (("termination_notice", 20), ("resignation_cert", 16)),
}


def _best(have: set[str], weights) -> int:
    return max((w for t, w in weights if t in have), default=0)


def score(have: set[str], types: set[str] | None = None) -> dict:
    """证据强度：返回 {score, level, known, dimensions, gaps, strong}。

    `known=False` 表示用户根本没说自己手上有哪些材料——这时不给"弱"的评价，
    因为"没上传"不等于"没有"。这一维按中性 55 分算，并在 gaps 里直接问一句。
    """
    types = set(types or ())
    if not have:
        return {
            "score": 55,
            "level": "未评估",
            "known": False,
            "dimensions": {"劳动关系": 0, "工资标准": 0, "解除事实": 0, "争议关键证据": 0},
            "gaps": [
                "你还没说手上具体有哪些材料：按下面清单对着找一遍，"
                "有哪几样就在原话里补一句（例如「我有工资条和银行流水」），我再重算这一维"
            ],
            "strong": [],
        }

    relation = _best(have, RELATION_WEIGHTS)
    wage = _best(have, WAGE_WEIGHTS)
    is_term = "termination" in types
    if is_term:
        term = _best(have, TERMINATION_WEIGHTS)
    else:
        term = 18  # 不是解除类争议，这一维不构成门槛，按"不扣分"处理
    specific = max((_best(have, w) for t, w in SPECIFIC.items() if t in types), default=0)
    if not specific:
        specific = 8  # 没有类型相关证据：给底线分，不归零（清单里会提示补）

    raw = relation + wage + term + specific
    maximum = 30 + 25 + (25 if is_term else 18) + 22
    pct = max(0, min(100, round(raw * 100 / maximum)))
    level = "强" if pct >= 75 else ("中" if pct >= 50 else "弱")

    gaps = []
    if relation < 20:
        gaps.append("缺少能直接证明劳动关系的书证（合同/流水/社保记录），先补银行流水或社保记录")
    if wage < 20:
        gaps.append("工资标准证据偏弱：个税 App 的收入纳税明细可以替代工资条")
    if is_term and "termination_notice" not in have:
        gaps.append("没有书面解除通知：截图 HR 的微信/钉钉辞退消息，或提供离职证明")
    if "overtime" in types and "attendance" not in have:
        gaps.append("加班缺打卡/排班记录：可申请仲裁委向单位调取（单位掌握管理的由单位举证）")
    if "annual_leave" in types and "attendance" not in have:
        gaps.append("年休假缺请假/考勤记录：先导出 OA 或考勤系统的年假余额")
    if "unpaid_wage" in types and not ({"bank_flow", "payslip"} & have):
        gaps.append("欠薪缺工资条/流水：工资支付记录由单位保管，可要求对方提供")
    if "social_insurance" in types and "social_record" not in have:
        gaps.append("社保争议缺参保缴费记录：「电子社保卡」可查并截图")

    strong = [MATERIAL_LABELS[t] for t in MATERIAL_LABELS if t in have]
    return {
        "score": pct,
        "level": level,
        "known": True,
        "dimensions": {
            "劳动关系": relation,
            "工资标准": wage,
            "解除事实": term,
            "争议关键证据": specific,
        },
        "gaps": gaps,
        "strong": strong,
    }
