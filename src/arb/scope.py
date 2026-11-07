"""范围判定与拒答（S3.5）。

这个模块存在的理由，是"负功能"比"正功能"更能体现工程判断：
- 用户讲的是工伤、社保补缴、公积金，硬算一个金额给他，是最坏的结果；
- 用户想让我们预测胜诉率、教他怎么"补"证据，必须明确拒绝。

约定：
    judge(story, fields=None) -> Verdict(in_scope, cause, confidence, redirect, refusal_reason, hints)

in_scope=False 时有 redirect（去哪、带什么）；绝不能既拒答又不给出路。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 明确的"不归仲裁管"事项：命中即指路
OUT_OF_SCOPE = [
    {
        "key": "工伤",
        "patterns": [r"工伤", r"上班路上.{0,6}(?:撞|摔|车祸)", r"认定.{0,4}工伤"],
        "redirect": "去人社局工伤科做工伤认定（先认定、后劳动能力鉴定，都是行政程序，不是仲裁）。带：事故证明、劳动关系材料、病历与医疗票据。单位不配合的，可先单独申请确认劳动关系。",
    },
    {
        "key": "社保补缴",
        "patterns": [r"社保.{0,10}(?:没交|未缴|补缴|断缴|能补|可以补)", r"(?:没|未|不).{0,8}(?:交|缴).{0,3}社保", r"补缴.{0,4}社保", r"五险.{0,4}(?:没|未)"],
        "redirect": "社保补缴不属于仲裁受理范围，走行政征收：社保征收机构 / 12333。带：劳动合同、工资流水、社保缴费记录。",
    },
    {
        "key": "公积金",
        "patterns": [r"公积金"],
        "redirect": "住房公积金不属于仲裁受理范围，去公积金管理中心投诉（行政路径）。带：劳动合同、工资流水。",
    },
]

# 明确禁止的回答方式（这些是红线，不是建议）
RED_LINE_PATTERNS = [
    (r"胜诉率|胜算.{0,4}\d+%|百分之.{0,3}\d+\s*(?:会|能)赢", "不预测胜诉率，只说证据缺口和裁判倾向"),
    (r"(?:教|帮)你.{0,6}(?:补|伪造|弄一份|做一份|造).{0,6}(?:证据|证明|流水|材料)", "不教人补证据或造材料，这是伪造证据风险"),
    (r"一定(?:能|会)(?:赢|赔)|包赢", "不做结果承诺"),
    (r"(?:建议|应该).{0,6}报警", "涉刑只能提示报案途径，由用户自行决定"),
]

# 案由关键词（按优先级从高到低匹配）
CAUSE_RULES = [
    ("illegal_dismissal", [r"违法解除", r"违法辞退", r"口头辞退", r"被辞", r"让我(?:当天|立刻|马上|明天)?走", r"不要我了", r"开除", r"把我(?:辞|开)"]),
    ("double_wage", [r"没签.{0,6}合同", r"未签.{0,6}劳动合同", r"二倍工资", r"双倍工资", r"补签", r"一直没签", r"两份都收走", r"都收走了"]),
    ("overtime", [r"加班", r"周末上班", r"节假日上班", r"法定(?:节假日|假日)上班", r"休假日上班", r"排班"]),
    ("annual_leave", [r"年假", r"年休假"]),
    ("unpaid_wage", [r"拖欠", r"欠.{0,12}工资", r"没发工资", r"工资.{0,6}(?:没发|没结|没给|欠着|未发|未结)", r"扣工资", r"克扣"]),
    ("severance", [r"经济补偿", r"补偿金", r"裁员", r"协商解除", r"到期不续", r"合同到期"]),
    ("pregnant_protection", [r"怀孕", r"孕期", r"产假", r"哺乳期", r"三期"]),
    ("mutual_agreement", [r"协商一致", r"谈好", r"签了协议"]),
]

DEPARTMENT = "用工所在地或用人单位所在地的劳动人事争议仲裁委员会"


@dataclass
class Verdict:
    in_scope: bool
    cause: str
    causes: list[str] = field(default_factory=list)
    redirect: str | None = None
    refusal_reason: str | None = None
    hints: list[str] = field(default_factory=list)


NEGATIONS = ("不预测", "不做", "不给", "不承诺", "不告诉", "不提供", "不是", "并非", "绝不", "没法给", "无法给")


def _negated(text: str, start: int) -> bool:
    """命中的词前面紧跟着否定语，说明这句是在**声明不做**，不是在做。

    没有这一层，我们自己的免责声明「这不是胜诉率，也不预测裁判结果」会被红线检查判成违规——
    一个把免责句当违规的检查器，等于逼着工程师把话说得含糊。只回看 8 个字，不做语义推断，
    所以它宁可漏判一个刁钻的绕弯说法，也不误伤正常表述。
    """
    window = (text or "")[max(0, start - 8):start]
    for sep in ("；", ";", "。", "\n", "，", ","):
        window = window.rsplit(sep, 1)[-1]
    return any(n in window for n in NEGATIONS)


def check_red_lines(text: str) -> list[str]:
    """检查一段（拟输出的）文字有没有踩红线。用于评测里的"危险建议率=0"。

    只看"真的在做"，不看"声明不做"：否定语紧随其前的命中不计入。
    """
    hits = []
    for pat, why in RED_LINE_PATTERNS:
        if any(not _negated(text, m.start()) for m in re.finditer(pat, text or "")):
            hits.append(why)
    return hits


# 直接索要"包赢/胜诉率"、要求教造证据：这不是能力问题，是边界问题，入口即拒
RED_LINE_REQUESTS = [
    (
        r"(?:能不能|会不会|有没有把握|有多大把握)\s*(?:赢|胜|拿得到)|胜诉率|胜算|赢的?概率|能赢吗|几分把握",
        "不预测胜诉率",
        "我只能告诉你证据缺口和裁判倾向，不给概率——谁给概率谁在骗你。",
        ["把「有没有书面解除通知」「考勤/工资流水在谁手上」这两件事补齐，比问胜率有用得多"],
    ),
    (
        r"(?:教|帮)(?:我|他|她)?.{0,20}(?:补|造|伪造|改|弄)(?:成|上|一份)?.{0,16}(?:证据|考勤|打卡|流水|记录|证明|材料)"
        r"|(?:教|帮)(?:我|他|她)?.{0,20}(?:考勤|打卡|证据|流水|记录|证明|材料).{0,12}(?:补|造|伪造|改|弄)",
        "不教人伪造证据",
        "伪造证据可能构成违法，这条我不做。",
        ["真实证据不足时的合法路径：申请仲裁委调取考勤/工资发放记录（用人单位负举证责任）"],
    ),
]


def judge(story: str, fields: dict | None = None) -> Verdict:
    story = story or ""
    for pat, why, reason, hints in RED_LINE_REQUESTS:
        if re.search(pat, story):
            return Verdict(
                in_scope=False,
                cause="red_line",
                redirect=None,
                refusal_reason=f"这个请求我不接：{why}",
                hints=[reason] + hints,
            )
    for item in OUT_OF_SCOPE:
        if any(re.search(p, story) for p in item["patterns"]):
            return Verdict(
                in_scope=False,
                cause=item["key"],
                redirect=item["redirect"],
                refusal_reason=f"「{item['key']}」不属于劳动争议仲裁的受理范围",
                hints=[f"办理地点：{item['redirect'].split('。')[0]}", "把材料带齐再去，避免白跑一趟"],
            )

    causes = [name for name, pats in CAUSE_RULES if any(re.search(p, story) for p in pats)]
    if not causes and fields:
        # 关键词没命中，但能抽出劳动关系要素：不算"超出范围"，只是请求没说清楚
        term = fields.get("termination")
        mapped = {"illegal_dismissal": "illegal_dismissal", "mutual_agreement": "severance",
                  "legal_termination": "severance", "employee_resign": "severance"}.get(term)
        if mapped and fields.get("monthly_wage") is not None:
            return Verdict(
                in_scope=True,
                cause=mapped,
                causes=[mapped],
                hints=["没听出具体想要什么，先按解除类主项试算；钱数只是下限，具体请求请补充"],
            )
    if not causes:
        return Verdict(
            in_scope=False,
            cause="unknown",
            refusal_reason="从这段描述里还看不出具体的劳动争议事项",
            redirect=None,
            hints=["可以补充：什么时候入职、什么时候离开、公司做了什么、你想要什么（钱/继续上班/一张证明）"],
        )

    if "pregnant_protection" in causes:
        causes = [c for c in causes if c != "pregnant_protection"] + ["pregnant_protection"]
        hints = ["三期（孕期/产期/哺乳期）内被解除，属于法律特别保护情形，按违法解除主张 2N 更有把握"]
    else:
        hints = []

    if (fields or {}).get("monthly_wage") is not None:
        hints.append(f"月薪 {fields['monthly_wage']:,.0f} 元已识别，若与实际不符请直接改数字")

    return Verdict(
        in_scope=True,
        cause=causes[0],
        causes=causes,
        hints=hints + [f"受理机关：{DEPARTMENT}；仲裁不收费，受理后 45 日内审结（复杂可延 15 日）"],
    )
