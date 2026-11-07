# -*- coding: utf-8 -*-
"""把项目打成可分发的压缩包（不含 .libs、缓存、.git 与临时文件）。

为什么改掉写死的本机盘符路径：
原来脚本里把项目根目录写成了某一台 Windows 机器的绝对路径，换台机器
（尤其是 macOS / Linux）直接 FileNotFoundError——而这个脚本恰恰是"交付给别人"时用的。
现在全部从 `__file__` 推出来，三个平台一致。

为什么包内路径统一用正斜杠：
zip 规范里分隔符就是 `/`。用 `os.path.join` 在 Windows 上会写成 `a\\b`，
解压到 macOS/Linux 会得到一个名叫 `a\\b` 的单个文件，而不是目录——很难查。

用法：
    python -m scripts.make_zip                 # 打到项目上一级目录
    python -m scripts.make_zip --out 交付包.zip  # 指定输出路径（测试用这个）
    python -m scripts.make_zip --list           # 只列清单，不打包
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PROJ)
DEFAULT_NAME = "劳动仲裁维权助手_交付包.zip"

SKIP_DIRS = {".libs", ".libs_off", "__pycache__", ".pytest_cache", ".git", "_tmp_profile",
             "uploads", ".mypy_cache", ".ruff_cache", ".coverage_html"}
SKIP_FILES = {"_tmp_report.html", ".coverage"}
SKIP_EXT = (".pyc", ".zip", ".log")

# 放在项目上一级的规划文档，一起打进交付包（有就带，没有就算了）
EXTRA = ["劳动仲裁专项_项目章程.md", "劳动仲裁项目_执行计划与验收清单.md"]


def _arc(*parts: str) -> str:
    """包内路径：永远用 `/` 分隔（zip 规范）。"""
    return "/".join(p.replace("\\", "/").strip("/") for p in parts if p)


def collect() -> list[tuple[str, str]]:
    """返回 [(磁盘绝对路径, 包内路径)]。包内路径一律正斜杠。"""
    base = os.path.basename(PROJ)
    files: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(PROJ):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn in SKIP_FILES or fn.endswith(SKIP_EXT):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, PROJ)
            files.append((full, _arc(base, rel)))
    for name in EXTRA:
        full = os.path.join(ROOT, name)
        if os.path.exists(full):
            files.append((full, name))
    return files


def build(out: str) -> dict:
    files = collect()
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for full, arc in files:
            z.write(full, arc)
    with zipfile.ZipFile(out) as z:
        bad = z.testzip()
        names = z.namelist()
    return {
        "out": out,
        "count": len(files),
        "size": os.path.getsize(out),
        "intact": bad is None,
        "tops": sorted({n.split("/")[0] for n in names}),
        "names": names,
    }


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, os.path.join(PROJ, "src"))
    from arb.console import enable_utf8

    enable_utf8()
    ap = argparse.ArgumentParser(description="打包交付物（纯标准库）")
    ap.add_argument("--out", default=os.path.join(ROOT, DEFAULT_NAME))
    ap.add_argument("--list", action="store_true", help="只列清单，不打包")
    args = ap.parse_args(argv)

    if args.list:
        for _full, arc in collect():
            print(arc)
        return 0

    res = build(args.out)
    print(f"打包完成：{res['out']}")
    print(f"文件数 {res['count']}，压缩后 {res['size'] / 1024:.1f} KB")
    print("完整性检查：", "通过" if res["intact"] else "损坏")
    print("顶层条目：")
    for top in res["tops"]:
        print("  -", top, f"({sum(1 for n in res['names'] if n.startswith(top))} 项)")
    return 0 if res["intact"] else 1


if __name__ == "__main__":
    sys.exit(main())
