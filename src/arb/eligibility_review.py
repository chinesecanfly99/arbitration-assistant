"""Identify legal prerequisites before assigning an employment-related amount."""
from __future__ import annotations

import re

RELATIONSHIP_ASK = re.compile(
    r"(?:确认|认定|确定)(?:.{0,8}的)?劳动关系|(?:是|算)(?:不算|不是)?(?:公司|单位)?员工"
    r"|(?:是不是|有没有|是否存在)劳动关系|(?:实际)?用人单位是谁|确认(?:实际)?用人单位"
)
PLATFORM = re.compile(r"平台|派单|接单|配送|骑手|外卖|代驾|主播|直播|网约|家政|合作协议|承揽协议|经纪合同")
MULTIPLE_ENTITIES = re.compile(r"关联(?:企业|公司|单位)|劳务派遣|劳务公司.{0,30}(?:合作商|用工单位|平台)|挂靠|层层转包|分包")
FREE_CHOICE = re.compile(r"(?:自由|自行|自己)(?:决定|选择|定)?.{0,8}(?:接单|抢单|工作时间|内容|定价)|自主(?:定价|接单)|分成.{0,8}(?:谈过|协商|议价)|车主直接付")
MANAGEMENT = re.compile(r"排班|打卡|签到|不得拒单|限制拒单|考核扣|按[^，。！？]{0,10}扣(?:钱|罚)|固定单量|最低单量|规定运费|请假.{0,6}批")
ALTERNATE_AGREEMENT = re.compile(r"签(?:了|过)?.{0,8}(?:合作|承揽|经纪)(?:协议|合同)")
REFUSED_CONTRACT = re.compile(
    r"故意(?:不签|拒.{0,5}签)|(?:多次|书面).{0,12}(?:要求|通知|提出).{0,10}(?:续签|补签|签订)"
    r".{0,18}(?:拒绝|拒签|不肯签)|拒绝.{0,5}续签"
)
TREATMENT_EXTENSION = re.compile(r"停工留薪期.{0,8}(?:满|延长)|延长.{0,6}停工留薪期|诊断证明.{0,14}(?:停工留薪|继续休息)")
SOCIAL_LOSS = re.compile(r"(?:养老保险|社保|社会保险).{0,22}(?:抚恤金|损失|垫付|自己承担|返还)|抚恤金.{0,14}(?:差额|少|补)")
NONCOMPETE = re.compile(r"竞业限制|竞业义务|竞业协议|离职.{0,10}不.{0,5}去同行")
PAY_CLAIM = re.compile(r"欠薪|欠工资|工钱|工资|劳动报酬")
SIGNAL_PREFIX = re.compile(r"(?:不(?:可以|需要|安排|要求|会|用|必|能)?|没(?:有)?(?:安排|要求)?|无需|可以|必须)\s*$")


def _phrases(pattern: re.Pattern, text: str) -> list[str]:
    phrases = []
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - 8):match.start()]
        prefix = SIGNAL_PREFIX.search(before)
        phrase = (prefix[0] if prefix else "") + match[0]
        if phrase not in phrases:
            phrases.append(phrase)
    return phrases[:5]


def review_prerequisites(text: str, causes: list[str], administrative: str | None) -> dict:
    multiple = MULTIPLE_ENTITIES.search(text)
    is_platform = PLATFORM.search(text)
    employment = None
    if "employment_relationship" in causes or (
        (multiple and PAY_CLAIM.search(text)) or (is_platform and "double_wage" in causes)
    ):
        employment = {
            "management": _phrases(MANAGEMENT, text),
            "autonomy": _phrases(FREE_CHOICE, text),
            "multiple": bool(multiple),
            "platform": bool(is_platform),
        }
    contract = None
    if "double_wage" in causes:
        has_agreement = bool(ALTERNATE_AGREEMENT.search(text))
        refusal = bool(REFUSED_CONTRACT.search(text))
        if has_agreement or refusal or employment:
            terms_described = all(re.search(pattern, text) for pattern in (r"岗位|工作内容", r"工资|报酬|工钱", r"期限|起止"))
            contract = {"other_agreement": has_agreement, "refusal": refusal, "terms_described": terms_described}
    return {
        "employment": employment, "contract": contract,
        "noncompete": bool(NONCOMPETE.search(text)),
        "injury_extension": bool(TREATMENT_EXTENSION.search(text)),
        "social_loss": administrative == "社保补缴" and bool(SOCIAL_LOSS.search(text)),
    }
