"""故事 → 结构化要素的抽取（S3.1）。

这里先做一个**确定性的规则基线**，不是最终方案，理由有三：
1. 没有模型也能跑：没有 API key 时整条流水线（抽取→计算→报告）依旧完整，答辩时不会翻车。
2. 有了基线才知道大模型值不值：同一套 50 条案例，规则基线 与 LLM 各自跑一遍，差距是量化出来的。
3. 每条抽取都带 evidence（原文片段 + 位置），前端可以高亮回原文——这是"可信"的具体形态。

接口：
    extract(story, today=None) -> {"fields", "evidence", "unresolved", "relative"}

字段名与 schema.json 严格一致；抽不到就给 None 并写进 unresolved（交给缺口追问），不瞎猜。
相对时间（去年 / 今年 / 前年）在这里是**已知风险**：规则层只能按 today 推定，
推错就是错的，所以把用到的相对词记在 relative 里，前端要把它当"请确认"项展示。
"""
from __future__ import annotations

import re
from datetime import date

CN_NUM = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

DATE_FULL = re.compile(r"(20\d{2})\s*[年\-/]\s*(\d{1,2})\s*(?:[月\-/]\s*(\d{1,2})\s*[日号]?)?")
DATE_MD = re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]")
DATE_MONTH = re.compile(r"(?<!\d)(\d{1,2})\s*月份?(?:\s*(初|中|底))?")
REL_WORDS = (("大前年", -3), ("前年", -2), ("去年", -1), ("今年", 0), ("本年", 0))

WAGE = re.compile(r"(?:月薪|月工资|每月工资|工资|一个?月|每月)\s*(?:约|大概|是|给|拿|挣)?\s*(\d{3,6})")
SAW = re.compile(r"(?:社平工资|社会平均工资|上年度职工月平均工资|社平)[^0-9]{0,10}(\d{4,6})")
WAGE_ALT = re.compile(r"(\d{3,6})\s*(?:块|元)\s*(?:一个月|/月|每月)?")

HIRE_CTX = ("入职", "进厂", "进公司", "开始上班", "开始做", "上岗", "来的")
END_CTX = ("离职", "走的", "走人", "辞职", "辞退", "被辞", "解除", "不干了", "离开", "裁员",
           "到期", "没发工资", "欠薪", "试用期最后一天", "干到", "做到", "就辞了")
END_PAT = re.compile(r"让我(?:当天|立刻|马上|明天)?走|不要我了|别来了|不用来了|把我(?:辞|开|炒)了|(?:被|把我)开除")

OT_TYPE = [
    ("overtime_workday_hours", ("工作日", "平时晚上", "下班后")),
    ("overtime_restday_hours", ("周末", "周六", "周日", "双休日")),
    ("overtime_holiday_hours", ("法定节假日", "法定假日", "春节", "国庆", "五一", "中秋")),
]
OT_PAIR = re.compile(r"([\u4e00-\u9fff]{0,8}?)\s*(?:加班|加了?)\s*(?:约|大概)?\s*(\d{2,4})\s*个?\s*小时")
OT_DAYS = re.compile(r"([\u4e00-\u9fff]{0,8}?)\s*上班\s*([一二三四五六七八九十\d]+)\s*天")
OT_DAY_HOURS = re.compile(r"每天\s*(\d{1,2})\s*个?\s*小时")


def _cn_int(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not s:
        return None
    if len(s) == 1 and s in CN_NUM:
        return CN_NUM[s]
    if s.startswith("十") and len(s) == 1:
        return 10
    if len(s) == 2 and s[0] == "十" and s[1] in CN_NUM:
        return 10 + CN_NUM[s[1]]
    if len(s) == 2 and s[0] in CN_NUM and s[1] == "十":
        return CN_NUM[s[0]] * 10
    if len(s) == 3 and s[1] == "十":
        return CN_NUM.get(s[0], 0) * 10 + CN_NUM.get(s[2], 0)
    return None


def _mk(y, m, d) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _collect_dates(story: str, today: date):
    """返回 [dict(dt, s, e, rel, ym_only)]；dt=None 表示需追问。"""
    out, taken = [], []
    for m in DATE_FULL.finditer(story):
        ym_only = m.group(3) is None
        dt = _mk(m.group(1), m.group(2), (m.group(3) or 1))
        if dt:
            out.append({"dt": dt, "s": m.start(), "e": m.end(), "rel": None, "ym_only": ym_only, "has_day": not ym_only})
            taken.append((m.start(), m.end()))
    full_dates = [d for d in out]
    for m in DATE_MD.finditer(story):
        if any(s0 <= m.start() < e0 for s0, e0 in taken):
            continue
        prev = story[max(0, m.start() - 6) : m.start()]
        rel, delta = None, None
        for w, dv in REL_WORDS:
            if w in prev:
                rel, delta = w, dv
                break
        if delta is None:
            # 没写年份也没写"去年"：若故事里有完整日期，借用最近的一个年份
            before = [d for d in full_dates if d["e"] <= m.start()]
            if before:
                base = before[-1]["dt"]
                dt = _mk(base.year, m.group(1), m.group(2))
                if dt and dt < base:
                    dt = _mk(base.year + 1, m.group(1), m.group(2))
                out.append({"dt": dt, "s": m.start(), "e": m.end(), "rel": None, "ym_only": False, "has_day": True})
                taken.append((m.start(), m.end()))
                continue
            out.append({"dt": None, "s": m.start(), "e": m.end(), "rel": "无年份", "ym_only": False, "has_day": True})
            continue
        dt = _mk(today.year + delta, m.group(1), m.group(2))
        if dt and dt > today:
            dt = _mk(today.year + delta - 1, m.group(1), m.group(2))
        out.append({"dt": dt, "s": m.start(), "e": m.end(), "rel": rel, "ym_only": False, "has_day": True})
        taken.append((m.start(), m.end()))
    for m in DATE_MONTH.finditer(story):
        if any(s0 <= m.start() < e0 for s0, e0 in taken):
            continue
        day_word = m.group(2)
        if day_word is None and re.match(r"\s*\d", story[m.end():]):
            continue  # 形如"5月20日"已被上一轮吃掉，这里不重复
        prev = story[max(0, m.start() - 8): m.start()]
        year = None
        ym = re.search(r"(20\d{2})\s*年\s*$", prev)
        if ym:
            year = int(ym.group(1))
        if year is None:
            for w, dv in REL_WORDS:
                if w in prev:
                    year = today.year + dv
                    break
        if year is None:
            before = [d for d in full_dates if d["e"] <= m.start()]
            year = before[-1]["dt"].year if before else today.year
        day = 1
        has_day = False
        if day_word in ("初",):
            has_day = True
        dt = _mk(year, m.group(1), day)
        if dt is None:
            continue
        out.append({"dt": dt, "s": m.start(), "e": m.end(), "rel": None,
                    "ym_only": not has_day, "has_day": has_day, "month_end": day_word == "底"})
        taken.append((m.start(), m.end()))
    return out

def extract(story: str, today: date | None = None) -> dict:
    story = story or ""
    today = today or date.today()
    fields: dict = {
        "hire_date": None, "end_date": None, "monthly_wage": None, "termination": None,
        "has_written_contract": None, "contract_signed_date": None,
        "overtime_workday_hours": 0, "overtime_restday_hours": 0, "overtime_holiday_hours": 0,
        "taken_annual_leave_days": None, "unused_annual_leave_days": None, "unpaid_wages": 0,
        "social_avg_wage": None,
    }
    ev: dict[str, str] = {}
    relative: list[str] = []

    dates = _collect_dates(story, today)
    hires, ends = [], []
    for d in dates:
        dt, s0, e0 = d["dt"], d["s"], d["e"]
        if d["rel"]:
            relative.append(story[s0:e0] + (f"（按 today={today} 推定为 {dt}）" if dt else ""))
        if dt is None:
            continue
        ctx_before = story[max(0, s0 - 24) : s0]
        ctx_after = story[e0 : e0 + 24]
        ctx = ctx_before + ctx_after
        if re.search(r"^[^。，]{0,6}(?:补签|补订|签订|订立)", ctx_after):
            fields["contract_signed_date"] = dt
            continue
        near_end = max([ctx.rfind(k) for k in END_CTX] + [-1])
        near_end = max(near_end, ctx.rfind("解除"), ctx.rfind("被辞"))
        if END_PAT.search(ctx_after):
            near_end = 999
        near_hire = max([ctx.rfind(k) for k in HIRE_CTX] + [-1])
        if near_end > near_hire:
            ends.append(d)
        elif near_hire >= 0:
            hires.append(d)
        elif "补签" in ctx:
            fields["contract_signed_date"] = dt

    if hires:
        d = min(hires, key=lambda x: x["dt"])
        fields["hire_date"] = d["dt"]
        ev["hire_date"] = story[d["s"] : d["e"]]
    if ends:
        d = max(ends, key=lambda x: x["dt"])
        end = d["dt"]
        if not d.get("has_day", True) or d.get("month_end"):
            # "2024年5月解除" / "3月辞职"：按该月最后一天记
            nxt = _mk(end.year + (end.month == 12), (end.month % 12) + 1, 1)
            if nxt:
                end = date.fromordinal(nxt.toordinal() - 1)
            ev["end_date"] = story[d["s"] : d["e"]] + "（按月末计）"
        else:
            ev["end_date"] = story[d["s"] : d["e"]]
        if re.search(r"(?:待岗|停工|放假)\s*(?:了)?\s*[一1]\s*个?月后", story) or "一个月后解除" in story:
            # "待岗一个月后解除"：解除在下个月，从**原始日期**推下月月末（不要从已对齐的月末再推）
            base = d["dt"]
            y2 = base.year + (1 if base.month == 12 else 0)
            m2 = 1 if base.month == 12 else base.month + 1
            nxt = _mk(y2, m2, 1)
            if nxt:
                y3 = y2 + (1 if m2 == 12 else 0)
                m3 = 1 if m2 == 12 else m2 + 1
                nxt2 = _mk(y3, m3, 1)
                if nxt2:
                    end = date.fromordinal(nxt2.toordinal() - 1)
            ev["end_date"] = (ev.get("end_date", "") + "（待岗一个月后解除，取下月月末）").strip()
        fields["end_date"] = end

    known = sorted(d["dt"] for d in dates if d["dt"])
    if fields["hire_date"] is None and known:
        fields["hire_date"] = known[0]
        ev["hire_date"] = "（按最早日期推定）"
    if fields["end_date"] is not None:
        pass
    if fields["end_date"] is None and len(known) >= 2:
        last = [d for d in dates if d["dt"] == known[-1]][-1]
        end = known[-1]
        if not last.get("has_day", True) or last.get("month_end"):
            nxt = _mk(end.year + (end.month == 12), (end.month % 12) + 1, 1)
            if nxt:
                end = date.fromordinal(nxt.toordinal() - 1)
            ev["end_date"] = "（按最晚日期推定，按月末计）"
        else:
            ev["end_date"] = "（按最晚日期推定）"
        fields["end_date"] = end
    if fields["hire_date"] and fields["end_date"] and fields["hire_date"] > fields["end_date"]:
        fields["hire_date"], fields["end_date"] = fields["end_date"], fields["hire_date"]

    if re.search(r"还在上班|仍在职|还没离职|还在干|一直在职|现在还在", story):
        fields["end_date"] = today
        ev["end_date"] = "（仍在职，按今天计）"

    m = WAGE.search(story) or WAGE_ALT.search(story)
    if m:
        fields["monthly_wage"] = float(m.group(1))
        ev["monthly_wage"] = m.group(0)

    saw = SAW.search(story)
    if saw:
        fields["social_avg_wage"] = float(saw.group(1))
        ev["social_avg_wage"] = saw.group(0)

    forced = re.search(r"调岗|调去|换地点|搬到|部门撤|厂搬|我不去|我没去|拒绝", story)
    if re.search(r"按旷工解除|算我自动离职|说我自动离职|以旷工", story) and forced:
        # 公司用"旷工/自动离职"包装，但起因是逼你调岗→按违法解除处理
        fields["termination"] = "illegal_dismissal"
        ev["termination"] = "公司以旷工为由解除，但起因是调岗/搬迁（推定违法解除）"
    elif re.search(r"依法解除|依法终止|提前终止|公司依法", story):
        fields["termination"] = "legal_termination"
    elif re.search(r"违法解除|违法辞退|口头辞退|被辞退|被辞|让我当天走|让我立刻走|要我立刻走|要我走|把我辞|把我开|不要我了|别来了", story):
        fields["termination"] = "illegal_dismissal"
    elif re.search(r"协商一致|协商解除|谈好|签了协议|双方同意", story):
        fields["termination"] = "mutual_agreement"
    elif re.search(r"主动辞职|我辞职|我自己走|不干了|我走的|我走了|辞职走|我离职|我就离职", story):
        fields["termination"] = "employee_resign"
    elif re.search(r"到期|期满|不续签|合同结束|待岗|项目结束|停工", story):
        fields["termination"] = "legal_termination"
    elif re.search(r"解除(?:劳动)?合同|单方解除|以[^，。]{0,14}(?:为由|解除|终止)|不能胜任|调岗|降薪|裁员|不要我了|让我走|开除", story):
        # 公司动作为主语的"解除"，规则层按违法解除处理；最终要用户确认
        fields["termination"] = "illegal_dismissal"

    if re.search(r"没签|没有签|一直没(?:跟|给|和)我?签|未签|没给我签|没跟我签|两份都收走|都收走了|收走没给我", story):
        fields["has_written_contract"] = False
    elif re.search(
        r"(?:签了|签过|签订了?|补签了?|订立了?)(?:一份|书面)?(?:劳动)?合同"
        r"|(?:劳动|书面)合同(?:已经|已)?签",
        story,
    ):
        fields["has_written_contract"] = True

    for pre, hours in OT_PAIR.findall(story):
        key = "overtime_workday_hours"
        for k0, words in OT_TYPE:
            if any(w in pre for w in words):
                key = k0
                break
        fields[key] += int(hours)
        ev[key] = ev.get(key, "") + f"{pre}加班{hours}小时；"
    for pre, days in OT_DAYS.findall(story):
        n = _cn_int(days)
        h = OT_DAY_HOURS.search(story)
        if not n:
            continue
        for key, words in OT_TYPE:
            if any(w in pre for w in words):
                per = int(h.group(1)) if h else 8
                fields[key] += n * per
                ev[key] = ev.get(key, "") + f"{pre}上班{n}天×{per}小时；"
                break

    m = re.search(r"只休了?\s*(\d+)\s*天", story) or re.search(r"休了\s*(\d+)\s*天年假", story)
    if m:
        fields["taken_annual_leave_days"] = int(m.group(1))
        ev["taken_annual_leave_days"] = m.group(0)
    elif re.search(r"年假一天没休|一天年假都没休|没休过年假|年假都没休", story):
        fields["taken_annual_leave_days"] = 0
    m = re.search(r"(\d+)\s*天年假没休|还有\s*(\d+)\s*天年假", story)
    if m:
        fields["unused_annual_leave_days"] = int(m.group(1) or m.group(2))
        ev["unused_annual_leave_days"] = m.group(0)
    if fields["unused_annual_leave_days"] is None:
        m = re.search(r"(?:一共|总共|合计|加起来)\s*(\d+)\s*天(?:的)?年假", story)
        if m:
            fields["unused_annual_leave_days"] = int(m.group(1))
            ev["unused_annual_leave_days"] = m.group(0)

    # ① "欠四个月 / 欠了四个月工资"
    m = re.search(r"欠(?:了|我)?[^。，]{0,10}?([零一二两三四五六七八九十\d]+)\s*个?月", story)

    if m and fields["monthly_wage"]:
        n = _cn_int(m.group(1))
        if n:
            fields["unpaid_wages"] = float(n) * fields["monthly_wage"]
            ev["unpaid_wages"] = m.group(0)
    # ② "2024年2月到4月工资没发/欠着"：按月区间算
    if not fields["unpaid_wages"]:
        m = re.search(r"(20\d{2})?\s*年?\s*(\d{1,2})\s*月\s*(?:到|至|-|—)\s*(?:20\d{2}\s*年)?\s*(\d{1,2})\s*月[^。，]{0,10}(?:没发|欠着|未发|没给|拖欠)", story)
        if m and fields["monthly_wage"]:
            a, b = int(m.group(2)), int(m.group(3))
            n = b - a + 1
            if 0 < n <= 24:
                fields["unpaid_wages"] = float(n) * fields["monthly_wage"]
                ev["unpaid_wages"] = m.group(0)
    # ②b 单个月："4月工资没发"（配合离职月份推 1 个月）
    if not fields["unpaid_wages"]:
        m = re.search(r"(?:最后|上)\s*一?\s*个?月的?工资\s*(?:还)?(?:没结|没发|没给|欠着|未发|拖着)", story)
        if m and fields["monthly_wage"]:
            fields["unpaid_wages"] = float(fields["monthly_wage"])
            ev["unpaid_wages"] = m.group(0) + "（按 1 个月计）"
    if not fields["unpaid_wages"]:
        m = re.search(r"(?:20\d{2}\s*年)?\s*(\d{1,2})\s*月(?:份)?的?工资\s*(?:还)?(?:没发|没给|欠着|未发|拖着)", story)
        if m and fields["monthly_wage"]:
            fields["unpaid_wages"] = float(fields["monthly_wage"])
            ev["unpaid_wages"] = m.group(0) + "（按 1 个月计）"
    # ③ "欠 5000 元"
    if not fields["unpaid_wages"]:
        m = re.search(r"欠(?:了|我)?[^。，]{0,8}?(\d{3,6})\s*元", story)
        if m:
            fields["unpaid_wages"] = float(m.group(1))
            ev["unpaid_wages"] = m.group(0)

    unresolved = [k for k in ("hire_date", "end_date", "monthly_wage", "termination") if fields[k] is None]
    if any(d["dt"] is None for d in dates):
        unresolved.append("no_year_date")
    return {"fields": fields, "evidence": ev, "unresolved": unresolved, "relative": relative}
