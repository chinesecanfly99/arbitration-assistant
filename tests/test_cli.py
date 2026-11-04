"""CLI 与模型层的测试：这两层最容易"看起来能跑，其实没接上"。"""
import io
import json
from datetime import date
from contextlib import redirect_stdout, redirect_stderr

import pytest

from arb import llm
from arb.cli import main, render_markdown
from arb.pipeline import analyze

STORY = "2020年3月1日入职，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了，让我当天走人。"


def test_cli_prints_report(capsys):
    code = main([STORY])
    out = capsys.readouterr()
    assert code == 0
    assert "可主张金额合计" in out.out
    assert "法" in out.out


def test_cli_need_more_asks_questions(capsys):
    code = main(["公司把我辞了"])
    out = capsys.readouterr()
    assert code == 2
    assert "需要您补充" in out.out


def test_cli_json_mode(capsys):
    main([STORY, "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] == "ok"
    assert data["total"] > 0


def test_render_markdown_contains_every_item():
    r = analyze(STORY, today=date(2025, 1, 1))
    md = render_markdown(r)
    for it in r["items"]:
        assert it["name"] in md
        assert f"{it['amount']:,.2f}" in md
    assert "不构成法律意见" in md


def test_llm_not_configured(capsys):
    # 默认环境没 key：必须优雅降级，不能抛异常
    assert llm.config() is None or llm.available()
    main([STORY])
    err = capsys.readouterr().err
    if not llm.available():
        assert "未配置模型" in err


def test_cli_out_of_scope_prints_redirect(capsys):
    # 红线拒答（索要胜诉率）：不能崩，也不给金额，要给出替代做法
    code = main(["我被辞退了，你直接告诉我我能不能赢，胜率多少？"])
    out = capsys.readouterr().out
    assert code == 2
    assert "不归劳动仲裁管" in out
    assert "可主张金额合计" not in out
    assert "12348" in out


def test_cli_out_of_scope_gongshang_redirects(capsys):
    # 工伤要走人社局，不是仲裁：必须指路，而不是硬算一笔钱
    code = main(["我在厂里被机器压断手指，想让公司赔工伤，月薪6000。"])
    out = capsys.readouterr().out
    assert code == 2
    assert "工伤" in out
    assert "该去这里办" in out
    assert "人社局" in out
    assert "可主张金额合计" not in out


def test_llm_validate_drops_bad_fields():
    got = llm.validate({
        "hire_date": "2020-03-01",
        "monthly_wage": "九千",          # 类型错
        "termination": "被开除",          # 不在枚举
        "has_written_contract": "false",  # 字符串不是 bool
        "overtime_holiday_hours": 3,
    })
    assert got["fields"] == {"hire_date": "2020-03-01", "overtime_holiday_hours": 3}
    assert len(got["bad"]) == 3


def test_llm_validate_rejects_non_dict():
    with pytest.raises(ValueError):
        llm.validate(["不是对象"])


def test_llm_extract_without_key_raises():
    if llm.available():
        pytest.skip("配置了 key")
    with pytest.raises(llm.LLMNotConfigured):
        llm.extract_fields("测试")
