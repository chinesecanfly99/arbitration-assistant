"""三层漏斗闸门：受案范围 → 资格 → 口径（S3.6）。

为什么要在"能算多少钱"之外单独做一层：
- 算得准只回答"多少"，回答不了"我现在能不能去申请"；
- 一事不再理、已过时效、退休返聘、在校实习、跨城市口径，任何一条踩中，
  屏幕上那个总额都是误导；
- 所以把"能不能进门"做成独立的、可单测、可回溯的三层闸门，每层都给出
  法条依据和一条出路——不给出路的拒答，等于把人晾在门口。

与 scope.py 的分工：
    scope.judge   管"这件事归不归劳动仲裁"（受案范围、红线拒答）；
    gates.qualify 管"这个人、这个时间、这个城市，够不够格申请"。

约定：
    qualify(story, fields, verdict, today=None, city=None) -> dict
    {"status": "pass|warn|fail", "can_arbitrate": bool, "blockers": [...],
     "warnings": [...], "layers": [{key,title,status,message,detail,cites,route}],
     "cites": [...], "city": {...}|None}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from . import city as city_store
from .deadline import analyze as analyze_deadlines
from .scope import Verdict

# 《劳动争议调解仲裁法》第二条六类受案范围 → 本项目案由
ARTICLE_2 = [
    (1, "因确认劳动关系发生的争议", {"unknown"}),
    (2, "因订立、履行、变更、解除和终止劳动合同发生的争议", {"double_wage", "severance", "mutual_agreement"}),
    (3, "因除名、辞退和辞职、离职发生的争议", {"illegal_dismissal"}),
    (4, "因工作时间、休息休假、社会保险、福利、培训以及劳动保护发生的争议", {"overtime", "annual_leave", "pregnant_protection"}),
    (5, "因劳动报酬、工伤医疗费、经济补偿或者赔偿金等发生的争议", {"unpaid_wage", "severance"}),
    (6, "法律、法规规定的其他劳动争议", set()),
]

# 已完成程序的表述：命中即"一事不再理"，不再往下算钱
# 每条带自己的依据：能引准的才引，引不准的宁可留空并说清出处——
# "引得到但引不准"比"不引"更危险，评审一查原文就穿帮。
RES_JUDICATA = [
    (
        r"(?:仲裁)?裁决(?:书)?(?:已经|已)?(?:下来|作出|生效|出了?结果)",
        "同一请求已有仲裁裁决",
        [],
        "依据《劳动人事争议仲裁办案规则》关于不予受理的规定；本库未收录该规章，故不列条文号",
    ),
    (
        r"(?:已经|已)(?:经)?(?:仲裁|裁决)(?:过|了)(?!时效)",
        "同一请求已经仲裁处理过",
        [],
        "依据《劳动人事争议仲裁办案规则》关于不予受理的规定；本库未收录该规章，故不列条文号",
    ),
    (
        r"法院(?:已经|已)?(?:判决|判了|判过)|终审判决|生效判决|二审(?:已经)?判",
        "同一请求已有生效判决",
        [],
        "生效裁判已确定权利义务，只能走审判监督程序；本库未收录民事诉讼法，故不列条文号",
    ),
    (
        r"调解书.{0,8}(?:生效|已经|已)",
        "调解书已生效后反悔",
        ["sfjs1:11"],
        "调解书已发生法律效力、一方反悔再起诉的，法院不予受理",
    ),
    (
        r"一事不再理",
        "同一请求已作处理",
        [],
        "依据《劳动人事争议仲裁办案规则》关于不予受理的规定；本库未收录该规章，故不列条文号",
    ),
]

# 程序还在路上：不能重复申请，但可以变更/增加请求
PENDING = [
    (
        r"(?:已经|已)(?:申请|提交|提起|走)(?:了|过)?(?:劳动)?仲裁",
        "已申请仲裁、尚未结案",
        [],
        "同一请求不能再立一案，但可在原案中增加或变更仲裁请求",
    ),
    (
        r"(?:已经|已)(?:向)?(?:法院)?(?:起诉|立案)",
        "已向法院起诉",
        [],
        "同一请求不能再申请仲裁，诉讼与仲裁只能选一条路走",
    ),
]

# 已达成协议：原则上不再受理，除非有欺诈/胁迫/重大误解/显失公平
SETTLED = [
    (
        r"(?:签|达成)(?:了)?(?:调解|和解|赔偿)协议|调解书|和解协议",
        "已签调解/和解协议",
        ["sfjs1:35"],
        "不违反强制性规定、且不存在欺诈、胁迫或乘人之危的，协议有效，按协议履行",
    ),
]

SUBJECT_RULES = [
    (
        r"退休|返聘|领(?:取)?(?:养老金|退休金)|养老保险待遇",
        "warn",
        "已退休 / 返聘",
        "这类关系过去一律按劳务关系处理（解释（一）第 32 条第 1 款），但该款自 2025-09-01 起"
        "被解释（二）第 21 条废止；现在要看是否已依法享受养老保险待遇、是否受单位劳动管理，"
        "先确认关系性质，再决定走仲裁还是民事诉讼。",
        ["sfjs1:32", "sfjs2:21"],
    ),
    (
        r"实习|在校生|学校安排|顶岗实习|大三|大四",
        "warn",
        "在校实习",
        "在校生实习一般不认定为劳动关系，按实习协议/劳务处理；拿不到 N、2N 和二倍工资，"
        "但实习报酬、人身伤害仍可另行主张。",
        [],
    ),
    (
        r"未满\s*1[56]\s*(?:周)?岁|童工|十五岁|十六岁",
        "warn",
        "疑似未满 16 周岁",
        "未满 16 周岁属禁止使用的童工，不是普通劳动争议；先向劳动保障监察举报（12333），"
        "人身安全问题优先。",
        [],
    ),
    (
        r"外国人|外籍|留学生打工|工作许可|工作签证",
        "warn",
        "外籍人员",
        "外国人未依法取得就业证件，通常不认定劳动关系（解释（一）第 33 条）；"
        "先确认工作许可与居留手续是否齐全。",
        ["sfjs1:33"],
    ),
]


@dataclass
class Gate:
    key: str
    title: str
    status: str                 # pass | warn | fail | info
    message: str
    detail: list[str] = field(default_factory=list)
    cites: list[str] = field(default_factory=list)
    route: dict | None = None

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "status": self.status,
            "message": self.message,
            "detail": self.detail,
            "cites": self.cites,
            "route": self.route,
        }


def mapped_categories(verdict: Verdict) -> list[dict]:
    """案由 → 第二条六类受案范围（用于"凭什么归仲裁管"的展示）。"""
    causes = set(verdict.causes or ([verdict.cause] if verdict.cause else []))
    hit = []
    for no, text, keys in ARTICLE_2:
        if causes & keys:
            hit.append({"no": no, "text": text})
    return hit or [{"no": 6, "text": ARTICLE_2[5][1]}]


def _find(story: str, rules) -> tuple[str, list[str], str] | None:
    """返回 (命中标签, 法条依据, 说明)。规则表统一四元组（pattern, label, cites, note）。"""
    for pat, label, rule_cites, note in rules:
        if re.search(pat, story or ""):
            return label, list(rule_cites), note
    return None


def detect_cities(story: str) -> list[str]:
    """从叙述里找出**所有**已覆盖城市（用于发现"跨城市"管辖冲突）。

    只认库里有的、且长度 ≥2 的写法：单字别名（京/沪/穗/深/杭）误报率太高
    （"深刻""杭州"之外还会撞上"南京""京沪高铁"），宁可少认也不要认错。
    """
    text = story or ""
    found: list[str] = []
    for c in city_store.load_all():
        for name in [c.name, *c.aliases]:
            if len(name or "") < 2:
                continue
            if name in text and c.name not in found:
                found.append(c.name)
                break
    return found


# 用户说了一个我们没收录的城市——这时必须**明说没覆盖**，不能假装不知道，
# 更不能拿最近的城市顶替。只认"在/去 + 地名 + 上班/市"这种明确句式，避免把
# "在城市里上班""在这家公司工作"当成地名。
PLACE_PATTERNS = (
    r"(?:在|去)\s*([\u4e00-\u9fa5]{2,3}市)",
    r"(?:在|去)\s*([\u4e00-\u9fa5]{2,3}?)(?:上班|工作|打工|干活)",
)
PLACE_STOP = {"这家", "那家", "一家", "公司", "单位", "厂里", "城里", "城市", "本地", "外地", "家里"}


def guess_place(story: str) -> str | None:
    """猜一个**未覆盖**的地名；猜不到返回 None。"""
    text = story or ""
    for pat in PLACE_PATTERNS:
        for m in re.finditer(pat, text):
            name = city_store.normalize(m.group(1))
            if not name or name in PLACE_STOP or name.endswith(("省", "里", "家", "司")):
                continue
            return name
    return None


def detect_city(story: str, city: str | None = None) -> str | None:
    """显式传入优先；其次库里覆盖的城市；最后是"说了但没覆盖"的地名（用于明说没覆盖）。"""
    if city:
        return city_store.normalize(city)
    found = detect_cities(story)
    if found:
        return found[0]
    return guess_place(story)


def qualify(
    story: str,
    fields: dict | None = None,
    verdict: Verdict | None = None,
    today: date | None = None,
    city: str | None = None,
) -> dict:
    today = today or date.today()
    fields = fields or {}
    layers: list[Gate] = []
    blockers: list[str] = []
    warnings: list[str] = []

    # ---------- 第一层：受案范围（结论由 scope.judge 给，这里只做展示与归类） ----------
    if verdict is not None:
        cats = mapped_categories(verdict)
        layers.append(
            Gate(
                key="scope",
                title="第一层 · 归不归劳动仲裁管",
                status="pass" if verdict.in_scope else "fail",
                message=(
                    "属于《劳动争议调解仲裁法》第二条受案范围："
                    + "；".join(c["text"] for c in cats)
                    if verdict.in_scope
                    else (verdict.refusal_reason or "不属于劳动争议仲裁受案范围")
                ),
                cites=["arbitration_law:2"],
                route={"redirect": verdict.redirect} if verdict.redirect else None,
            )
        )

    # ---------- 第二层：资格（主体 / 时效 / 管辖 / 是否重复申请） ----------
    detail: list[str] = []
    cites: list[str] = []
    status = "pass"

    # 2.1 主体
    for pat, level, title, msg, cs in SUBJECT_RULES:
        if re.search(pat, story or ""):
            status = "warn" if status == "pass" else status
            detail.append(f"{title}：{msg}")
            cites.extend(cs)
            warnings.append(f"{title}：先确认关系性质再算钱")

    # 2.2 一事不再理 / 程序在途 / 已达成协议
    done = _find(story, RES_JUDICATA)
    pending = _find(story, PENDING)
    settled = _find(story, SETTLED)
    if done:
        status = "fail"
        blockers.append(f"一事不再理：{done[0]}")
        detail.append(f"{done[0]}——同一请求不能重复申请；裁决被撤销、或出现新证据的除外，"
                      "这两种情况要先找律师看材料。{done[2]}")
        cites.extend(done[1])
    elif pending:
        status = "warn" if status == "pass" else status
        detail.append(f"{pending[0]}：不能就同一请求再申请一次；如请求有遗漏，可在本案中增加/变更仲裁请求。{pending[2]}")
        cites.extend(pending[1])
    elif settled:
        status = "warn" if status == "pass" else status
        detail.append(f"{settled[0]}：原则上按协议履行；只有在欺诈、胁迫、重大误解或显失公平时才可能撤销，"
                      f"不承诺结果。{settled[2]}")
        cites.extend(settled[1])

    # 2.3 时效（只提示，不替用户断定"过期就没救"：对方不抗辩，仲裁委不主动审查）
    dls = []
    if fields.get("end_date"):
        try:
            dls = analyze_deadlines(fields["end_date"], today, employment_ongoing=False)
        except Exception:  # 日期异常不该让整条流水线挂掉
            dls = []
    expired = [d for d in dls if getattr(d, "expired", False)]
    if dls:
        if expired and len(expired) == len(dls):
            status = "warn" if status == "pass" else status
            detail.append(f"{len(expired)} 项请求可能已过一年仲裁时效（自 {fields['end_date']} 起算）；"
                          "时效需对方抗辩，仲裁委不主动审查，仍可申请，但要先问 12348 怎么说")
        elif expired:
            detail.append(f"有 {len(expired)} 项请求可能已过时效，其余仍在期内")
        else:
            left = min((d.days_left for d in dls if getattr(d, "days_left", None) is not None), default=None)
            if left is not None:
                detail.append(f"时效：最紧的一项还剩 {left} 天")
        cites.append("arbitration_law:27")

    # 2.4 管辖与城市口径
    city_name = detect_city(story, city)
    c = city_store.get(city_name) if city_name else None
    city_block = None

    # 跨城市：叙述里同时出现两个已覆盖城市（"在深圳上班、公司注册在北京"），
    # 管辖会打架——劳动合同履行地 vs 用人单位所在地，必须先问清楚，不能自己挑一个。
    multi = detect_cities(story)
    if len(multi) >= 2:
        status = "warn" if status == "pass" else status
        detail.append(
            f"叙述里同时出现 {'、'.join(multi)}：劳动合同履行地或用人单位所在地的仲裁委都有管辖权，"
            "两边都能立，但**只能挑一个**，挑错要重新立案。金额口径按你实际提交的那一地算，"
            "两地社平工资不同，算出来的 3 倍封顶和一裁终局线也不同。"
        )
        cites.append("arbitration_law:21")
        warnings.append(f"跨城市：{'/'.join(multi)} 口径可能不一致，先定管辖地再定金额")

    if c is not None:
        detail.append(
            f"按{c.name}口径：上年度职工月平均工资 {c.avg_wage:,.0f} 元，3 倍封顶 {c.cap_3x:,.0f} 元/月；"
            f"一裁终局金额线 {c.one_final_award_threshold:,.0f} 元（最低工资 {c.min_wage:,.0f}×12）"
        )
        cites.append("labor_contract_law:47")
        cites.append("arbitration_law:21")
        city_block = c.as_dict()
    elif city_name:
        status = "warn" if status == "pass" else status
        detail.append(f"{city_name}的金额口径不在覆盖范围（现有：{'、'.join(city_store.names())}）；"
                      "受案范围、时效、解除合法性按全国通行规则判断，金额请按当地口径确认，我不套用别的城市数字")
        warnings.append(f"{city_name}口径未覆盖：金额只作参考，别直接拿去立案")
    else:
        detail.append("用工所在地未确认：3 倍封顶和最低工资按当地口径，确认城市后我再套用对应数字")

    layers.append(
        Gate(
            key="qualification",
            title="第二层 · 够不够格申请",
            status=status,
            message={
                "pass": "主体、时效、管辖、是否重复申请，四项都没有障碍",
                "warn": "可以申请，但有一项要先确认",
                "fail": "存在硬性障碍，暂不具备申请条件",
            }[status],
            detail=detail,
            cites=sorted(set(cites)),
        )
    )

    # ---------- 第三层：口径提示（金额线 / 时效线，只做提醒） ----------
    layers.append(
        Gate(
            key="caliber",
            title="第三层 · 数字从哪来",
            status="info",
            message="金额由规则内核计算，引用逐条回库核对；城市口径带核验日，过期需重新核对",
            detail=[
                "3 倍封顶的口径是「上年度职工月平均工资」，各地算法不同（全口径 / 城镇非私营在岗职工），跨城市不能混用",
                "一裁终局金额线 = 当地月最低工资 × 12，只影响单位能不能起诉，不影响你能主张多少",
            ],
            cites=["labor_contract_law:47", "arbitration_law:47"],
        )
    )

    return {
        "status": status,
        "can_arbitrate": status != "fail",
        "blockers": blockers,
        "warnings": warnings,
        "layers": [g.as_dict() for g in layers],
        "cites": sorted({c for g in layers for c in g.cites}),
        "city": city_block,
        "city_name": city_name,
        "cities_seen": multi,
    }


def one_final_award_note(city_name: str | None, total: float | None) -> str | None:
    """一裁终局判断：只对用人单位有意义，但当事人知道这条会少走弯路。"""
    c = city_store.get(city_name) if city_name else None
    if c is None or total is None:
        return None
    line = c.one_final_award_threshold
    if line and total <= line:
        return (f"本案金额 {total:,.0f} 元 ≤ 当地一裁终局线 {line:,.0f} 元：裁决作出即生效，"
                "单位不能起诉，只能向中院申请撤销（《劳动争议调解仲裁法》第 47、49 条）")
    if line:
        return f"本案金额 {total:,.0f} 元 > 当地一裁终局线 {line:,.0f} 元：单位不服可以起诉，做好打两审的准备"
    return None
