"""schema.json 的测试：它是"前后端与模型层共用的唯一字段定义"，所以它自己必须先是对的。

这条测试是被一个真实 bug 逼出来的：schema.json 里曾经有一行
    "social_avg_wage", "has_written_contract": { ... }
这是**语法错误**的 JSON——两个 key 挤在一个冒号前面。因为它从来没被任何代码解析过
（只有 llm.py 在 prompt 里提到路径），所以没人发现，直到这次核对字段才看见。
教训：叫"唯一字段定义"的文件，必须有一条测试真的去解析它。
"""
import dataclasses
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "schema.json")


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA, encoding="utf-8") as f:
        return json.load(f)


def test_schema_is_valid_json(schema):
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["type"] == "object"
    assert isinstance(schema["properties"], dict)


def test_every_claim_input_field_is_declared(schema):
    """ClaimInput 的每个字段都必须在 schema 里有定义，否则"唯一字段定义"就是假的。"""
    from arb.calc import ClaimInput

    declared = set(schema["properties"])
    missing = [f.name for f in dataclasses.fields(ClaimInput) if f.name not in declared]
    assert missing == [], f"schema.json 少了这些字段：{missing}"


def test_required_fields_are_declared(schema):
    for key in schema["required"]:
        assert key in schema["properties"], f"required 里的 {key} 没有定义"


def test_required_matches_pipeline_requirements(schema):
    """schema 的 required 与 pipeline 的 REQUIRED 不能两套说法。

    pipeline 额外把 end_date 当必填（strict 模式），schema 里它是"仍在职可留空"，
    所以这里只要求 schema.required ⊆ pipeline.REQUIRED，且必须包含三个核心字段。
    """
    from arb.pipeline import REQUIRED

    assert set(schema["required"]) <= set(REQUIRED)
    assert {"hire_date", "monthly_wage", "termination"} <= set(schema["required"])


def test_field_types_are_reasonable(schema):
    props = schema["properties"]
    for key, spec in props.items():
        assert "type" in spec, f"{key} 没写 type"
        t = spec["type"]
        assert isinstance(t, (str, list)), f"{key} 的 type 写法不对"
        if isinstance(t, list):
            assert all(isinstance(x, str) for x in t), key


def test_termination_enum_matches_calc_types(schema):
    from arb.calc import TerminationType

    enum = set(schema["properties"]["termination"]["enum"])
    assert enum == set(getattr(TerminationType, "__args__")), "解除方式枚举与 calc.py 不一致"


def test_city_field_mentions_coverage_not_a_single_default(schema):
    """城市口径现在是五城各自一套，schema 里不该再把"深圳"写成默认值。"""
    city = schema["properties"]["city"]
    assert "default" not in city, "默认城市会让人以为全国都按深圳算"
    assert "深圳市" in city["examples"]
