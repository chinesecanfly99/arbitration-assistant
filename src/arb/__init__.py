"""劳动仲裁维权助手 —— 规则内核（不依赖大模型）。

导入本包时会做一件环境层面的兜底：把 stdout/stderr 切成 UTF-8。
理由见 console.py——Windows 默认 GBK 控制台遇到 ✅/❌ 会 UnicodeEncodeError 直接退出码 1，
而这不是功能坏了，只是输出管道编码没对齐。放在 `__init__` 里是为了覆盖全部入口：
`python -m arb.cli / arb.web / arb.demo / arb.pdf` 以及 `python -m scripts.*` 都会先导入本包。
"""
from .calc import (  # noqa: F401
    ClaimInput,
    Item,
    Policy,
    annual_leave_entitlement,
    annual_leave_pay,
    compute,
    double_wage,
    economy_compensation,
    illegal_dismissal_compensation,
    overtime_pay,
    service_months,
    severance_months_by_law,
)
from .console import enable_utf8
from .deadline import analyze, limitation  # noqa: F401

__version__ = "0.1.0"

# 永不抛异常：设置输出编码失败不该让主流程挂掉（console.enable_utf8 内部已 try/except）
enable_utf8()
