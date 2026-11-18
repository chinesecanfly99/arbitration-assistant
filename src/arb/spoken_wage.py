"""Signals shared by wage intake and the staged wage review."""
from __future__ import annotations

import re
from decimal import Decimal

from .extract import CN_NUM

COUNT = r"(?:\d{1,2}|[一二两三四五六七八九十]{1,3})"
AMOUNT = (
    r"((?:\d{1,8}(?:,\d{3})*(?:\.\d{1,2})?\s*(?:万|千|百)?"
    r"|[零〇一二两三四五六七八九十百千万]+)(?:\s*(?:元|块(?:钱)?))?)"
)
SPACE = r"[\s，,。.!！?？、：:]*"
WAGE = r"(?:工资|薪资|薪水|月薪|工钱|报酬|实习补贴)"
UNPAID = (
    r"(?:(?:并|还|仍|一直|都|也|至今)" + SPACE + r"){0,4}"
    r"(?:没有|没|未曾|未|不曾)" + SPACE +
    r"(?:发(?:放|给|出来)?|支付|付(?:给)?|打(?:款|给)|给|结(?:清|算)?|到账|收到|拿到)"
)
WAGE_UNPAID = re.compile(
    rf"{WAGE}{SPACE}(?:(?:这笔|公司|单位|老板|他|她|一分){SPACE}){{0,3}}{UNPAID}"
    rf"|{UNPAID}(?:过|我|我们|这笔|我的|实习期内的|实习的|实习期间的|实习)*{SPACE}{WAGE}"
)
NO_PAY_AT_ALL = re.compile(rf"(?:一分(?:钱)?|一分钱|一块钱){SPACE}(?:都|也){SPACE}{UNPAID}")
SHORT_PAY = re.compile(
    rf"{WAGE}{SPACE}(?:(?:公司|单位|老板|他|她){SPACE})?"
    r"(?:少发|少给|扣了|压了|降了|少了|给少了|发少了|没给够|发得不够|不一样|对不上)"
    rf"|(?:少发|少给|补发|补齐|补足|补我|发我){SPACE}(?:我的?|欠的|实习(?:期间)?的?|该发的)*{SPACE}{WAGE}"
)
PAY_MISMATCH = re.compile(
    rf"(?:工资|薪资|月薪)[^。！？；\n]{{0,14}}(?:说好|约定|承诺|答应)[^。！？；\n]{{0,25}}"
    rf"(?:实际|结果|后来|但)[^。！？；\n]{{0,12}}(?:只|少|才)(?:给|发|到账|拿)"
)
OWED_BY_EMPLOYER = re.compile(
    rf"(?:公司|单位|老板|厂里){SPACE}(?:还|一直|至今|都)*{SPACE}"
    rf"(?:还欠我(?:薪水|工资|工钱)|{UNPAID}(?:我|我们)?{SPACE}(?:钱|{WAGE}))"
)
ONGOING_WORK = re.compile(
    r"(?:还|仍(?:然)?|目前|现在)(?:我)?(?:在职|在上班|在公司(?:上班|工作|做事))|在职中|还没离职|我在职"
)
ENDED_WORK = re.compile(r"(?:已(?:经)?|目前已|今天|现在已经)(?:离职|辞职)|最后一天上班")
COMPENSATION_QUESTION = re.compile(r"赔偿(?:我|吗|金)?|赔我|经济补偿|(?:能|要|应不应该|有没有).{0,6}补偿")
CASE_GOAL = re.compile(
    r"希望(?:单位|公司|老板|对方)?(?:能|可以|帮我)?(?:补|给|发|恢复|开|出具|赔|退|支付|继续)"
    r"|(?:我想要|我要求|我想让).{0,16}(?:钱|工资|继续|证明|赔偿|补偿|退还|复职|解决)"
    r"|(?:给我|拿到|开一?张|要一?份)(?:离职|在职|工作)证明"
    r"|(?i:\bI (?:want|need|am asking for)\b)"
)
UNPAID_TOTAL = re.compile(
    rf"(?:一共|总共|合计|加起来){SPACE}(?:还|约|大概|大约)*{SPACE}"
    rf"(?:欠我?|差|少发|少给|没发|没给){SPACE}(?:我|工资|薪资|报酬|工钱)*{SPACE}{AMOUNT}"
)


def clean_dictation(story: str) -> str:
    """Preserve sentence boundaries and remove standalone hesitation tokens."""
    story = re.sub(r"(?<=[，,。.!！?？；;\n])\s*(?:嗯+|呃+|额+|那个)\s*[，,。.!！?？、]+", "", story)
    return re.sub(r"(?<=[\u4e00-\u9fff\d])\s+(?=[\u4e00-\u9fff])", "", story)


def parse_amount(raw: str) -> Decimal | None:
    raw = re.sub(r"[\s,元块钱]", "", raw)
    numeric = re.fullmatch(r"(\d+(?:\.\d{1,2})?)([万千百]?)", raw)
    if numeric:
        return Decimal(numeric[1]) * {"万": 10000, "千": 1000, "百": 100, "": 1}[numeric[2]]
    if not re.fullmatch(r"[零〇一二两三四五六七八九十百千万]+", raw):
        return None
    digits = {**CN_NUM, "零": 0, "〇": 0}
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    section, total, digit = 0, 0, None
    for token in raw:
        if token in digits:
            digit = digits[token]
        elif token == "万":
            total += (section + (digit or 0)) * 10000
            section, digit = 0, None
        elif token in units:
            section += (1 if digit is None else digit) * units[token]
            digit = None
    # An omitted final unit is common in dictation: “一千五” is 1,500, while “一千零五” is 1,005.
    last_unit = {"百": 10, "千": 100, "万": 1000}.get(raw[-2], 1) if len(raw) > 1 else 1
    return Decimal(total + section + (digit or 0) * last_unit)


def spoken_wage_issue(story: str) -> bool:
    text = clean_dictation(story)
    return bool(
        WAGE_UNPAID.search(text) or SHORT_PAY.search(text) or OWED_BY_EMPLOYER.search(text) or PAY_MISMATCH.search(text)
        or (re.search(WAGE, text) and NO_PAY_AT_ALL.search(text))
    )


def stated_unpaid_total(story: str) -> Decimal | None:
    matches = list(UNPAID_TOTAL.finditer(clean_dictation(story)))
    return parse_amount(matches[-1][1]) if matches else None
