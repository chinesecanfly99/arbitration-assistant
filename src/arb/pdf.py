"""纯标准库生成 PDF 报告（不装任何包、不依赖浏览器）。

为什么自己写：本机装不了第三方库，沙箱里也起不了无头浏览器（Chromium 的 IPC 被拒）。
但有件事可以实现得很干净——**用 PDF 的标准中文字体（STSong-Light）不嵌字体内嵌**，
任何阅读器都能替换成系统宋体显示。于是"下载 PDF"成了真功能，而不是"教用户按 Ctrl+P"。

局限（如实写在文档里）：文字按系统字体替换显示；本文件不含图片与超链接。
"""
from __future__ import annotations

from datetime import date

PAGE_W, PAGE_H = 595, 842
MARGIN = 50
FONT = "F1"


# ---------- 简单排版工具 ----------

def _char_w(ch: str, size: float) -> float:
    """粗略字宽：中日韩字符 1em，其它 0.5em。够用，不做字距微调。"""
    return size if ord(ch) > 0x2E7F else size * 0.5


def wrap(text: str, width: float, size: float) -> list[str]:
    lines, cur, w = [], "", 0.0
    for ch in text:
        cw = _char_w(ch, size)
        if ch == "\n":
            lines.append(cur)
            cur, w = "", 0.0
            continue
        if w + cw > width and cur:
            lines.append(cur)
            cur, w = "", 0.0
        cur += ch
        w += cw
    if cur:
        lines.append(cur)
    return lines or [""]


def _hex(s: str) -> str:
    return s.encode("utf-16-be").hex().upper()


class _Doc:
    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.cur: list[str] = []
        self.y = PAGE_H - MARGIN

    def new_page(self) -> None:
        self.pages.append(self.cur)
        self.cur = []
        self.y = PAGE_H - MARGIN

    def need(self, h: float) -> None:
        if self.y - h < MARGIN:
            self.new_page()

    def text(self, x: float, y: float, s: str, size: float) -> None:
        if not s:
            return
        self.cur.append(
            f"BT /{FONT} {size:.1f} Tf {x:.1f} {y:.1f} Td <{_hex(s)}> Tj ET"
        )

    def line(self, x1: float, y1: float, x2: float, y2: float, gray: float = 0.7) -> None:
        self.cur.append(f"{gray:.2f} G 0.6 w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def paragraph(self, s: str, size: float = 10.5, gap: float = 5, indent: float = 0) -> None:
        for ln in wrap(s, PAGE_W - 2 * MARGIN - indent, size):
            self.need(size + gap)
            self.text(MARGIN + indent, self.y - size, ln, size)
            self.y -= size + gap

    def heading(self, s: str, size: float = 12.5) -> None:
        self.need(size + 16)
        self.y -= 8
        self.text(MARGIN, self.y - size, s, size)
        self.y -= size + 6

    def finish(self) -> list[str]:
        self.pages.append(self.cur)
        return self.pages


# ---------- PDF 组装 ----------

def _obj(n: int, body: str) -> bytes:
    return f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1", "replace")


def _stream(n: int, data: str) -> bytes:
    raw = data.encode("latin-1", "replace")
    return f"{n} 0 obj\n<< /Length {len(raw)} >>\nstream\n".encode() + raw + b"\nendstream\nendobj\n"


def build_pdf(pages: list[str], title: str = "劳动仲裁金额测算单") -> bytes:
    n_pages = len(pages)
    # 对象编号：1 catalog, 2 pages, 3 Type0 font, 4 descendant, 5 descriptor, 6 info
    # 之后每页：page 对象 + content 对象
    first_page = 7
    page_ids = [first_page + 2 * i for i in range(n_pages)]
    content_ids = [p + 1 for p in page_ids]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}

    def add(n: int, data: bytes) -> None:
        offsets[n] = len(out)
        out.extend(data)

    add(1, _obj(1, "<< /Type /Catalog /Pages 2 0 R >>"))
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    add(2, _obj(2, f"<< /Type /Pages /Count {n_pages} /Kids [{kids}] >>"))
    add(3, _obj(3, f"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
                   f"/Encoding /UniGB-UCS2-H /DescendantFonts [4 0 R] >>"))
    add(4, _obj(4, "<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
                   "/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 5 >> "
                   "/FontDescriptor 5 0 R /DW 1000 >>"))
    add(5, _obj(5, "<< /Type /FontDescriptor /FontName /STSong-Light /Flags 6 "
                   "/FontBBox [-25 -254 1000 880] /ItalicAngle 0 /Ascent 880 "
                   "/Descent -120 /CapHeight 880 /StemV 93 >>"))
    add(6, _obj(6, f"<< /Title <{_hex(title)}> /Producer (arbitration_assistant) "
                   f"/CreationDate (D:{date.today().strftime('%Y%m%d')}) >>"))

    for page_id, content_id, parts in zip(page_ids, content_ids, pages):
        add(page_id, _obj(
            page_id,
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /{FONT} 3 0 R >> >> /Contents {content_id} 0 R >>",
        ))
        add(content_id, _stream(content_id, "\n".join(parts)))

    xref_at = len(out)
    total = 6 + 2 * n_pages + 1
    out.extend(f"xref\n0 {total}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for n in range(1, total):
        out.extend(f"{offsets.get(n, 0):010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {total} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode())

    if offsets.get(1) is None:  # pragma: no cover - 组装逻辑兜底
        raise RuntimeError("PDF 组装失败：缺少 catalog")
    return bytes(out)


# ---------- 报告 → 版面 ----------

def _money(x: float) -> str:
    return f"{x:,.2f}"


def render_pdf(report: dict) -> bytes:
    d = _Doc()
    d.text(MARGIN, d.y - 20, "劳动仲裁金额测算单", 18)
    d.y -= 30
    d.text(MARGIN, d.y - 9, f"生成日期：{date.today().isoformat()}　口径城市：深圳（示例）", 8)
    d.y -= 14

    if report.get("status") == "need_more":
        d.heading("现在还不能算，需要补充")
        for q in report.get("questions", []):
            d.paragraph("· " + q, 10.5, 4)
        return build_pdf(d.finish())

    if report.get("status") == "out_of_scope":
        scope = report.get("scope") or {}
        d.heading("不属于劳动仲裁受理范围")
        d.paragraph(scope.get("reason", ""), 10.5, 5)
        if report.get("redirect"):
            d.paragraph("该去这里办：" + report["redirect"], 10.5, 5)
        for h in report.get("hints", []):
            d.paragraph("· " + h, 9.5, 4)
        d.paragraph("本单不构成法律意见；可拨 12348 免费咨询。", 9, 4)
        return build_pdf(d.finish())

    d.heading("当事人原话")
    d.paragraph(report.get("story", ""), 9.5, 4)

    d.heading(f"可主张金额合计：{_money(report.get('total', 0))} 元")
    for it in report.get("items", []):
        d.need(34)
        d.text(MARGIN, d.y - 10, it["name"], 10.5)
        amount = _money(it["amount"]) + " 元"
        d.text(PAGE_W - MARGIN - sum(_char_w(c, 10.5) for c in amount), d.y - 10, amount, 10.5)
        d.y -= 13
        d.paragraph(it.get("formula", ""), 8, 2, indent=10)
        d.paragraph("依据：" + it.get("basis", ""), 8, 3, indent=10)
        d.line(MARGIN, d.y + 1, PAGE_W - MARGIN, d.y + 1, 0.85)

    cites = [c for it in report.get("items", []) for c in it.get("cite_texts", [])]
    if cites:
        d.heading("法律依据原文（可逐条核对）")
        seen = set()
        for c in cites:
            key = c.get("cite")
            if key in seen:
                continue
            seen.add(key)
            d.paragraph(c.get("cite", ""), 9, 2)
            d.paragraph(c.get("text", "")[:260], 8.5, 4, indent=10)

    ds = [x for x in report.get("deadlines", []) if x.get("applicable")]
    if ds:
        d.heading("仲裁时效")
        for x in ds:
            left = "已过期" if x.get("expired") else f"还剩 {x.get('days_left')} 天"
            d.paragraph(f"{x['label']}：起算 {x['anchor']}，截止 {x['deadline']}（{left}）", 9, 3)

    reh = (report.get("rehearsal") or {}).get("rounds") or []
    if reh:
        d.heading("抗辩预演（AI 扮 HR）")
        for i, rd in enumerate(reh, 1):
            d.paragraph(f"第 {i} 轮　HR：{rd['hr_says']}", 9, 3)
            d.paragraph(f"      为什么难缠：{rd['why']}", 8.5, 3, indent=10)
            d.paragraph(f"      你怎么接：{rd['counter']}", 8.5, 5, indent=10)

    if report.get("assumptions"):
        d.heading("本单采用的口径（请确认）")
        for a in report["assumptions"]:
            d.paragraph("· " + a, 9, 3)

    d.y -= 6
    d.line(MARGIN, d.y, PAGE_W - MARGIN, d.y, 0.5)
    d.y -= 12
    d.paragraph("本单只是根据您提供的信息做的初步测算，不构成法律意见，也不能代替律师。"
                "正式申请前请核对工资流水、社保记录和劳动合同原件；符合条件可拨 12348 申请法律援助。", 8, 3)
    return build_pdf(d.finish())

# ---------- 自检与命令行 ----------

def validate(data: bytes) -> list[str]:
    """检查 PDF 结构合法性，返回问题列表（空列表=通过）。

    我们没有 PDF 阅读器可以做端到端验证，所以至少把"结构自洽"钉死：
    头尾标记、对象数、xref 偏移必须真的指向 `N 0 obj`。
    """
    problems: list[str] = []
    if not data.startswith(b"%PDF-1."):
        problems.append("缺少 %PDF 头")
    if not data.rstrip().endswith(b"%%EOF"):
        problems.append("缺少 %%EOF 尾")
    text = data.decode("latin-1")
    if "startxref" not in text:
        problems.append("缺少 startxref")
    if "/Type /Font /Subtype /Type0 /BaseFont /STSong-Light" not in text:
        problems.append("缺少中文字体引用")
    marker = chr(10) + "xref" + chr(10)
    cut = text.rfind(marker)
    if cut < 0:
        problems.append("缺少 xref 表")
        return problems
    tail = text[cut + len(marker):]
    rows = [ln for ln in tail.splitlines() if ln.strip()]
    try:
        count = int(rows[0].split()[1])
        entries = rows[1:]
    except (IndexError, ValueError):
        problems.append("xref 计数行不可解析")
        return problems
    for obj_no in range(1, count):
        parts = entries[obj_no].split() if obj_no < len(entries) else []
        if len(parts) < 3:
            problems.append(f"xref 第 {obj_no} 条格式错")
            continue
        off = int(parts[0])
        expect = f"{obj_no} 0 obj".encode()
        if data[off:off + len(expect)] != expect:
            problems.append(f"xref 第 {obj_no} 条偏移指错了")
    n_pages = text.count("/Type /Page ")
    if n_pages < 1:
        problems.append("没有页面对象")
    return problems
    head, _tail = m[0], m[1]
    lines = _tail.split("\n")
    try:
        count = int(lines[1].split()[1])
    except (IndexError, ValueError):
        problems.append("xref 计数行不可解析")
        return problems
    for i in range(1, count):
        row = lines[2 + i] if 2 + i < len(lines) else ""
        parts = row.split()
        if len(parts) < 3:
            problems.append(f"xref 第 {i} 条格式错")
            continue
        off = int(parts[0])
        obj_no = i
        expect = f"{obj_no} 0 obj".encode()
        if data[off:off + len(expect)] != expect:
            problems.append(f"xref 第 {obj_no} 条偏移指错了")
    n_pages = text.count("/Type /Page ")
    if n_pages < 1:
        problems.append("没有页面对象")
    return problems


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .pipeline import analyze

    ap = argparse.ArgumentParser(description="把测算单导出成 PDF（纯标准库）")
    ap.add_argument("story", nargs="?", default=(
        "2020年3月1日入职，月薪9000，一直没签书面合同，2024年5月20日公司口头把我辞了，还有5天年假没休。"))
    ap.add_argument("-o", "--out", default="report.pdf")
    args = ap.parse_args(argv)

    r = analyze(args.story)
    data = render_pdf(r)
    problems = validate(data)
    if problems:
        print("PDF 自检未通过：", problems)
        return 1
    with open(args.out, "wb") as f:
        f.write(data)
    total = r.get("total")
    extra = f"，合计 {total:,.2f} 元" if isinstance(total, (int, float)) else "（本条不含金额）"
    print(f"已导出 {args.out}（{len(data) // 1024} KB{extra}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
