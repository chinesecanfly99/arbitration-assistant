"""劳动仲裁赔偿计算内核。

设计原则（写进文档、答辩时会问）：
1. 这里**绝不调用任何大模型**。钱必须算得准、算得可复现。
2. 每一项都返回 `formula` 与 `basis`（法条号），让用户能自己核对。
3. 口径有争议的地方（低工资封顶、二倍工资不足一月怎么算）集中放在
   `Policy` 里，改一处即可，不散落在代码各处。

法条依据：
- 《劳动合同法》第 47 条  经济补偿
- 《劳动合同法》第 87 条  违法解除赔偿金（2N）
- 《劳动合同法》第 82 条  未签书面合同二倍工资
- 《劳动法》第 44 条      加班费
- 《劳动法》第 50 条      工资应当按月支付
- 《职工带薪年休假条例》第 5 条 / 《实施办法》第 10 条  未休年假 300%
- 《最高人民法院关于审理劳动争议案件适用法律问题的解释（二）》第 6 条
  二倍工资按月计算、不满一个月按该月实际工作日折算（2025-09-01 施行）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Optional

from .dates import add_months, add_years, days_elapsed_in_year, days_inclusive, months_between

# ---------------------------------------------------------------- 常量
DAILY_WAGE_DIVISOR = 21.75  # 月计薪天数
HOURS_PER_DAY = 8.0
MAX_DOUBLE_WAGE_MONTHS = 11.0
CAP_YEARS_WHEN_3X = 12.0  # 月工资高于社平 3 倍时，年限最高 12 年

TerminationType = Literal[
    "legal_termination",      # 合法解除 / 合同期满单位不续签 -> N
    "mutual_agreement",       # 协商一致（单位提出）      -> N
    "employee_resign",        # 劳动者主动辞职            -> 一般无补偿
    "illegal_dismissal",      # 违法解除                  -> 2N
]


@dataclass
class Policy:
    """有争议的口径集中在这里，换城市/换判例口径只改这一处。"""

    daily_wage_divisor: float = DAILY_WAGE_DIVISOR
    # 二倍工资不足一个月怎么算：True=不足一月按一月（有利于劳动者），False=不足一月不计
    double_wage_round_up_partial_month: bool = False
    # 未休年假按日工资的多少倍额外支付（不含已发的 100%，只算额外部分）
    annual_leave_extra_rate: float = 2.0


@dataclass
class ClaimInput:
    hire_date: date
    end_date: date
    monthly_wage: float                     # 离职前 12 个月平均**应得**工资
    termination: TerminationType = "legal_termination"
    social_avg_wage: Optional[float] = None  # 当地上年度职工月平均工资（用于 3 倍封顶）
    has_written_contract: bool = True        # 是否签过书面劳动合同（默认签过，避免默认多算 11 个月）
    contract_signed_date: Optional[date] = None  # 补签日期；仅 has_written_contract=True 时有意义
    overtime_workday_hours: float = 0.0
    overtime_restday_hours: float = 0.0
    overtime_holiday_hours: float = 0.0
    restday_compensated_by_leave: bool = False
    total_work_years: Optional[float] = None  # 累计工作年限（含前东家），用于年假档位
    taken_annual_leave_days: float = 0.0
    unused_annual_leave_days: Optional[float] = None  # 直接给数则跳过折算
    unpaid_wages: float = 0.0


def service_months(hire: date, end: date) -> int:
    """本单位工作年限，折算为整月数。"""
    if end < hire:
        raise ValueError(f"离职日 {end} 早于入职日 {hire}")
    return months_between(hire, end) + (0 if end.day >= hire.day else 0)


def severance_months_by_law(months: int) -> float:
    """第 47 条：每满一年一个月；六个月以上不满一年按一年；不满六个月半个月。"""
    if months <= 0:
        return 0.5  # 干过但不满一个月，仍给半个月
    years, rest = divmod(months, 12)
    if rest == 0:
        return float(years)
    if rest >= 6:
        return float(years + 1)
    return years + 0.5


@dataclass
class Item:
    name: str
    amount: float
    formula: str
    basis: str
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "amount": round(self.amount, 2),
            "formula": self.formula,
            "basis": self.basis,
            "note": self.note,
        }


def _round2(x: float) -> float:
    return round(x + 1e-9, 2)


# ---------------------------------------------------------------- 各项计算
def economy_compensation(inp: ClaimInput, policy: Policy) -> Item:
    """经济补偿 N（第 47 条）。3 倍封顶时年限最高 12 年。"""
    months = service_months(inp.hire_date, inp.end_date)
    n_months = severance_months_by_law(months)

    base = inp.monthly_wage
    note = ""
    if inp.social_avg_wage:
        cap = inp.social_avg_wage * 3
        if inp.monthly_wage > cap:
            base = cap
            n_months = min(n_months, CAP_YEARS_WHEN_3X)
            note = f"月工资高于当地社平工资 3 倍（{cap:.2f}），按 3 倍封顶且年限上限 12 年"
    amount = base * n_months
    return Item(
        name="经济补偿金（N）",
        amount=amount,
        formula=f"{base:.2f} 元/月 × {n_months:g} 个月（本单位 {months} 个月工龄折算）",
        basis="《劳动合同法》第 47 条",
        note=note,
    )


def illegal_dismissal_compensation(inp: ClaimInput, policy: Policy) -> Item:
    """违法解除赔偿金 2N（第 87 条）。与 N 不并用。"""
    n = economy_compensation(inp, policy)
    return Item(
        name="违法解除赔偿金（2N）",
        amount=n.amount * 2,
        formula=f"{n.formula} × 2",
        basis="《劳动合同法》第 87 条",
        note="赔偿金与第 47 条经济补偿不并用，故本项已包含 N，不再单独计经济补偿",
    )


def double_wage(inp: ClaimInput, policy: Policy) -> Optional[Item]:
    """未签书面合同二倍工资（第 82 条），最多 11 个月。

    期间：用工满一个月的次日起，至补签前一日；若始终未签，至满一年的前一日。
    """
    start = add_months(inp.hire_date, 1) + timedelta(days=1)
    hard_end = add_years(inp.hire_date, 1) - timedelta(days=1)  # 满一年前一日

    if inp.has_written_contract and inp.contract_signed_date is None:
        return None  # 已按法签了书面合同，不产生二倍工资

    if inp.contract_signed_date is not None:
        end = inp.contract_signed_date - timedelta(days=1)
        end = min(end, hard_end)
    else:
        end = hard_end

    if end < start:
        return None

    days = days_inclusive(start, end)
    if policy.double_wage_round_up_partial_month:
        months = min(MAX_DOUBLE_WAGE_MONTHS, float(-(-days // 30)))
    else:
        months = min(MAX_DOUBLE_WAGE_MONTHS, float(days // 30))

    if months == 0:
        return None

    amount = inp.monthly_wage * months
    return Item(
        name="未签书面劳动合同二倍工资",
        amount=amount,
        formula=f"{inp.monthly_wage:.2f} 元/月 × {months:g} 个月（{start} 至 {end}，共 {days} 天，上限 11 个月）",
        basis="《劳动合同法》第 82 条、《最高人民法院关于审理劳动争议案件适用法律问题的解释（二）》第 6 条",
        note=(
            "指应付而未付的**另一倍**工资，不是把已发工资再算一遍；"
            "《司法解释（二）》第 6 条已明确二倍工资按月计算、不满一个月按该月实际工作日折算，"
            f"本单对不满一个月的尾数采用{'不足一月按一月' if policy.double_wage_round_up_partial_month else '整月计、不足一月不计'}的保守口径，"
            "可在 Policy 里切换"
        ),
    )


def overtime_pay(inp: ClaimInput, policy: Policy) -> Optional[Item]:
    """加班费：工作日 150%、休息日 200%（已调休则不计）、法定节假日 300%。"""
    total_hours = (
        inp.overtime_workday_hours + inp.overtime_restday_hours + inp.overtime_holiday_hours
    )
    if total_hours <= 0:
        return None

    daily = inp.monthly_wage / policy.daily_wage_divisor
    hourly = daily / HOURS_PER_DAY

    wd = inp.overtime_workday_hours * hourly * 1.5
    rd_hours = 0.0 if inp.restday_compensated_by_leave else inp.overtime_restday_hours
    rd = rd_hours * hourly * 2.0
    hd = inp.overtime_holiday_hours * hourly * 3.0

    parts = [f"{hourly:.2f} 元/小时"]
    if inp.overtime_workday_hours:
        parts.append(f"工作日 {inp.overtime_workday_hours:g}h×150%")
    if inp.overtime_restday_hours:
        if inp.restday_compensated_by_leave:
            parts.append(f"休息日 {inp.overtime_restday_hours:g}h 已安排调休，不计")
        else:
            parts.append(f"休息日 {inp.overtime_restday_hours:g}h×200%")
    if inp.overtime_holiday_hours:
        parts.append(f"法定节假日 {inp.overtime_holiday_hours:g}h×300%")

    return Item(
        name="加班费",
        amount=wd + rd + hd,
        formula="；".join(parts),
        basis="《劳动法》第 44 条",
        note="加班时长须由劳动者举证或单位考勤记录佐证；休息日加班已安排补休的无需支付",
    )


def annual_leave_entitlement(total_work_years: float) -> int:
    """年假天数档位：累计工作满 1 年不满 10 年 5 天；10–20 年 10 天；满 20 年 15 天。"""
    if total_work_years < 1:
        return 0
    if total_work_years < 10:
        return 5
    if total_work_years < 20:
        return 10
    return 15


def annual_leave_pay(inp: ClaimInput, policy: Policy) -> Optional[Item]:
    """未休年假折算：日工资 × 200%（额外部分），应休天数按当年度已过天数折算。"""
    if inp.unused_annual_leave_days is not None:
        unused = inp.unused_annual_leave_days
        basis_note = "按用户提供的未休天数"
    else:
        years = inp.total_work_years
        if years is None:
            years = months_between(inp.hire_date, inp.end_date) / 12.0
        entitled = annual_leave_entitlement(years)
        elapsed = days_elapsed_in_year(inp.end_date)
        prorated = int(entitled * elapsed / 365)  # 不足 1 整天不计
        # 已休天数可能是"用户没说"（None），不能当成 0 硬算——按 0 算 + 提示去确认
        taken = inp.taken_annual_leave_days
        assumed = taken is None
        taken = taken or 0
        unused = max(prorated - taken, 0)
        basis_note = (
            f"累计工作 {years:g} 年应享 {entitled} 天，当年已过 {elapsed} 天折算 {prorated} 天，"
            f"已休 {taken:g} 天" + ("（未确认，暂按 0 天）" if assumed else "")
        )

    if unused <= 0:
        return None

    daily = inp.monthly_wage / policy.daily_wage_divisor
    amount = unused * daily * policy.annual_leave_extra_rate
    return Item(
        name="未休年休假工资",
        amount=amount,
        formula=f"{unused:g} 天 × {daily:.2f} 元/天 × {policy.annual_leave_extra_rate * 100:.0f}%",
        basis="《职工带薪年休假条例》第 5 条、《企业职工带薪年休假实施办法》第 10 条",
        note=f"{basis_note}；此处只计额外 200%，正常工资 100% 视为已随工资发放",
    )


def unpaid_wage_item(inp: ClaimInput) -> Optional[Item]:
    if inp.unpaid_wages <= 0:
        return None
    return Item(
        name="拖欠工资",
        amount=inp.unpaid_wages,
        formula=f"欠发金额 {inp.unpaid_wages:.2f} 元",
        basis="《劳动法》第 50 条",
        note="需提供工资条/银行流水/聊天记录佐证",
    )


# ---------------------------------------------------------------- 汇总
COMPENSABLE = {"legal_termination", "mutual_agreement"}


def compute(inp: ClaimInput, policy: Optional[Policy] = None) -> dict:
    """返回 {items, total, service_months, severance_months, warnings}。"""
    policy = policy or Policy()
    items: list[Item] = []
    warnings: list[str] = []

    months = service_months(inp.hire_date, inp.end_date)
    n_months = severance_months_by_law(months)

    if inp.monthly_wage <= 0:
        warnings.append("月工资为 0 或未提供，补偿类金额将不可信")

    if inp.termination == "illegal_dismissal":
        items.append(illegal_dismissal_compensation(inp, policy))
    elif inp.termination in COMPENSABLE:
        items.append(economy_compensation(inp, policy))
    elif inp.termination is None:
        warnings.append("解除方式未确认，暂不计经济补偿（N）/赔偿金（2N）；确认后可能再加一笔。")
    else:
        warnings.append(
            "劳动者主动辞职原则上无经济补偿（N）；若属《劳动合同法》第 38 条被迫解除，"
            "应改按合法解除主张 N，请人工确认解除原因。"
        )

    dw = double_wage(inp, policy)
    if dw:
        items.append(dw)

    ot = overtime_pay(inp, policy)
    if ot:
        items.append(ot)

    al = annual_leave_pay(inp, policy)
    if al:
        items.append(al)

    uw = unpaid_wage_item(inp)
    if uw:
        items.append(uw)

    total = _round2(sum(i.amount for i in items))

    return {
        "items": [i.as_dict() for i in items],
        "total": total,
        "service_months": months,
        "service_years": round(months / 12.0, 2),
        "severance_months": n_months,
        "warnings": warnings,
    }
