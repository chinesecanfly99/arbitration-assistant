"""代码里引用的每一条法条，都必须能在法条库里查明。

这是"幻觉引用率 = 0"落到自己代码上的检查：写代码的人也可能记错条号。
用源码扫描 + 运行时双重校验，任何一处 basis 失配就让测试红。
"""
import os
import re
from datetime import date

import pytest

from arb import laws
from arb.calc import ClaimInput, compute

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CITE_RE = re.compile(r"《([^》]+)》\s*第\s*([零一二三四五六七八九十百\d]+)\s*条")



def _extract_citations(text: str):
    out = []
    for law_name, art in CITE_RE.findall(text):
        out.append((law_name, art))
    return out


def test_all_basis_in_source_resolve():
    src = open(os.path.join(ROOT, "src", "arb", "calc.py"), encoding="utf-8").read()
    cites = _extract_citations(src)
    assert len(cites) >= 5, f"只扫到 {len(cites)} 处引用，正则可能失效"
    for law_name, art in cites:
        slug = laws.resolve_name(law_name)
        assert slug, f"《{law_name}》未收录，无法校验"
        assert laws.exists(slug, art), f"《{law_name}》第{art}条在库中不存在"


def test_all_basis_in_computed_items_resolve():
    """跑一遍完整算账，逐条核验输出里的 basis。"""
    inp = ClaimInput(
        hire_date=date(2021, 3, 1),
        end_date=date(2024, 8, 20),
        monthly_wage=9000,
        termination="illegal_dismissal",
        has_written_contract=False,
        contract_signed_date=date(2022, 9, 1),
        overtime_workday_hours=40,
        overtime_restday_hours=32,
        overtime_holiday_hours=8,
        unused_annual_leave_days=5,
        unpaid_wages=4000,
    )
    res = compute(inp)
    assert res["items"], "算账结果为空"
    for item in res["items"]:
        for law_name, art in _extract_citations(item["basis"]):
            slug = laws.resolve_name(law_name)
            assert slug, f"《{law_name}》未收录"
            assert laws.exists(slug, art), f"{item['name']} 引用《{law_name}》第{art}条不存在"
        assert item["formula"], f"{item['name']} 缺公式，无法向用户解释"


def test_every_item_has_citable_source():
    inp = ClaimInput(hire_date=date(2020, 1, 1), end_date=date(2023, 6, 30), monthly_wage=12000)
    res = compute(inp)
    for item in res["items"]:
        assert item["basis"].startswith("《"), f"{item['name']} 无法条依据"


def test_verifier_catches_hallucinated_cite():
    """模拟模型输出一个假条号，校验器必须拦住。"""
    bad = laws.verify_citation("labor_contract_law", "第120条", "解除时应支付三个月工资安抚金")
    assert bad["ok"] is False and bad["reason"] == "law_or_article_not_found"
