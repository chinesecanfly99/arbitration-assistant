"""交付打包测试：压缩包要能打、要完整、且不能把 .git / 缓存 / 密钥打进去。

为什么值得测：
- `make_zip.py` 原来把 `F:\\DSH_file` 写死，换台机器直接崩——而它恰恰是"交付给别人"时用的；
- 打包脚本最容易犯的错是"把不该带的东西带进去"：.git 里有历史、.libs 有几 MB、
  .coverage 是临时文件；带错了不报错，只是包变大、泄露不该泄露的东西。
"""
import os
import zipfile

import pytest

from scripts import make_zip


def test_collect_skips_heavy_and_private_dirs():
    arcs = [arc for _full, arc in make_zip.collect()]
    joined = "\n".join(arcs)
    for banned in ("/.git/", "/.libs/", "/__pycache__/", "/.pytest_cache/", "/.coverage"):
        assert banned not in joined, f"打包不该包含 {banned}"
    assert not any(a.endswith(".pyc") for a in arcs)


def test_collect_includes_the_things_that_matter():
    arcs = [arc for _full, arc in make_zip.collect()]
    joined = "\n".join(arcs)
    for need in ("README.md", "run.py", "run_tests.py", "LICENSE",
                 "src/arb/pipeline.py", "tests/test_city_gates.py",
                 "data/laws/labor_contract_law.jsonl"):
        assert any(a.endswith(need) for a in arcs), f"交付包缺 {need}"
    assert "vendor/pkgs/pytest" in joined, "零安装跑测试依赖随包携带的 pytest"


def test_build_writes_a_valid_zip(tmp_path):
    out = tmp_path / "pkg.zip"
    res = make_zip.build(str(out))
    assert out.exists()
    assert res["intact"] is True
    assert res["count"] > 50
    with zipfile.ZipFile(out) as z:
        assert z.namelist()
        assert z.read("arbitration_assistant/README.md")[:2] == b"# "


def test_build_is_idempotent(tmp_path):
    """同一个目录打两次，文件清单必须一致（顺序稳定 → 便于比较）。"""
    a = make_zip.build(str(tmp_path / "a.zip"))
    b = make_zip.build(str(tmp_path / "b.zip"))
    assert a["names"] == b["names"]


def test_main_list_does_not_write(tmp_path, capsys):
    target = tmp_path / "should_not_exist.zip"
    code = make_zip.main(["--out", str(target), "--list"])
    assert code == 0
    assert not target.exists()
    assert "src/arb/pipeline.py" in capsys.readouterr().out


def test_project_root_is_derived_not_hardcoded():
    """不能再出现写死的盘符：换台机器就崩，而这个脚本是交付时用的。"""
    text = open(os.path.join(make_zip.PROJ, "scripts", "make_zip.py"), encoding="utf-8").read()
    for token in ("F:\\", "C:\\", "/Users/"):
        assert token not in text, f"make_zip.py 里还有写死的路径：{token}"
    assert os.path.isabs(make_zip.PROJ)
    assert os.path.exists(os.path.join(make_zip.PROJ, "README.md"))
