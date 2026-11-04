"""仲裁时效内核（《劳动争议调解仲裁法》第 27 条）。

第 27 条要点（写进输出里，让用户看见法律原文逻辑）：
1. 一般时效：**一年**，从当事人知道或者应当知道其权利被侵害之日起计算。
2. 中断：向对方主张权利、向有关部门请求救济、对方同意履行义务而中断，中断后重新计算。
3. 中止：因不可抗力或其他正当理由不能在期间内申请，中止原因消除之日起继续计算。
4. 拖欠劳动报酬特别规则：**劳动关系存续期间**因拖欠劳动报酬发生争议，不受一年限制；
   但劳动关系终止的，应自终止之日起一年内提出。

注意：这一模块同样是纯规则，不经过大模型——时效算错会直接害人。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .dates import add_years

CLAIM_DISMISSAL = "dismissal"
CLAIM_WAGE = "wage"
CLAIM_OVERTIME = "overtime"
CLAIM_ANNUAL_LEAVE = "annual_leave"
CLAIM_DOUBLE_WAGE = "double_wage"

CLAIM_LABELS = {
    CLAIM_DISMISSAL: "解除/辞退相关请求（N、2N）",
    CLAIM_WAGE: "拖欠劳动报酬",
    CLAIM_OVERTIME: "加班费",
    CLAIM_ANNUAL_LEAVE: "未休年休假工资",
    CLAIM_DOUBLE_WAGE: "未签书面合同二倍工资",
}

# 不同请求"权利被侵害之日"的默认起算口径（起争议时以当地仲裁委口径为准）
DEFAULT_ANCHOR_HINT = {
    CLAIM_DISMISSAL: "劳动合同解除或终止之日",
    CLAIM_WAGE: "应发而未发工资之日（一般按发薪日）",
    CLAIM_OVERTIME: "应发而未发加班费之日（一般按对应发薪日）",
    CLAIM_ANNUAL_LEAVE: "劳动关系终止之日（部分口径为次年度末）",
    CLAIM_DOUBLE_WAGE: "应订立书面合同而未订立之月起",
}


@dataclass
class LimitationResult:
    claim_type: str
    label: str
    applicable: bool          # False 表示"存续期间不受时效限制"
    anchor: Optional[date]
    anchor_hint: str
    deadline: Optional[date]
    days_left: Optional[int]
    expired: bool
    urgent: bool              # 剩余 <= 30 天
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "claim_type": self.claim_type,
            "label": self.label,
            "applicable": self.applicable,
            "anchor": self.anchor.isoformat() if self.anchor else None,
            "anchor_hint": self.anchor_hint,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "days_left": self.days_left,
            "expired": self.expired,
            "urgent": self.urgent,
            "note": self.note,
        }


def limitation(
    claim_type: str,
    anchor: Optional[date],
    today: date,
    employment_ongoing: bool = False,
    interrupted_on: Optional[date] = None,
    years: int = 1,
) -> LimitationResult:
    """计算一项请求的仲裁时效。

    employment_ongoing: 劳动关系是否仍然存续（只对拖欠劳动报酬有意义）
    interrupted_on:    最近一次主张权利/对方同意履行的日期，会重新起算
    """
    label = CLAIM_LABELS.get(claim_type, claim_type)
    hint = DEFAULT_ANCHOR_HINT.get(claim_type, "")

    # 特别规则：劳动关系存续期间追讨劳动报酬，不受一年时效限制
    if claim_type == CLAIM_WAGE and employment_ongoing:
        return LimitationResult(
            claim_type=claim_type,
            label=label,
            applicable=False,
            anchor=None,
            anchor_hint=hint,
            deadline=None,
            days_left=None,
            expired=False,
            urgent=False,
            note="劳动关系存续期间追讨拖欠工资不受一年时效限制；但劳动关系一旦终止，"
            "须自终止之日起一年内提出——别拖到离职后再过一年。",
        )

    if anchor is None:
        return LimitationResult(
            claim_type=claim_type,
            label=label,
            applicable=True,
            anchor=None,
            anchor_hint=hint,
            deadline=None,
            days_left=None,
            expired=False,
            urgent=False,
            note="尚未确定权利被侵害之日，无法计算时效；请先补全关键日期。",
        )

    start = interrupted_on if interrupted_on and interrupted_on > anchor else anchor
    deadline = add_years(start, years)
    days_left = (deadline - today).days
    expired = days_left < 0
    urgent = 0 <= days_left <= 30

    note = ""
    if interrupted_on and interrupted_on > anchor:
        note = f"因 {interrupted_on} 曾主张权利，时效从该日重新起算。"
    if expired:
        note += (
            "已超过仲裁时效。仍可提交申请，但对方以时效抗辩时可能被驳回；"
            "建议同时咨询 12348 或当地法律援助中心，评估是否存在中断/中止情形。"
        )
    elif urgent:
        note += "剩余不足 30 天，请立即提交仲裁申请。"

    return LimitationResult(
        claim_type=claim_type,
        label=label,
        applicable=True,
        anchor=start,
        anchor_hint=hint,
        deadline=deadline,
        days_left=days_left,
        expired=expired,
        urgent=urgent,
        note=note,
    )


def analyze(
    end_date: Optional[date],
    today: date,
    employment_ongoing: bool = False,
    anchors: Optional[dict] = None,
    interrupted_on: Optional[date] = None,
) -> list[LimitationResult]:
    """一次算清所有常见请求的时效。

    end_date: 劳动关系终止日（仍在职则传 None 且 employment_ongoing=True）
    anchors:  可覆盖某类请求的起算日，如 {"dismissal": date(2025,3,1)}
    """
    anchors = anchors or {}
    out: list[LimitationResult] = []

    for ct in [
        CLAIM_DISMISSAL,
        CLAIM_WAGE,
        CLAIM_OVERTIME,
        CLAIM_ANNUAL_LEAVE,
        CLAIM_DOUBLE_WAGE,
    ]:
        if ct in anchors:
            a = anchors[ct]
        elif ct in (CLAIM_DISMISSAL, CLAIM_ANNUAL_LEAVE):
            a = end_date
        else:
            # 工资/加班费/二倍工资：默认按劳动关系终止日粗算（保守，宁可早不能晚）
            a = end_date
        out.append(
            limitation(
                ct,
                anchor=a,
                today=today,
                employment_ongoing=employment_ongoing and ct == CLAIM_WAGE,
                interrupted_on=interrupted_on,
            )
        )
    return out
