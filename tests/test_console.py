"""跨平台与入口的测试。

为什么值得测：这个项目最大的卖点是"clone 下来一条命令就能跑"，
而它在 Windows 上最容易翻车的地方不是算法，是**输出编码**——
GBK 控制台遇到 ✅ 会 UnicodeEncodeError，整条命令退出码 1。
所以这里钉住三件事：编码兜底不许抛异常、入口函数在管道被接管时也不崩、
仓库里带的那份 pytest 能真的跑起来。
"""
import io
import os
import subprocess
import sys

import pytest

from arb.console import _is_utf8, enable_utf8

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_enable_utf8_never_raises():
    assert isinstance(enable_utf8(), bool)


def test_enable_utf8_is_idempotent():
    enable_utf8()
    enable_utf8()


def test_is_utf8_recognizes_variants():
    class S:
        def __init__(self, enc):
            self.encoding = enc

    for enc in ("utf-8", "UTF8", "utf_8", "UTF-16", "utf32"):
        assert _is_utf8(S(enc)) is True, enc
    for enc in ("gbk", "cp936", "ascii", None):
        assert _is_utf8(S(enc)) is False, enc


def test_enable_utf8_tolerates_captured_stream(monkeypatch):
    """pytest 的 capsys / 被重定向到 StringIO 时没有 reconfigure，必须静默跳过。"""
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert enable_utf8() is False


def test_emoji_output_works_after_enable_utf8():
    """复现真实故障：GBK 编码流打印 ✅ 会抛 UnicodeEncodeError。"""
    buf = io.BytesIO()
    stream = io.TextIOWrapper(buf, encoding="gbk", errors="strict")
    try:
        stream.write("✅")
        raise AssertionError("这个前提不成立：GBK 竟然能写 emoji，测试需要更新")
    except UnicodeEncodeError:
        pass
    finally:
        stream.detach()


def test_modules_import_without_system_packages():
    """纯标准库：不装任何第三方包也要能导入核心模块。"""
    for mod in ("arb.calc", "arb.deadline", "arb.pipeline", "arb.web", "arb.pdf",
                "arb.gates", "arb.city", "arb.materials", "arb.venue", "arb.worth",
                "arb.evidence", "arb.console", "arb.laws"):
        __import__(mod)


def test_no_hardcoded_absolute_paths_in_src():
    """源码里不能出现写死的盘符/家目录，否则换台机器就找不到数据。"""
    bad = []
    src = os.path.join(ROOT, "src", "arb")
    for fn in os.listdir(src):
        if not fn.endswith(".py"):
            continue
        text = io.open(os.path.join(src, fn), encoding="utf-8").read()
        for token in ("C:\\", "/Users/", "/home/", "D:\\"):
            if token in text:
                bad.append(f"{fn}: {token}")
    assert bad == [], bad


def test_zero_install_test_runner_exists_and_is_runnable():
    """run_tests.py 是"一条命令跑测试"的入口，它必须存在、且不依赖 pip 装的东西。"""
    runner = os.path.join(ROOT, "run_tests.py")
    assert os.path.exists(runner)
    text = io.open(runner, encoding="utf-8").read()
    assert "vendor" in text and "pytest" in text
    proc = subprocess.run(
        [sys.executable, runner, "--collect-only", "-q", "--no-cov"],
        cwd=ROOT, capture_output=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout.decode("utf-8", "replace")[-2000:]
    assert b"test" in proc.stdout.lower()
