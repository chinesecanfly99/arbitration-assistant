"""材料清单：按案由生成 + 举证责任分配 + 去哪拿。纯规则库，不调模型。

为什么值得单独一个模块：
"能拿多少钱"是算术题，"要带什么去立案"是手续题——后者答错，前面算得再准也白搭：
- 申请书份数按被申请人数 +1，少一份当场让你回去复印；
- 用人单位工商登记信息不查，被申请人全称写错，立案窗口直接退；
- 劳动关系证明（合同/流水/社保/工牌/工作群）缺一样，可能连"受理"这一关都过不去。

举证责任的分配写在这里，是因为它决定"缺了还能不能立案"：
属于单位掌握管理的证据（考勤、工资台账、解除决定、规章制度公示），
劳动者只要提出初步线索，单位不提供就承担不利后果（《劳动争议调解仲裁法》第六条）。
所以清单里标"单位"的项，缺了不等于输，而是"当庭要求对方出示"。

约定：
    build_materials(types, story="") -> list[dict]
    types 是本项目内部案由（termination / no_contract / unpaid_wage / overtime /
    annual_leave / social_insurance / noncompete），由 pipeline.dispute_types() 给出。
"""
from __future__ import annotations

# 受理范围映射：scope.py 的案由 → 本模块的争议类型
TYPE_MAP = {
    "illegal_dismissal": "termination",
    "severance": "termination",
    "mutual_agreement": "termination",
    "pregnant_protection": "termination",
    "double_wage": "no_contract",
    "overtime": "overtime",
    "annual_leave": "annual_leave",
    "unpaid_wage": "unpaid_wage",
}

# 每个类型的中文名，用于报告里"为什么这些材料与本案有关"
TYPE_LABELS = {
    "termination": "解除劳动合同",
    "no_contract": "未签书面合同",
    "unpaid_wage": "拖欠工资",
    "overtime": "加班费",
    "annual_leave": "未休年休假",
    "social_insurance": "社保待遇损失",
    "noncompete": "竞业限制",
}

BASE = [
    {
        "key": "application",
        "name": "劳动人事争议仲裁申请书",
        "purpose": "立案必备（仲裁委有格式表，现场可领可抄）",
        "burden": "申请人",
        "how": "按被申请人人数 +1 份准备；仲裁不收费，别信「代办立案」的收费",
        "required": True,
    },
    {
        "key": "id_card",
        "name": "身份证原件 + 复印件",
        "purpose": "主体资格核验",
        "burden": "申请人",
        "how": "正反面复印 1 份，窗口核原件后收复印件",
        "required": True,
    },
    {
        "key": "company_registry",
        "name": "用人单位工商登记信息（全称、统一社会信用代码、存续状态）",
        "purpose": "被申请人写不准，立案窗口直接退",
        "burden": "申请人",
        "how": "「电子营业执照」小程序查；或到仲裁窗口请工作人员查并打印",
        "required": True,
        "material_type": "badge",
    },
    {
        "key": "relation",
        "name": "劳动关系证明（合同 / 工资流水 / 社保记录 / 工牌 / 工作群，有一样即可）",
        "purpose": "证明「我确实在这家公司上过班」",
        "burden": "申请人初步举证",
        "how": "银行 App 导工资流水；「电子社保卡」查参保缴费记录；企业微信导出工作群",
        "required": True,
        # 四类只要有一类就够——劳动关系证明不要求"全套"
        "material_type": ("contract", "bank_flow", "social_record", "badge"),
    },
]

BY_TYPE = {
    "termination": [
        {
            "key": "termination_notice",
            "name": "解除通知 / 离职证明 / 辞退聊天记录",
            "purpose": "决定赔 N 还是 2N 的关键：解除的主体、日期、理由",
            "burden": "申请人举证解除事实；单位解除的，由单位举证解除合法性",
            "how": "书面通知原件、邮件、HR 微信/钉钉截图；口头辞退可录自己参与的谈话",
            "required": True,
            "material_type": "termination_notice",
        },
        {
            "key": "wage_standard",
            "name": "工资标准证据（工资条 / 银行流水 / 个税记录）",
            "purpose": "N 和 2N 的计算基数",
            "burden": "申请人；工资台账在单位",
            "how": "个人所得税 App → 收入纳税明细；银行流水里标「工资」的入账",
            "required": True,
            "material_type": "payslip",
        },
    ],
    "no_contract": [
        {
            "key": "no_contract_proof",
            "name": "没有书面合同的佐证（入职登记、工牌、工作群、工资流水）",
            "purpose": "证明有用工事实、且单位确实没签",
            "burden": "申请人初步举证；合同文本由单位保管，单位应提供",
            "how": "入职通知、排班表、工作群公告、社保参保记录",
            "required": True,
            "material_type": "badge",
        }
    ],
    "unpaid_wage": [
        {
            "key": "wage_owed",
            "name": "欠薪证据（工资条 / 流水 / 催讨记录 / 考勤）",
            "purpose": "欠了多少、欠了几个月",
            "burden": "申请人；工资支付记录由单位保管",
            "how": "近 12 个月工资条 + 银行流水 + 催讨聊天记录",
            "required": True,
            "material_type": "bank_flow",
        }
    ],
    "overtime": [
        {
            "key": "overtime_proof",
            "name": "加班证据（打卡记录、排班表、加班审批、工作群安排）",
            "purpose": "加班事实与时长——这一项最容易因证据不足打折",
            "burden": "申请人初步举证；考勤属单位掌握管理的，单位举证",
            "how": "钉钉/企业微信考勤导出、排班表、领导安排加班的聊天记录",
            "required": True,
            "material_type": "attendance",
        }
    ],
    "annual_leave": [
        {
            "key": "leave_record",
            "name": "年休假记录（请假单、考勤、工资条里的年假折算）",
            "purpose": "应休几天、已休几天",
            "burden": "申请人；休假台账在单位",
            "how": "OA 请假记录截图、考勤系统年假余额",
            "required": True,
            "material_type": "attendance",
        }
    ],
    "social_insurance": [
        {
            "key": "si_record",
            "name": "社保缴纳记录 / 断缴截图",
            "purpose": "未缴、断缴的事实与损失范围（补缴本身走行政征收，不归仲裁）",
            "burden": "申请人；缴费记录在社保经办机构",
            "how": "「电子社保卡」→ 参保缴费信息查询；或社保窗口打印",
            "required": True,
            "material_type": "social_record",
        }
    ],
    "noncompete": [
        {
            "key": "noncompete_agreement",
            "name": "竞业限制协议 / 条款 + 岗位说明",
            "purpose": "是否存在有效的竞业限制义务（主体适格性看岗位）",
            "burden": "单位主张违约的，由单位举证",
            "how": "劳动合同附件、保密协议、岗位职责说明",
            "required": True,
            "material_type": "contract",
        }
    ],
}

# 用户嘴上提到过什么，就当他手上已经有 —— 不追问，只在清单里标"你提到过"。
# 这是保守推断：只认明确的说法，不猜。
HAVE_HINTS = {
    "contract": ("劳动合同", "签了合同", "录用通知", "offer"),
    "bank_flow": ("银行流水", "流水", "转账记录", "工资打到卡"),
    "payslip": ("工资条", "工资单"),
    "tax_record": ("个税", "纳税记录"),
    "social_record": ("社保记录", "社保缴费", "参保记录"),
    "termination_notice": ("解除通知", "辞退通知", "离职证明", "辞退邮件"),
    "chat_record": ("聊天记录", "微信", "钉钉", "企业微信"),
    "attendance": ("考勤", "打卡", "排班"),
    "badge": ("工牌", "工作证", "工作群"),
}


def dispute_types(causes, items=None) -> set[str]:
    """把 scope 的案由 + 实际算出来的项目，合并成材料库认的争议类型。

    两边都要看：案由来自用户原话，item 来自计算内核。
    比如用户只说"被辞退"，但内核算出了二倍工资，那"未签合同"这一组材料也该出现。
    """
    out = {TYPE_MAP[c] for c in (causes or []) if c in TYPE_MAP}
    for it in items or []:
        name = it.get("name", "")
        if "二倍工资" in name:
            out.add("no_contract")
        elif "加班费" in name:
            out.add("overtime")
        elif "年休假" in name:
            out.add("annual_leave")
        elif "拖欠工资" in name:
            out.add("unpaid_wage")
        elif "经济补偿" in name or "赔偿金" in name:
            out.add("termination")
    return out


def what_you_have(story: str) -> set[str]:
    """从叙述里认"你提到过已有的材料"，返回 material_type 集合。"""
    text = story or ""
    return {t for t, kws in HAVE_HINTS.items() if any(k in text for k in kws)}


def build_materials(types, story: str = "") -> list[dict]:
    """按争议类型生成清单。有/缺只影响展示，不缺任何一项才能算"材料齐"。"""
    have = what_you_have(story)
    items = [dict(x) for x in BASE]
    for t in sorted(types or ()):
        for x in BY_TYPE.get(t, []):
            if x["key"] not in {i["key"] for i in items}:
                items.append(dict(x))
    owner = {}
    for t, rows in BY_TYPE.items():
        for x in rows:
            owner.setdefault(x["key"], TYPE_LABELS.get(t, t))
    for it in items:
        mt = it.get("material_type")
        if isinstance(mt, str):
            mt = (mt,)
        it["have"] = bool(mt and any(m in have for m in mt))
        it["from_type"] = owner.get(it["key"], "")
    return items


def summary(items: list[dict]) -> str:
    if not items:
        return ""
    have = sum(1 for i in items if i["have"])
    unit = sum(1 for i in items if i["burden"].startswith("申请人"))
    return (
        f"共 {len(items)} 项：你提到手上已有的 {have} 项，其余 {len(items) - have} 项需要去开；"
        f"其中 {unit} 项由你先做初步举证，之后单位掌握管理的部分可要求对方出示。"
    )
