"""Assess separate claims when mixed facts cannot support a single total."""
from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal

from .calc import DAILY_WAGE_DIVISOR, ClaimInput, Policy, economy_compensation
from .dates import months_between
from .extract import _cn_int
from .spoken_wage import AMOUNT, COUNT, SPACE, clean_dictation, parse_amount, stated_unpaid_total

START = r"(?:入职|进公司|进厂|开始上班|开始工作|工作开始)"
HIRE_DATE = re.compile(
    rf"(20\d{{2}})年(?!\d{{1,2}}[日号])(?:(\d{{1,2}})月(?:(\d{{1,2}})[日号])?)?"
    rf"(?:开始)?(?:在(?:这家|该|这|原)?公司)?{SPACE}{START}"
    rf"|(?:入职(?:日期|时间|年份)?|开始工作(?:日期|时间)?){SPACE}(?:是|为|在|于|从)?{SPACE}"
    r"(20\d{2})年(?:(\d{1,2})月(?:(\d{1,2})[日号])?)?"
)
TENURE = re.compile(rf"(?:工作|上班|入职|做|干)(?:了|满|快|有|约|大约)?{SPACE}({COUNT}){SPACE}个?年")
PARTIAL_PAY_PERIOD = re.compile(
    r"(?:工作|上班|干|做)(?:了|到)?(?:只有|只|才)?(?:了)?半(?:个)?月"
    r"|(?:只|仅|才)(?:工作|上班|干|做)(?:了)?半(?:个)?月"
    r"|(?:工作|上班|干|做)(?:到|至)月中|只干到.{0,6}月中"
)
PAY_DAYS = re.compile(rf"(?:应计薪|计薪|应付工资的){SPACE}(?:是|为|有|共|合计)?{SPACE}({COUNT}|\d{{1,2}}\.\d)\s*天")
# A same-period payment figure must be tied to the current wage dispute.
PARTIAL_RECEIVED = re.compile(rf"(?:本期|当月|该月|这个月|最后(?:半个|一个|一)月)(?:工资)?{SPACE}(?:实际已发|已发|实发|已付|已领)(?:了)?{SPACE}{AMOUNT}")
NONE_RECEIVED = re.compile(
    r"(?:本期|当月|该月|这个月|最后(?:半个|一个|一)月)(?:的)?(?:工资)?(?:也|都|还|仍|一分)?(?:没有|没|未)(?:发|给|付|结|到账)"
    r"|(?:工资|薪水)(?:一分(?:钱)?都|一分(?:钱)?也)(?:没有|没)(?:发|给|付)"
    r"|(?:工资|薪水)(?:也|都|还|仍)?(?:没有|没|未)(?:发|给|付|结)(?=[，。；！？\n]|$)"
)
ACCIDENT_INJURY = re.compile(r"(?:事故|上班|工作中|工作时|工地|车间)[^。！？；\n]{0,26}(?:受伤|伤了|摔伤|被砸|骨折)|工伤|停工留薪")
INJURY_WITH_DISMISSAL = re.compile(r"(?:受伤|伤了|伤后)[^。！？；\n]{0,24}(?:开除|辞退|裁掉|解除|不用来)")
NOTICE_AT_MONTH_END = re.compile(r"(?:月底|月末)(?:才|时|公司|单位|人事){0,3}(?:说|告知|通知|打电话)")
EFFECTIVE_DATE = re.compile(
    rf"(?:解除生效日期|解除日期|解除时间|正式解除日期){SPACE}(?:是|为)?{SPACE}"
    r"(20\d{2})年(\d{1,2})月(\d{1,2})[日号]"
)
LAST_WORK_DAY = re.compile(
    rf"(?:(20\d{{2}})年)?(\d{{1,2}})月(\d{{1,2}})[日号]{SPACE}(?:走的|离开公司|是最后工作日)"
)
REASONS = {
    "capability": r"不能胜任|工作能力|能力不足|不胜任|绩效不达标|考核不合格",
    "layoff": r"裁员|减员|裁撤|经济性裁减",
    "age": r"(?:年纪|年龄|岁数)(?:太|偏)?大",
    "injury": r"因.{0,8}受伤|受伤之后|受伤后|停工留薪",
}
DISMISSAL = {"illegal_dismissal", "severance", "mutual_agreement"}


def _hire_window(text: str) -> tuple[date, date] | None:
    windows = []
    for match in HIRE_DATE.finditer(text):
        parts = match.groups()
        year, month, day = parts[:3] if parts[0] else parts[3:]
        year = int(year)
        try:
            if day:
                d = date(year, int(month), int(day))
                windows.append((d, d))
            elif month:
                m = int(month)
                windows.append((date(year, m, 1), date(year, m, calendar.monthrange(year, m)[1])))
            else:
                windows.append((date(year, 1, 1), date(year, 12, 31)))
        except ValueError:
            continue
    return windows[-1] if windows else None


def _elapsed_start(
    text: str, fields: dict, evidence: dict, sources: dict,
) -> tuple[tuple[date, date] | None, bool, int | None]:
    reported_years = TENURE.search(text)
    years = _cn_int(reported_years[1]) if reported_years else None
    start, end = fields.get("hire_date"), fields.get("end_date")
    inferred = "推定" in evidence.get("hire_date", "") and sources.get("hire_date") != "confirmed"
    start_window = _hire_window(text)
    if sources.get("hire_date") == "confirmed" and start:
        return (start, start), False, years
    if start_window is None and start and not inferred:
        start_window = (start, start)
    inconsistent = bool(
        years and end and start_window
        and (months_between(start_window[0], end) < (years - 1) * 12
             or months_between(start_window[1], end) > (years + 1) * 12)
    )
    inferred_conflict = bool(
        years and start_window is None and
        (not start or not end or (inferred and abs(months_between(start, end) - years * 12) > 12))
    )
    return start_window, inconsistent or inferred_conflict, years


def _pay_review(text: str, fields: dict, sources: dict, partial: bool) -> dict:
    days_token = list(PAY_DAYS.finditer(text))
    days = parse_amount(days_token[-1][1]) if days_token else None
    days = days if days is not None and Decimal(0) < days <= 31 else None
    received_token = list(PARTIAL_RECEIVED.finditer(text))
    received = parse_amount(received_token[-1][1]) if received_token else None
    if received is None and NONE_RECEIVED.search(text):
        received = Decimal(0)

    known_total = (
        fields.get("unpaid_wages") if sources.get("unpaid_wages") == "confirmed"
        else stated_unpaid_total(text)
    )
    wage = fields.get("monthly_wage")
    due = round(Decimal(str(wage)) * days / Decimal(str(DAILY_WAGE_DIVISOR)), 2) if wage and days is not None else None
    if known_total is not None:
        difference = known_total
    elif due is not None and received is not None:
        difference = max(due - received, Decimal(0))
    else:
        difference = None
    return {"partial": partial, "days": days, "received": received, "due": due,
            "difference": difference, "stated_total": known_total is not None}


def _recognition_status(text: str) -> str | None:
    if re.search(r"不予认定(?:为)?工伤|认定决定.{0,6}不属于工伤", text):
        return "denied"
    if re.search(r"(?:没|尚未|还未|还没)(?:提出|提交|申请)(?:工伤|认定)|工伤认定.{0,6}(?:还没|尚未)(?:申请|提交)", text):
        return "not_filed"
    if re.search(r"已申请|已提交|正在申请|正在认定", text) and "工伤" in text:
        return "pending"
    if re.search(r"已认定.{0,3}工伤|已拿到工伤认定书|人社部门认定为工伤", text):
        return "recognized"
    return None


def review_issues(story: str, fields: dict, evidence: dict, sources: dict, causes: list[str],
                  administrative: str | None, city_average: float | None) -> dict | None:
    text = clean_dictation(story)
    dismissal = bool(DISMISSAL.intersection(causes))
    unpaid = "unpaid_wage" in causes
    injury = administrative == "工伤" or bool(ACCIDENT_INJURY.search(text) or INJURY_WITH_DISMISSAL.search(text))
    partial = unpaid and bool(PARTIAL_PAY_PERIOD.search(text) or PAY_DAYS.search(text))
    window, suspect_start, years = _elapsed_start(text, fields, evidence, sources)
    uncertain_year = window and window[0].year == window[1].year and (window[1] - window[0]).days >= 364
    reasons = [key for key, pattern in REASONS.items() if re.search(pattern, text)] if dismissal else []
    competing_reasons = len(reasons) > 1
    if not causes or not (
        administrative or partial or (dismissal and (uncertain_year or (years and suspect_start) or competing_reasons))
        or (injury and dismissal and unpaid)
    ):
        return None

    end = fields.get("end_date")
    if sources.get("end_date") == "assumed" or (
        sources.get("end_date") != "confirmed" and re.search(r"推定|仍在职|按月末计", evidence.get("end_date", ""))
    ):
        end = None
    departure = end
    last_day = list(LAST_WORK_DAY.finditer(text))
    if end and last_day:
        last_day = last_day[-1]
        year, month, day = last_day.groups()
        prior_years = re.findall(r"(20\d{2})年", text[:last_day.start()])
        try:
            departure = date(int(year or (prior_years[-1] if prior_years else end.year)), int(month), int(day))
        except ValueError:
            pass
    effective = list(EFFECTIVE_DATE.finditer(text))
    if effective:
        try:
            end = date(*(int(value) for value in effective[-1].groups()))
        except ValueError:
            pass
    end_needs_review = bool(dismissal and departure and not effective and NOTICE_AT_MONTH_END.search(text) and departure.day < 25)
    if end_needs_review:
        end = departure
    recognition = _recognition_status(text) if injury else None
    scenarios = None
    wage = fields.get("monthly_wage")
    if dismissal and window and end and end >= window[1] and wage and (not suspect_start or uncertain_year):
        inputs = [ClaimInput(start, end, wage, social_avg_wage=city_average) for start in (window[1], window[0])]
        amounts = [economy_compensation(inp, Policy()).amount for inp in inputs]
        scenarios = {"n": amounts, "2n": [round(amount * 2, 2) for amount in amounts]}
    pay = _pay_review(text, fields, sources, partial) if unpaid else None
    prompts = []
    if dismissal and (window is None or window[0] != window[1] or suspect_start):
        prompts.append("hire_date")
    if dismissal and not end:
        prompts.append("dismissal_date")
    if unpaid and pay["difference"] is None:
        prompts.append("paid_days" if (partial and pay["days"] is None) else "unpaid_total")
    if end_needs_review:
        prompts.append("effective_date")
    if (dismissal or unpaid) and not wage:
        prompts.append("gross_pay")
    if injury and not recognition:
        prompts.append("injury_recognition")
    return {
        "dismissal": dismissal, "pay": pay, "injury": injury, "administrative": administrative,
        "start_window": window, "suspect_start": bool(suspect_start), "reported_years": years,
        "end": end, "departure": departure, "end_needs_review": end_needs_review,
        "recognition": recognition, "monthly_wage": wage, "city_average": city_average,
        "scenarios": scenarios, "reasons": reasons, "prompts": prompts,
    }


def review_lines_zh(review: dict) -> list[str]:
    lines = []
    pay = review["pay"]
    if pay and pay["difference"] is None:
        lines.append("欠薪可按本期应发与同口径已发金额核对。")
    elif pay:
        lines.append(f"本期工资差额按所填信息核对为 {pay['difference']:,.2f} 元。")
    scenarios = review["scenarios"]
    if scenarios:
        for key, caption in (("n", "符合经济补偿条件时"), ("2n", "被认定违法解除且适用赔偿金时")):
            low, high = scenarios[key]
            estimate = f"{low:,.2f}" if low == high else f"{low:,.2f} 至 {high:,.2f}"
            lines.append(f"{caption}，按口述工资和日期暂估 {estimate} 元。")
        lines.append("N 和 2N 对应不同情形，只取适用的一项。")
    elif review["dismissal"]:
        lines.append("解除争议需核对工龄、解除生效日、当期工资基数和解除理由。")
    if review["injury"]:
        lines.append("受伤相关的工伤认定向当地人社部门办理，可按认定和治疗资料核对待遇。")
    return lines
