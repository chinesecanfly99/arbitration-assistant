# -*- coding: utf-8 -*-
"""把项目打成可分发的压缩包（不含 pytest 的 .libs、缓存与临时文件）。"""
import os
import zipfile

ROOT = r"F:\DSH_file"
PROJ = os.path.join(ROOT, "arbitration_assistant")
OUT = os.path.join(ROOT, "劳动仲裁维权助手_交付包.zip")

SKIP_DIRS = {".libs", "__pycache__", ".pytest_cache", ".git", "_tmp_profile", "uploads"}
SKIP_FILES = {"_tmp_report.html", "make_zip.py"}
EXTRA = ["劳动仲裁专项_项目章程.md", "劳动仲裁项目_执行计划与验收清单.md"]

files = []
for dirpath, dirnames, filenames in os.walk(PROJ):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        if fn in SKIP_FILES or fn.endswith(".pyc"):
            continue
        full = os.path.join(dirpath, fn)
        files.append((full, os.path.join("arbitration_assistant", os.path.relpath(full, PROJ))))

for name in EXTRA:
    full = os.path.join(ROOT, name)
    if os.path.exists(full):
        files.append((full, name))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for full, arc in files:
        z.write(full, arc)

size = os.path.getsize(OUT)
print(f"打包完成：{OUT}")
print(f"文件数 {len(files)}，压缩后 {size/1024:.1f} KB")

with zipfile.ZipFile(OUT) as z:
    bad = z.testzip()
    print("完整性检查：", "通过" if bad is None else f"损坏于 {bad}")
    names = z.namelist()
    print("顶层条目：")
    for top in sorted({n.split('/')[0] for n in names}):
        print("  -", top, f"({sum(1 for n in names if n.startswith(top))} 项)")
