"""Provisional wage review using stated facts and user-entered monthly records."""
from __future__ import annotations

import re
from decimal import Decimal

from .extract import _cn_int

MONTH = r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})"
YEAR_MONTH = rf"(?:20\d{{2}}(?:\s*年(?:的)?\s*{MONTH}\s*月(?:份)?|-\d{{1,2}}))"
DAY = r"(?:\s*\d{1,2}\s*[日号])?"
RANGE = re.compile(rf"({YEAR_MONTH}){DAY}\s*(?:到|至|(?i:to))\s*({YEAR_MONTH}){DAY}")
CORRECTION = re.compile(r"核对期间|欠薪期间|工资期间|核对区间|工资区间|更正(?:为|是)?|(?i:pay period)")
PAY_CONTEXT = re.compile(r"发(?:了|过)?工资|工资|发了|少发|欠付|欠薪|报酬|到账")
AMOUNT = r"((?:\d{1,7}(?:,\d{3})*(?:\.\d{1,2})?\s*(?:万|千)?|[一二两三四五六七八九十]{1,3}(?:万|千|百))(?:\s*(?:元|块(?:钱)?))?)"
AGREED = re.compile(
    rf"(?:答应|承诺|约定|说好|合同写明)[^。！？；\n]{{0,36}}?"
    rf"(?:每个?月|月薪|工资)(?:是|为|有|约)?\s*{AMOUNT}"
)
NET = re.compile(rf"(?:实际发放|实际到账|扣除五险一金|到手|实发)[^。，！？；\n\d一二两三四五六七八九十]{{0,16}}{AMOUNT}")
PAID_COUNT = re.compile(rf"(?:只|仅)(?:发|给|支付)(?:了|过)?\s*({MONTH}|两)\s*个?月(?:份)?的?工资")
PAID_MONTHS = re.compile(
    rf"(?:已经发了|已发|发了|已到账|也就是)\s*({YEAR_MONTH})"
    rf"((?:(?:\s*(?:、|和|与|及|[，,])?\s*){MONTH}\s*月(?:份)?)*)"
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
    matches = re.findall(rf"({YEAR_MONTH}){DAY}\s*(?:并|正式|开始)?\s*(?:{event})", story)
    matches += re.findall(rf"(?:{event})(?:日期|时间|起始)?\s*(?:是|为|从|在|[:：])\s*({YEAR_MONTH})", story)
    return _month_key(matches[-1]) if matches else None


def _money(pattern: re.Pattern, story: str) -> Decimal | None:
    matches = pattern.findall(story)
    if not matches:
        return None
    raw = re.sub(r"[\s,元块钱]", "", matches[-1])
    multiplier = {"万": 10000, "千": 1000, "百": 100}.get(raw[-1])
    if multiplier:
        raw = raw[:-1]
    if re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        return Decimal(raw) * (multiplier or 1)
    number = _cn_int(raw)
    return Decimal(number * (multiplier or 1)) if number is not None else None


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
        match = re.search(rf"(?:我有|保留了|已保存|可提供|能提供|我拿到了)\s*(?:一份|一张|公司发的|自己的)?\s*({names})", story)
        if match:
            recorded[kind] = [match.group(1)]
    return recorded


def review_staged_pay(story: str) -> dict:
    internship = _event_month(story, "开始实习|实习")
    conversion = _event_month(story, "转正|转为正式员工|转为全职")
    narrative = "\n".join(line for line in story.splitlines() if not line.startswith(("【补证：", "【工资核对】")))
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
    if not conversion or ("用工" not in evidence and "考勤" not in evidence):
        gaps.append("employment")
    if reversed_dates or not period:
        gaps.append("period")
    if not monthly or unreviewed or payment_conflict:
        gaps.append("pay")
    return {
        "internship": internship,
        "conversion": conversion,
        "agreed": _money(AGREED, narrative),
        "net": _money(NET, narrative),
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
