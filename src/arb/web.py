"""单页前端（纯标准库，零依赖）：python -m arb.web

为什么不用框架：这台机器装不了包（沙箱禁写 site-packages），
而 stdlib 的 http.server 足够撑起"输入故事 → 出测算单"的闭环，
评审现场只要浏览器能打开就行，不用先 pip install 十分钟。

路由：
    GET  /            输入页
    POST /analyze     计算并返回结果页
    GET  /report?story=...  下载 Markdown 测算单（可直接打印/存 PDF）
"""
from __future__ import annotations

import html
import json
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .cli import render_markdown
from .application import render_application, render_notes
from .chips import groups, suggest
from .evidence import rows as evidence_rows, summary as evidence_summary
from .map import completeness, summary_line
from .pdf import render_pdf
from .pipeline import analyze, covered_cities

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:24px 16px 64px;font:16px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
     color:#1f2329;background:#f7f8fa;max-width:760px;margin:0 auto}
h1{font-size:22px;margin:0 0 6px}
h2{font-size:17px;margin:28px 0 10px;padding-left:10px;border-left:4px solid #2f6feb}
.sub{color:#6b7280;font-size:14px;margin:0 0 20px}
textarea{width:100%;min-height:132px;padding:12px;border:1px solid #d5d9e0;border-radius:10px;font-size:16px;line-height:1.6;background:#fff}
button{margin-top:12px;width:100%;padding:14px;border:0;border-radius:10px;background:#2f6feb;color:#fff;font-size:17px}
button:active{background:#2557c0}
.card{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:16px;margin:14px 0}
.total{font-size:28px;font-weight:700;color:#c0392b}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{padding:8px 6px;border-bottom:1px solid #eef0f3;text-align:left;vertical-align:top}
td.num{text-align:right;white-space:nowrap}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:12px;background:#e8f2ff;color:#2557c0;margin-left:6px}
.badge.ok{background:#e7f7ed;color:#1a7f45}
.badge.warn{background:#fff4e5;color:#b26a00}
blockquote{margin:6px 0 0;padding:8px 12px;background:#f5f7fb;border-left:3px solid #cfd8e6;font-size:14px;color:#4b5563}
.hr{height:1px;background:#e6e8ec;margin:22px 0}
.foot{color:#8a919c;font-size:13px;margin-top:28px}
a{color:#2f6feb}
details{margin:6px 0}
summary{cursor:pointer;color:#2557c0;font-size:14px}
.ask{background:#fffbe6;border:1px solid #ffe58f}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 0}
.chip{border:1px solid #cfd8e6;background:#fff;color:#1f2329;border-radius:20px;padding:6px 12px;font-size:14px;width:auto;margin:0}
.chip:active{background:#eef3ff}
.groupname{font-size:13px;color:#6b7280;margin:12px 0 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
@media (max-width:520px){.grid{grid-template-columns:1fr}}
.cell{border:1px solid #e6e8ec;border-radius:10px;padding:8px 10px;font-size:14px;display:flex;flex-direction:column;gap:2px;background:#fbfcfd}
.cell .k{color:#6b7280;font-size:13px}
.cell .v{color:#1f2329;word-break:break-all}
.cell .m{font-size:12px;color:#8a919c}
.cell.ok{border-color:#bfe8cd;background:#f2fbf5}
.cell.ok .m{color:#1a7f45}
.cell.missing{border-color:#ffc9c9;background:#fff5f5}
.cell.missing .m{color:#c0392b}
.cell.optional{background:#f8f9fb}
.pct{font-size:15px;color:#2557c0;font-weight:600}
.badge.unit{background:#fff4e5;color:#b26a00}
.badge.both{background:#eef3ff;color:#2557c0}
.badge.me{background:#e7f7ed;color:#1a7f45}
.badge.fail{background:#ffe8e8;color:#c0392b}
.verdict{display:inline-block;padding:4px 12px;border-radius:8px;font-size:15px;font-weight:600;margin:2px 0 6px}
.verdict.recommend{background:#e7f7ed;color:#1a7f45}
.verdict.better_alternative{background:#fff4e5;color:#b26a00}
.verdict.not_recommended{background:#f1f3f6;color:#4b5563}
.gate{border:1px solid #e6e8ec;border-radius:10px;padding:10px 12px;margin:8px 0;background:#fbfcfd}
.gate.pass{border-left:4px solid #1a7f45}
.gate.warn{border-left:4px solid #b26a00;background:#fffdf7}
.gate.fail{border-left:4px solid #c0392b;background:#fff7f7}
.gate.info{border-left:4px solid #8a919c}
.gate .t{font-weight:600;font-size:14px}
.gate .m{font-size:14px;color:#4b5563;margin:2px 0}
.gate ul{margin:4px 0 0;padding-left:18px;font-size:13px;color:#4b5563}
.bar{height:6px;background:#eef0f3;border-radius:4px;overflow:hidden;margin:2px 0 6px}
.bar i{display:block;height:100%;background:#2f6feb}
.dim{font-size:13px;color:#4b5563}
.ok-i{color:#1a7f45;font-weight:600}
.no-i{color:#c0392b;font-weight:600}
.stage{font-size:13px;color:#2557c0;font-weight:600}
#explain{margin-top:10px;font-size:14px;color:#4b5563;background:#f5f7fb;border-left:3px solid #cfd8e6;padding:8px 12px;display:none}
@media print{form,button,.chips,.noprint{display:none!important}body{background:#fff;padding:0}}
"""


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def _money(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return esc(v)



CHIP_JS = r"""
<script>
document.addEventListener('click', function (e) {
  var el = e.target.closest('.chip');
  if (!el) return;
  var box = document.getElementById('story');
  var term = el.dataset.term || '';
  var val = box.value;
  box.value = (val && !/[\s，。,;；]$/.test(val)) ? val + '，' + term + '。' : val + term + '。';
  box.focus();
  var ex = document.getElementById('explain');
  ex.style.display = 'block';
  ex.innerHTML = '<b>' + term + '</b><br>' + (el.dataset.plain || '') +
                 '<br><span style="color:#6b7280">什么时候用得上：' + (el.dataset.when || '') + '</span>' +
                 '<br><span style="color:#6b7280">为什么要说清楚：' + (el.dataset.why || '') + '</span>';
});
</script>
"""


def chips_html() -> str:
    out = []
    for g, items in groups().items():
        out.append(f'<p class="groupname">{esc(g)}</p><div class="chips">')
        for c in items:
            out.append(
                f'<button type="button" class="chip" data-term="{esc(c["term"])}" '
                f'data-plain="{esc(c["plain"])}" data-when="{esc(c["when"])}" data-why="{esc(c["why"])}">'
                f'{esc(c["term"])}</button>'
            )
        out.append("</div>")
    return "".join(out)


MAP_JS = r"""
<script>
document.addEventListener('click', function (e) {
  var el = e.target.closest('.fill');
  if (!el) return;
  var box = document.getElementById('story');
  if (!box) return;
  var add = el.dataset.text || '';
  var val = box.value;
  var sep = (!val || /[\\s，。；;,、]$/.test(val)) ? '' : '；';
  box.value = val + sep + add;
  box.focus();
});
</script>
"""


def map_html(fields: dict, clickable: bool = False) -> str:
    """9 格完整度地图：已填的绿、必填缺失的红、可选的灰。"""
    c = completeness(fields)
    out = [f'<div class="card"><b>案件完整度</b> <span class="pct">{int(c["score"] * 100)}%</span>']
    out.append('<p class="sub" style="margin:4px 0 10px">' + esc(summary_line(fields)) + "</p>")
    out.append('<div class="grid">')
    for r in c["rows"]:
        cls = "cell " + r["status"]
        mark = "✓" if r["status"] == "ok" else ("可选" if r["status"] == "optional" else "缺")
        val = esc(r["value"]) if r["value"] else esc(r["hint"].replace("例如：", "").replace("可选：", ""))
        out.append(f'<div class="{cls}"><span class="k">{esc(r["label"])}</span>'
                   f'<span class="v">{val}</span><span class="m">{mark}</span></div>')
    out.append("</div>")
    if clickable:
        miss = [r for r in c["rows"] if r["status"] == "missing"]
        if miss:
            out.append('<p class="sub" style="margin:12px 0 6px">点一下，把这句补进上面的输入框，再改数字：</p><div class="chips">')
            for r in miss:
                out.append(f'<button type="button" class="chip fill" data-text="{esc(r["hint"])}">补：{esc(r["label"])}</button>')
            out.append("</div>")
    out.append("</div>")
    return "".join(out)


def evidence_html(rehearsal: dict | None) -> str:
    if not rehearsal or not rehearsal.get("evidence_checklist"):
        return ""
    rows_ = evidence_rows(rehearsal["evidence_checklist"])
    out = ['<div class="card"><h2>五、证据清单（谁举证）</h2>']
    out.append('<p class="sub">' + esc(evidence_summary(rows_)) + "。依据《劳动争议调解仲裁法》第六条。</p>")
    out.append("<table><tr><th>证据</th><th>谁出</th><th>为什么</th></tr>")
    for r in rows_:
        badge = {"单位": '<span class="badge unit">单位举证</span>',
                 "双方": '<span class="badge both">双方</span>',
                 "你": '<span class="badge me">你自己准备</span>'}[r["who"]]
        out.append(f'<tr><td>{esc(r["name"])}</td><td>{badge}</td><td class="sub" style="margin:0">{esc(r["why"])}</td></tr>')
    out.append("</table></div>")
    return "".join(out)


def print_page(story: str, today=None, confirmed=()) -> str:
    """打印/导 PDF 用的整页 HTML（与网页同一套渲染，只多一行提示）。"""
    r = analyze(story, today=today, mode="best_effort", confirmed=confirmed)
    page = render_page(r, story)
    tip = ('<p class="noprint" style="color:#8a919c;font-size:13px">'
           '按 Ctrl+P（Mac 是 ⌘P）可存成 PDF。</p>')
    return page.replace("</body>", tip + "</body>")


# ---------------------------------------------------------------- 新增板块
def gates_html(gates: dict | None) -> str:
    """三道闸门：受案范围 → 资格 → 口径。每层都给出状态、理由与法条。"""
    if not gates:
        return ""
    layers = gates.get("layers") or []
    if not layers:
        return ""
    out = ['<div class="card"><h2>能不能申请（三道闸门）</h2>']
    out.append(
        '<p class="sub">第一层问「归不归仲裁管」，第二层问「你够不够格」，第三层问「数字从哪来」。'
        "任何一层判不过，下面就不该再出现一个看起来很确定的总金额。</p>"
    )
    for g in layers:
        cls = g.get("status") or "info"
        out.append(f'<div class="gate {cls}"><div class="t">{esc(g.get("title"))}</div>')
        out.append(f'<div class="m">{esc(g.get("message"))}</div>')
        if g.get("detail"):
            out.append("<ul>" + "".join(f"<li>{esc(d)}</li>" for d in g["detail"]) + "</ul>")
        if g.get("cites"):
            out.append(f'<div class="dim" style="margin-top:4px">依据：{esc("、".join(g["cites"]))}</div>')
        out.append("</div>")
    for b in gates.get("blockers") or []:
        out.append(f'<p class="gate fail"><b>硬性障碍：</b>{esc(b)}</p>')
    out.append("</div>")
    return "".join(out)


def pending_html(pending: list[dict], story: str) -> str:
    """未确认读数：本单**没有**用它们算钱，勾选后重算。"""
    if not pending:
        return ""
    out = ['<div class="card ask"><h2>有几项读数还没确认（本单没有采用）</h2>']
    out.append(
        '<p class="sub">模型或图片读出来的数字，没经你点头就不进计算——'
        "一个没核对过的数字被当成结论，比算不出来更糟。</p>"
    )
    out.append('<form method="post" action="/analyze">')
    out.append(f'<input type="hidden" name="story" value="{esc(story)}">')
    for p in pending:
        if p.get("reason") == "conflict":
            out.append(
                f'<p style="margin:10px 0 2px"><b>{esc(p.get("label"))}</b>'
                '<span class="badge warn">说法不一致</span><br>'
                f'<span class="sub">你原话里说的是：{esc(p.get("from_story"))}'
                f'（本单按这个算）　建议值：{esc(p.get("suggested"))}</span></p>'
            )
            out.append(
                f'<label class="sub"><input type="checkbox" name="confirm" value="{esc(p.get("key"))}"> '
                f'改用 {esc(p.get("suggested"))} 重算</label>'
            )
        else:
            out.append(
                f'<p style="margin:10px 0 2px"><b>{esc(p.get("label"))}</b> '
                f'<span class="badge">建议值 {esc(p.get("suggested"))}</span></p>'
            )
            out.append(
                f'<label class="sub"><input type="checkbox" name="confirm" value="{esc(p.get("key"))}"> '
                f'对，就是这个数，用它重算</label>'
            )
    out.append('<button type="submit">确认后重算</button></form></div>')
    return "".join(out)


def materials_html(mats: list[dict], ev: dict | None) -> str:
    """证据强度 + 材料清单（谁举证、去哪开、你有没有）。"""
    if not mats:
        return ""
    out = ['<div class="card"><h2>六、要带什么（材料清单 + 谁举证）</h2>']
    ev = ev or {}
    if ev:
        pct = int(ev.get("score") or 0)
        out.append(
            f'<p class="sub">证据强度：<b>{pct}/100</b>（{esc(ev.get("level") or "未评估")}）'
            + ("　—　你提到手上已有的材料，已按有处理。" if ev.get("known") else
               "　—　你还没说手上有哪些材料，这一维先按中性算。")
            + "</p>"
        )
        out.append(f'<div class="bar"><i style="width:{pct}%"></i></div>')
        for g in ev.get("gaps") or []:
            out.append(f'<p class="sub" style="margin:4px 0">· {esc(g)}</p>')
    have = sum(1 for m in mats if m["have"])
    out.append(f'<p class="sub">共 {len(mats)} 项：你说已有的 {have} 项（绿），其余 {len(mats) - have} 项要去开（红）。</p>')
    out.append("<table><tr><th>材料</th><th>状态</th><th>为什么需要 / 怎么拿</th></tr>")
    for m in mats:
        flag = '<span class="ok-i">有</span>' if m["have"] else '<span class="no-i">缺</span>'
        out.append(
            f'<tr><td>{esc(m["name"])}<div class="dim">{esc(m.get("from_type") or "")}</div></td>'
            f'<td>{flag}</td>'
            f'<td class="sub" style="margin:0">{esc(m["purpose"])}<br>'
            f'<span style="color:#8a919c">谁举证：{esc(m["burden"])}　怎么拿：{esc(m["how"])}</span></td></tr>'
        )
    out.append("</table></div>")
    return "".join(out)


def venue_html(blocks: list[dict]) -> str:
    """立案路径：去哪、带什么、点一下就能打电话。"""
    if not blocks:
        return ""
    out = ['<div class="card"><h2>七、去哪办（立案路径）</h2>']
    out.append('<p class="sub">① 是主路径；② 能少跑一趟；⑤ 可以和仲裁同时走；④ 由单位发起，你了解即可；⑥ 兜底。</p>')
    for b in blocks:
        out.append(f'<div class="gate info"><span class="stage">{esc(b["stage"])}</span>')
        out.append(f'<div class="t">{esc(b["name"])}</div>')
        if b.get("where"):
            out.append(f'<div class="m">📍 {esc(b["where"])}</div>')
        if b.get("hours"):
            out.append(f'<div class="dim">🕘 {esc(b["hours"])}</div>')
        if b.get("note"):
            out.append(f'<div class="dim" style="margin-top:4px">{esc(b["note"])}</div>')
        acts = b.get("actions") or []
        if acts:
            links = []
            for a in acts:
                kind, label, value = a.get("kind"), a.get("label"), a.get("value") or ""
                if kind == "tel":
                    links.append(f'<a href="tel:{esc(value)}">{esc(label)}</a>')
                elif kind == "url":
                    links.append(f'<a href="{esc(value)}" target="_blank" rel="noopener">{esc(label)}</a>')
                else:
                    links.append(f'<span class="dim">{esc(label)}：{esc(value)}</span>')
            out.append('<div style="margin-top:6px;font-size:14px">' + "　".join(links) + "</div>")
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def worth_html(worth: dict | None, one_final: str | None = None) -> str:
    """值不值得去：六维打分 + 三选一结论。不是胜诉率。"""
    if not worth:
        return ""
    decision = worth.get("decision") or "not_recommended"
    out = ['<div class="card"><h2>八、值不值得去（六维加权）</h2>']
    out.append(
        f'<div class="verdict {esc(decision)}">{esc(worth.get("decision_label"))}'
        f'　总分 {esc(worth.get("score"))}/100</div>'
    )
    out.append(
        '<p class="sub">这不是胜诉率，也不预测裁判结果；它只把「标的额、证据、一裁终局、执行、'
        "替代路径、时效」六件事放在一起，告诉你先做哪件。</p>"
    )
    out.append("<table><tr><th>维度</th><th class=\"num\">分数</th><th>为什么给这个分</th></tr>")
    for d in worth.get("dimensions") or []:
        out.append(
            f'<tr><td>{esc(d["label"])}<div class="dim">权重 {int(round(d["weight"] * 100))}%</div></td>'
            f'<td class="num">{esc(d["score"])}</td>'
            f'<td class="sub" style="margin:0">{esc(d["note"])}</td></tr>'
        )
    out.append("</table>")
    alt = worth.get("alternative")
    if alt:
        out.append(
            f'<p class="gate warn" style="margin-top:10px"><b>更快的路：{esc(alt.get("title"))}</b><br>'
            f'{esc(alt.get("why"))}　<span class="dim">可拨 {esc(alt.get("tel"))}</span></p>'
        )
    if one_final:
        out.append(f'<p class="sub">一裁终局：{esc(one_final)}</p>')
    out.append("</div>")
    return "".join(out)


def render_page(report: dict | None = None, story: str = "", error: str = "") -> str:
    body = []
    if error:
        body.append(f'<div class="card ask">⚠️ {esc(error)}</div>')
    if report is None:
        body.append("<h1>劳动仲裁维权助手</h1>")
        body.append('<p class="sub">把你遇到的情况用大白话说一遍，我们帮你算清楚能主张多少钱、依据哪一条、还剩多少时间。</p>')
        body.append('<form method="post" action="/analyze">')
        body.append('<textarea name="story" id="story" placeholder="例如：2020年3月1日入职一家电子厂，月薪9000，一直没签书面合同。2024年5月20日主管口头说不要我了，让我当天走人。我还有5天年假没休。">'
                    + esc(story) + "</textarea>")
        body.append('<button type="submit">测算我能拿多少钱</button></form>')
        body.append('<div class="card noprint"><b>不会说？点一个词，帮你把话说清楚</b>')
        body.append('<p class="sub" style="margin:4px 0 0">法律里有专门的说法。点一下插进上面的输入框，下面会用人话解释它是什么意思。</p>')
        body.append(chips_html())
        body.append('<div id="explain"></div></div>')
        body.append('<div class="card"><b>先说清楚三件事</b>'
                    '<p style="margin:6px 0 0">① 金额由规则内核计算，不是模型随口说的；'
                    '② 每条金额都给出法律条文原文，可自行核对；③ 信息不够时会先问你，不会硬算。</p></div>')
        cities = covered_cities()
        if cities:
            rows = "、".join(
                f'{esc(c["city"])}（社平 {c["avg_wage_monthly"]:,.0f} 元/月，核验 {esc(c["verified_at"])}）'
                for c in cities
            )
            body.append('<div class="card"><b>金额口径覆盖哪些城市</b>'
                        f'<p class="sub" style="margin:6px 0 0">{rows}</p>'
                        '<p class="sub" style="margin:6px 0 0">你所在的城市不在上面时，'
                        '受案范围、时效、解除合法性照样能判，但 3 倍封顶和最低工资**不套用别的城市**，'
                        '会明说「未覆盖」，不编数字。</p></div>')
        body.append('<p class="foot">本工具只覆盖内地劳动争议仲裁，不构成法律意见。符合条件可拨 12348 申请法律援助。</p>')
    elif report["status"] == "out_of_scope":
        body.append(f'<h1>这件事不归劳动仲裁管</h1><p class="sub">{esc(report["scope"]["reason"])}</p>')
        body.append('<div class="card"><h2>该去哪、带什么</h2>')
        body.append(f'<p>{esc(report.get("redirect") or "请补充更多细节")}</p>')
        for h in report.get("hints", []):
            body.append(f'<p>· {esc(h)}</p>')
        body.append("</div>")
        body.append(pending_html(report.get("pending") or [], story))
        body.append('<p><a href="/">← 换个问题</a></p>')
    elif report["status"] == "blocked":
        body.append("<h1>现在还不能申请</h1>")
        body.append(
            '<p class="sub">这不是算不出来，而是这道门现在就进不去——'
            '所以我不给你一个看起来很像结论的金额。</p>'
        )
        for b in report.get("blockers") or []:
            body.append(f'<div class="card ask"><b>硬性障碍：</b>{esc(b)}</div>')
        body.append(gates_html(report.get("gates")))
        if report.get("assumptions"):
            body.append('<div class="card"><h2>说明</h2>')
            for a in report["assumptions"]:
                body.append(f"<p>· {esc(a)}</p>")
            body.append("</div>")
        body.append('<p><a href="/">← 换个问题</a></p>')
    elif report["status"] == "need_more":
        body.append("<h1>还差几个信息才能算</h1>")
        body.append('<div class="card ask"><h2>请补充</h2>')
        for q in report["questions"]:
            body.append(f"<p>· {esc(q)}</p>")
        if report.get("relative"):
            body.append("<p><b>系统自动推定的时间，请确认：</b></p>")
            for x in report["relative"]:
                body.append(f"<p>· {esc(x)}</p>")
        body.append("</div>")
        body.append(gates_html(report.get("gates")))
        body.append(map_html(report.get("fields") or {}, clickable=True))
        body.append(pending_html(report.get("pending") or [], story))
        body.append('<form method="post" action="/analyze"><h2>把补充的内容写在这里</h2>')
        body.append('<textarea name="story" id="story">' + esc(story) + "</textarea>")
        body.append('<button type="submit">再算一次</button></form>')
        body.append('<p><a href="/">← 从头重写</a></p>')
    else:
        worth = report.get("worth") or {}
        body.append(f'<h1>你能主张 <span class="total">{_money(report["total"])}</span> 元</h1>')
        if worth.get("decision_label"):
            body.append(
                f'<div class="verdict {esc(worth.get("decision"))}">'
                f'{esc(worth["decision_label"])}　<span class="dim">值得性 {esc(worth.get("score"))}/100</span></div>'
            )
        if report.get("scope", {}).get("hints"):
            body.append('<p class="sub">' + "；".join(esc(h) for h in report["scope"]["hints"][:2]) + "</p>")
        body.append(pending_html(report.get("pending") or [], story))
        body.append(gates_html(report.get("gates")))
        if story:
            body.append(f'<div class="card"><h2>你描述的经过</h2><blockquote>{esc(story)}</blockquote></div>')
        body.append(map_html(report.get("fields") or {}))
        body.append('<div class="card"><h2>一、逐项金额</h2><table><tr><th>项目</th><th class="num">金额（元）</th><th>算法</th></tr>')
        for it in report["items"]:
            body.append(f'<tr><td>{esc(it["name"])}</td><td class="num">{_money(it["amount"])}</td><td>{esc(it["formula"])}</td></tr>')
        body.append(f'<tr><th>合计</th><th class="num">{_money(report["total"])}</th><th></th></tr></table></div>')

        body.append('<div class="card"><h2>二、法律依据（可逐条核对）</h2>')
        for it in report["items"]:
            flag = '<span class="badge ok">引用已核验</span>' if it["cite_ok"] else '<span class="badge warn">引用异常</span>'
            body.append(f'<p style="margin:10px 0 2px"><b>{esc(it["name"])}</b>{flag}<br><span class="sub" style="margin:0">{esc(it["basis"])}</span></p>')
            for c in it.get("cite_texts", []):
                body.append(f'<details><summary>{esc(c["cite"])} 原文</summary><blockquote>{esc(c["text"])}</blockquote></details>')
        body.append("</div>")

        if report.get("reference_cases"):
            body.append('<div class="card"><h2>类案参考</h2>'
                        '<p class="sub">按案由与案情线索选取。请结合本人证据与案件差异阅读。</p>')
            for case in report["reference_cases"]:
                body.append(f'<h3>{esc(case["title"])}</h3>')
                for label, key in (("争议焦点", "focus"), ("处理结果", "result"),
                                   ("可比点", "compare"), ("区别", "distinguish")):
                    body.append(f'<p><b>{label}</b>　{esc(case[key])}</p>')
                body.append(f'<p><a href="{esc(case["url"])}">{esc(case["source"])}</a></p>')
            body.append("</div>")

        body.append('<div class="card"><h2>三、仲裁时效</h2><table><tr><th>请求</th><th>起算</th><th>截止</th><th class="num">剩余</th></tr>')
        for d in report["deadlines"]:
            left = "—" if d["days_left"] is None else ("已过期" if d["expired"] else f'{d["days_left"]} 天')
            body.append(f'<tr><td>{esc(d["label"])}</td><td>{esc(d["anchor"])}</td><td>{esc(d["deadline"])}</td><td class="num">{esc(left)}</td></tr>')
        body.append("</table></div>")

        if report.get("rehearsal"):
            body.append('<div class="card"><h2>四、对方会怎么反驳你（提前演一遍）</h2>')
            for rd in report["rehearsal"]["rounds"]:
                body.append(f'<p style="margin:12px 0 2px"><b>HR 可能说：</b>{esc(rd["hr_says"])}</p>')
                body.append(f'<p style="margin:0"><span class="sub">为什么难缠：</span>{esc(rd["why"])}</p>')
                body.append(f'<p style="margin:0"><span class="sub">你拿什么顶回去：</span>{esc(rd["counter"])}</p>')
                body.append('<p class="sub" style="margin:2px 0 0">要准备：' + "、".join(esc(n) for n in rd["need"]) + "</p>")
            body.append(f'<p class="sub">{esc(report["rehearsal"]["tip"])}</p></div>')
            body.append(evidence_html(report.get("rehearsal")))

        body.append(materials_html(report.get("materials") or [], report.get("evidence_score")))
        body.append(venue_html(report.get("venue") or []))
        body.append(worth_html(report.get("worth"), report.get("one_final_note")))

        if report.get("assumptions"):
            body.append('<div class="card ask"><h2>本单采用的假设（请确认）</h2>')
            for a in report["assumptions"]:
                body.append(f"<p>· {esc(a)}</p>")
            body.append("</div>")

        body.append(f'<p><a href="/pdf?story={urllib.parse.quote(story)}">⬇ 下载 PDF</a>　'
                    f'<a href="/print?story={urllib.parse.quote(story)}">🖨 网页版打印</a>　'
                    f'<a href="/report?story={urllib.parse.quote(story)}">⬇ 下载 Markdown</a>　'
                    f'<a href="/application?story={urllib.parse.quote(story)}">📄 生成仲裁申请书草稿</a></p>')
        body.append('<p><a href="/">← 重新算一单</a></p>')
        body.append('<p class="foot">本单仅根据你提供的信息做初步测算，不构成法律意见，不能代替律师。正式申请前请核对工资流水、社保记录和劳动合同原件。</p>')
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>劳动仲裁维权助手</title><style>{CSS}</style></head><body>
{''.join(body)}
{CHIP_JS if report is None else ''}
{MAP_JS if (report is not None and report.get("status") == "need_more") else ''}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "arb/1.0"

    def _send(self, code: int, body, ctype: str = "text/html; charset=utf-8", extra: dict | None = None):
        data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _q(query: str) -> tuple[str, list[str]]:
        """从查询串里取出 story 与已确认字段（confirm 可重复）。"""
        p = urllib.parse.parse_qs(query)
        return p.get("story", [""])[0], p.get("confirm", [])

    def do_GET(self):  # noqa: N802
        q = urllib.parse.urlparse(self.path).query
        if self.path.startswith("/print"):
            story, confirmed = self._q(q)
            self._send(200, print_page(story, confirmed=confirmed))
            return
        if self.path.startswith("/application"):
            story, confirmed = self._q(q)
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            txt = render_application(r) + chr(10) + chr(10) + render_notes(r)
            self._send(200, txt, "text/plain; charset=utf-8",
                       {"Content-Disposition": 'attachment; filename="arb-application.txt"'})
            return
        if self.path.startswith("/report"):
            story, confirmed = self._q(q)
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            md = render_markdown(r)
            name = f"arb-report-{date.today().isoformat()}.md"
            self._send(200, md, "text/markdown; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="{name}"'})
            return
        if self.path.startswith("/pdf"):
            story, confirmed = self._q(q)
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            data = render_pdf(r)
            name = f"arb-report-{date.today().isoformat()}.pdf"
            self._send(200, data, "application/pdf",
                       {"Content-Disposition": f'attachment; filename="{name}"'})
            return
        self._send(200, render_page())

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        p = urllib.parse.parse_qs(raw)
        story = p.get("story", [""])[0].strip()
        confirmed = p.get("confirm", [])   # 用户勾了"对，就是这个数"的字段
        if not story:
            self._send(400, render_page(error="还没输入内容"))
            return
        try:
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            self._send(200, render_page(r, story))
        except Exception as e:  # 现场演示不能白屏
            self._send(500, render_page(error=f"出错了：{e}", story=story))

    def log_message(self, fmt, *args):
        print(f"[web] {fmt % args}")


def main(port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"劳动仲裁维权助手已启动： http://127.0.0.1:{port}  （Ctrl+C 退出）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    import sys

    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
