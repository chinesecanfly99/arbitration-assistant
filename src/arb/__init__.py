"""劳动仲裁维权助手 —— 规则内核（不依赖大模型）。"""
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
from .deadline import analyze, limitation  # noqa: F401

__version__ = "0.1.0"
