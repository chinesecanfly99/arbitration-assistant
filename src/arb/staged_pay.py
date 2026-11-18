"""Provisional wage review using stated facts and user-entered monthly records."""
from __future__ import annotations

import re
from decimal import Decimal

from .extract import _cn_int
from .spoken_wage import (
    AMOUNT, COMPENSATION_QUESTION, COUNT, ENDED_WORK, NO_PAY_AT_ALL, ONGOING_WORK,
    SPACE, WAGE, WAGE_UNPAID, clean_dictation, parse_amount,
)

MONTH = r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})"
YEAR_MONTH = rf"(?:20\d{{2}}(?:\s*年(?:的)?\s*{MONTH}\s*月(?:份)?|-\d{{1,2}}))"
DAY = r"(?:\s*\d{1,2}\s*[日号])?"
RANGE = re.compile(rf"({YEAR_MONTH}){DAY}\s*(?:到|至|(?i:to))\s*({YEAR_MONTH}){DAY}")
CORRECTION = re.compile(r"核对期间|欠薪期间|工资期间|核对区间|工资区间|更正(?:为|是)?|(?i:pay period)")
PAY_CONTEXT = re.compile(r"发(?:了|过)?工资|工资|发了|少发|欠付|欠薪|报酬|到账")
AGREED = re.compile(
    rf"(?:答应|承诺|约定|说好|合同写明)[^。！？；\n]{{0,36}}?"
    rf"(?:每个?月|月薪|工资|薪资)(?:是|为|有|约|按)?{SPACE}{AMOUNT}"
)
AGREED_FIRST = re.compile(rf"(?:答应|承诺|约定|说好){SPACE}{AMOUNT}{SPACE}(?:一?个?月|每个?月|/月)")
NET = re.compile(
    rf"(?:实际到账|到手|税后|净工资|实到|扣除五险一金(?:后)?){SPACE}"
    rf"(?:预计|大概|差不多|约|是|为|有|只|了|只有)*{SPACE}{AMOUNT}"
)
EXPECTED_NET = re.compile(
    rf"(?:预计|应当|应该|本该|说好的?|约定的?|正常)(?:每个?月)?{SPACE}{NET.pattern}"
    rf"|(?:应|预计|约定){SPACE}(?:净到手|到账){SPACE}{AMOUNT}"
)
AFTER_CONVERSION = re.compile(r"转正(?:以后|之后|后)|转为正式员工(?:以后|之后|后)")
INTERN_PHASE = r"(?:实习(?:期(?:间)?|阶段|那段(?:时间)?|的时候|的那几个月|的|时)|转正前)"
INTERN_MONTHLY = re.compile(
    rf"{INTERN_PHASE}{SPACE}(?:的|说好|约定|按|是|为|工资|报酬|补贴|每个?月|月薪){{0,8}}{SPACE}{AMOUNT}"
    rf"|{WAGE}{SPACE}(?:每个?月|按月){SPACE}{AMOUNT}(?=[^。！？；\n]{{0,12}}{INTERN_PHASE})"
)
INTERN_DURATION = re.compile(
    rf"(?:经过|干了|做了|先)?{SPACE}(?:实习(?:了|满)?{SPACE}({COUNT}{SPACE}个?月|半年)"
    rf"|({COUNT}{SPACE}个?月|半年)(?:的)?实习){SPACE}(?:以后|之后|后|才|就|并|然后){{0,3}}{SPACE}(?:正式)?转正"
)
ACTUAL_WAGE = re.compile(
    rf"(?:转正(?:后|以后|之后)|之后|后来|现在|给我的|实际){SPACE}"
    rf"(?:公司|单位|只|每个?月|给我的?|实发的?|发了?|给了?|的|是|税前){{0,8}}{SPACE}"
    rf"(?:{WAGE}{SPACE}(?:只|只有|就|是|为|按){{0,4}}{SPACE})?{AMOUNT}"
)
SCHOOL_ARRANGEMENT = re.compile(
    r"学校(?:统一|直接|老师|给我们?|要求)?(?:安排|派去|组织|要求我去)|教学实习|课程实习|三方实习协议"
)
EMPLOYER_ARRANGEMENT = re.compile(
    r"(?:公司|单位|人事|主管|领导|店长|经理)[^。！？；\n]{0,16}"
    r"(?:排班|管着我|管理我的工作|安排工作|分配任务|考勤|打卡|招聘|招进去|布置任务)"
    r"|实习[^。！？；\n]{0,10}(?:打卡|按排班|正常上班|全职上班)"
    r"|我(?:是)?自己(?:找的|应聘|投简历)|公司直接招(?:我|用)"
)
PAID_COUNT = re.compile(rf"(?:只|仅)(?:发|给|支付)(?:了|过)?\s*({MONTH}|两)\s*个?月(?:份)?的?工资")
PAID_MONTHS = re.compile(
    rf"(?:已经发了|已发|发了|已到账|也就是)\s*({YEAR_MONTH})"
    rf"((?:(?:\s*(?:、|和|与|及)?\s*){MONTH}\s*月(?:份)?)*)"
)
PAY_ROW = re.compile(
    r"^【工资核对】(20\d{2}-(?:0[1-9]|1[0-2]))\s+应到账\s+"
    r"(\d{1,8}(?:\.\d{1,2})?)\s+元，实际到账\s+(\d{1,8}(?:\.\d{1,2})?)\s+元。?$",
    re.MULTILINE,
)
EVIDENCE = re.compile(r"^【补证：(用工|工资约定|付款|考勤)】([^\n]{1,400})$", re.MULTILINE)
EVIDENCE_REFERENCES = {
    "用工": r"劳动合同|转正(?:通知|邮件|审批|证明)|入职通知",
    "工资约定": r"工资条|工资单|薪资约定|薪资通知|工资聊天",
    "付款": r"银行流水|转账记录|到账截图",
    "考勤": r"考勤记录|排班表|打卡记录",
}


def _month_key(value: str) -> str | None:
    match = re.match(r"(20\d{2})(?:\s*年(?:的)?\s*|-)\s*(.+?)(?:\s*月份?)?$", value)
    if not match:
        return None
    year, raw_month = match.groups()
    month = _cn_int(raw_month)
    return f"{year}-{month:02d}" if month and 1 <= month <= 12 else None


def _event_month(story: str, event: str) -> str | None:
    patterns = (
        rf"({YEAR_MONTH}){DAY}{SPACE}(?:并|正式|开始|就|才)?{SPACE}(?:{event})",
        rf"(?:{event})(?:日期|时间|起始)?\s*(?:是|为|从|在|于|[:：])\s*({YEAR_MONTH})",
    )
    matches = [match for pattern in patterns for match in re.finditer(pattern, story)]
    return _month_key(max(matches, key=lambda match: match.end())[1]) if matches else None


def _money(pattern: re.Pattern, story: str) -> Decimal | None:
    amounts = [value for match in pattern.finditer(story) if (value := parse_amount(next(g for g in match.groups() if g))) is not None]
    return amounts[-1] if amounts else None


def _month_range(story: str) -> tuple[str | None, str | None]:
    spans = []
    for match in RANGE.finditer(story):
        before = story[max(0, match.start() - 20):match.start()]
        after = story[match.end():match.end() + 32]
        if CORRECTION.search(before) or PAY_CONTEXT.search(after):
            spans.append(tuple(_month_key(value) for value in match.groups()))
    return spans[-1] if spans else (None, None)


def _period_months(start: str, end: str) -> list[str]:
    start_year, start_month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    first = start_year * 12 + start_month - 1
    last = end_year * 12 + end_month - 1
    return [f"{n // 12:04d}-{n % 12 + 1:02d}" for n in range(first, last + 1)] if 0 <= last - first < 36 else []


def _stated_paid_months(story: str) -> list[str]:
    paid = set()
    for first, additional in PAID_MONTHS.findall(story):
        key = _month_key(first)
        if not key:
            continue
        paid.add(key)
        for raw_month in re.findall(rf"({MONTH})\s*月(?:份)?", additional):
            month = _cn_int(raw_month)
            if month and 1 <= month <= 12:
                paid.add(f"{key[:4]}-{month:02d}")
    return sorted(paid)


def _evidence(story: str) -> dict[str, list[str]]:
    recorded: dict[str, list[str]] = {}
    for kind, note in EVIDENCE.findall(story):
        notes = recorded.setdefault(kind, [])
        if note.strip() and note.strip() not in notes:
            notes.append(note.strip())
    for kind, names in EVIDENCE_REFERENCES.items():
        if kind in recorded:
            continue
        match = re.search(
            rf"(?:我(?:手里|这边)?有|手上有|手里有|留着|保留了|已保存|可提供|能提供|我拿到了|我签了)"
            rf"{SPACE}(?:一份|一张|公司发的|自己的|这个)?{SPACE}({names})"
            rf"|({names})(?:上|里|里面)?(?:写着|写了|载明|显示|能证明)", story,
        )
        if match:
            recorded[kind] = [next(value for value in match.groups() if value)]
    return recorded


def _oral_pay(narrative: str) -> dict:
    employment_status = None
    for match in re.finditer(rf"({ONGOING_WORK.pattern})|({ENDED_WORK.pattern})", narrative):
        employment_status = "ongoing" if match[1] else "ended"

    durations = list(INTERN_DURATION.finditer(narrative))
    duration = durations[-1] if durations else None
    spoken_duration = (duration[1] or duration[2]) if duration else ""
    count = re.match(COUNT, spoken_duration)
    internship_months = 6 if spoken_duration == "半年" else _cn_int(count[0]) if count else None
    internship = _event_month(narrative, r"开始实习|(?:在|去|进|到)[^，。！？；\n]{1,24}?实习|实习")
    conversion = _event_month(narrative, "转正|转为正式员工|转为全职")
    inferred = False
    if internship and internship_months and not conversion:
        year, month = map(int, internship.split("-"))
        offset = year * 12 + month - 1 + internship_months
        conversion = f"{offset // 12:04d}-{offset % 12 + 1:02d}"
        inferred = True

    internship_pay = _money(INTERN_MONTHLY, narrative)
    internship_unpaid = False
    for match in re.finditer(r"实习(?!转正)|转正前", narrative):
        context = re.split(r"转正(?:后|以后|之后|[。！？?])|正式工作后|[；;\n]", narrative[match.end():match.end() + 58], maxsplit=1)[0]
        if WAGE_UNPAID.search(context) or NO_PAY_AT_ALL.search(context):
            internship_unpaid = True
            break
    agreed = _money(AGREED, narrative) or _money(AGREED_FIRST, narrative)
    expected_mentions = list(EXPECTED_NET.finditer(narrative))
    nets = [
        (match.start(), parse_amount(match[1])) for match in NET.finditer(narrative)
        if not any(expected.start() <= match.start() < expected.end() for expected in expected_mentions)
    ]
    net = nets[-1][1] if nets else None
    expected_net = _money(EXPECTED_NET, narrative)
    boundary = duration.end() if duration else None
    if boundary is None:
        transition = AFTER_CONVERSION.search(narrative)
        boundary = transition.end() if transition else None
    actual_wage = _money(ACTUAL_WAGE, narrative[boundary:] if duration and boundary else narrative)
    if expected_net is None and agreed and boundary is not None and len(nets) > 1 and nets[0][0] < boundary <= nets[-1][0]:
        expected_net = nets[0][1]
    school = SCHOOL_ARRANGEMENT.search(narrative)
    employer = EMPLOYER_ARRANGEMENT.search(narrative)
    arrangement = "employer" if employer else "school" if school else None
    if school and employer:
        arrangement = "both"
    return {
        "internship": internship, "internship_months": internship_months,
        "conversion": conversion, "conversion_inferred": inferred,
        "agreed": agreed, "net": net, "expected_net": expected_net, "actual_wage": actual_wage,
        "internship_pay": internship_pay, "internship_unpaid": internship_unpaid,
        "employment_status": employment_status, "arrangement": arrangement,
        "asks_compensation": bool(COMPENSATION_QUESTION.search(narrative)),
    }


def review_staged_pay(story: str) -> dict:
    narrative = clean_dictation("\n".join(line for line in story.splitlines() if not line.startswith(("【补证：", "【工资核对】"))))
    oral = _oral_pay(narrative)
    conversion = oral["conversion"]
    first, last = _month_range(narrative)
    paid = _stated_paid_months(narrative)
    count = PAID_COUNT.search(narrative)
    evidence = _evidence(story)
    monthly = {}
    for month, due, received in PAY_ROW.findall(story):
        expected, actual = Decimal(due), Decimal(received)
        monthly[month] = {"due": expected, "received": actual, "difference": max(expected - actual, Decimal(0))}

    period = _period_months(first, last) if first and last and first <= last else []
    reversed_dates = bool(first and last and first > last)
    post_conversion = bool(conversion and first and first >= conversion)
    paid_count = _cn_int(count[1]) if count else None
    payment_conflict = bool(paid and (paid_count not in (None, len(paid)) or (period and not set(paid) <= set(period))))
    unreviewed = (
        sorted(set(period) - set(paid) - set(monthly))
        if post_conversion and paid and not payment_conflict else []
    )
    gaps = []
    if not (oral["arrangement"] or evidence.get("用工") or evidence.get("考勤")):
        gaps.append("employment")
    has_pay_comparison = (
        (oral["agreed"] is not None and (oral["actual_wage"] is not None or oral["net"] is not None))
        or (oral["expected_net"] is not None and oral["net"] is not None)
    )
    has_internship_amount = oral["internship_unpaid"] and oral["internship_pay"] is not None
    oral["internship_estimate"] = (
        oral["internship_pay"] * oral["internship_months"]
        if has_internship_amount and oral["internship_months"] else None
    )
    oral["net_estimate"] = (
        max(oral["expected_net"] - oral["net"], Decimal(0))
        if oral["expected_net"] is not None and oral["net"] is not None else None
    )
    if reversed_dates or (not period and not (monthly or has_pay_comparison or (has_internship_amount and oral["internship_months"]))):
        gaps.append("period")
    if payment_conflict or (not monthly and not (has_pay_comparison or has_internship_amount)):
        gaps.append("pay")
    return {
        **oral,
        "paid_months": paid,
        "paid_count": paid_count,
        "first": first,
        "last": last,
        "reversed_dates": reversed_dates,
        "payment_conflict": payment_conflict,
        "unreviewed": unreviewed,
        "evidence": evidence,
        "monthly": dict(sorted(monthly.items())),
        "difference": sum((row["difference"] for row in monthly.values()), Decimal(0)),
        "gaps": gaps,
    }
