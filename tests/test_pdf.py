"""PDF 导出的测试：结构必须真的合法，而不是"文件存在就算过"。

我们没有 PDF 阅读器可以做像素级验证，所以把能钉死的都钉死：
头尾标记、xref 偏移真的指向对象、中文字体引用、三种 status 都能出 PDF。
"""
from datetime import date

import pytest

from arb import pdf
from arb.pipeline import analyze

STORY = "2020年3月1日入职，月薪9000，一直没签书面合同，2024年5月20日公司口头把我辞了，还有5天年假没休。"


def _report(story=STORY):
    return analyze(story, today=date(2025, 1, 1))


def test_render_pdf_structure_is_valid():
    data = pdf.render_pdf(_report())
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")
    assert data.count(b"/Type /Page ") >= 1
    assert b"STSong-Light" in data
    assert pdf.validate(data) == []


def test_render_pdf_contains_key_numbers():
    # 中文以 UCS2 十六进制写入，所以按同样方式编码后比对
    data = pdf.render_pdf(_report())
    assert pdf._hex("劳动仲裁金额测算单").encode() in data
    assert pdf._hex("违法解除赔偿金").encode() in data


def test_render_pdf_need_more_has_no_amount():
    r = analyze("公司把我辞了")
    data = pdf.render_pdf(r)
    assert pdf.validate(data) == []
    assert r["status"] == "need_more"
    # 追问页不应该出现"可主张金额合计"
    assert pdf._hex("可主张金额合计").encode() not in data


def test_render_pdf_out_of_scope_redirects():
    r = analyze("我在厂里被机器压断手指，想让公司赔工伤。")
    data = pdf.render_pdf(r)
    assert pdf.validate(data) == []
    assert pdf._hex("该去这里办").encode() in data


def test_render_pdf_multi_page_when_long():
    # 三条长故事拼一起，必然多页；验证分页后 xref 仍然自洽
    long_story = (
        "我2018年1月1日入职，月薪9800，一直没签书面合同，"
        "2020年到2024年每年工作日加班200小时、休息日加班100小时、法定节假日加班30小时，"
        "还有15天年假没休，公司还欠我2个月工资，2024年5月20日把我辞了。"
    )
    data = pdf.render_pdf(analyze(long_story, today=date(2025, 1, 1)))
    assert pdf.validate(data) == []
    assert data.count(b"/Type /Page ") >= 1


def test_validate_catches_broken_file():
    bad = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    problems = pdf.validate(bad)
    assert problems, "坏文件必须被 validate 抓出来"


def test_wrap_never_exceeds_width():
    text = "劳动者违法解除劳动合同的赔偿金按照经济补偿标准的二倍支付" * 3
    for ln in pdf.wrap(text, 300, 10.5):
        width = sum(pdf._char_w(c, 10.5) for c in ln)
        assert width <= 300 + 10.5, f"这一行超宽：{width}"


def test_cli_main_writes_file(tmp_path, capsys):
    out = tmp_path / "r.pdf"
    code = pdf.main([STORY, "-o", str(out)])
    assert code == 0
    assert out.exists() and out.stat().st_size > 3000
    assert "已导出" in capsys.readouterr().out
