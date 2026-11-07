"""城市口径库：社平工资、最低工资、一裁终局金额线、仲裁窗口。

为什么单独抽出来：
- 同一部《劳动合同法》第 47 条，在深圳和北京算出来的 3 倍封顶不是一个数；
- 把城市数字写死在代码里，改一次要动核心计算，评审一问"你这数哪来的"就答不上；
- 所以每城一个 JSON，带 `sources`（官方文件名称+发布日期）与 `verified_at`（核验日），
  程序只读不算，缺城市就明说"没覆盖"，绝不拿别的城市的数字顶替。

口径提醒（写在数据里，也写在这里）：
- 3 倍封顶用的是"上年度职工月平均工资"，各地口径不同（全口径 / 城镇非私营在岗职工）；
- 一裁终局金额线 = 当地月最低工资 × 12（《劳动争议调解仲裁法》第 47 条第 1 项）；
- 社保缴费基数上下限是另一套口径，不能拿来当 3 倍封顶用。

纯标准库、纯相对路径，macOS / Windows / Linux 行为一致。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CITY_DIR = os.path.join(ROOT, "data", "city")


@dataclass
class City:
    name: str
    province: str
    aliases: list[str] = field(default_factory=list)
    verified_at: str = ""
    verify_required: bool = True
    params: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)
    arbitration: dict = field(default_factory=dict)
    online: str = ""
    hotlines: dict = field(default_factory=dict)

    # ---- 常用口径，全部是"读数据"，不是"猜数字" ----
    @property
    def min_wage(self) -> float | None:
        return self.params.get("min_wage_monthly")

    @property
    def avg_wage(self) -> float | None:
        """上年度职工月平均工资（3 倍封顶的基数）。"""
        return self.params.get("avg_wage_monthly")

    @property
    def cap_3x(self) -> float | None:
        a = self.avg_wage
        return round(a * 3, 2) if a else None

    @property
    def one_final_award_threshold(self) -> float | None:
        m = self.min_wage
        return m * 12 if m else None

    def as_dict(self) -> dict:
        return {
            "city": self.name,
            "province": self.province,
            "verified_at": self.verified_at,
            "verify_required": self.verify_required,
            "params": self.params,
            "sources": self.sources,
            "notes": self.notes,
            "arbitration": self.arbitration,
            "online": self.online,
            "hotlines": self.hotlines,
            "cap_3x": self.cap_3x,
            "one_final_award_threshold": self.one_final_award_threshold,
        }


@lru_cache(maxsize=1)
def load_all() -> tuple[City, ...]:
    if not os.path.isdir(CITY_DIR):
        return ()
    out = []
    for fn in sorted(os.listdir(CITY_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(CITY_DIR, fn), encoding="utf-8") as f:
            r = json.load(f)
        out.append(
            City(
                name=r.get("city", fn[:-5]),
                province=r.get("province", ""),
                aliases=r.get("aliases", []),
                verified_at=r.get("verified_at", ""),
                verify_required=r.get("verify_required", True),
                params=r.get("params", {}),
                sources=r.get("sources", {}),
                notes=r.get("notes", {}),
                arbitration=r.get("arbitration", {}),
                online=r.get("online", ""),
                hotlines=r.get("hotlines", {}),
            )
        )
    return tuple(out)


def _clean(name: str | None) -> str:
    s = (name or "").strip()
    for tail in ("市", "省", "特别行政区"):
        if s.endswith(tail) and len(s) > len(tail):
            s = s[: -len(tail)]
    return s


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    """别名 → 规范城市名（"深圳市"）。"""
    m: dict[str, str] = {}
    for c in load_all():
        m[_clean(c.name)] = c.name
        for a in c.aliases:
            m[_clean(a)] = c.name
    return m


def normalize(name: str | None) -> str:
    """把用户的写法收敛成规范城市名；没覆盖的城市原样返回（调用方据此说"没覆盖"）。"""
    cleaned = _clean(name)
    return _alias_map().get(cleaned, cleaned)


def get(name: str | None) -> City | None:
    if not name:
        return None
    target = normalize(name)
    for c in load_all():
        if c.name == target:
            return c
    return None


def covered(name: str | None) -> bool:
    return get(name) is not None


def names() -> list[str]:
    return [c.name for c in load_all()]


def table() -> list[dict]:
    """给 CLI / 前端做"我们覆盖了哪些城市"的对照表。"""
    return [
        {
            "city": c.name,
            "province": c.province,
            "min_wage_monthly": c.min_wage,
            "avg_wage_monthly": c.avg_wage,
            "cap_3x": c.cap_3x,
            "one_final_award_threshold": c.one_final_award_threshold,
            "verified_at": c.verified_at,
            "source": c.sources.get("avg_wage", ""),
        }
        for c in load_all()
    ]


def social_avg_wage(name: str | None) -> float | None:
    c = get(name)
    return c.avg_wage if c else None
