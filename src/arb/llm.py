"""模型层：把"一大段话"抽成 schema.json 里的字段（S3.2）。

三条设计原则：
1. **可缺席**：没有配置 key 时 `available()` 为 False，上层退回规则抽取，整条流水线照跑。
   答辩现场断网/欠费也不至于全崩。
2. **不信任输出**：模型返回的必须是 JSON，且要通过 schema 校验；字段类型不对就整条丢弃，
   退回规则结果，而不是"尽力修补"——修补出来的参数会直接变成错的钱。
3. **只抽参数、不算钱**：这里绝不出现任何金额计算，钱永远由 calc.py 算。

环境变量：
    ARB_LLM_API_KEY / OPENAI_API_KEY    密钥
    ARB_LLM_BASE_URL / OPENAI_BASE_URL  兼容 OpenAI 协议的网关（默认 api.openai.com/v1）
    ARB_LLM_MODEL                       默认 gpt-4o-mini
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "schema.json")

FIELD_TYPES: dict[str, type] = {
    "hire_date": str,
    "end_date": str,
    "monthly_wage": (int, float),
    "termination": str,
    "has_written_contract": bool,
    "contract_signed_date": str,
    "overtime_workday_hours": (int, float),
    "overtime_restday_hours": (int, float),
    "overtime_holiday_hours": (int, float),
    "taken_annual_leave_days": (int, float),
    "unused_annual_leave_days": (int, float),
    "unpaid_wages": (int, float),
}
TERMINATIONS = {"illegal_dismissal", "mutual_agreement", "employee_resign", "legal_termination"}

PROMPT = """你是劳动仲裁立案窗口的工作人员，负责把当事人的大白话转成结构化要素。
只输出一个 JSON 对象，字段如下（不知道就填 null，绝对不要编）：
hire_date: 入职日期 YYYY-MM-DD
end_date: 离职/解除日期 YYYY-MM-DD
monthly_wage: 离职前 12 个月平均月薪（税前，数字）
termination: 四选一 illegal_dismissal(公司违法辞退) / mutual_agreement(协商一致) / employee_resign(自己辞职) / legal_termination(到期终止或依法解除)
has_written_contract: 是否签过书面劳动合同 true/false
contract_signed_date: 补签日期 YYYY-MM-DD 或 null
overtime_workday_hours / overtime_restday_hours / overtime_holiday_hours: 工作日/休息日/法定节假日加班小时数，没有填 0
taken_annual_leave_days: 已休年假天数
unused_annual_leave_days: 未休年假天数
unpaid_wages: 被拖欠工资金额（元），没有填 0
当事人原话：
"""


class LLMNotConfigured(RuntimeError):
    pass


def _env(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def config() -> dict[str, str] | None:
    key = _env("ARB_LLM_API_KEY", "OPENAI_API_KEY")
    if not key:
        return None
    base = _env("ARB_LLM_BASE_URL", "OPENAI_BASE_URL") or "https://api.openai.com/v1"
    return {"key": key, "base": base.rstrip("/"), "model": _env("ARB_LLM_MODEL") or "gpt-4o-mini"}


def available() -> bool:
    return config() is not None


def validate(obj: Any) -> dict:
    """只保留类型正确的字段；类型不对的整条丢弃并在 bad 里说明。"""
    if not isinstance(obj, dict):
        raise ValueError("模型返回的不是 JSON 对象")
    good, bad = {}, []
    for k, t in FIELD_TYPES.items():
        if k not in obj:
            continue
        v = obj[k]
        if v is None:
            continue
        if isinstance(t, tuple):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        elif t is bool:
            ok = isinstance(v, bool)
        elif t is str:
            ok = isinstance(v, str) and v.strip() != ""
        else:
            ok = isinstance(v, t)
        if not ok:
            bad.append(f"{k} 的类型不对：{type(v).__name__}")
            continue
        if k == "termination" and v not in TERMINATIONS:
            bad.append(f"termination 不在枚举内：{v}")
            continue
        good[k] = v
    return {"fields": good, "bad": bad}


def call(prompt: str) -> dict:
    cfg = config()
    if cfg is None:
        raise LLMNotConfigured("没有配置 ARB_LLM_API_KEY / OPENAI_API_KEY")
    body = json.dumps({
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["base"] + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["choices"][0]["message"]["content"])


def extract_fields(story: str) -> dict:
    """返回 {"fields": {...}, "bad": [...]}；未配置时抛 LLMNotConfigured，由上层回退。"""
    return validate(call(PROMPT + story))
