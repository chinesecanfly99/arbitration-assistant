"""控制台编码兜底：让同一份代码在 Windows(GBK 控制台) / macOS(UTF-8) 上输出一致。

为什么需要这个模块：
- Windows 的默认控制台代码页是 936(GBK)，`print("✅")` 会直接抛 UnicodeEncodeError，
  整条命令以退出码 1 结束——评审在自己电脑上跑一遍就以为是"跑不起来"；
- 但这不是功能坏了，是**输出管道编码**没对齐。改代码里的表情符号是治标的错法
  （换台机器又换一种编码），正确的做法是把输出流显式设成 UTF-8；
- 只在入口调用一次，且**永不抛异常**：管道被重定向到文件、被 pytest 接管、
  被调用方关掉 stdout 的场合都必须静默放过，绝不能因为"设置输出编码失败"让主流程挂掉。

用法：
    from .console import enable_utf8
    def main(...):
        enable_utf8()
        ...
"""
from __future__ import annotations

import sys

_UTF8_ALIASES = {"utf8", "utf_8", "utf-8", "utf16", "utf_16", "utf32", "utf_32"}


def _is_utf8(stream) -> bool:
    enc = (getattr(stream, "encoding", "") or "").replace("-", "").replace("_", "").lower()
    return enc in {a.replace("-", "").replace("_", "") for a in _UTF8_ALIASES}


def enable_utf8() -> bool:
    """尽力把 stdout/stderr 切成 UTF-8。返回是否真的改了（测试用）。"""
    changed = False
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            if _is_utf8(stream):
                continue
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is None:  # pytest 的 capsys / 被替换的管道
                continue
            reconfigure(encoding="utf-8", errors="replace")
            changed = True
        except Exception:
            # 编码只影响"看得见"，不影响"算得对"：宁可打不出 emoji，也不能崩
            pass
    return changed
