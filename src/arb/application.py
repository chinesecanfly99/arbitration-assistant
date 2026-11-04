"""仲裁申请书草稿（S3.7）。

只做"把已经算出来的东西写成申请书格式"，不做任何法律判断。
原则：能确定的填好，不确定的留 `____` 让人手写——**绝不替当事人编事实**。
"""
from __future__ import annotations

from datetime import date


def _d(x) -> str:
    if not x:
        return "____年__月__日"
    if isinstance(x, str):
        return x
    return f"{x.year}年{x.month}月{x.day}日"


def render_application(report: dict, applicant: dict | None = None) -> str:
    """report 来自 pipeline.analyze(mode='best_effort')；applicant 可含 name/sex/id/phone/address。"""
    a = applicant or {}
    reqs = []
    for it in report.get("items", []):
        reqs.append(f"{len(reqs)+1}. 请求裁决被申请人支付{it['name']} {it['amount']:,.2f} 元（依据：{it['basis']}）")
    total = report.get("total", 0)
    reqs.append(f"{len(reqs)+1}. 本案仲裁费用由被申请人承担。")

    tail = []
    tail.append("事实与理由：")
    tail.append("")
    tail.append(f"申请人于 {_d(report.get('fields', {}).get('hire_date'))} 入职被申请人处工作，"
                f"离职前十二个月平均工资为每月 {report.get('fields', {}).get('monthly_wage') or '____'} 元。"
                f"双方劳动关系于 {_d(report.get('fields', {}).get('end_date'))} 解除/终止。")
    tail.append("")
    tail.append("具体经过：____（请用 3–5 句话写清时间、地点、谁说了什么、有没有书面通知）")
    tail.append("")
    tail.append("证据清单：")
    for i, ev in enumerate([
        "劳动合同（如有）或入职登记表",
        "近 12 个月工资流水 / 工资条 / 个税记录",
        "解除劳动关系的通知、微信或录音（如有）",
        "考勤记录 / 排班表（主张加班费时）",
        "社保缴费记录",
    ], 1):
        tail.append(f"  {i}) {ev}")
    tail.append("")
    tail.append("此致")
    tail.append(f"{report.get('scope', {}).get('department') or '____劳动人事争议仲裁委员会'}")
    tail.append("")
    tail.append(f"申请人（签名）：____　　　　　　　　{date.today().year} 年 __ 月 __ 日")

    head = []
    head.append("劳动仲裁申请书")
    head.append("")
    head.append(f"申请人：{a.get('name') or '____'}　性别：{a.get('sex') or '____'}")
    head.append(f"身份证号：{a.get('id') or '____'}")
    head.append(f"住址：{a.get('address') or '____'}　联系电话：{a.get('phone') or '____'}")
    head.append("")
    head.append("被申请人：____（请填写公司全称，与营业执照一致）")
    head.append("统一社会信用代码：____")
    head.append("住所地：____　　法定代表人：____")
    head.append("")
    head.append("仲裁请求：")
    head.extend(reqs)
    head.append("")
    head.append(f"（合计：{total:,.2f} 元）")
    head.append("")
    return "\n".join(head + tail)


def render_notes(report: dict) -> str:
    """申请书之外必须给当事人的提醒：时效、管辖、材料、别造假。"""
    notes = ["提交前请核对："]
    dls = report.get("deadlines") or []
    urges = [d for d in dls if d.get("days_left") is not None and not d.get("expired")]
    if urges:
        nxt = min(urges, key=lambda d: d["days_left"])
        notes.append(f"· 时效：{nxt['label']} 剩 {nxt['days_left']} 天（截止 {nxt['deadline']}），别拖过。")
    expired = [d for d in dls if d.get("expired")]
    if expired:
        notes.append(f"· 有 {len(expired)} 项请求可能已过时效，先咨询 12348 或仲裁委立案窗口。")
    notes.append(f"· 管辖：{(report.get('scope') or {}).get('department') or '用工所在地或单位所在地仲裁委'}。")
    notes.append("· 材料：身份证复印件、公司工商信息（国家企业信用信息公示系统可查）、证据复印件一式两份。")
    notes.append("· 仲裁不收费；受理后一般 45 日内审结，复杂可延 15 日。")
    notes.append("· 不要伪造、补造任何材料——伪造证据可能被追究责任，也会毁掉你本来能赢的案子。")
    return "\n".join(notes)
