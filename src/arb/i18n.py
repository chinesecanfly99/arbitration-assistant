"""中英文双语字典与结果本地化辅助模块（纯标准库）。

默认前端以英文展示（lang='en'），支持一键切换回中文（lang='zh'）。
英文模式下，所有 UI、城市名、计算公式、时效、三层闸门、值得性、证据、材料、
立案路径及 HR 抗辩预演均提供完整英文表达；仅在展开「Original PRC Statute」时
保留中文权威法条原文以便核对。
"""
from __future__ import annotations

import re

UI: dict[str, dict[str, str]] = {
    "en": {
        "page_title": "Labor Arbitration Console · AI & Rule Workbench",
        "brand_title": "Arbitration Console",
        "brand_pill": "Rule Engine · Zero Hallucination",
        "nav_modules": "Console Modules",
        "nav_cases": "Demo Case Library",
        "nav_specs": "Engine Specs",
        "mod_overview": "01 · Overview & AI Compare",
        "mod_statutes": "02 · Statutes & Case Map",
        "mod_defense": "03 · Deadlines & Defense",
        "mod_filing": "04 · Filing, Worth & Export",
        "spec_laws": "· 10 PRC Laws · 519 Verified Articles",
        "spec_cities": "· 5 Cities: BJ / SH / GZ / SZ / HZ",
        "spec_offline": "· Pure Python Stdlib · Offline Ready",
        "reset_btn": "Reset Console",
        "topbar_title": "Labor Arbitration Workbench & AI Comparison",
        "topbar_sub": "Deterministic legal calculation & statute verification — never guessed by an LLM",
        "pill_cities": "5 City Standards",
        "pill_laws": "519 Statutes Loaded",
        "pill_live": "Live AI Compare:",
        "pill_offline": "Rule Engine (Offline Baseline)",
        "console_head": "Case Narrative & Voice Intake",
        "clear_btn": "Clear",
        "placeholder": "Example: Hired on 2020-03-01, monthly salary 9000 RMB, no written contract, verbally fired on 2024-05-20, 5 unused annual leave days.",
        "voice_btn": "Voice Input",
        "voice_stop": "Stop Dictation",
        "voice_language": "Dictation language",
        "voice_connecting": "Connecting to dictation. Check for a microphone permission prompt in your browser.",
        "voice_listening": "Keep speaking at your own pace. When you’re done, tap Stop Dictation.",
        "voice_resuming": "Reconnecting dictation. Your transcript is still here.",
        "voice_idle": "Dictation stopped after a long pause. You can review the transcript or start speaking again.",
        "voice_finishing": "Finishing dictation…",
        "voice_done": "Check names, dates and amounts before adding the transcript.",
        "voice_relative_date": "The transcript contains a relative date. If you know the date, write it explicitly.",
        "voice_unsupported": "Dictation is unavailable in this browser. Type or use your keyboard’s microphone if available.",
        "voice_no_speech": "No speech was recognized. Check the selected language and try a short sentence.",
        "voice_not_allowed": "Microphone access is unavailable. Check site permissions or type your description.",
        "voice_no_microphone": "The browser couldn’t start a microphone. Check that one is connected and available.",
        "voice_network": "The browser couldn’t reach its speech recognition service. Try keyboard dictation.",
        "voice_timeout": "The browser did not respond in time. Try again or use keyboard dictation.",
        "voice_secure": "Browser dictation needs HTTPS or a localhost address. You can still use keyboard dictation.",
        "voice_bad_language": "This browser’s speech service doesn’t support the selected language. Try keyboard dictation.",
        "voice_failed": "Dictation couldn’t finish. Try again or use your keyboard’s microphone.",
        "voice_review": "Review transcript",
        "voice_discard": "Discard transcript",
        "voice_keyboard": "Use keyboard dictation",
        "voice_keyboard_hint": "Use your device’s dictation tool with the case description focused.",
        "voice_close": "Close voice input",
        "guide_btn": "Guided Prompts",
        "guide_open": "Show",
        "guide_close": "Collapse guide",
        "api_btn": "Live AI API",
        "compare_toggle": "Compare vs Generic AI",
        "submit_btn": "Analyze & Compare",
        "recalc_btn": "Re-Analyze",
        "guide_intro": "Choose a topic to see what details to include. Answer only what you know.",
        "guide_more": "More case topics",
        "guide_followup": "The analysis needs the following details. Add what you know and run it again.",
        "guide_continue": "Continue adding details",
        "guide_answer": "Your answer",
        "guide_example": "Example wording",
        "guide_question": "What happened, when did it happen, and what records do you have?",
        "story_add": "Add to case description",
        "story_added": "Added to your case description.",
        "api_connected_note": "Backend API loaded ({model} @ {base}). Leave blank to use it automatically, or override below:",
        "api_note": "Optional: Enter any OpenAI-compatible API key for live side-by-side LLM testing (session-only, never saved to disk):",
        "welcome_why_title": "Why a Deterministic Legal Console Beats Generic AI?",
        "welcome_why_1": "Exact Arithmetic, Never Guessed: 21.75 daily wage divisor, tiered tenure (N/2N), and 3× local average wage caps are computed by audited rules.",
        "welcome_why_2": "100% Statute Verification: Every legal citation is matched against 519 local PRC labor law articles with expandable original text.",
        "welcome_why_3": "Safety Gates & Anti-Guessing: Missing key facts trigger targeted follow-ups; out-of-scope disputes (work injury/social insurance) and win-rate requests are blocked.",
        "welcome_tip": "Select any case from the Demo Case Library on the left for an instant side-by-side comparison.",
        "welcome_city_title": "Covered City Wage Standards & Compliance Scope",
        "welcome_city_note": "For unlisted cities, eligibility, deadlines, and termination legality still work, while 3× caps and minimum wages are explicitly marked uncovered rather than guessed.",
        "welcome_foot": "Covers Mainland China labor arbitration calculation & guidance only. Not formal legal representation. Legal aid hotline: 12348.",
        "kpi_total": "Claimable Total",
        "kpi_cites": "Verified Citations",
        "kpi_deadline": "Arbitration Deadline",
        "kpi_worth": "Action Worthiness",
        "cmp_ai_title": "Generic LLM (Direct Prompt)",
        "cmp_ours_title": "This Console · Rule + Statute Engine",
        "cmp_ours_badge": "Auditable · <10ms",
        "cmp_loading": "Querying {model} in background while our rule engine already finished in {ms} ms...",
        "cmp_cite_audit": "Citation Audit:",
        "cmp_verified": "Verified",
        "cmp_unverified": "Not Found in DB",
        "total_prefix": "Estimated Claimable Amount",
        "story_label": "Case Narrative:",
        "items_title": "1. Itemized Compensation Breakdown",
        "col_item": "Claim Item",
        "col_amount": "Amount (RMB)",
        "col_formula": "Formula / Basis",
        "col_total": "Total",
        "laws_title": "2. Verified Legal Basis (Expandable Original Text)",
        "cite_ok": "Citation Verified",
        "cite_warn": "Check Citation",
        "original_text": "Original PRC Statute",
        "map_title": "Case Completeness Map",
        "ref_title": "Reference Precedents (Supreme People's Court)",
        "ref_sub": "Selected by dispute cause and factual cues. Compare carefully with your own evidence.",
        "deadlines_title": "3. Statutory Arbitration Deadlines (1-Year Rule)",
        "col_claim": "Claim",
        "col_anchor": "Start Anchor",
        "col_deadline": "Deadline",
        "col_left": "Remaining",
        "expired": "Expired",
        "days_left": "{n} days left",
        "rehearsal_title": "4. Employer Defense Rehearsal (3 Rounds)",
        "hr_says": "HR / Employer Likely Argument:",
        "hr_why": "Why It Matters:",
        "hr_counter": "How to Counter:",
        "hr_need": "Prepare Evidence:",
        "evidence_title": "5. Burden of Proof Checklist",
        "col_ev": "Evidence",
        "col_who": "Burden",
        "col_why": "Legal Reason",
        "materials_title": "6. Required Documents & Readiness",
        "ev_strength": "Evidence Strength:",
        "col_mat": "Document",
        "col_status": "Status",
        "col_how": "Purpose & Where to Obtain",
        "have": "Have",
        "missing": "Missing",
        "gates_title": "Eligibility & Jurisdiction Gates (3 Layers)",
        "gates_sub": "Layer 1: Scope -> Layer 2: Procedural Eligibility -> Layer 3: Local Wage Standard.",
        "venue_title": "7. Filing Paths & Channels",
        "worth_title": "8. Six-Dimension Action Worthiness (Not Win Probability)",
        "worth_sub": "Balances claim size, evidence, final-award rule, collectability, alternatives, and deadline urgency.",
        "col_dim": "Dimension",
        "col_score": "Score",
        "col_note": "Reasoning",
        "assumptions_title": "Assumptions Applied (Please Confirm)",
        "export_title": "Export Report & Arbitration Application",
        "dl_pdf": "Download PDF",
        "dl_print": "Print View",
        "dl_md": "Download Markdown",
        "dl_app": "Arbitration Application Draft",
        "need_more_title": "More Information Required Before Calculation",
        "need_more_sub": "Please clarify the missing required facts below (our engine refuses to guess amounts):",
        "out_scope_title": "Outside Labor Arbitration Jurisdiction",
        "out_scope_where": "Recommended Channel & Materials",
        "blocked_title": "Not Eligible to File Yet (Gate Blocked)",
        "blocked_sub": "A procedural barrier blocks filing right now — showing a fake monetary total would be misleading.",
        "blocker_label": "Hard Blocker:",
        "pending_title": "Unconfirmed Extracted Readings (Excluded from Total)",
        "pending_btn": "Confirm & Recalculate",
        "empty_err": "Please enter or dictate a case description first.",
        "days_unit": "days",
        "score_unit": "/100",
        "foot_note": "Preliminary calculation for reference only; does not constitute formal legal advice. Verify payroll & social security records before filing.",
    },
    "zh": {
        "page_title": "劳动仲裁维权助手 · 控制台",
        "brand_title": "劳动仲裁维权助手",
        "brand_pill": "规则内核 · 零幻觉控制台",
        "nav_modules": "控制台板块",
        "nav_cases": "演示案例库（点击即跑）",
        "nav_specs": "内核规格",
        "mod_overview": "01 · 总览与 AI 对比",
        "mod_statutes": "02 · 法条核验与完整度",
        "mod_defense": "03 · 时效、证据与抗辩",
        "mod_filing": "04 · 路径、值得性与导出",
        "spec_laws": "· 10 部法规 519 条原文",
        "spec_cities": "· 京沪广深杭 5 城口径",
        "spec_offline": "· 纯标准库 · 离线可用",
        "reset_btn": "重置控制台",
        "topbar_title": "案件测算与 AI 对比工作台",
        "topbar_sub": "把大白话翻译成能立案的仲裁主张 · 金额按法条规则算清、不靠模型猜",
        "pill_cities": "京沪广深杭 5 城口径",
        "pill_laws": "519 条法条已加载",
        "pill_live": "实时对比已接入：",
        "pill_offline": "纯规则内核（离线对比）",
        "console_head": "案情描述与语音录入",
        "clear_btn": "清空重填",
        "placeholder": "例如：2020年3月1日入职一家电子厂，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了，让我当天走人。我还有5天年假没休。",
        "voice_btn": "语音输入",
        "voice_stop": "停止听写",
        "voice_language": "听写语言",
        "voice_connecting": "正在连接听写服务，请留意浏览器的麦克风权限提示。",
        "voice_listening": "可以连续说一整段，中间可以停顿。说完后点「停止听写」。",
        "voice_resuming": "正在接续听写，已识别的文字会保留。",
        "voice_idle": "长时间未检测到新语音，已结束听写。你可以核对文字，或继续听写。",
        "voice_finishing": "正在结束听写…",
        "voice_done": "请核对姓名、日期和金额，再加入案情。",
        "voice_relative_date": "听写里有「去年」「上个月」这类相对日期。如果记得具体日期，请把它写清楚。",
        "voice_unsupported": "当前浏览器不支持听写。可直接打字，或使用手机键盘上的麦克风。",
        "voice_no_speech": "没有识别到语音。请确认听写语言，再试一句短话。",
        "voice_not_allowed": "无法使用麦克风。请检查网站权限，或直接打字。",
        "voice_no_microphone": "浏览器无法启动麦克风。请检查设备是否已连接、是否被占用。",
        "voice_network": "浏览器连接不上语音识别服务。可以改用系统键盘听写。",
        "voice_timeout": "浏览器的语音识别迟迟没有响应。请重试，或改用系统键盘听写。",
        "voice_secure": "网页听写需要 HTTPS，或者在本机用 localhost 或 127.0.0.1 打开。也可以使用系统键盘听写。",
        "voice_bad_language": "浏览器的语音服务不支持所选语言。可以改用系统键盘听写。",
        "voice_failed": "这次听写未完成。可以重试，或使用手机键盘上的麦克风。",
        "voice_review": "核对听写文本",
        "voice_discard": "丢弃听写文本",
        "voice_keyboard": "改用键盘听写",
        "voice_keyboard_hint": "光标已定位到案情框，请使用手机键盘的麦克风或电脑的系统听写功能。",
        "voice_close": "关闭语音面板",
        "guide_btn": "智能要素引导",
        "guide_open": "展开",
        "guide_close": "收起引导",
        "api_btn": "实时对比 API",
        "compare_toggle": "开启普通 AI 对比",
        "submit_btn": "开始测算与对比",
        "recalc_btn": "再算与对比",
        "guide_intro": "点一个相关话题，看看该补哪些细节。只填你知道的事实。",
        "guide_more": "更多案情话题",
        "guide_followup": "测算还需要补充以下信息。填入你知道的事实后，可以再算一次。",
        "guide_continue": "继续补充案情",
        "guide_answer": "你的回答",
        "guide_example": "参考句式",
        "guide_question": "发生了什么？是什么时候发生的？有哪些记录可以核对？",
        "story_add": "加入案情描述",
        "story_added": "已加入案情描述。",
        "api_connected_note": "已自动读取本地配置（{model} @ {base}），默认直接进行实时对比；如需临时替换，可在下方覆盖：",
        "api_note": "可选：填入兼容 OpenAI 协议的 API 配置进行实时大模型 PK（密钥仅用于当前会话，不落盘）：",
        "welcome_why_title": "为什么需要专业规则控制台？",
        "welcome_why_1": "钱和时效绝不让大模型估算：21.75 日薪折算、工龄分段、社平 3 倍封顶全由确定性代码计算；",
        "welcome_why_2": "每条依据回库核验原文：拒绝法条幻觉，直接给出可展开核对的法条原文；",
        "welcome_why_3": "宁可追问、绝不乱答：缺字段先问，超范围（工伤/社保）指路，问胜诉率当场拦截。",
        "welcome_tip": "点击左侧「演示案例库」中的任意案例，即可同屏查看「普通大模型 vs 本系统」对比效果。",
        "welcome_city_title": "城市口径覆盖与合规边界",
        "welcome_city_note": "未收录城市时，受案范围、时效、解除合法性照样可判，但 3 倍封顶和最低工资绝不跨城套用，会明说「未覆盖」。",
        "welcome_foot": "本工具只覆盖内地劳动争议仲裁，不构成正式法律意见。符合条件可拨 12348 申请法律援助。",
        "kpi_total": "合计可主张",
        "kpi_cites": "法条原文核验",
        "kpi_deadline": "最近仲裁时效",
        "kpi_worth": "六维值得性",
        "cmp_ai_title": "普通通用大模型（直接提问）",
        "cmp_ours_title": "本系统 · 规则 + 法条核验内核",
        "cmp_ours_badge": "可复算 · <10ms",
        "cmp_loading": "本系统规则内核已于 {ms} ms 内算清，正在后台实时请求 {model} 生成对比回答…",
        "cmp_cite_audit": "法条核验结果：",
        "cmp_verified": "核验通过",
        "cmp_unverified": "库中未查到",
        "total_prefix": "你能主张",
        "story_label": "案情原文：",
        "items_title": "一、逐项金额",
        "col_item": "项目",
        "col_amount": "金额（元）",
        "col_formula": "算法",
        "col_total": "合计",
        "laws_title": "二、法律依据（可逐条核对）",
        "cite_ok": "引用已核验",
        "cite_warn": "引用异常",
        "original_text": "原文",
        "map_title": "案件完整度",
        "ref_title": "类案参考",
        "ref_sub": "按案由与案情线索选取。请结合本人证据与案件差异阅读。",
        "deadlines_title": "三、仲裁时效",
        "col_claim": "请求",
        "col_anchor": "起算",
        "col_deadline": "截止",
        "col_left": "剩余",
        "expired": "已过期",
        "days_left": "还剩 {n} 天",
        "rehearsal_title": "四、对方会怎么反驳你（提前演一遍）",
        "hr_says": "HR 可能说：",
        "hr_why": "为什么难缠：",
        "hr_counter": "你怎么顶回去：",
        "hr_need": "要准备：",
        "evidence_title": "五、证据清单（谁举证）",
        "col_ev": "证据",
        "col_who": "谁出",
        "col_why": "为什么",
        "materials_title": "六、要带什么（材料清单 + 谁举证）",
        "ev_strength": "证据强度：",
        "col_mat": "材料",
        "col_status": "状态",
        "col_how": "为什么需要 / 怎么拿",
        "have": "有",
        "missing": "缺",
        "gates_title": "能不能申请（三道闸门）",
        "gates_sub": "第一层问「归不归仲裁管」，第二层问「你够不够格」，第三层问「数字从哪来」。",
        "venue_title": "七、去哪办（立案路径）",
        "worth_title": "八、值不值得去（六维加权）",
        "worth_sub": "这不是胜诉率，也不预测裁判结果；它把六件事放在一起，告诉你先做哪件。",
        "col_dim": "维度",
        "col_score": "分数",
        "col_note": "为什么给这个分",
        "assumptions_title": "本单采用的假设（请确认）",
        "export_title": "报告导出与仲裁申请书",
        "dl_pdf": "下载 PDF 报告",
        "dl_print": "网页版打印",
        "dl_md": "下载 Markdown",
        "dl_app": "生成仲裁申请书草稿",
        "need_more_title": "还差几个信息才能算",
        "need_more_sub": "请补充以下核心要素：",
        "out_scope_title": "这件事不归劳动仲裁管",
        "out_scope_where": "该去哪、带什么",
        "blocked_title": "现在还不能申请",
        "blocked_sub": "这不是算不出来，而是这道门现在就进不去——所以不给出假的总金额。",
        "blocker_label": "硬性障碍：",
        "pending_title": "有几项读数还没确认（本单没有采用）",
        "pending_btn": "确认后重算",
        "empty_err": "还没输入内容",
        "days_unit": "天",
        "score_unit": "/100",
        "foot_note": "本单仅根据你提供的信息做初步测算，不构成法律意见，不能代替律师。正式申请前请核对工资流水、社保记录和劳动合同原件。",
    },
}

CITY_EN = {
    "北京市": "Beijing", "北京": "Beijing",
    "上海市": "Shanghai", "上海": "Shanghai",
    "广州市": "Guangzhou", "广州": "Guangzhou",
    "深圳市": "Shenzhen", "深圳": "Shenzhen",
    "杭州市": "Hangzhou", "杭州": "Hangzhou",
}

ITEM_EN = {
    "违法解除赔偿金（2N）": "Illegal Dismissal Compensation (2N)",
    "经济补偿金（N）": "Statutory Severance (N)",
    "未签书面劳动合同二倍工资": "Double-Wage Penalty (No Written Contract)",
    "未签书面劳动合同二倍工资差额": "Double-Wage Penalty (No Written Contract)",
    "未休年休假工资": "Unused Annual Leave Pay (200% Extra)",
    "拖欠工资": "Unpaid Wages",
    "工作日加班费": "Workday Overtime Pay (150%)",
    "休息日加班费": "Rest-Day Overtime Pay (200%)",
    "法定节假日加班费": "Statutory Holiday Overtime Pay (300%)",
}

FIELD_LABEL_EN = {
    "入职日期": "Hire Date",
    "离职日期": "Termination Date",
    "月工资": "Monthly Salary",
    "离职前月均工资": "Avg Monthly Salary",
    "谁提的解除": "Termination Type",
    "解除方式": "Termination Type",
    "有没有签书面合同": "Written Contract",
    "是否签书面合同": "Written Contract",
    "工作日加班": "Workday Overtime",
    "休息日加班": "Rest-Day Overtime",
    "法定节假日加班": "Holiday Overtime",
    "加班小时数": "Overtime Hours",
    "没休的年假": "Unused Annual Leave",
    "未休年假天数": "Unused Annual Leave",
    "被拖欠的工资": "Unpaid Wages",
    "被拖欠工资": "Unpaid Wages",
    "当地社平工资": "Local Avg Wage",
}

FIELD_VAL_EN = {
    "没签": "Not Signed",
    "签了": "Signed",
    "已签": "Signed",
    "illegal_dismissal": "Illegal Dismissal",
    "mutual_agreement": "Mutual Agreement",
    "employee_resign": "Employee Resignation",
    "legal_termination": "Lawful Termination",
}

FIELD_HINT_EN = {
    "入职日期": "e.g., Hired on 2020-03-01",
    "离职日期": "e.g., Fired on 2024-05-20",
    "月工资": "e.g., Monthly salary 9000",
    "谁提的解除": "e.g., Verbally fired / resigned",
    "有没有签书面合同": "e.g., No written contract",
    "工作日加班": "Optional: weekday overtime hours",
    "休息日加班": "Optional: weekend overtime hours",
    "法定节假日加班": "Optional: holiday overtime hours",
    "没休的年假": "Optional: 5 unused annual leave days",
    "被拖欠的工资": "Optional: unpaid wages 10000",
}

FILL_TEMPLATE_EN = {
    "入职日期": "Hired on 2020-03-01",
    "离职日期": "Fired on 2024-05-20",
    "月工资": "monthly salary 9000",
    "谁提的解除": "verbally fired by the company",
}

BURDEN_EN = {
    "单位": "Employer Burden",
    "双方": "Both Parties",
    "你": "Claimant",
    "申请人": "Claimant",
}

DECISION_EN = {
    "recommend": "Recommended to File Arbitration",
    "better_alternative": "Consider Faster Alternative First",
    "not_recommended": "Low Priority / Evaluate Cost First",
}

DEADLINE_EN = {
    "dismissal": ("Dismissal / Severance Claims (N / 2N)", "Date of termination notice"),
    "wage": ("Unpaid Wages", "Scheduled payday (or termination date)"),
    "overtime": ("Overtime Pay", "Scheduled overtime payday"),
    "annual_leave": ("Unused Annual Leave Pay", "End of labor relationship"),
    "double_wage": ("Double-Wage Penalty (No Contract)", "Month contract was due"),
}

WORTH_DIM_EN = {
    "amount_cost": ("Claim Size vs Cost", "Claim amount is substantial relative to filing cost (arbitration is free)"),
    "evidence": ("Evidence Strength", "Score based on evidence currently mentioned; improves once checklist is gathered"),
    "one_final": ("Final-Award Threshold", "Depends on local minimum wage × 12; restricts employer appeal rights"),
    "enforcement": ("Collectability", "Verify employer registration & solvency via e-Business License before filing"),
    "alternative": ("Faster Alternatives", "Evaluates mediation or labor inspection vs formal arbitration"),
    "urgency": ("Limitation Urgency", "Prioritized by remaining 1-year arbitration filing window"),
}

LAW_NAME_EN = {
    "劳动合同法": "PRC Labor Contract Law",
    "劳动法": "PRC Labor Law",
    "劳动争议调解仲裁法": "PRC Labor Dispute Mediation & Arbitration Law",
    "最高人民法院关于审理劳动争议案件适用法律问题的解释（一）": "SPC Labor Dispute Interpretation (I)",
    "最高人民法院关于审理劳动争议案件适用法律问题的解释（二）": "SPC Labor Dispute Interpretation (II)",
    "劳动争议司法解释（一）": "SPC Labor Dispute Interpretation (I)",
    "劳动争议司法解释（二）": "SPC Labor Dispute Interpretation (II)",
    "职工带薪年休假条例": "Paid Annual Leave Regulations",
    "企业职工带薪年休假实施办法": "Annual Leave Implementation Measures",
    "工资支付暂行规定": "Interim Provisions on Wage Payment",
    "劳动合同法实施条例": "Labor Contract Law Impl. Regulations",
    "社会保险法": "PRC Social Insurance Law",
}

STATUTE_TEXT_EN: dict[str, str] = {
    "《劳动合同法》第八十七条": (
        "Where an employer terminates or ends a labor contract in violation of this Law, "
        "it shall pay damages to the employee at twice the statutory severance standard prescribed in Article 47."
    ),
    "《劳动合同法》第八十二条": (
        "Where an employer fails to conclude a written labor contract with an employee for more than one month "
        "but less than one year from the date employment begins, it shall pay double the employee's monthly wage each month."
    ),
    "《劳动争议司法解释（二）》第六条": (
        "Where an employer fails to conclude a written labor contract as required by law, the double-wage penalty "
        "shall be calculated on a monthly basis; for periods under one month, it shall be pro-rated by actual working days."
    ),
    "《职工带薪年休假条例》第五条": (
        "Where an employer is genuinely unable to arrange annual leave due to work needs and obtains the employee's consent, "
        "it may forego arranging leave and pay 300% of the employee's daily wage income for each unused annual leave day."
    ),
    "《企业职工带薪年休假实施办法》第十条": (
        "For unused annual leave days, the employer shall pay 300% of daily wage income within the current year "
        "(which includes the 100% normal wage already paid for workdays, i.e., 200% extra compensation)."
    ),
    "《劳动法》第五十条": (
        "Wages shall be paid directly to the employee in monetary form on a monthly basis. "
        "Employers must not deduct from or delay payment of wages without justification."
    ),
    "《劳动合同法》第四十七条": (
        "Statutory severance (N) is paid at 1 month's wage per full year of service (6+ months counts as 1 year; "
        "under 6 months pays 0.5 month). Where monthly wage exceeds 3× the local prior-year average wage, "
        "the base is capped at 3× that average and compensable years are capped at 12 years."
    ),
    "《劳动法》第四十四条": (
        "Overtime pay floors: (1) ≥150% of normal wage for extended weekday work hours; "
        "(2) ≥200% for rest-day work when compensatory time off cannot be arranged; "
        "(3) ≥300% for work on statutory public holidays."
    ),
    "《劳动合同法》第四十六条": (
        "An employer shall pay statutory severance (N) where employment ends due to mutual agreement proposed by the employer (Art. 36), "
        "employee termination for employer fault (Art. 38), non-fault termination (Art. 40), economic layoff (Art. 41), or fixed-term expiration without renewal."
    ),
}

REF_CASES_EN: dict[str, dict[str, str]] = {
    "spc-319151-1": {
        "title": "Dismissal After Refusing Excessive Overtime",
        "focus": "Can refusing excessive overtime be grounds for termination during probation?",
        "result": "The courier company's fixed shifts far exceeded statutory limits. The arbitration commission ruled that refusing unlawful overtime does not prove failure to meet hiring standards and awarded illegal dismissal compensation (2N).",
        "compare": "Verify the stated dismissal reason, work schedule records, and written notices.",
        "distinguish": "Involves probation and severe overtime; different dismissal grounds or work-hour systems may change the outcome.",
        "source": "SPC & MHRSS Typical Labor Dispute Cases (Batch 2), Case 1",
    },
    "spc-319151-6": {
        "title": "Cross-Corroborating Punch Logs & Wage Deduction Records",
        "focus": "How can an employee prove overtime when attendance data is held by the employer?",
        "result": "Real-name punch records and wage-deduction slips corroborated each other, while the employer failed to produce custody records in rebuttal. Overtime pay was awarded.",
        "compare": "Check whether punch logs, shift rosters, task outputs, and payslips align.",
        "distinguish": "Entry/exit logs alone require proof of actual assigned work; recovery depends on specific overtime hours.",
        "source": "SPC & MHRSS Typical Labor Dispute Cases (Batch 2), Case 6",
    },
    "spc-423922-6": {
        "title": "After-Hours Work Completed via WeChat",
        "focus": "How is fragmented online work after hours recognized as overtime?",
        "result": "Based on WeChat logs, work deliverables, and salary records, the court awarded discretionary extended-hours overtime pay and rest-day overtime pay where evidenced.",
        "compare": "Check specific after-hours tasks assigned, completion timestamps, and delivery records.",
        "distinguish": "Online workload and duration vary case by case; discretionary sums cannot be mechanically copied.",
        "source": "SPC, MHRSS & ACFTU Typical Wage-Arrears Case 6",
    },
    "spc-472681-3": {
        "title": "Employee Repeatedly Refused Written Contract Renewal",
        "focus": "Does an employee's refusal to renew affect a double-wage penalty claim?",
        "result": "After the initial contract expired, the employer continued paying wages/social insurance and repeatedly requested renewal, which the employee intentionally refused. Double-wage penalty was denied.",
        "compare": "Verify whether a prior contract existed, when renewal was requested, and communication records.",
        "distinguish": "Applies to renewal after expiration with proven bad-faith refusal, unlike initial onboarding where no contract was ever offered.",
        "source": "SPC Typical Labor Dispute Cases (Aug 1, 2025), Case 3",
    },
    "spc-guiding-179": {
        "title": "Cooperation Agreement Containing Essential Labor Contract Terms",
        "focus": "Can an agreement titled 'Cooperation Agreement' count as a written labor contract?",
        "result": "In Guiding Case No. 179, the court examined actual employment and contract clauses. Because job duties, pay, and term were already agreed in writing, double wages for no written contract were denied.",
        "compare": "Inspect all signed agreements for clauses covering duties, compensation, and duration.",
        "distinguish": "Requires an existing written instrument containing statutory contract terms; absent any signed agreement, analyze separately.",
        "source": "SPC Guiding Case No. 179",
    },
    "spc-450661-3": {
        "title": "Employer Repudiated Written Arrears Repayment Plan",
        "focus": "If an employer explicitly refuses a signed arrears payment plan, can unmatured installments be claimed immediately?",
        "result": "The court upheld the repayment agreement, found anticipatory breach by the employer's explicit refusal, and ordered full payment of the unpaid wages.",
        "compare": "Verify arrears periods, written acknowledgments, agreed due dates, and proof of refusal.",
        "distinguish": "Involves a valid payment plan plus explicit repudiation; ongoing installment plans require case-by-case review.",
        "source": "SPC Typical Wage-Arrears Case 3",
    },
    "spc-507531-3": {
        "title": "Military Service Years Omitted from Annual Leave Calculation",
        "focus": "How does prior active military service count toward cumulative work years for annual leave?",
        "result": "Based on discharge/service records, the court included military service in cumulative tenure and ordered compensation for unused annual leave.",
        "compare": "Verify cumulative tenure proof, service certificates, and historical leave logs.",
        "distinguish": "Specifically concerns documented military service; leave tiers and balances must be verified individually.",
        "source": "SPC Typical Judicial Protection Cases for Military Personnel, Case 3",
    },
}

OUT_SCOPE_EN = {
    "工伤": (
        "Work-related injury determination & disability grading must be handled first by the Human Resources and Social Security Bureau (HRSSB), not directly by labor arbitration.",
        "Submit work-injury determination application at local HRSSB within 1 year of the accident. Bring: accident report, proof of employment, medical records & invoices.",
    ),
    "社保补缴": (
        "Social insurance arrears collection is an administrative matter outside arbitration scope.",
        "File a complaint with the local Social Insurance Collection Agency or call 12333. Bring: labor contract, bank payroll statements, social insurance logs.",
    ),
    "公积金": (
        "Housing provident fund disputes fall under administrative enforcement rather than labor arbitration.",
        "Report to the local Housing Provident Fund Management Center with your labor contract and payroll statements.",
    ),
}


def t(lang: str, key: str, **kw) -> str:
    d = UI["zh"] if lang == "zh" else UI["en"]
    val = d.get(key, UI["en"].get(key, key))
    return val.format(**kw) if kw else val


def tr_city(lang: str, name: str) -> str:
    if lang == "zh":
        return name
    return CITY_EN.get(name, name)


def tr_item(lang: str, name: str) -> str:
    if lang == "zh":
        return name
    return ITEM_EN.get(name, name)


def tr_formula(lang: str, formula: str) -> str:
    if lang == "zh":
        return formula
    s = formula
    s = re.sub(r"本单位\s*(\d+)\s*个月工龄折算", r"\1 mo tenure converted", s)
    s = re.sub(r"共\s*(\d+)\s*天，上限\s*(\d+)\s*个月", r"\1 days, capped at \2 mo", s)
    s = re.sub(r"上限\s*(\d+)\s*个月", r"capped at \1 mo", s)
    s = re.sub(r"按\s*3\s*倍社平封顶[^）)]*", "capped at 3× local avg wage", s)
    for cn, en in (
        ("元/月", "RMB/mo"),
        ("元/天", "RMB/day"),
        ("元/小时", "RMB/hr"),
        ("欠发金额", "Unpaid amount"),
        ("元", "RMB"),
        ("个月", "mo"),
        ("天", "days"),
        ("小时", "hrs"),
        ("至", "to"),
        ("（", " ("),
        ("）", ")"),
    ):
        s = s.replace(cn, en)
    return re.sub(r"\s{2,}", " ", s).strip()


_CN_DIG = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _art_num(s: str) -> str:
    s = s.strip()
    if s.isdigit():
        return s
    total, cur = 0, 0
    for ch in s:
        if ch in _CN_DIG:
            cur = _CN_DIG[ch]
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        elif ch == "百":
            total += (cur or 1) * 100
            cur = 0
    return str(total + cur) if (total + cur) > 0 else s


def tr_basis(lang: str, basis: str) -> str:
    if lang == "zh":
        return basis
    parts = []
    for seg in re.split(r"[、，,]+", basis or ""):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"《([^》]+)》第\s*([零一二两三四五六七八九十百\d]+)\s*条", seg)
        if m:
            lname = LAW_NAME_EN.get(m.group(1), m.group(1))
            parts.append(f"{lname}, Art. {_art_num(m.group(2))}")
        else:
            parts.append(seg)
    return " · ".join(parts) if parts else basis


def tr_field_label(lang: str, label: str) -> str:
    if lang == "zh":
        return label
    return FIELD_LABEL_EN.get(label, label)


def tr_field_value(lang: str, value: str) -> str:
    if lang == "zh":
        return value
    return FIELD_VAL_EN.get(value, value)


def tr_field_hint(lang: str, label: str, hint: str) -> str:
    if lang == "zh":
        return hint.replace("例如：", "").replace("可选：", "")
    return FIELD_HINT_EN.get(label, hint)


def tr_fill_text(lang: str, label: str, hint: str) -> str:
    if lang == "zh":
        return hint
    return FILL_TEMPLATE_EN.get(label, hint)


def tr_map_summary(lang: str, text: str) -> str:
    if lang == "zh":
        return text
    if "可以算了" in text:
        return "All required facts collected — ready to calculate."
    return "Some required facts are missing — please complete the highlighted fields."


def tr_decision(lang: str, decision: str, fallback: str) -> str:
    if lang == "zh":
        return fallback
    return DECISION_EN.get(decision, fallback)


def tr_deadline(lang: str, d: dict) -> tuple[str, str]:
    if lang == "zh":
        return d.get("label") or "", str(d.get("anchor") or "")
    lbl, hint = DEADLINE_EN.get(d.get("claim_type") or "", (d.get("label") or "", ""))
    anchor = str(d.get("anchor") or "")
    return lbl, f"{anchor} ({hint})" if hint else anchor


def tr_worth_dim(lang: str, d: dict) -> tuple[str, str]:
    if lang == "zh":
        return d.get("label") or "", d.get("note") or ""
    lbl, note = WORTH_DIM_EN.get(d.get("key") or "", (d.get("label") or "", d.get("note") or ""))
    return lbl, note


def tr_worth_level(lang: str, level: str) -> str:
    if lang == "zh":
        return level
    return {"强": "Strong", "中等": "Moderate", "偏弱": "Weak", "未评估": "Not Assessed"}.get(level, "Moderate")


def tr_gate(lang: str, idx: int, g: dict) -> tuple[str, str, list[str]]:
    if lang == "zh":
        return g.get("title") or "", g.get("message") or "", list(g.get("detail") or [])
    if idx == 0:
        return (
            "Layer 1 · Arbitration Jurisdiction Scope",
            "Covered under Art. 2 of the PRC Labor Dispute Mediation & Arbitration Law (contract formation, termination, wages, and statutory leave).",
            [],
        )
    if idx == 1:
        st = g.get("status")
        msg = (
            "Blocked — a hard procedural obstacle prevents filing right now."
            if st == "fail" else (
                "Eligible to file (please verify limitation & local city standard)."
                if st == "warn" else "Eligible to file."
            )
        )
        details = []
        for item in g.get("detail") or []:
            if "时效" in item:
                details.append("1-year limitation notice: arbitration commissions do not reject expired claims unless the employer raises a limitation defense.")
            elif "用工所在地" in item or "城市" in item:
                details.append("Local city wage standard not specified — 3× cap and minimum wage rules depend on workplace city.")
            elif "管辖" in item:
                details.append("Dual-city jurisdiction detected — you may choose either workplace or company registration city.")
            else:
                details.append("Procedural check passed.")
        return "Layer 2 · Procedural Eligibility", msg, details
    return (
        "Layer 3 · Calculation & Citation Provenance",
        "All amounts computed by deterministic rules; every legal basis verified against the 519-article local PRC law DB.",
        ["Local 3× cap uses prior-year employee avg wage.", "Final-award threshold = 12 × local monthly minimum wage."],
    )


def tr_question(lang: str, q: str) -> str:
    if lang == "zh":
        return q
    if "入职" in q:
        return "When were you hired? (YYYY-MM-DD or YYYY-MM)"
    if "离开" in q or "解除" in q and "哪一天" in q:
        return "What was your termination / last working date?"
    if "工资" in q:
        return "What was your average pre-tax monthly salary?"
    if "辞退" in q or "辞职" in q:
        return "How did employment end (fired by employer, mutual agreement, or resignation)?"
    return "Please provide the missing case details."


def tr_scope_out(lang: str, report: dict) -> tuple[str, str, list[str]]:
    if lang == "zh":
        return (
            report["scope"].get("reason") or "",
            report.get("redirect") or "请补充更多细节",
            list(report.get("hints") or []),
        )
    cause = report["scope"].get("cause") or ""
    if cause in OUT_SCOPE_EN:
        reason, redir = OUT_SCOPE_EN[cause]
        return reason, redir, ["Prepare labor relationship proof and official records before visiting the agency."]
    if cause == "red_line":
        return (
            "Compliance Guardrail: This console refuses to predict win-rate percentages or advise fabricating evidence.",
            "Please submit objective facts (dates, salary, termination notice) to evaluate statutory claims and evidence gaps.",
            ["Focus on gathering written notice, payroll bank statements, and attendance logs."],
        )
    return (
        "Cannot identify a concrete labor dispute claim from the text.",
        "Describe hire date, termination date, monthly salary, and how employment ended.",
        ["Example: Hired on 2020-03-01, salary 9000, verbally fired on 2024-05-20."],
    )


def tr_evidence_summary(lang: str, total: int, employer_n: int) -> str:
    if lang == "zh":
        return f"共 {total} 项：其中 {employer_n} 项可要求单位提供，{total - employer_n} 项需自行准备。"
    return f"{total} evidence items total: {employer_n} under employer burden of proof (Art. 6), {total - employer_n} prepared by claimant."


def tr_evidence_row(lang: str, r: dict) -> tuple[str, str, str]:
    if lang == "zh":
        who_lbl = {"单位": "单位举证", "双方": "双方", "你": "你自己准备"}.get(r["who"], r["who"])
        return r["name"], who_lbl, r["why"]
    name_map = {
        "解除/终止通知书原件": "Written Termination Notice",
        "离职证明": "Separation Certificate",
        "工资流水 / 银行转账记录": "Bank Payroll Statements",
        "考勤记录 / 打卡记录": "Attendance & Punch Logs",
        "考勤原始记录": "Original Attendance / Punch Logs",
        "劳动合同原件": "Original Labor Contract",
        "社保缴费记录": "Social Insurance Payment History",
        "社保停缴月份": "Social Security Termination Month",
        "最后一个月工资流水": "Final Month Bank Payroll Statement",
        "工作交接单": "Handover Record",
        "录音 / 微信聊天记录": "Chat Logs / Audio Recordings",
        "当时的沟通记录（微信 / 邮件 / 录音）": "Communication Logs (WeChat / Email / Audio)",
        "停工/调岗通知": "Suspension / Job-Transfer Notice",
        "离职协议原件（含签署页）": "Signed Separation Agreement (Original)",
        "协议签署前后聊天记录": "Chat Logs Around Agreement Signing",
        "已实际收到的款项凭证": "Receipts of Payments Already Received",
        "劳动关系证明（合同/工资流水/社保记录/工牌/工作群）": "Proof of Employment (Contract / Payroll / Social Security / Badge / Work Group)",
        "年假审批/剩余记录": "Annual Leave Approval & Balance Logs",
        "加班审批/加班记录": "Overtime Approval & Work Logs",
    }
    disp = name_map.get(r["name"])
    if not disp:
        if "劳动关系" in r["name"]:
            disp = "Proof of Employment (Contract / Payroll / Social Security / Badge)"
        elif "银行" in r["name"] or "工资" in r["name"]:
            disp = "Bank Payroll & Wage Records"
        elif "考勤" in r["name"] or "打卡" in r["name"]:
            disp = "Attendance & Timekeeping Logs"
        elif "聊天" in r["name"] or "录音" in r["name"] or "沟通" in r["name"]:
            disp = "Chat Logs / Email / Audio Recordings"
        elif "社保" in r["name"]:
            disp = "Social Insurance Contribution Records"
        elif "年假" in r["name"]:
            disp = "Annual Leave Approval & Balance Logs"
        elif "加班" in r["name"]:
            disp = "Overtime Approval & Work Logs"
        elif "合同" in r["name"]:
            disp = "Employment Contract / Onboarding Proof"
        elif "手册" in r["name"] or "制度" in r["name"] or "考核" in r["name"] or "岗位" in r["name"]:
            disp = "Employee Handbook, Job Description & Performance Rules"
        elif "调岗" in r["name"] or "转主体" in r["name"]:
            disp = "Job-Transfer / Entity-Change Notice"
        elif "年终奖" in r["name"] or "个税" in r["name"] or "纳税" in r["name"]:
            disp = "Annual Bonus & Tax Income Records"
        else:
            disp = r["name"]
    who_en = BURDEN_EN.get(r["who"], "Claimant")
    why_en = (
        "Employer bears statutory burden under Art. 6 of Arbitration Law"
        if r["who"] == "单位" else "Claimant should collect & submit"
    )
    return disp, who_en, why_en


def tr_material_row(lang: str, m: dict) -> tuple[str, str, str]:
    if lang == "zh":
        return m["name"], m["purpose"], f'{m["burden"]} · {m["how"]}'
    mat_map = {
        "劳动人事争议仲裁申请书": ("Labor Arbitration Application", "Required filing form", "Prepare N+1 copies; filing is free"),
        "身份证原件 + 复印件": ("ID Card (Original + Copy)", "Identity verification", "Verify original at counter, submit copy"),
        "用人单位工商登记信息（全称、统一社会信用代码、存续状态）": ("Employer Business Registration Info", "Required to identify respondent", "Query via e-Business License mini-program"),
    }
    if m["name"] in mat_map:
        return mat_map[m["name"]]
    is_emp = "单位" in m["burden"]
    n, _, w = tr_evidence_row(lang, {"name": m["name"], "who": "单位" if is_emp else "你", "why": ""})
    how_en = "Employer custody — request commission retrieval if withheld" if is_emp else "Claimant preparation — keep originals & copies"
    return n, w, f'{BURDEN_EN.get(m["burden"], "Employer & Claimant")} · {how_en}'


def tr_venue_block(lang: str, b: dict) -> tuple[str, str, str, str]:
    if lang == "zh":
        return b["stage"], b["name"], b.get("where") or "", b.get("note") or ""
    st = b["stage"]
    if "主路径" in st or "①" in st:
        return (
            "1. Primary Path · Labor Arbitration",
            "Labor & Personnel Dispute Arbitration Commission (Workplace or Company Registration City)",
            "Choose either actual workplace city or registered business address",
            "Filing labor arbitration is free. Call 12333 to confirm local jurisdiction before visiting.",
        )
    if "网上" in st or "②" in st:
        return (
            "2. Online Pre-Filing",
            "Local Online Arbitration Portal / WeChat Mini-Program",
            "Submit application & scans online first to save trips",
            "Available in supported cities (Beijing / Shanghai / Guangzhou / Shenzhen / Hangzhou).",
        )
    if "起诉" in st or "③" in st:
        return (
            "3. Court Litigation (If Appealing Award)",
            "Primary People's Court (Labor Dispute First Instance)",
            "WeChat Mini-Program: People's Court Online Service",
            "File within 15 days of receiving arbitration award; court fee is RMB 10.",
        )
    if "撤销" in st or "④" in st:
        return (
            "4. Employer Award-Revocation Check",
            "Intermediate People's Court (Final-Award Cases Only)",
            "Employer may only seek revocation within 30 days on statutory procedural grounds",
            "Informational only — applies to final-award threshold cases.",
        )
    if "监察" in st or "⑤" in st:
        return (
            "5. Labor Inspection (Parallel Administrative Track)",
            "Local Labor Security Supervision Brigade (Hotline 12333)",
            "Fast-track administrative enforcement for unpaid wages",
            "Can run alongside arbitration for clear wage arrears.",
        )
    return (
        "6. Legal Aid Fallback",
        "12348 Public Legal Aid Center",
        "Free lawyer consultation & representation for eligible workers",
        "Call 12348 hotline for free procedural assistance.",
    )


def tr_rehearsal_round(lang: str, rd: dict) -> dict[str, Any]:
    if lang == "zh":
        return rd
    hr = rd["hr_says"]
    if "自己提出" in hr or "辞职" in hr:
        return {
            "hr_says": "You resigned voluntarily — this was not a dismissal.",
            "why": "If classified as voluntary resignation, 2N and N severance drop to zero.",
            "counter": "Show who initiated termination: written notice stamp, social-security stop reason, and separation certificate.",
            "need": ["Written Termination Notice", "Separation Certificate", "Payroll & Social Security Logs"],
        }
    if "严重违纪" in hr or "制度" in hr:
        return {
            "hr_says": "You violated company rules, so dismissal was lawful without compensation.",
            "why": "Employers often cite handbook clauses retroactively to avoid paying 2N.",
            "counter": "Employer bears full burden to prove valid democratic handbook adoption, employee acknowledgment, and proportional misconduct.",
            "need": ["Employee Handbook", "Acknowledgment Receipt", "Disciplinary Notice"],
        }
    return {
        "hr_says": "Your calculation is too high — bonuses or allowances don't count, or claims expired.",
        "why": "Attempts to shrink the wage base or assert procedural expiration.",
        "counter": "Art. 47 uses full pre-tax 12-month average earnings (including regular bonuses/allowances); limitation defense must be proven by employer.",
        "need": ["12-Month Bank Payroll Statements", "Tax App Income Records", "Payslips"],
    }


def tr_ref_case(lang: str, case: dict) -> dict[str, str]:
    if lang == "zh":
        return case
    tr = REF_CASES_EN.get(case.get("id") or "")
    if not tr:
        return case
    return {**case, **tr}


def tr_statute_text(lang: str, cite: str, zh_text: str) -> str:
    if lang == "zh":
        return zh_text
    return STATUTE_TEXT_EN.get(cite, zh_text)


CHIP_GROUP_EN: dict[str, str] = {
    "离职": "Termination & Exit",
    "工资": "Wages & Overtime",
    "合同": "Contracts",
    "工时": "Hours & Leave",
    "证据": "Evidence & Procedure",
    "特殊": "Special Cases",
}

CHIPS_EN: dict[str, dict[str, str]] = {
    "违法解除劳动合同": {
        "term": "illegal dismissal",
        "plain": "Employer fired you without a lawful reason or proper statutory procedure.",
        "when": "Sudden verbal firing, told to leave immediately without written notice.",
        "why": "Determines whether you claim 2N damages instead of 1N severance.",
    },
    "经济补偿金": {
        "term": "severance (N)",
        "plain": "Statutory severance based on years of service when terminated lawfully.",
        "when": "Mutual termination, layoffs, or contract expiration without renewal.",
        "why": "Calculated on 12-month average pre-tax wage, not just base salary.",
    },
    "赔偿金（2N）": {
        "term": "double severance (2N)",
        "plain": "Twice the statutory severance (N) for wrongful or illegal termination.",
        "when": "Dismissed without lawful grounds or required procedures.",
        "why": "2N and N cannot be claimed together; only one applies.",
    },
    "代通知金": {
        "term": "pay in lieu of notice (+1N)",
        "plain": "One extra month's wage if employer skipped the mandatory 30-day advance notice.",
        "when": "Non-fault dismissal (e.g., incompetence/medical expiry) without 30-day notice.",
        "why": "Often overlooked; equals one full month's salary.",
    },
    "被迫离职（劳动者解除）": {
        "term": "constructive dismissal",
        "plain": "Resigning because the employer failed to pay wages or social insurance on time.",
        "when": "Leaving due to employer breach without forfeiting severance.",
        "why": "Still entitles you to statutory 1N severance under Art. 38.",
    },
    "离职证明": {
        "term": "separation certificate",
        "plain": "Written proof of employment dates and termination issued at exit.",
        "when": "Employer withholds the certificate or states an untrue exit reason.",
        "why": "Needed for your next job and unemployment benefits.",
    },
    "失业保险金": {
        "term": "unemployment benefits",
        "plain": "Statutory allowance for involuntary job loss.",
        "when": "Fired or contract non-renewal (usually unavailable for voluntary resignation).",
        "why": "Separate from arbitration, but affected by recorded termination reason.",
    },
    "拖欠工资": {
        "term": "unpaid wages",
        "plain": "Unpaid base pay, bonuses, or commissions owed for work already performed.",
        "when": "Salary delayed past payday or unpaid upon departure.",
        "why": "Protected from the 1-year limitation while employment is ongoing.",
    },
    "加班费": {
        "term": "overtime pay",
        "plain": "150% for weekday overtime, 200% for weekends, 300% for public holidays.",
        "when": "Supported by punch logs, rosters, or work chat assignments.",
        "why": "Uses the statutory 21.75-day monthly divisor.",
    },
    "未休年休假工资": {
        "term": "unused annual leave",
        "plain": "Unused statutory paid annual leave compensated at 200% extra daily wage.",
        "when": "Leave balance remains unused at exit or denied by employer.",
        "why": "Just specify how many days remain unused.",
    },
    "最低工资标准": {
        "term": "below minimum wage",
        "plain": "Monthly pay below the local government's statutory minimum wage floor.",
        "when": "Take-home base pay is lower than local minimum standards.",
        "why": "Used to test wage compliance and final-award thresholds.",
    },
    "工资条/银行流水": {
        "term": "bank payroll statements",
        "plain": "Bank transfer records and payslips proving actual monthly income.",
        "when": "Employer claims your salary was lower than stated.",
        "why": "Establishes the true pre-tax 12-month average wage base.",
    },
    "未签书面劳动合同二倍工资": {
        "term": "no written contract",
        "plain": "Double-wage penalty from month 2 to month 12 (max 11 months) if no contract was signed.",
        "when": "Never signed a contract, or employer took both copies back.",
        "why": "Just state no written contract was signed; engine calculates up to 11 months.",
    },
    "无固定期限劳动合同": {
        "term": "open-ended contract",
        "plain": "Mandatory permanent contract after 10+ years or two consecutive fixed contracts.",
        "when": "Employer refused to sign an open-ended contract when legally required.",
        "why": "May trigger double-wage penalties and stricter dismissal protection.",
    },
    "试用期": {
        "term": "probation period",
        "plain": "Capped at 1–6 months depending on contract term; cannot fire arbitrarily.",
        "when": "Overlong probation or abrupt dismissal during probation.",
        "why": "Employer must still prove failure to meet documented hiring criteria.",
    },
    "竞业限制": {
        "term": "non-compete clause",
        "plain": "Post-exit restriction requiring monthly compensation from the employer.",
        "when": "Employer enforces non-compete without paying monthly allowance.",
        "why": "3 months of non-payment allows you to terminate the restriction.",
    },
    "劳动合同变更": {
        "term": "unilateral demotion/transfer",
        "plain": "Job transfer, pay cut, or relocation without mutual written agreement.",
        "when": "Employer forces resignation via unilateral demotion or pay cut.",
        "why": "Often treated as constructive or illegal dismissal.",
    },
    "标准工时制": {
        "term": "standard work hours",
        "plain": "8 hours/day, 40 hours/week; anything beyond counts as overtime.",
        "when": "Employer claims flexible hours without government approval.",
        "why": "Special work-hour systems require official labor bureau approval.",
    },
    "考勤记录": {
        "term": "attendance logs",
        "plain": "Punch-card, biometric, or shift schedule records.",
        "when": "Employer withholds attendance records or denies overtime.",
        "why": "Employer bears statutory burden to produce records under its custody.",
    },
    "病假/医疗期": {
        "term": "sick leave / medical period",
        "plain": "Protected statutory medical treatment period with sick-leave pay.",
        "when": "Fired while on approved medical leave.",
        "why": "Dismissal during statutory medical period is generally unlawful.",
    },
    "工伤": {
        "term": "work injury",
        "plain": "Injury suffered during work hours at the workplace due to work duties.",
        "when": "Injured at factory, site, or during work commute.",
        "why": "Handled first by HRSSB for injury determination, not directly by arbitration.",
    },
    "举证责任": {
        "term": "burden of proof",
        "plain": "Employer must produce payroll, attendance, and dismissal records it holds.",
        "when": "Employer claims you lack internal company records.",
        "why": "Shifts key evidence risk onto the employer under Art. 6.",
    },
    "录音证据": {
        "term": "audio recording",
        "plain": "Unedited recording of a conversation you personally participated in.",
        "when": "Verbal firing or oral settlement promises.",
        "why": "Strong corroboration for undocumented oral dismissal.",
    },
    "微信/钉钉记录": {
        "term": "WeChat / DingTalk chat logs",
        "plain": "Work group messages showing task assignments or dismissal notices.",
        "when": "Employer assigns work or fires staff via messaging apps.",
        "why": "Keep original device data rather than screenshots alone.",
    },
    "劳动仲裁申请书": {
        "term": "arbitration application",
        "plain": "Formal written petition listing claims, amounts, and factual grounds.",
        "when": "Preparing to file with the local arbitration commission.",
        "why": "Can be exported directly as a draft from Tab 04.",
    },
    "仲裁时效": {
        "term": "1-year limitation",
        "plain": "1-year filing deadline from when you knew your rights were infringed.",
        "when": "Long gap since leaving the employer.",
        "why": "Employer may raise a limitation defense if expired.",
    },
    "管辖": {
        "term": "jurisdiction venue",
        "plain": "Arbitration commission at either workplace or company registration city.",
        "when": "Workplace and company HQ are in different cities.",
        "why": "You have the statutory right to choose the more favorable venue.",
    },
    "一裁终局": {
        "term": "final arbitration award",
        "plain": "Small claims (≤ 12× local monthly min wage) are final for the employer.",
        "when": "Checking if employer can appeal the award to court.",
        "why": "Restricts employer delay tactics on smaller claims.",
    },
    "法律援助": {
        "term": "legal aid (12348)",
        "plain": "Free public legal representation for eligible workers.",
        "when": "Need free lawyer assistance for filing or hearing.",
        "why": "Call 12348 or apply at the local legal aid center.",
    },
    "三期女职工": {
        "term": "pregnancy/maternity protection",
        "plain": "Special dismissal protection during pregnancy, maternity, and nursing.",
        "when": "Dismissed, demoted, or pay-cut while pregnant or nursing.",
        "why": "Termination during this period is almost always illegal (2N).",
    },
    "劳务派遣": {
        "term": "labor dispatch",
        "plain": "Employed by a staffing agency while working at a host company.",
        "when": "Returned by host company or unpaid by agency.",
        "why": "Agency and host company may bear joint liability.",
    },
    "关联公司/换主体": {
        "term": "affiliated company transfer",
        "plain": "Employer asks you to re-sign under a sister entity.",
        "when": "Entity switched without resetting actual job duties.",
        "why": "Prior tenure must carry over continuously if transfer wasn't your choice.",
    },
    "退休返聘": {
        "term": "re-employed retiree",
        "plain": "Receiving statutory pension usually converts relationship to civil service.",
        "when": "Dispute after retirement age while drawing pension.",
        "why": "Triggers civil court jurisdiction check instead of labor arbitration.",
    },
    "在校生实习": {
        "term": "student internship",
        "plain": "Enrolled student internships are generally not statutory labor relations.",
        "when": "Unpaid or dismissed during university internship.",
        "why": "Usually handled via civil claims or school mediation.",
    },
    "个体户/无照经营": {
        "term": "unlicensed employer",
        "plain": "Working for an unregistered shop or contractor.",
        "when": "Boss lacks a valid business license or shut down.",
        "why": "Individual investors or contracting entity can be named as respondent.",
    },
}


def tr_chip_group(lang: str, group: str) -> str:
    if lang == "zh":
        return group
    return CHIP_GROUP_EN.get(group, group)


def tr_chip(lang: str, c: dict) -> dict[str, str]:
    if lang == "zh":
        return c
    tr = CHIPS_EN.get(c.get("term") or "")
    if not tr:
        return c
    return {**c, **tr}


# Questions and sentence starters for the facts most useful to the calculation.
# The sentence starters are shown as examples and are never sent as answers.
CASE_PROMPTS = {
    "违法解除劳动合同": {
        "zh": ("公司哪天、怎么通知你不用上班了？给了什么理由，哪天是最后工作日？",
               "___年___月___日，___通过___通知我不用上班了，给出的理由是___。最后工作日是___。"),
        "en": ("When and how did the employer tell you to stop working? What reason did they give, and what was your last day?",
               "On ___, ___ told me via ___ that I was being dismissed because ___. My last day was ___."),
    },
    "拖欠工资": {
        "zh": ("哪几个月的工资没发？原定哪天发，实际发了多少，还欠多少？",
               "___月的工资应在___发，实际收到___元，还欠工资___元。"),
        "en": ("Which pay periods are unpaid? When was payment due, how much did you receive, and how much is still owed?",
               "My wages for ___ were due on ___. I received ___ RMB and am still owed ___ RMB in wages."),
    },
    "加班费": {
        "zh": ("哪段时间加了班？工作日、休息日和法定节假日各加了多少小时？公司是否付过加班费？",
               "___期间，工作日加班___小时，休息日加班___小时，法定节假日加班___小时。公司已付___元加班费。"),
        "en": ("When did you work overtime? How many hours were on workdays, rest days or public holidays, and what overtime pay did you receive?",
               "During ___, I worked ___ weekday overtime hours, ___ rest-day hours and ___ public-holiday hours. I received ___ RMB in overtime pay."),
    },
    "未休年休假工资": {
        "zh": ("哪一年的年假没休完？已休几天，还剩几天？是否已经补发过工资？",
               "___年我已休年假___天，还有___天年假没休。公司已就此支付___元。"),
        "en": ("Which year had unused annual leave? How many days did you take, how many were left, and was any compensation paid?",
               "In ___ I took ___ days of annual leave and had ___ unused annual leave days. I received ___ RMB for them."),
    },
    "工资条/银行流水": {
        "zh": ("工资条和银行流水能核对哪些月份？每月应发多少、实际到账多少，哪天到账？",
               "___月工资条写明应发___元，银行流水记录___日到账___元。"),
        "en": ("Which months can you verify with payslips and bank statements? What was owed, what was paid, and when?",
               "My ___ payslip shows ___ RMB due. The bank statement shows ___ RMB received on ___."),
    },
    "未签书面劳动合同二倍工资": {
        "zh": ("你哪天开始上班？是否签过书面合同？如果后来补签，实际签字是哪天？",
               "我在___入职。入职时___签书面劳动合同，实际签字日期是___（如有）。"),
        "en": ("When did you start work? Did you sign a written contract? If you signed later, what was the actual signing date?",
               "I started work on ___. I ___ a written contract when I started. The actual signature date was ___, if applicable."),
    },
    "管辖": {
        "zh": ("你实际上在哪个城市、哪个区上班？公司登记地在哪里？",
               "我实际在___市___区工作，公司登记在___市___区。"),
        "en": ("In which city and district did you work? Where was the employer registered?",
               "I worked in ___ district, ___ city. The employer was registered in ___."),
    },
    "仲裁时效": {
        "zh": ("你哪天知道这件事？之后是否找公司要求处理、申请调解或收到过回复？分别是哪天？",
               "我在___知道这件事，___向___提出处理请求，___收到___的回复。"),
        "en": ("When did you learn about the issue? When did you contact the employer, seek mediation, or get a response?",
               "I learned about the issue on ___. I raised it with ___ on ___ and received a response on ___."),
    },
}


def case_prompt(lang: str, term: str) -> tuple[str, str]:
    prompts = CASE_PROMPTS.get(term)
    if prompts:
        return prompts[lang]
    return t(lang, "guide_question"), ""


CLARIFICATION_GUIDES = {
    "unclear_issue": {
        "zh": (
            "先补充发生了什么",
            "现有描述还不足以判断争议事项。请补充单位做了什么，以及你希望解决什么。",
            "",
            "",
            (
                ("单位做了什么", "单位哪天做了什么？现在还在职吗？",
                 "___月___日，单位___。我现在___。"),
                ("你想解决什么", "你希望补发工资、继续上班、拿到证明，还是解决其他问题？",
                 "我希望单位___，涉及___这段时间。"),
            ),
        ),
        "en": (
            "Tell us what happened",
            "The description does not yet identify the dispute. Explain what the employer did and what you would like to resolve.",
            "",
            "",
            (
                ("Employer’s action", "What did the employer do, when did it happen, and are you still working there?",
                 "On ___, my employer ___. I am currently ___."),
                ("What you want resolved", "Are you seeking unpaid wages, continued employment, a document, or something else?",
                 "I am asking my employer to ___ for the period ___."),
            ),
        ),
    },
    "internship_pay": {
        "zh": (
            "已识别欠薪线索，请分开核对实习和转正",
            "这段描述涉及实习和转正。需要先确认你在哪个阶段工作、如何受单位管理，以及欠付发生在哪几个月。"
            "在校身份本身不能决定是否存在劳动关系。",
            "先保存实习协议、劳动合同或转正通知、约定薪资的聊天记录、排班考勤、每月工资条和银行流水。"
            "工资承诺和到账金额要核对税前、税后及扣款口径，再判断哪些月份少发。",
            "如果争议涉及劳动关系或劳动报酬，可带着这些资料向当地劳动仲裁机构核实。"
            "如果涉及实习协议报酬，可拨 12348 核实处理途径。"
            "当前测算一次处理一段用工，试算时请单独填写该阶段的日期、工资约定和欠付金额。",
            (
                ("实习和转正时间", "实习何时开始和结束？是否学校安排？从哪天起按正式岗位上班、由谁排班或考勤？现在还在职吗？",
                 "实习从___到___，由___安排。___起我在___岗位工作，由___管理排班，我现在___。"),
                ("逐月工资", "哪几个月没发、哪些月少发？分别属于实习还是转正后？请按同一口径写每月应发、实发和扣款。",
                 "___月属于___阶段，应发___元，实发___元，扣款项目及金额是___。"),
                ("工资和转正证据", "工资约定、转正日期和实际付款分别能用哪些材料核对？",
                 "我有___记录工资约定，有___记录转正日期，有___记录各月到账。"),
            ),
        ),
        "en": (
            "Possible unpaid wages across internship and employment",
            "The description covers an internship and later employment. Identify the work arrangement and supervision in each period, "
            "and which months were affected. Student status alone does not settle whether an employment relationship existed.",
            "Keep the internship agreement, employment contract or conversion notice, pay messages, schedules, attendance, payslips and bank records. "
            "Compare gross pay, net pay and deductions on a consistent basis.",
            "If the dispute concerns employment status or wages under an employment relationship, ask the local labor arbitration office. "
            "For pay under an internship agreement, ask public legal services (12348) about the appropriate route. "
            "The calculator handles one period at a time. To estimate an amount, enter the dates, agreed pay, and unpaid amount for that period separately.",
            (
                ("Work periods", "When did the internship begin and end? Who arranged it? When did the regular role start, who managed your work, and are you still employed?",
                 "My internship was ___ to ___ and was arranged by ___. I started the regular role on ___ and was supervised by ___."),
                ("Monthly pay", "Which months were unpaid or underpaid, and in which period? List amounts due, amounts received and deductions on a consistent basis.",
                 "Month ___ was in the ___ period. Pay due was ___ RMB, received ___ RMB and deductions were ___."),
                ("Supporting records", "What records support the agreed pay, date of conversion and amounts received?",
                 "___ shows the agreed pay, ___ shows the conversion date, and ___ shows the payments."),
            ),
        ),
    },
    "unpaid_amount": {
        "zh": (
            "已识别欠薪线索，请补充未付金额",
            "已识别到工资未付或少付的描述。请把涉及月份和应发、实发金额对应起来。",
            "可对照工资条、银行流水和工资约定，核对每月应发、扣除和到账金额。",
            "",
            (
                ("欠付月份和金额", "哪些月份少发或没发？请写下各月应发、实际到账和扣款。能确定时，再写明合计欠工资多少元。",
                 "___月应发___元、实发___元、扣款___元。经核对，合计欠工资___元。"),
            ),
        ),
        "en": (
            "Possible unpaid wages. Please add the amounts.",
            "The description indicates unpaid or underpaid wages. Match the amounts owed and received to the affected months.",
            "Check the agreed amounts, payslips, deductions, and bank payments for each month.",
            "",
            (
                ("Unpaid months and amounts", "Which pay periods were unpaid or underpaid? List pay due, payments and deductions. Give the total unpaid wages if you can verify it.",
                 "For ___ month, ___ RMB was due, ___ RMB was received and ___ RMB was deducted. Verified unpaid wages total ___ RMB."),
            ),
        ),
    },
}


def staged_prompts(review: dict, lang: str) -> list[tuple[str, str, str]]:
    work = CLARIFICATION_GUIDES["internship_pay"][lang][-1][0]
    period = (
        ("核对期间", "请确认欠薪从哪月到哪月。", "核对期间：___年___月到___年___月。")
        if lang == "zh" else
        ("Check the period", "Which months does the wage dispute cover?", "Pay period: YYYY-MM to YYYY-MM.")
    )
    pay = (
        ("尚未核对的工资", "还有哪些月份没发或少发？可在初步分析里逐月填写。", "")
        if lang == "zh" else
        ("Remaining pay periods", "Which months were unpaid or underpaid? You can check each month in the assessment.", "")
    )
    prompts = {"employment": work, "period": period, "pay": pay}
    return [prompts[gap] for gap in review["gaps"]]
