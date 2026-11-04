"""法条库读取与检索（S2.4 的最小可用版）。

设计取舍：
- 不引第三方检索库（三周项目，装不动、调不动）。用中文 bigram 覆盖率打分，
  30 条法条规模下 top5 命中已经够用；数据长到几千条再换 BM25/向量。
- 只做「检索」，不做「生成」。模型只能从检索结果里挑条号——这是防幻觉的地基。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Optional

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "laws"
)

LAW_ORDER = [
    "labor_contract_law",
    "arbitration_law",
    "labor_law",
    "annual_leave_regulation",
    "annual_leave_impl",
    "social_insurance_law",
    "labor_contract_impl",
    "wage_payment_rules",
]

CN = "零一二三四五六七八九十百"


def cn_to_int(s: str) -> Optional[int]:
    if not s:
        return None
    if s.isdigit():
        return int(s)
    section = 0
    for ch in s:
        if ch == "百":
            section = (section or 1) * 100
        elif ch == "十":
            section = (section or 1) * 10
        elif ch in CN:
            section += CN.index(ch)
        else:
            return None
    return section or None


def int_to_cn(n: int) -> str:
    if n <= 10:
        return "十" if n == 10 else CN[n]
    if n < 20:
        return "十" + CN[n - 10]
    if n < 100:
        tens, ones = divmod(n, 10)
        return CN[tens] + "十" + (CN[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        s = CN[hundreds] + "百"
        if rest == 0:
            return s
        if rest < 10:
            return s + "零" + CN[rest]
        return s + int_to_cn(rest)
    return str(n)


@dataclass
class Article:
    law: str
    slug: str
    version_date: str
    article_no: str
    article_idx: Optional[int]
    text: str
    source_url: str

    @property
    def num(self) -> Optional[int]:
        """条号（阿拉伯数字），如第四十七条 -> 47。article_idx 是源文件里的位置，不是条号。"""
        return cn_to_int(self.article_no.replace("第", "").replace("条", ""))

    @property
    def cite(self) -> str:
        """人类可读的引用串，如《劳动合同法》第四十七条。"""
        short = SHORT_NAME.get(self.slug, self.law)
        return f"《{short}》{self.article_no}"

    def as_dict(self) -> dict:
        return {
            "law": self.law,
            "slug": self.slug,
            "version_date": self.version_date,
            "article_no": self.article_no,
            "cite": self.cite,
            "text": self.text,
            "source_url": self.source_url,
        }


SHORT_NAME = {
    "labor_contract_law": "劳动合同法",
    "arbitration_law": "劳动争议调解仲裁法",
    "labor_law": "劳动法",
    "annual_leave_regulation": "职工带薪年休假条例",
    "annual_leave_impl": "企业职工带薪年休假实施办法",
    "social_insurance_law": "社会保险法",
    "labor_contract_impl": "劳动合同法实施条例",
    "wage_payment_rules": "工资支付暂行规定",
}


ALIASES = {
    "实施办法": "annual_leave_impl",
    "年休假实施办法": "annual_leave_impl",
    "年休假条例": "annual_leave_regulation",
    "带薪年休假条例": "annual_leave_regulation",
    "劳动合同法": "labor_contract_law",
    "仲裁法": "arbitration_law",
    "调解仲裁法": "arbitration_law",
    "劳动法": "labor_law",
    "社保法": "social_insurance_law",
    "社会保险法": "social_insurance_law",
    "实施条例": "labor_contract_impl",
    "工资支付暂行规定": "wage_payment_rules",
}


def resolve_name(name: str) -> Optional[str]:
    """把法名或简称解析成 slug；不在库里的返回 None（这也是拦"编造法规"的入口）。"""
    name = (name or "").strip().strip("《》")
    for slug, short in SHORT_NAME.items():
        if name == short or name == slug:
            return slug
    return ALIASES.get(name)


@lru_cache(maxsize=1)
def load_all() -> tuple[Article, ...]:
    arts: list[Article] = []
    for slug in LAW_ORDER:
        path = os.path.join(DATA_DIR, f"{slug}.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                arts.append(
                    Article(
                        law=r["law"],
                        slug=r["slug"],
                        version_date=r.get("version_date", ""),
                        article_no=r["article_no"],
                        article_idx=r.get("article_idx"),
                        text=r["text"],
                        source_url=r.get("source_url", ""),
                    )
                )
    return tuple(arts)


def by_slug(slug: str) -> list[Article]:
    return [a for a in load_all() if a.slug == slug]


def get(slug: str, num: "int | str") -> Optional[Article]:
    """按条号取（第四十七条 -> get(slug, 47)）。允许传 "87" 这类字符串。"""
    try:
        target = int(num)
    except (TypeError, ValueError):
        return None
    for a in load_all():
        if a.slug == slug and a.num == target:
            return a
    return None


def exists(slug: str, article_no: str) -> bool:
    """用于校验模型输出的条号是否真实存在——防幻觉的最后一关。"""
    n = cn_to_int(str(article_no).replace("第", "").replace("条", ""))
    return get(slug, n) is not None if n else False


_BIGRAM_CACHE: dict[str, set[str]] = {}


def bigrams(text: str) -> set[str]:
    key = text
    if key in _BIGRAM_CACHE:
        return _BIGRAM_CACHE[key]
    clean = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
    grams = {clean[i : i + 2] for i in range(len(clean) - 1)} if len(clean) > 1 else {clean}
    _BIGRAM_CACHE[key] = grams
    return grams


NUM_RE = re.compile(r"([零一二三四五六七八九十百两\d\.]+)\s*(个月|年|日|天|%|倍|元|小时)")


def num_tokens(text: str) -> set[tuple[str, str]]:
    """把"两年""300%""二十四个月"抽成 (数字, 单位)，用于拦截"条号对、数字被改"。"""
    out = set()
    for num, unit in NUM_RE.findall(text or ""):
        out.add((num.replace("两", "二"), unit))
    return out


def support(claim: str, text: str) -> float:
    """主张文字被法条原文覆盖的比例（0–1）。用于拦"条号真、内容是编的"。"""
    c = bigrams(claim)
    if not c:
        return 0.0
    return round(len(c & bigrams(text)) / len(c), 4)


def verify_citation(slug: str, article_no: str, claim: str = "", min_support: float = 0.60) -> dict:
    """一次校验三件事：法是否存在、条号是否存在、内容是否被原文支持。

    这是产品"可信层"的内核，也是评测里"幻觉引用率 = 0"的执行点。

    分工要说清楚：
    - 第一层（这里，确定性的）：法是否存在 / 条号是否存在 / 主张里的数字是否出现在原文。
      能挡住全部条号越界、整部法编造、以及绝大多数改数字的伪造。
    - 第二层（模型层，尚未接入）：把"关系被反写"的情况挑出来。例：原文"六个月以上不满一年
      按一年计算"，伪造"按半个月计算"——每个词都在原文里，bigram 支持度反而高达 0.85，
      比正常改写（0.68–0.78）还高。所以 support 只能当"是否抄自原文"的信号，
      不能当"内容是否正确"的判据，语义裁决必须交给第二层。
    """
    art = None
    if slug in SHORT_NAME:
        n = cn_to_int(article_no.replace("第", "").replace("条", ""))
        art = get(slug, n) if n else None
    if art is None:
        return {"ok": False, "reason": "law_or_article_not_found", "cite": f"《{slug}》{article_no}", "support": 0.0}
    if not claim:
        return {"ok": True, "reason": "article_exists", "cite": art.cite, "support": 1.0}
    s = support(claim, art.text)
    missing = num_tokens(claim) - num_tokens(art.text)
    if missing:
        return {
            "ok": False,
            "reason": "numbers_not_in_article",
            "cite": art.cite,
            "support": s,
            "missing": sorted(missing),
            "source_url": art.source_url,
        }
    return {
        "ok": s >= min_support,
        "reason": "supported" if s >= min_support else "claim_not_in_article",
        "cite": art.cite,
        "support": s,
        "source_url": art.source_url,
    }


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    import math

    docs = load_all()
    n = len(docs) or 1
    df: dict[str, int] = {}
    for a in docs:
        for g in bigrams(a.text):
            df[g] = df.get(g, 0) + 1
    return {g: math.log((n + 1) / (c + 0.5)) for g, c in df.items()}


EXPAND = {
    "年限": "工作年限 每满一年",
    "双倍工资": "二倍的工资",
    "辞退": "解除",
    "开除": "解除",
    "炒": "解除",
    "年假": "年休假",
    "没签合同": "订立书面劳动合同",
    "拖欠": "无故拖欠",
    "加班": "延长工作时间",
    "赔偿": "赔偿金",
    "仲裁费": "不收费",
    "多久": "时效期间",
}


def expand_query(query: str) -> str:
    extra = [v for k, v in EXPAND.items() if k in query]
    return query + " " + " ".join(extra) if extra else query


def search(query: str, k: int = 5, slugs: Optional[Iterable[str]] = None) -> list[tuple[Article, float]]:
    """IDF 加权的 bigram 覆盖率打分，返回 top-k 法条。

    纯覆盖率会让长条文占便宜（词多自然命中多），所以按 bigram 的稀有度加权：
    "双倍工资"这种只出现在个别条文里的词，权重远高于"用人单位"。
    """
    q = bigrams(expand_query(query))
    if not q:
        return []
    allow = set(slugs) if slugs else None
    idf = _idf()
    qw = {g: idf.get(g, 0.0) for g in q}
    total = sum(qw.values()) or 1.0
    scored = []
    for a in load_all():
        if allow and a.slug not in allow:
            continue
        hit = q & bigrams(a.text)
        if not hit:
            continue
        s = sum(qw[g] for g in hit) / total
        scored.append((a, s))
    scored.sort(key=lambda x: (-x[1], x[0].slug, x[0].num or 0))
    return scored[:k]
