"""演示案例库与「普通 AI vs 本系统」对比模块（纯标准库，零依赖）。

特性：
1. DEMO_CASES：8 个中英双语预设演示案例（含 5 个合规可算清案例 + 3 个缺口/超范围/红线边界案例）。
2. 内存缓存（_LIVE_CACHE）+ 精简高速直答 Prompt（max_tokens=280），大幅缩短大模型对比响应时间。
3. 配合前端 /api/compare 异步加载：主测算结果在 10ms 内秒出，大模型对比异步填充，不阻塞主界面。
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from . import laws, llm

CITE_RE = re.compile(r"《([^》]+)》第\s*([零一二三四五六七八九十百\d]+)\s*条")

GENERIC_PROMPT_ZH = (
    "你是通用 AI 助手。请直接根据下面劳动者描述，简明扼要地用 120 字以内回答："
    "大概能拿到多少钱、依据什么法条以及下一步怎么办：\n\n"
)

GENERIC_PROMPT_EN = (
    "You are a generic AI assistant. Based on this China labor dispute description, "
    "briefly answer in under 110 words: roughly how much compensation they may claim, "
    "which PRC labor laws apply, and what to do next:\n\n"
)

# 简单内存缓存：同一案例重复演示秒回（最多保留 64 条）
_LIVE_CACHE: dict[tuple[str, str, str, str], dict[str, Any]] = {}

DEMO_CASES: list[dict[str, Any]] = [
    {
        "id": "full_2n",
        "title": "违法辞退 2N + 未签合同 + 年假",
        "title_en": "Illegal Dismissal 2N + No Contract",
        "tag": "合规可算",
        "tag_en": "Eligible",
        "badge_cls": "ok",
        "summary": "2020-03-01 入职，月薪 9000，未签合同，口头辞退，5 天未休年假",
        "summary_en": "Hired 2020-03-01, ¥9,000/mo, no written contract, verbally fired, 5 unused leave days",
        "story": (
            "我2020年3月1日进的这家厂，一个月9000，一直没跟我签书面合同。"
            "2024年5月20号主管口头说不要我了，让我当天就走，还有5天年假没休。"
        ),
        "story_en": (
            "Hired on 2020-03-01, monthly salary 9000, no written contract. "
            "Verbally fired on 2024-05-20, 5 unused annual leave days."
        ),
        "generic_baseline": {
            "reply": (
                "根据描述，公司口头辞退可能构成违法解除，通常可主张 2N 赔偿金（约 7～8 万元）；"
                "未签书面合同一般可主张最多 11 个月双倍工资差额（约 9.9 万元）；"
                "未休年假约 4000 元左右。合计估计 17～18 万元，具体以当地仲裁口径为准。"
            ),
            "reply_en": (
                "Verbal dismissal may entitle you to 2N severance (roughly RMB 70k-80k), "
                "up to 11 months of double-wage penalty for no written contract (~RMB 99k), "
                "and ~RMB 4,000 for unused annual leave. Total roughly RMB 170k-180k."
            ),
            "flaws": [
                "金额模糊区间化（“约 17～18 万”），未按 21.75 日薪与精确工龄折算到分",
                "未区分《劳动合同法》第 82 条与《司法解释（二）》第 6 条的按月计算及 1 年时效限制",
                "缺少逐条可核验的法条原文、时效倒计时、举证清单及申请书导出",
            ],
            "flaws_en": [
                "Vague range estimates (~170k-180k) instead of exact RMB/cent calculation via 21.75 daily divisor",
                "Misses Supreme Court Interpretation II Art. 6 (monthly double-wage rule) & 1-year limitation check",
                "Lacks verifiable statute texts, deadline countdown, evidence burden table, and filing draft export",
            ],
        },
    },
    {
        "id": "overtime_unpaid",
        "title": "拖欠工资 + 加班费 + 违法解除",
        "title_en": "Unpaid Wages + Overtime + Firing",
        "tag": "合规可算",
        "tag_en": "Eligible",
        "badge_cls": "ok",
        "summary": "月薪 8000，签过合同，拖欠 2 个月工资 + 违法辞退（工作日/周末加班）",
        "summary_en": "Signed contract, ¥8,000/mo, 2 months unpaid wages + overtime + illegal dismissal",
        "story": (
            "我2022年6月1日入职一家贸易公司，月薪8000，签过书面合同。"
            "公司欠了2个月工资没发，2024年10月15日又突然把我辞退让我当天走。"
        ),
        "story_en": (
            "Hired on 2022-06-01, monthly salary 8000, signed a written contract, "
            "unpaid wages of 16000, verbally fired on 2024-10-15."
        ),
        "generic_baseline": {
            "reply": (
                "公司拖欠的 2 个月工资 1.6 万元必须支付，违法辞退工作两年多大概给 5 个月工资（约 4 万元），"
                "总共大概 5.6 万元左右。建议保留好考勤和工资流水去申请仲裁。"
            ),
            "reply_en": (
                "You can claim RMB 16,000 in unpaid wages plus roughly 5 months of salary (~RMB 40,000) "
                "for wrongful termination, totaling around RMB 56,000."
            ),
            "flaws": [
                "未区分《调解仲裁法》第 27 条“欠薪在存续期间不受 1 年时效限制”的特殊规则",
                "未折算离职当年应享未休年休假补偿，也未给出单位负举证责任的证据清单",
            ],
            "flaws_en": [
                "Omits Art. 27 special statute-of-limitations exception for unpaid wages during active employment",
                "Misses pro-rata unused annual leave calculation and employer burden-of-proof checklist",
            ],
        },
    },
    {
        "id": "mutual_severance",
        "title": "协商一致解除 N + 未休年假",
        "title_en": "Mutual Agreement Severance (N)",
        "tag": "合规可算",
        "tag_en": "Eligible",
        "badge_cls": "ok",
        "summary": "2019-04-01 入职，月薪 12000，签过合同，2024-08-31 协商解除 + 8 天年假",
        "summary_en": "Hired 2019-04-01, ¥12,000/mo, signed contract, mutual termination 2024-08-31, 8 leave days",
        "story": (
            "我2019年4月1日入职，月薪12000，签了书面合同。"
            "2024年8月31日公司跟我协商一致解除劳动合同，还有8天年假没休。"
        ),
        "story_en": (
            "Hired on 2019-04-01, monthly salary 12000, signed a written contract, "
            "terminated by mutual agreement on 2024-08-31, 8 unused annual leave days."
        ),
        "generic_baseline": {
            "reply": (
                "协商一致解除通常由公司支付 N 倍经济补偿，您工作 5 年零 5 个月大约按 5.5 个月计算（约 6.6 万元），"
                "加上 8 天年假大约 8000～9000 元，合计约 7.5 万元。"
            ),
            "reply_en": (
                "Mutual termination usually pays N severance (~5.5 months × 12,000 = RMB 66,000) "
                "plus ~RMB 8,000-9,000 for 8 leave days, roughly RMB 75,000."
            ),
            "flaws": [
                "明确区分了协商一致（1N，适用《劳动合同法》第 46/47 条）而非违法解除（2N），普通 AI 易混淆",
                "本系统同时核验《司法解释（一）》第 35 条关于协商协议效力的前置风险提示",
            ],
            "flaws_en": [
                "Accurately applies 1N severance (Art. 46/47) instead of 2N, and formats exact 200% daily leave pay",
                "Includes judicial interpretation warning on binding effect of signed mutual settlement agreements",
            ],
        },
    },
    {
        "id": "high_wage_cap",
        "title": "高薪三倍封顶（12 年工龄）",
        "title_en": "High-Salary 3× Cap (12-Yr Tenure)",
        "tag": "合规可算",
        "tag_en": "Eligible",
        "badge_cls": "ok",
        "summary": "月薪 45000，工龄 12 年，社平工资 13000（触发 3 倍封顶与 12 年上限）",
        "summary_en": "Salary ¥45,000/mo, 12-yr tenure, local avg wage ¥13,000 (triggers 3× & 12-yr cap)",
        "story": (
            "我从2012年5月就在现在这家公司，一直做到2024年6月，月薪45000，"
            "公司突然以组织架构调整为由解除，我不接受。社平工资按13000算。"
        ),
        "story_en": (
            "Hired on 2012-05-01, terminated for restructuring on 2024-06-30, "
            "monthly salary 45000, local average wage 13000."
        ),
        "generic_baseline": {
            "reply": (
                "您工作了 12 年零 1 个月，按 N=12.5 个月计算，违法解除赔偿金 2N 就是 25 个月工资，"
                "45000 × 25 = 112.5 万元左右。具体是否封顶建议咨询当地仲裁委。"
            ),
            "reply_en": (
                "With 12+ years of tenure (N=12.5), 2N equals 25 months × RMB 45,000 = RMB 1,125,000. "
                "Local caps may apply depending on city policy."
            ),
            "flaws": [
                "直接拿 45000 全额乘以 25 个月，多算近 19 万元（漏算《劳动合同法》第 47 条 3 倍封顶与 12 年上限）",
                "没有给出《劳动合同法》第 47 条第 2 款原文及精确封顶公式（39,000 × 12 × 2）",
            ],
            "flaws_en": [
                "Overstates compensation by ~RMB 190,000 by ignoring Art. 47 mandatory 3× wage & 12-year tenure caps",
                "Fails to compute capped formula (39,000 × 12 × 2 = RMB 936,000) or cite Art. 47(2) text",
            ],
        },
    },
    {
        "id": "cross_city_gate",
        "title": "跨城市管辖 · 深圳工作/北京注册",
        "title_en": "Dual-City Jurisdiction (SZ / BJ)",
        "tag": "合规可算",
        "tag_en": "Eligible",
        "badge_cls": "ok",
        "summary": "同时出现深圳（履行地）与北京（注册地），提示管辖权与社平口径差异",
        "summary_en": "Work in Shenzhen, company registered in Beijing — checks jurisdiction & city standards",
        "story": "我在深圳上班，公司注册在北京，2021年4月入职，月薪10000，一直没签合同，2024年5月被违法辞退。",
        "story_en": (
            "Working in Shenzhen, company registered in Beijing. Hired 2021-04-01, "
            "monthly salary 10000, no written contract, fired on 2024-05-20."
        ),
        "generic_baseline": {
            "reply": (
                "您可以向公司所在地的北京劳动仲裁委申请仲裁，大概可以主张 2N 赔偿金 6.5 万元左右"
                "以及未签合同二倍工资 11 万元，一共 17.5 万元。"
            ),
            "reply_en": (
                "You can file in Beijing where the company is registered, claiming roughly RMB 65k severance "
                "and RMB 110k double wages (total ~RMB 175k)."
            ),
            "flaws": [
                "擅自帮当事人选定北京管辖，忽略“劳动合同履行地（深圳）优先”的法定选择权",
                "未核对京/深两地社平工资口径差异及未签合同二倍工资的 1 年时效起算",
            ],
            "flaws_en": [
                "Arbitrarily picks Beijing venue instead of alerting claimant to Shenzhen (workplace priority) option",
                "Ignores local average wage differences and double-wage 1-year limitation window",
            ],
        },
    },
    {
        "id": "gap_need_more",
        "title": "信息缺口 · 触发精准追问",
        "title_en": "Missing Facts · Anti-Guess Gate",
        "tag": "拒猜追问",
        "tag_en": "Follow-up",
        "badge_cls": "warn",
        "summary": "缺少入离职日期与月薪，验证系统绝不瞎猜金额",
        "summary_en": "Missing dates & salary — tests strict refusal to fabricate numbers",
        "story": "公司把我辞了，我没签合同。",
        "story_en": "The company fired me and there is no written contract.",
        "generic_baseline": {
            "reply": (
                "被辞退且未签合同通常非常有利！假设月薪 8000 元、工作 2 年，"
                "大概能拿到 12 万元左右的赔偿，建议尽快去仲裁。"
            ),
            "reply_en": (
                "You have a strong case! Assuming a salary of RMB 8,000 and 2 years tenure, "
                "you could claim roughly RMB 120,000 in total."
            ),
            "flaws": [
                "在不知入离职日期和月薪时直接“假设一个金额（12 万元）”误导当事人",
                "未列出必填缺口项，也没有提供结构化快速补录模板",
            ],
            "flaws_en": [
                "Hallucinates a fictional RMB 120,000 estimate using assumed salary and tenure",
                "Fails to halt calculation or guide user to fill the exact missing fields",
            ],
        },
    },
    {
        "id": "out_of_scope",
        "title": "工伤认定 · 超出仲裁范围指路",
        "title_en": "Work Injury · Administrative Redirect",
        "tag": "超范围",
        "tag_en": "Out-of-Scope",
        "badge_cls": "warn",
        "summary": "工伤认定归人社局行政前置程序，仲裁委不直接认定",
        "summary_en": "Work injury determination belongs to HRSSB before arbitration",
        "story": "我在厂里被机器压断手指，想让公司赔工伤，月薪6000。",
        "story_en": "My finger was injured by a machine at work, monthly salary 6000, seeking work injury compensation.",
        "generic_baseline": {
            "reply": (
                "在厂里工作压断手指属于工伤，您可以申请劳动仲裁要求公司赔付一次性伤残补助金和医疗费，"
                "按月薪 6000 元大概能赔几万到十几万元不等。"
            ),
            "reply_en": (
                "This qualifies as a work injury. File labor arbitration for disability allowance and medical costs, "
                "typically tens of thousands to over RMB 100k."
            ),
            "flaws": [
                "混淆行政前置程序：未先到人社局做工伤认定与伤残鉴定前，仲裁无法直接裁决工伤赔款",
                "直接估算赔款可能误导伤者错过 1 年内申报工伤认定的法定窗口",
            ],
            "flaws_en": [
                "Confuses administrative pre-procedure: arbitration cannot award disability pay prior to HRSSB injury determination",
                "Risk of causing claimant to miss the statutory 1-year work-injury filing window",
            ],
        },
    },
    {
        "id": "redline_winrate",
        "title": "索要胜诉率 · 红线合规拦截",
        "title_en": "Win-Rate Request · Red-Line Block",
        "tag": "红线拦截",
        "tag_en": "Red-Line",
        "badge_cls": "fail",
        "summary": "拒绝编造胜诉率百分比，守住法律科技合规边界",
        "summary_en": "Refuses fabricated win-rate percentages per compliance guardrails",
        "story": "我被辞退了，你直接告诉我能不能赢，胜率多少？",
        "story_en": "I was fired. Tell me directly if I will win and what my win rate is.",
        "generic_baseline": {
            "reply": (
                "在没有严重违纪证据的情况下，员工被辞退申请劳动仲裁的胜诉率通常在 70%～85% 左右，"
                "只要准备好聊天记录，大概率能够赢下官司。"
            ),
            "reply_en": (
                "Employees typically have a 70%-85% win rate in wrongful dismissal arbitration "
                "if chat logs are preserved."
            ),
            "flaws": [
                "在无任何事实与证据下编造“70%～85%”伪概率",
                "违反法律科技合规红线：用虚假确定性替代举证责任与值得性评估",
            ],
            "flaws_en": [
                "Fabricates a baseless 70%-85% win-rate guarantee with zero factual record",
                "Violates legal-tech compliance guardrails against outcome promises",
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
        if item["story"].strip() == norm or item["story_en"].strip() == norm:
            return item
    return None


EN_LAW_SLUGS = {
    "labor contract law": ("labor_contract_law", "Labor Contract Law"),
    "labor law": ("labor_law", "Labor Law"),
    "labor dispute mediation": ("arbitration_law", "Mediation & Arbitration Law"),
    "arbitration law": ("arbitration_law", "Mediation & Arbitration Law"),
    "annual leave": ("annual_leave_regulation", "Annual Leave Regulations"),
    "social insurance law": ("social_insurance_law", "Social Insurance Law"),
}
EN_CITE_RE = re.compile(
    r"(?i)(labor\s+contract\s+law|labor\s+law|labor\s+dispute\s+mediation[^()]*|arbitration\s+law|[^\.,;()]*annual\s+leave[^\.,;()]*|social\s+insurance\s+law)"
    r"\s*(?:\(?\s*arts?\.?\s*([\d,\s]+)\s*\)?)"
)


def audit_reply_citations(text: str) -> dict[str, Any]:
    """用本系统法条库核验中英文法条引用（支持《法规》第X条与 English Art(s). N）。"""
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
    for m in EN_CITE_RE.finditer(text or ""):
        raw_law = m.group(1).lower()
        slug = ""
        disp = m.group(1).strip()
        for kw, (s, label) in EN_LAW_SLUGS.items():
            if kw in raw_law:
                slug, disp = s, label
                break
        for art in re.findall(r"\d+", m.group(2)):
            key = (slug or disp, art)
            if key in seen:
                continue
            seen.add(key)
            exists = bool(slug and laws.exists(slug, art))
            found.append({
                "cite": f"{disp} Art. {art}",
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


def _resolve_live_cfg(api_key: str = "", base_url: str = "", model: str = "") -> dict[str, str] | None:
    env_cfg = llm.config() or {}
    client_key = (api_key or "").strip()
    key = client_key or env_cfg.get("key", "")
    if not key:
        return None
    # 访客提供自己的 key 时才允许覆盖地址和模型；服务器 key 只发送到后台配置的接口。
    base = env_cfg.get("base") or "https://api.openai.com/v1"
    mdl = env_cfg.get("model") or "gpt-4o-mini"
    if client_key:
        base = (base_url or "").strip() or base
        mdl = (model or "").strip() or mdl
    return {"key": key, "base": base.rstrip("/"), "model": mdl}


def has_live_cache(
    story: str,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    lang: str = "en",
) -> bool:
    cfg = _resolve_live_cfg(api_key, base_url, model)
    if not cfg:
        return False
    return (story.strip(), cfg["model"], cfg["base"], lang) in _LIVE_CACHE


def _call_generic_chat(
    story: str,
    cfg: dict[str, str],
    lang: str = "en",
) -> tuple[str, int]:
    """调用 OpenAI 兼容接口获取简短直答文本，返回 (reply_text, elapsed_ms)。"""
    prompt = (GENERIC_PROMPT_ZH if lang == "zh" else GENERIC_PROMPT_EN) + story
    payload = json.dumps({
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 280,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['base']}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['key']}",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    ms = int(round((time.perf_counter() - t0) * 1000))
    content = (raw.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return str(content).strip(), ms


def _build_live_flaws(reply: str, report: dict[str, Any], cite_audit: dict[str, Any], lang: str) -> list[str]:
    flaws: list[str] = []
    if lang == "zh":
        if cite_audit["total"] == 0:
            flaws.append("回复未引用《法规》第X条格式条号（无法直接回库核验）")
        elif cite_audit["unverified"] > 0:
            flaws.append(f"存在 {cite_audit['unverified']} 条引用未在本系统 10 部法规库中核实")
        if report.get("status") == "need_more":
            flaws.append("本系统判定要素不足已拒绝硬算；请对照是否盲目给出了估算区间")
        elif report.get("status") in ("out_of_scope", "blocked"):
            flaws.append("本系统已触发受案范围/红线闸门拦截；请对照是否越界作答")
        else:
            if any(tok in reply for tok in ("约", "大概", "左右", "万", "~")):
                flaws.append("金额表述多为近似估算（如“约/左右”），未按 21.75 日薪与精确工龄折算到分")
            flaws.append("纯对话回复缺少可逐条展开的法条原文、9 格完整度、时效倒计时与举证清单")
    else:
        if cite_audit["total"] == 0:
            flaws.append("No structured PRC statute citations detected for automated DB verification")
        elif cite_audit["unverified"] > 0:
            flaws.append(f"{cite_audit['unverified']} cited article(s) could not be verified in the 519-article DB")
        if report.get("status") == "need_more":
            flaws.append("Rule engine halted due to missing required facts; check if LLM guessed amounts")
        elif report.get("status") in ("out_of_scope", "blocked"):
            flaws.append("Rule engine blocked out-of-scope / red-line prompt; check if LLM overstepped")
        else:
            if any(tok in reply.lower() for tok in ("approx", "roughly", "around", "~", "about")):
                flaws.append("Uses rough estimates instead of deterministic 21.75-day & statutory cap math")
            flaws.append("Lacks expandable original PRC statute texts, 9-cell completeness, deadline & filing draft")
    return flaws


def compare_with_generic_ai(
    story: str,
    report: dict[str, Any],
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    lang: str = "en",
) -> dict[str, Any]:
    """生成「普通通用 AI vs 本系统」对比数据（支持缓存与中英双语）。"""
    cfg = _resolve_live_cfg(api_key=api_key, base_url=base_url, model=model)
    live_err = ""

    if cfg:
        ckey = (story.strip(), cfg["model"], cfg["base"], lang)
        cached = _LIVE_CACHE.get(ckey)
        if cached:
            return {**cached, "cached": True}
        try:
            reply, elapsed_ms = _call_generic_chat(story, cfg, lang=lang)
            cite_audit = audit_reply_citations(reply)
            flaws = _build_live_flaws(reply, report, cite_audit, lang=lang)
            res = {
                "mode": "live",
                "mode_label": (
                    f"实时大模型实测（{cfg['model']} · {elapsed_ms} ms）"
                    if lang == "zh" else f"Live LLM ({cfg['model']} · {elapsed_ms} ms)"
                ),
                "reply": reply or ("（模型返回为空）" if lang == "zh" else "(Empty response)"),
                "cite_audit": cite_audit,
                "flaws": flaws,
                "elapsed_ms": elapsed_ms,
                "cached": False,
                "error": "",
            }
            if len(_LIVE_CACHE) >= 64:
                _LIVE_CACHE.pop(next(iter(_LIVE_CACHE)))
            _LIVE_CACHE[ckey] = res
            return res
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            live_err = (
                f"实时大模型调用失败，已回退对照：{exc}"
                if lang == "zh" else f"Live LLM call failed, fell back to baseline: {exc}"
            )

    preset = match_demo_by_story(story)
    if preset:
        base = preset["generic_baseline"]
        reply_txt = base["reply"] if lang == "zh" else base.get("reply_en", base["reply"])
        flaw_list = base["flaws"] if lang == "zh" else base.get("flaws_en", base["flaws"])
        return {
            "mode": "preset",
            "mode_label": (
                "通用大模型典型直答对照（离线演示基线）"
                if lang == "zh" else "Generic LLM Typical Output (Offline Baseline)"
            ),
            "reply": reply_txt,
            "cite_audit": audit_reply_citations(reply_txt),
            "flaws": list(flaw_list),
            "elapsed_ms": None,
            "cached": True,
            "error": live_err,
        }

    return {
        "mode": "structural",
        "mode_label": (
            "未配置实时大模型 Key（结构化能力对照）"
            if lang == "zh" else "No Live LLM Key (Capability Comparison)"
        ),
        "reply": (
            "当前为纯离线规则模式。如需现场对比自定义案情，可在右上角「⚙ 实时对比 API」填入 API Key 后重新测算。"
            if lang == "zh" else
            "Offline rule mode active. Open '⚙ Live AI API' above to enter an OpenAI-compatible key for live side-by-side comparison on custom stories."
        ),
        "cite_audit": {"total": 0, "verified": 0, "unverified": 0, "items": []},
        "flaws": (
            [
                "普通大模型无规则算式约束，面对 21.75 折算、3 倍社平封顶与时效边界易出现偏差",
                "普通大模型无本地 519 条法条原文库校验，无法保证每条依据可溯源",
            ]
            if lang == "zh" else [
                "No deterministic 21.75-day / 3× cap / statutory tenure arithmetic",
                "No local 519-article PRC statute verification or compliance guardrails",
            ]
        ),
        "elapsed_ms": None,
        "cached": True,
        "error": live_err,
    }
