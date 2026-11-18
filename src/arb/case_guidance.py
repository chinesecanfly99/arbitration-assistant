"""Contextual case questions with plain wording and a formal reference sentence."""
from __future__ import annotations

from .i18n import clarification_prompts, staged_prompts

# Each entry contains a short label, a plain question, a reference sentence, and an optional tip.
PROMPTS = {
    "hire_date": (
        ("哪天开始干的", "你什么时候开始给这家单位干活？记得月份也可以。", "我于___年___月___日入职___单位，担任___。", "记不准可以看第一笔工资、入职通知或最早的打卡。"),
        ("Work start", "When did you start working there? The month is enough if you are unsure.", "I began employment with ___ on ___ as ___.", "Check the hiring notice, first payment or earliest time record."),
    ),
    "end_date": (
        ("最后干到哪天", "最后一次上班是哪天？合同是同一天结束的吗？", "我最后工作至___年___月___日，劳动合同于___结束。", "能找到的最后一次打卡或工资结算记录都可以参考。"),
        ("Last working day", "When did you last work, and did the contract end that day?", "My last day worked was ___. The employment contract ended on ___.", "Check the last attendance or payroll record."),
    ),
    "dismissal_date": (
        ("哪天让你走的", "单位哪天通知你不用再来了？最后实际干到哪天？", "用人单位于___通知解除劳动合同，我最后工作至___。", "通知日期和最后工作日不同的话，可以分别写。"),
        ("Notice and last day", "When did they tell you to stop coming in, and when did you last work?", "The employer notified me of termination on ___. My last day worked was ___.", "List both dates if they differ."),
    ),
    "gross_pay": (
        ("税前多少钱", "每个月扣税和社保之前，工资大约多少钱？", "我的月应发工资为___元，其中基本工资___元，奖金或津贴___元。", "可以看工资条上的「应发合计」。只知道银行实收时，照实写「到手___元」。"),
        ("Pay before deductions", "How much did you earn each month before tax and deductions?", "My gross monthly pay was ___, including base pay ___ and allowances or bonuses ___.", "Check your payslip. If you only know the deposit, label it as take-home pay."),
    ),
    "termination": (
        ("是谁提出离职的", "是单位让你走、你自己提出、双方协商，还是合同到期？", "劳动合同于___结束，由___提出，通知中写明的原因为___。", "按对方说过的话描述就行。"),
        ("Who ended the job?", "Did the employer end it, did you quit, did both agree, or did the contract expire?", "Employment ended on ___. ___ initiated it and gave the reason ___.", "Use the words from the notice or conversation."),
    ),
    "dismissal_reason": (
        ("公司给了什么理由", "单位是怎么说的，有微信、书面通知，还是只当面说？", "用人单位通过___通知解除，载明的事由为___。", "如果公司没给理由，可以直接说「只叫我别来了」。"),
        ("Reason the company gave", "What did they say, and did you get it in writing?", "The employer notified me by ___ and gave this reason for termination: ___.", "If no reason was given, say so."),
    ),
    "unpaid_span": (
        ("欠了几个月", "哪几个月少发或没发？记得几个月也可以。", "___年___月至___月工资未支付。___月另少发___元。", "可以打开银行流水，按月看哪几笔没到账。"),
        ("Which months were unpaid?", "Which months were unpaid or short? An approximate count is fine.", "Pay for ___ through ___ is outstanding. Pay in ___ was short by ___.", "Check bank deposits month by month."),
    ),
    "unpaid_total": (
        ("一共还差多少", "你提过欠薪的月份。算得出来的话，一共还差多少钱？", "按工资条与到账记录核对，___期间尚欠工资共计___元。", "如果有的月份只发了一部分，可以只说该月还差多少。"),
        ("What is still outstanding?", "If you have added it up, what is still unpaid across those months?", "For ___, the outstanding wages total ___ based on payslips and deposits.", "For a partially paid month, you can give just the shortfall."),
    ),
    "paid_days": (
        ("这个月计薪几天", "你说只干了半个月。工资条或考勤显示，本期该算工资的天数是多少？已发了多少？", "本期计薪___天，本期工资已发___元。", "可以先只写天数。拿不准时，按工资条的本期应发与已发核对。"),
        ("Paid days this month", "How many payable days did this period cover, and how much was already paid?", "This period included ___ payable days and ___ yuan already paid.", "Start with the paid days on your payslip or time records."),
    ),
    "effective_date": (
        ("合同哪天正式解除", "你说月中离开，也提到月底收到通知。公司实际从哪天解除合同？", "我最后工作至___，解除生效日期为___年___月___日。", "可以核对解除通知、工资结算或社保停缴记录。"),
        ("Effective termination date", "You describe leaving mid-month and being notified at month-end. When did the termination take effect?", "My last work day was ___. The termination took effect on ___.", "Check the notice or payroll records."),
    ),
    "injury_recognition": (
        ("工伤认定到了哪一步", "事故是在工作中发生的吗？工伤认定是尚未申请、已提交，还是已经拿到决定书？", "我于___在___受伤，工伤认定目前___。", "可先留存事故记录、病历和申请回执。"),
        ("Work injury decision", "Was the injury work-related, and have you applied for or received a decision?", "I was injured on ___ at ___. The work-injury application is ___.", "Keep the accident report, medical records and application receipt."),
    ),
    "overtime_hours": (
        ("哪天多干了几小时", "是平时下班后、周末，还是法定节假日？大概多干了多久？", "___期间，工作日延时加班合计___小时、休息日加班合计___小时、法定节假日加班合计___小时。", "先挑一周的排班表或打卡记录举例。"),
        ("When and how long?", "Was it after work, on rest days, or on public holidays? How much extra time roughly?", "For ___, I worked ___ extra workday hours, ___ rest-day hours, and ___ holiday hours.", "Start with one week of schedules or clock records."),
    ),
    "overtime_total": (
        ("一共多干了多久", "你说了平时怎么加班。方便的话，选一个时间段，把大概总时数说一下。", "从___到___，工作日延时加班合计___小时，休息日加班合计___小时，法定节假日加班合计___小时。", "可以先说每周几次、每次几小时。"),
        ("Total extra hours", "For one period, can you estimate the total extra time?", "From ___ to ___, overtime totalled ___ on workdays, and ___ on rest days or holidays.", "You can start with days per week and hours per day."),
    ),
    "overtime_rest": (
        ("周末有没有补休", "周末多干的这些天，单位后来安排你哪天休回来了吗？", "___日休息日加班___小时，用人单位已安排___日补休／尚未安排补休。", "只说实际休过的日期。"),
        ("Time off for weekend work", "Did the company let you take those weekend hours off later?", "I worked ___ hours on my rest day. Time off was scheduled for ___ / remains unscheduled.", "List any days you actually took off."),
    ),
    "leave_days": (
        ("年假还剩几天", "哪一年的年假，还有几天没休？", "___年度应享年休假___天，已休___天，尚有___天未休。", "可以看公司的请假记录，分开说每一年的天数。"),
        ("Days of leave left", "Which year and how many days of annual leave went unused?", "For ___, I was entitled to ___ annual leave days, used ___, and had ___ unused.", "Check leave records and list each year separately."),
    ),
    "signed_date": (
        ("后来哪天补签的", "你说后来补签了合同。哪天实际签字？", "我于___入职，于___实际签署书面劳动合同，合同载明的起始日期为___。", "可以分开说签字那天和合同上写的生效日期。"),
        ("When was it signed?", "On what day did you actually sign the contract?", "I started on ___, signed on ___, and the contract lists an effective date of ___.", "List the signature and effective dates separately."),
    ),
    "pregnancy_action": (
        ("单位做了什么", "单位有没有调岗、降工资、让你离开，或影响休产假？", "我在___期间，用人单位于___采取___措施，我希望解决___。", "可以从最近一次通知或工资变化说起。"),
        ("What did the employer do?", "Did the company change your job, pay, employment, or maternity leave?", "During ___, the employer did ___ on ___. I would like ___ resolved.", "Start with the latest notice or pay change."),
    ),
    "settlement_payment": (
        ("说好的给了吗", "双方当时说好给什么、哪天给？后来实际给了多少？", "双方于___达成协议，约定于___支付___元，目前已支付___元。", "有协议或聊天记录的话，看约定的付款日期。"),
        ("Was the agreement paid?", "What did both sides agree to, when was it due, and how much was paid?", "Under the agreement dated ___, ___ was due by ___. The amount paid so far is ___.", "Check the agreed payment date in the document or messages."),
    ),
    "goal": (
        ("你想要什么", "你最想先拿回工资、拿到补偿、继续上班，还是要一份证明？", "我的首要请求是___，涉及期间为___。", "有几件事可以分开说，先写对你最重要的一件。"),
        ("What do you want?", "Do you want unpaid wages, compensation, your job back, or a document?", "My main request is ___ for the period ___.", "If you have several requests, start with the most important one."),
    ),
}


def prompts_for_case(report: dict, lang: str) -> list[tuple[str, str, str, str, str]]:
    idx = int(lang != "zh")
    if report.get("issue_review"):
        return [(key, *PROMPTS[key][idx]) for key in report["issue_review"]["prompts"][:3]]
    stage = report.get("staged_review")
    if stage:
        return [
            ("", label, question, example or PROMPTS["unpaid_span"][idx][2],
             ("说出记得的情况就行，可对照排班、工资条或流水。" if not idx else
              "Describe what you remember. Schedules, payslips or deposits can help."))
            for label, question, example in staged_prompts(stage, lang)
        ]
    clarification = report.get("clarification")
    if clarification == "unclear_issue":
        return [
            ("", label, question, example, PROMPTS["goal"][idx][3] if n else PROMPTS["pregnancy_action"][idx][3])
            for n, (label, question, example) in enumerate(clarification_prompts(clarification, lang, report.get("case_goal", False)))
        ]

    intake, fields = report.get("intake", {}), report.get("fields", {})
    sources = report.get("sources", {})
    causes = set(report.get("scope", {}).get("causes", []))
    keys = []
    if "unpaid_wage" in causes and not fields.get("unpaid_wages"):
        keys.append("unpaid_total" if intake.get("wage_months") else "unpaid_span")
    if "overtime" in causes:
        has_total_hours = any(fields.get(f"overtime_{day}_hours") for day in ("workday", "restday", "holiday"))
        if not has_total_hours:
            keys.append("overtime_total" if intake.get("overtime") else "overtime_hours")
        if (intake.get("rest_day") or fields.get("overtime_restday_hours")) and not intake.get("time_off"):
            keys.append("overtime_rest")
    if "annual_leave" in causes and fields.get("unused_annual_leave_days") is None:
        keys.append("leave_days")
    if "double_wage" in causes and intake.get("late_contract") and not fields.get("contract_signed_date"):
        keys.append("signed_date")
    if causes & {"illegal_dismissal", "severance", "mutual_agreement"}:
        if not intake.get("ongoing"):
            if not fields.get("end_date") or sources.get("end_date") == "assumed":
                keys.append("dismissal_date" if "illegal_dismissal" in causes else "end_date")
            if not fields.get("termination"):
                keys.append("termination")
    if causes == {"pregnant_protection"} and not intake.get("adverse_action"):
        keys.append("pregnancy_action")
    if "mutual_agreement" in causes and not intake.get("settlement_paid"):
        keys.append("settlement_payment")
    if report.get("missing") and not fields.get("hire_date") and causes & {"illegal_dismissal", "severance", "double_wage", "mutual_agreement"}:
        keys.append("hire_date")
    if (report.get("missing") or clarification == "unpaid_amount") and not fields.get("monthly_wage") and causes - {"pregnant_protection"}:
        keys.append("gross_pay")
    if not intake.get("reason") and "illegal_dismissal" in causes:
        keys.append("dismissal_reason")
    if len(causes) > 1 and not intake.get("goal") and not keys:
        keys.append("goal")
    return [(key, *PROMPTS[key][idx]) for key in keys[:3]]
