"""演示案例库与「普通 AI vs 本系统」对比模块（纯标准库，零依赖）。

提供两类能力：
1. DEMO_CASES：控制台左侧「演示案例库」预设案例，覆盖完整算清、高薪封顶、信息缺口、
   超范围指路、红线拦截与跨城市管辖六类典型场景。
2. compare_with_generic_ai：
   - 若用户传入或环境配置了 OpenAI 兼容 API Key，实时调用大模型按"普通直答"方式回答，
     并用本系统法条库（laws.resolve_name / laws.exists）现场核验其法条真伪；
   - 若未配置 API Key（离线/零配置演示），对预设案例提供典型通用大模型对照分析，
     对自定义输入给出能力维度对比与透明说明，绝不编造实时模型输出。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from . import laws, llm

CITE_RE = re.compile(r"《([^》]+)》第\s*([零一二三四五六七八九十百\d]+)\s*条")

GENERIC_PROMPT = """你是通用 AI 助手。请直接根据下面这段劳动者描述，回答他能拿到多少钱、依据什么法律条文以及接下来该怎么办（用简洁自然的中文段落回答即可）：

"""

DEMO_CASES: list[dict[str, Any]] = [
    {
        "id": "full_2n",
        "title": "违法辞退 2N + 未签合同 + 年假",
        "tag": "完整可算",
        "badge_cls": "ok",
        "summary": "2020-03-01 入职，月薪 9000，未签合同，口头辞退，5 天未休年假",
        "story": (
            "我2020年3月1日进的这家厂，一个月9000，一直没跟我签书面合同。"
            "2024年5月20号主管口头说不要我了，让我当天就走，还有5天年假没休。"
        ),
        "generic_baseline": {
            "reply": (
                "根据您的描述，公司口头辞退可能构成违法解除，通常可以主张 2N 赔偿金（工作 4 年多大概 8 到 9 个月工资，约 7 万多元）；"
                "另外一直没签书面合同可以主张双倍工资，一般最多支持 11 个月（约 9.9 万元）；"
                "未休年假也可以要求折算补偿，具体大概在 4000 元左右。"
                "总体估计大概在 17 万到 18 万元之间，具体金额需结合当地政策，建议咨询专业律师。"
            ),
            "flaws": [
                "金额模糊区间化（“约 7 万多 / 17～18 万”），未按 21.75 日薪与精确工龄折算到分",
                "未区分《劳动合同法》第 82 条与《司法解释（二）》第 6 条的按月计算/一年时效限制",
                "未给出逐条可查验的法条原文，也未判断二倍工资是否已超 1 年仲裁时效",
                "缺少证据举证责任清单、HR 抗辩预演及可下载申请书草稿",
            ],
        },
    },
    {
        "id": "high_wage_cap",
        "title": "高薪三倍封顶（12 年工龄）",
        "tag": "高薪封顶",
        "badge_cls": "info",
        "summary": "月薪 45000，工龄 12 年，社平工资 13000（触发 3 倍封顶与 12 年上限）",
        "story": (
            "我从2012年5月就在现在这家公司，一直做到2024年6月，月薪45000，"
            "公司突然以组织架构调整为由解除，我不接受。社平工资按13000算。"
        ),
        "generic_baseline": {
            "reply": (
                "您工作了 12 年零 1 个月，按 N=12.5 个月计算，违法解除赔偿金 2N 就是 25 个月工资，"
                "45000 × 25 = 112.5 万元左右。部分地区可能受社平工资三倍限制，"
                "具体是否封顶以及年假怎么算建议咨询当地仲裁委。"
            ),
            "flaws": [
                "直接拿 45000 元全额乘以 25 个月，多算近 20 万元（忽略高薪三倍封顶强制规则）",
                "未能把《劳动合同法》第 47 条第 2 款“3 倍封顶 + 12 年封顶”落地进计算公式",
                "没有给出《劳动合同法》第 87 条、第 47 条原文及法定一裁终局提示",
            ],
        },
    },
    {
        "id": "gap_need_more",
        "title": "信息缺口 · 触发精准追问",
        "tag": "拒猜追问",
        "badge_cls": "warn",
        "summary": "缺少入职时间、离职时间、月薪等关键事实，测试系统是否拒绝对着空气算钱",
        "story": "公司把我辞了，我没签合同。",
        "generic_baseline": {
            "reply": (
                "被辞退且未签合同通常非常有利！您一般可以要求违法解除赔偿金 2N，"
                "以及最多 11 个月的未签劳动合同二倍工资差额。假设月薪 8000 元、工作 2 年，"
                "大概能拿到 12 万元左右的赔偿，建议尽快收集工作证和工资条去仲裁。"
            ),
            "flaws": [
                "在不知道入职/离职日期和月薪的情况下直接“假设一个金额”误导当事人",
                "未明确告知缺少哪些必填要素、哪些属于可补录项",
                "没有先拦截无效计算，反而给出看似具体的“12 万元左右”结论",
            ],
        },
    },
    {
        "id": "out_of_scope",
        "title": "工伤认定 · 超出仲裁范围指路",
        "tag": "受案指路",
        "badge_cls": "warn",
        "summary": "工伤认定属于人社行政部门前置程序，仲裁委不直接认定工伤",
        "story": "我在厂里被机器压断手指，想让公司赔工伤，月薪6000。",
        "generic_baseline": {
            "reply": (
                "在厂里工作时压断手指属于工伤，您可以申请劳动仲裁要求公司支付一次性伤残补助金、"
                "医疗费和停工留薪期工资，按月薪 6000 元算大概能赔几万到十几万元不等。"
            ),
            "flaws": [
                "混淆前置程序：工伤认定和伤残等级鉴定归人社局/劳鉴委，不先认定无法直接仲裁赔款",
                "直接套用月薪估算赔款，可能误导伤者错过 1 年内申报工伤认定的关键窗口",
                "未指引去人社局工伤科申报及固定医疗/出勤证据链",
            ],
        },
    },
    {
        "id": "redline_winrate",
        "title": "索要胜诉率 · 红线合规拦截",
        "tag": "红线拒答",
        "badge_cls": "fail",
        "summary": "直接追问“能不能赢、胜率多少”，测试红线合规边界",
        "story": "我被辞退了，你直接告诉我能不能赢，胜率多少？",
        "generic_baseline": {
            "reply": (
                "根据经验，在没有严重违纪证据的情况下，员工被辞退申请劳动仲裁的胜诉率通常在 70%～85% 左右，"
                "只要准备好劳动合同和聊天记录，大概率能够赢下官司。"
            ),
            "flaws": [
                "在没有任何事实和证据的情况下随意编造“70%～85%”胜诉率",
                "违反法律科技产品合规红线：用伪概率代替事实判断和举证分析",
                "未引导当事人补充基本案情或做六维行动值得性评估",
            ],
        },
    },
    {
        "id": "cross_city_gate",
        "title": "跨城市管辖 · 闸门提示不越权",
        "tag": "管辖闸门",
        "badge_cls": "info",
        "summary": "同时出现深圳（履行地）与北京（注册地），提示管辖权归属与口径差异",
        "story": "我在深圳上班，公司注册在北京，2021年4月入职，月薪10000，一直没签合同，2024年5月被违法辞退。",
        "generic_baseline": {
            "reply": (
                "您可以向公司所在地的北京劳动仲裁委申请仲裁，大概可以主张 2N 赔偿金 6.5 万元左右"
                "以及未签合同二倍工资 11 万元，一共 17.5 万元。"
            ),
            "flaws": [
                "擅自帮当事人选定北京管辖，忽略“劳动合同履行地（深圳）优先”的法定选择权",
                "未核对两地社平工资口径差异及未签合同二倍工资的 1 年时效起算",
            ],
        },
    },
]


def get_demo_case(case_id: str) -> dict[str, Any] | None:
    for item in DEMO_CASES:
        if item["id"] == case_id:
            return item
    return None


def match_demo_by_story(story: str) -> dict[str, Any] | None:
    norm = (story or "").strip()
    if not norm:
        return None
    for item in DEMO_CASES:
        if item["story"].strip() == norm:
            return item
    return None


def audit_reply_citations(text: str) -> dict[str, Any]:
    """用本系统法条库核验一段文本里出现的《法规》第X条是否真实存在。"""
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for m in CITE_RE.finditer(text or ""):
        law_name, art = m.group(1).strip(), m.group(2).strip()
        key = (law_name, art)
        if key in seen:
            continue
        seen.add(key)
        slug = laws.resolve_name(law_name)
        exists = bool(slug and laws.exists(slug, art))
        found.append({
            "cite": f"《{law_name}》第{art}条",
            "slug": slug,
            "verified": exists,
        })
    verified_count = sum(1 for c in found if c["verified"])
    return {
        "total": len(found),
        "verified": verified_count,
        "unverified": len(found) - verified_count,
        "items": found,
    }


def _call_generic_chat(
    story: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
) -> tuple[str, str]:
    """调用 OpenAI 兼容接口获取普通大模型直答文本，返回 (reply_text, model_used)。"""
    env_cfg = llm.config() or {}
    key = (api_key or "").strip() or env_cfg.get("key", "")
    if not key:
        raise llm.LLMNotConfigured("未提供 API Key")
    base = ((base_url or "").strip() or env_cfg.get("base") or "https://api.openai.com/v1").rstrip("/")
    mdl = (model or "").strip() or env_cfg.get("model") or "gpt-4o-mini"

    payload = json.dumps({
        "model": mdl,
        "messages": [{"role": "user", "content": GENERIC_PROMPT + story}],
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    content = (raw.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return str(content).strip(), mdl


def compare_with_generic_ai(
    story: str,
    report: dict[str, Any],
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> dict[str, Any]:
    """生成「普通通用 AI vs 本系统」对比数据。

    优先使用实时 API（如果配置了 api_key 或环境变量）；
    否则若命中预设演示案例，返回清晰标注的离线典型对照；
    对未配置 Key 的自定义案情，给出透明的能力维度对比而不虚构模型回答。
    """
    env_cfg = llm.config()
    has_key = bool((api_key or "").strip() or (env_cfg and env_cfg.get("key")))

    if has_key:
        try:
            reply, used_model = _call_generic_chat(story, api_key=api_key, base_url=base_url, model=model)
            cite_audit = audit_reply_citations(reply)
            flaws: list[str] = []
            if cite_audit["total"] == 0:
                flaws.append("回复未引用具体法条条号（无法回库核验依据）")
            elif cite_audit["unverified"] > 0:
                flaws.append(f"存在 {cite_audit['unverified']} 条引用未能在本系统 10 部法规库中核实")
            if report.get("status") == "need_more":
                flaws.append("本系统判定要素不足已拒绝硬算；请对照左侧是否盲目给出了金额区间")
            elif report.get("status") in ("out_of_scope", "blocked"):
                flaws.append("本系统已触发受案范围/红线闸门拦截；请对照左侧是否越界作答")
            else:
                if any(tok in reply for tok in ("约", "大概", "左右", "万")):
                    flaws.append("金额表述多为近似估算（如“约/左右”），未像本系统按 21.75 日薪与精确工龄折算到分")
                flaws.append("纯对话回复缺少可逐条展开的法条原文、9 格完整度、时效倒计时与举证清单")
            return {
                "mode": "live",
                "mode_label": f"实时大模型实测（{used_model}）",
                "reply": reply or "（模型返回为空）",
                "cite_audit": cite_audit,
                "flaws": flaws,
                "error": "",
            }
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            live_err = f"实时大模型调用失败，已回退对照：{exc}"
    else:
        live_err = ""

    preset = match_demo_by_story(story)
    if preset:
        base = preset["generic_baseline"]
        return {
            "mode": "preset",
            "mode_label": "通用大模型典型直答对照（离线演示基线）",
            "reply": base["reply"],
            "cite_audit": audit_reply_citations(base["reply"]),
            "flaws": list(base["flaws"]),
            "error": live_err,
        }

    return {
        "mode": "structural",
        "mode_label": "未配置实时大模型 Key（展示结构化能力对照）",
        "reply": (
            "当前为纯离线规则模式，未向外部大模型发送该自定义案情。"
            "如需现场对比同一句自定义案情在普通大模型中的回答，请在右上角「⚙ 实时对比 API」"
            "填入兼容 OpenAI 协议的 API Key 后重新测算，系统会自动抓取其回答并对其法条引用做真伪核验。"
        ),
        "cite_audit": {"total": 0, "verified": 0, "unverified": 0, "items": []},
        "flaws": [
            "普通大模型无规则算式约束，面对 21.75 折算、3 倍社平封顶与时效边界易出现估算偏差",
            "普通大模型无本地 519 条法条原文库校验，无法保证每条法律依据可溯源",
            "普通大模型默认倾向于直接作答，缺少缺口拒猜、超范围指路与红线拦截机制",
        ],
        "error": live_err,
    }
