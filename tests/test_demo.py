"""演示模式的测试：三屏必须各自说对三件事，且都不能崩。

演示模式最大的风险不是算错，而是"现场某屏崩了"或"某屏其实什么都不证明"——
所以这里断言的是每屏的**证明力**，不是排版。
"""
from datetime import date

import pytest

from arb import demo


def test_scene_full_has_amount_items_and_citations():
    txt = demo.scene_full()
    assert "场景 1/3" in txt
    assert "18" in txt  # 演示口径下的合计（184,137.93）
    assert "184,137.93" in txt
    assert "未签书面劳动合同二倍工资" in txt
    assert "未休年休假工资" in txt
    assert "依据" in txt
    assert "还剩" in txt  # 演示口径 today=2024-06-01 时未过期


def test_scene_full_is_deterministic():
    a = demo.scene_full(today=date(2024, 6, 1))
    b = demo.scene_full(today=date(2024, 6, 1))
    assert a == b


def test_scene_gap_refuses_to_guess():
    txt = demo.scene_gap()
    assert "场景 2/3" in txt
    assert "不给金额" in txt
    assert txt.count("?") >= 2


def test_scene_out_redirects_and_refuses():
    txt = demo.scene_out()
    assert "工伤" in txt
    assert "人社局" in txt
    assert "不接" in txt
    assert "胜诉率" in txt


def test_run_prints_three_scenes(capsys):
    code = demo.run(no_pause=True)
    out = capsys.readouterr().out
    assert code == 0
    for tag in ("场景 1/3", "场景 2/3", "场景 3/3"):
        assert tag in out
    # 演示里绝不能出现"模型编的"内容
    assert "未配置" not in out


def test_demo_today_is_fixed():
    assert demo.DEMO_TODAY == date(2024, 6, 1)
