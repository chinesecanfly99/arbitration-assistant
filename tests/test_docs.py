"""文档完整性测试：README 里链出去的文档必须真的存在。

为什么要测文档：评审最常做的就是"照 README 点一下"——链接 404 比数字错更难解释。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def _links(md: str):
    return re.findall(r"\]\(([^)#]+)\)", md)


def test_readme_links_exist():
    md = README.read_text(encoding="utf-8")
    broken = [l for l in _links(md) if not l.startswith("http") and not (ROOT / l).exists()]
    assert broken == [], f"README 里有断链：{broken}"


def test_demo_and_rehearsal_docs_exist():
    for name in ("one_pager.md", "demo_script.md", "rehearsal.md", "eval_report.md", "ablation.md"):
        p = ROOT / "docs" / name
        assert p.exists(), f"缺文档：{name}"
        assert len(p.read_text(encoding="utf-8")) > 500, f"{name} 太短，像是占位"


def test_demo_script_has_timeline_and_fallback():
    md = (ROOT / "docs" / "demo_script.md").read_text(encoding="utf-8")
    assert "0:00" in md and "5:00" in md
    assert "断网预案" in md
    assert "184,137.93" in md  # 演示数字必须与评测口径一致


def test_rehearsal_covers_the_questions():
    md = (ROOT / "docs" / "rehearsal.md").read_text(encoding="utf-8")
    for q in ("套壳", "幻觉", "真人测试", "不做全国"):
        assert q in md, f"彩排稿漏了关键问题：{q}"
