"""案件完整度地图：把 9 个业务字段变成"用户一眼能看懂的体检表"。

设计原则
- 只做**展示层**的映射，不改变抽取与计算逻辑；
- 每个缺失字段都配一句"补什么"，用户点一下就能把模板句插回输入框；
- 可选字段（加班、年假、欠薪）缺失不算问题，标"可选"而不是标红。
"""

from __future__ import annotations

# 顺序 = 用户讲的顺理成章的顺序，不是 schema 的字母序
FIELD_LABELS = [
    ("hire_date", "入职日期", "例如：2020年3月1日入职"),
    ("end_date", "离职日期", "例如：2024年5月20日让我走人"),
    ("monthly_wage", "月工资", "例如：月薪9000元（说税前、含不含奖金更好）"),
    ("termination", "谁提的解除", "例如：公司口头说不要我了 / 我自己辞职的"),
    ("has_written_contract", "有没有签书面合同", "例如：一直没签书面合同 / 签了两份都被收走"),
    ("overtime_workday_hours", "工作日加班", "可选：例如平时加班200小时"),
    ("overtime_restday_hours", "休息日加班", "可选：例如周末加班60小时"),
    ("overtime_holiday_hours", "法定节假日加班", "可选：例如国庆加班16小时"),
    ("unused_annual_leave_days", "没休的年假", "可选：例如还有5天年假没休"),
    ("unpaid_wages", "被拖欠的工资", "可选：例如欠了4个月工资"),
]

OPTIONAL = {
    "overtime_workday_hours",
    "overtime_restday_hours",
    "overtime_holiday_hours",
    "unused_annual_leave_days",
    "unpaid_wages",
}

# 少了这几个就真的算不出钱
CRITICAL = ["hire_date", "end_date", "monthly_wage", "termination"]


def _shown(key: str, value) -> str:
    if isinstance(value, bool):
        return "已签" if value else "没签"
    if key in ("hire_date", "end_date") and value is not None:
        return str(value)
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    if value is None:
        return ""
    return str(value)


def completeness(fields: dict) -> dict:
    """返回 {"rows": [...], "missing": [...], "critical_missing": [...], "score": 0-1}"""
    rows = []
    missing = []
    critical_missing = []
    for key, label, hint in FIELD_LABELS:
        value = fields.get(key)
        filled = value is not None and value != 0
        if key in ("has_written_contract",):
            filled = value is not None
        if filled:
            status = "ok"
        elif key in OPTIONAL:
            status = "optional"
        else:
            status = "missing"
            missing.append(key)
            if key in CRITICAL:
                critical_missing.append(key)
        rows.append(
            {
                "key": key,
                "label": label,
                "value": _shown(key, value),
                "status": status,
                "optional": key in OPTIONAL,
                "critical": key in CRITICAL,
                "hint": hint,
            }
        )
    total = len(rows)
    filled_n = sum(1 for r in rows if r["status"] == "ok")
    return {
        "rows": rows,
        "missing": missing,
        "critical_missing": critical_missing,
        "score": round(filled_n / total, 2),
    }


def summary_line(fields: dict) -> str:
    """一句话结论，给 need_more 页面用。"""
    c = completeness(fields)
    if not c["critical_missing"]:
        return "关键信息齐了，可以算了。"
    names = "、".join(r["label"] for r in c["rows"] if r["key"] in c["critical_missing"])
    return f"还差关键信息：{names}。补上就能算出金额和时效。"
