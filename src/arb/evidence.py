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
