#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""零安装跑测试：clone 下来直接 `python run_tests.py`。

为什么不用 pip：这台机器/课程环境不一定能装包，而且我们只是要跑测试。
pytest 9.2.0 和它的纯 Python 依赖已经放在 vendor/pkgs 里（约 2.3 MB），
再加一个 `py` shim，够跑 `tests/` 下的全部用例。

如果你本机有 pytest（或照 README 用 pip 装到 .libs），会优先用你自己的版本。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def ensure(path):
    if path not in sys.path:
        sys.path.insert(0, path)


ensure(ROOT)
ensure(os.path.join(ROOT, "src"))
ensure(os.path.join(ROOT, "vendor", "pkgs"))
ensure(os.path.join(ROOT, ".libs"))          # 每次 insert(0)，所以 .libs 排在最先 → 自装的优先

os.chdir(ROOT)                                # 让 pytest.ini 的 testpaths/pythonpath 生效

try:
    import pytest
except ImportError:
    sys.exit("找不到 pytest：vendor/pkgs 目录不见了？见 README「clone 后直接跑测试」。")

args = sys.argv[1:] or ["tests"]   # -q 已在 pytest.ini 里，重复会变成 -qq 把汇总行也吞掉
if not any(a.startswith("tests") or a.endswith(".py") for a in args):
    args = ["tests"] + args

try:                                          # 有覆盖率插件就顺手报一下，没有就算了
    import pytest_cov  # noqa: F401
    if not any("--cov" in a for a in args):
        args += ["--cov=arb", "--cov-report=term-missing:skip-covered"]
except ImportError:
    pass

print(f"[run_tests] pytest {pytest.__version__} · {args}")
sys.exit(pytest.main(args))
