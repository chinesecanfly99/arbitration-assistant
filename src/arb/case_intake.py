"""Additional facts that commonly appear in a spoken case description."""
from __future__ import annotations

import re

from .extract import _cn_int
from .spoken_wage import AMOUNT, CASE_GOAL, COUNT, ONGOING_WORK, SPACE, WAGE, clean_dictation, parse_amount

MONEY_LEAD = rf"{SPACE}(?:的大概|大约|大概|约|是|为|有|按)?{SPACE}"
BEFORE_TAX = re.compile(rf"(?:税前(?:月薪|工资)?|每月应发|应发工资){MONEY_LEAD}{AMOUNT}")
AFTER_TAX = re.compile(rf"(?:税后(?:月薪|工资)?|到手|实际到账){MONEY_LEAD}{AMOUNT}")
MONTHLY_PAY = re.compile(rf"(?:月薪|每个?月工资|月工资|每个?月){MONEY_LEAD}{AMOUNT}")
UNPAID_MONTHS = re.compile(
    rf"(?:拖欠|欠了?|拖了){SPACE}(?:我|我们|大概|约)?{SPACE}({COUNT}){SPACE}个?月{SPACE}(?:的)?{WAGE}"
    rf"|({COUNT}){SPACE}个?月{SPACE}(?:的)?{WAGE}{SPACE}(?:还|都|一直|至今)?{SPACE}(?:没有|没|未)(?:发|给|结)"
    rf"|({COUNT}){SPACE}个?月{SPACE}(?:都|一直)?(?:没|没有)(?:发|给)(?:我|我们)?{SPACE}{WAGE}"
)
LEAVE_DAYS = re.compile(
    rf"(?:年假|年休假){SPACE}(?:还(?:剩|有)|剩下|少了|没休的(?:有|是)?){SPACE}({COUNT}){SPACE}天"
    rf"|(?:还剩|有|剩下)?{SPACE}({COUNT}){SPACE}天{SPACE}(?:的)?(?:年假|年休假){SPACE}(?:没休|未休|没用)"
)
OVERTIME_DESCRIPTION = re.compile(
    r"(?:工作日|平时|下班后|每天|周[六日]|周末|星期[六日]|休息日|法定节假日|国庆|春节)"
    r"[^。！？；\n]{0,12}?(?:加班|加了|干到|做到|还要上班|照常上班|上班)"
    r"[^。，、！？；\n]{0,16}"
)
OVERTIME_TOTAL = re.compile(
    r"(工作日|平时|休息日|周末|周[六日]|法定节假日|法定假日)"
    rf"{SPACE}(?:延时)?(?:加班|多干了?){SPACE}(?:合计|总共|累计|一共|共){SPACE}({COUNT}|\d{{3,4}}){SPACE}个?小时"
)
REST_DAY = re.compile(r"周末|周[六日]|星期[六日]|休息日|双休日")
TIME_OFF = re.compile(r"没补休|没有补休|没给我补休|有过补休|补休过|安排了?补休|给我补休|调休过|没调休|没有调休")
REST_DAYS_MADE_UP = re.compile(r"(?:周末|周[六日]|休息日)[^，。！？\n]{0,15}(?:都|全部)已(?:经)?(?:补休|调休)(?:完|结束|过)")
NOTICE_REASON = re.compile(r"(?:说|通知上写|理由是|原因是|因为)(?:我)?(?:绩效|能力|考核|违纪|旷工|搬迁|裁员|部门撤|经营|怀孕|试用)|没(?:有)?(?:给|说明|说)(?:任何)?理由")
WRITTEN_NOTICE = re.compile(r"口头通知|口头(?:辞退|说)|书面通知|解除通知|离职通知|微信.{0,8}(?:让我走|通知|不用来了)")


def _matched_amount(pattern: re.Pattern, text: str):
    for match in reversed(list(pattern.finditer(text))):
        raw = match[1]
        value = parse_amount(raw)
        if value is not None and (value >= 100 or re.search(r"元|块|万|千|百", raw)):
            if not re.match(r"\s*(?:天|个?月|周|小时|次)", text[match.end():]):
                return value
    return None


def read_case_facts(story: str) -> dict:
    text = clean_dictation(story)
    wage_months = UNPAID_MONTHS.search(text)
    leave = LEAVE_DAYS.search(text)
    overtime = OVERTIME_DESCRIPTION.search(text)
    overtime_hours = {}
    for match in OVERTIME_TOTAL.finditer(text):
        group = "holiday" if match[1].startswith("法定") else "restday" if REST_DAY.search(match[1]) else "workday"
        overtime_hours[f"overtime_{group}_hours"] = _cn_int(match[2])
    return {
        "before_tax": _matched_amount(BEFORE_TAX, text),
        "after_tax": _matched_amount(AFTER_TAX, text),
        "monthly_pay": _matched_amount(MONTHLY_PAY, text),
        "wage_months": _cn_int(next(value for value in wage_months.groups() if value)) if wage_months else None,
        "leave_days": _cn_int(leave[1] or leave[2]) if leave else None,
        "overtime": overtime[0] if overtime else None,
        "overtime_hours": overtime_hours,
        "rest_day": bool(REST_DAY.search(text)),
        "time_off": bool(TIME_OFF.search(text)),
        "restday_compensated": bool(REST_DAYS_MADE_UP.search(text)),
        "reason": bool(NOTICE_REASON.search(text)),
        "notice": bool(WRITTEN_NOTICE.search(text)),
        "ongoing": bool(ONGOING_WORK.search(text)),
        "goal": bool(CASE_GOAL.search(text)),
        "late_contract": bool(re.search(r"后补签|后来签|才签|补签|补给我签", text)),
        "settlement_paid": bool(re.search(r"协议[^。！？；\n]{0,28}(?:没(?:有)?付|没(?:有)?给|未付|实际给|仅支付|只付|付清|给过|到账)", text)),
        "adverse_action": bool(re.search(r"调岗|降薪|扣工资|让我离开|不要我上班|不给休产假|不批产假|辞退", text)),
    }
