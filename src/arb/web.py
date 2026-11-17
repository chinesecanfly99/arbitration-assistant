"""控制台版单页前端（纯标准库，零依赖）：python -m arb.web

特性：
- 双栏控制台布局：左侧「演示案例库」+ 工作台视图导航，右侧「输入控制台 + 结果工作台」
- 普通 AI vs 本系统同屏对比视图（支持配置 API Key 实时实测，无 Key 时自动提供离线典型对照）
- 按需展开的智能要素引导（默认收起 35 个术语芯片，保持控制台清爽；缺字段时精准提示补录）
- 浏览器原生中文语音输入（Web Speech API，零后端依赖，不支持时友好降级）

路由：
    GET  /                  控制台首页（支持 ?case=<id> 直接运行预设案例）
    POST /analyze           计算并返回控制台结果页
    GET  /print?story=...   打印/导 PDF 用纯净版页面
    GET  /report?story=...  下载 Markdown 测算单
    GET  /pdf?story=...     下载 PDF 报告
    GET  /application?story=... 下载仲裁申请书草稿
"""
from __future__ import annotations

import html
import json
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import llm
from .application import render_application, render_notes
from .chips import groups
from .cli import render_markdown
from .compare import DEMO_CASES, compare_with_generic_ai, get_demo_case, match_demo_by_story
from .evidence import rows as evidence_rows, summary as evidence_summary
from .map import completeness, summary_line
from .pdf import render_pdf
from .pipeline import analyze, covered_cities

CSS = """
*{box-sizing:border-box}
:root{
  --bg:#f1f5f9;--card:#ffffff;--border:#e2e8f0;--text:#0f172a;--muted:#64748b;
  --side:#0f172a;--side-hover:#1e293b;--side-border:#1e293b;--primary:#2563eb;
  --primary-hover:#1d4ed8;--ok:#15803d;--ok-bg:#ecfdf5;--ok-bd:#a7f3d0;
  --warn:#b45309;--warn-bg:#fffbeb;--warn-bd:#fde68a;
  --fail:#b91c1c;--fail-bg:#fef2f2;--fail-bd:#fecaca;
}
body{margin:0;font:15px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
     color:var(--text);background:var(--bg)}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}
h1{font-size:22px;margin:0 0 6px;line-height:1.35}
h2{font-size:16px;margin:0 0 10px;padding-left:10px;border-left:4px solid var(--primary);line-height:1.4}
h3{font-size:15px;margin:14px 0 6px}
.sub{color:var(--muted);font-size:13.5px;margin:0 0 12px}

/* Console Layout */
.app-shell{display:flex;min-height:100vh}
.sidebar{width:280px;flex-shrink:0;background:var(--side);color:#e2e8f0;padding:18px 14px 28px;
         display:flex;flex-direction:column;gap:16px;border-right:1px solid var(--side-border)}
.brand{display:flex;flex-direction:column;gap:6px;padding:4px 6px 12px;border-bottom:1px solid #1e293b}
.brand-title{font-size:17px;font-weight:700;color:#fff;letter-spacing:.3px;display:flex;align-items:center;gap:8px}
.brand-pill{display:inline-block;width:fit-content;font-size:11.5px;padding:2px 8px;border-radius:999px;
            background:rgba(16,185,129,.16);color:#6ee7b7;border:1px solid rgba(16,185,129,.35)}
.side-label{font-size:11.5px;text-transform:uppercase;letter-spacing:.8px;color:#94a3b8;margin:4px 6px 6px}
.case-list{display:flex;flex-direction:column;gap:8px}
.case-btn{width:100%;text-align:left;background:#162033;color:#e2e8f0;border:1px solid #263449;
          border-radius:10px;padding:10px 11px;cursor:pointer;transition:.15s;margin:0}
.case-btn:hover{background:#1e293b;border-color:#3b82f6}
.case-btn.active{background:#1d4ed8;border-color:#60a5fa;color:#fff;box-shadow:0 4px 12px rgba(37,99,235,.32)}
.case-top{display:flex;align-items:center;justify-content:space-between;gap:6px;font-size:13.5px;font-weight:600;line-height:1.35}
.case-desc{font-size:12px;color:#94a3b8;margin-top:4px;line-height:1.45}
.case-btn.active .case-desc{color:#dbeafe}
.case-tag{font-size:11px;padding:1px 7px;border-radius:999px;white-space:nowrap;font-weight:500}
.case-tag.ok{background:rgba(16,185,129,.18);color:#6ee7b7}
.case-tag.info{background:rgba(56,189,248,.18);color:#7dd3fc}
.case-tag.warn{background:rgba(245,158,11,.2);color:#fcd34d}
.case-tag.fail{background:rgba(239,68,68,.2);color:#fca5a5}
.case-btn.active .case-tag{background:rgba(255,255,255,.22);color:#fff}

.nav-links{display:flex;flex-direction:column;gap:4px;margin-top:auto;padding-top:12px;border-top:1px solid #1e293b}
.nav-link{display:block;padding:7px 10px;border-radius:8px;color:#cbd5e1;font-size:13px}
.nav-link:hover{background:#1e293b;color:#fff;text-decoration:none}

.workspace{flex:1;min-width:0;padding:18px 24px 56px;max-width:1160px}
.topbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;
        margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--border)}
.topbar-title{font-size:19px;font-weight:700;margin:0}
.topbar-sub{font-size:13px;color:var(--muted);margin:2px 0 0}
.status-pills{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{font-size:12px;padding:4px 10px;border-radius:999px;background:#e0f2fe;color:#0369a1;font-weight:500}
.pill.green{background:#dcfce7;color:#15803d}
.pill.slate{background:#e2e8f0;color:#334155}

/* Input Console */
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin:14px 0;
      box-shadow:0 1px 2px rgba(15,23,42,.04)}
.console-card{margin-top:0;border-color:#cbd5e1}
.console-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.console-title{font-weight:600;font-size:14.5px;color:var(--text)}
.clear-link{font-size:12.5px;color:var(--muted);cursor:pointer;background:none;border:0;padding:2px 6px;width:auto;margin:0}
.clear-link:hover{color:var(--fail)}
textarea{width:100%;min-height:112px;padding:12px 14px;border:1px solid #cbd5e1;border-radius:10px;
         font-size:15px;line-height:1.6;background:#fff;color:var(--text);resize:vertical;font-family:inherit}
textarea:focus{outline:none;border-color:var(--primary);box-shadow:0 0 0 3px rgba(37,99,235,.12)}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-top:10px}
.tool-left,.tool-right{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.btn-tool{padding:7px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#f8fafc;color:#1e293b;
          font-size:13.5px;cursor:pointer;display:inline-flex;align-items:center;gap:6px;width:auto;margin:0}
.btn-tool:hover{background:#eef2ff;border-color:#93c5fd}
.btn-tool.recording{background:#fef2f2;border-color:#ef4444;color:#b91c1c;animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.72}}
.btn-primary{padding:9px 20px;border:0;border-radius:9px;background:var(--primary);color:#fff;font-size:14.5px;
             font-weight:600;cursor:pointer;width:auto;margin:0}
.btn-primary:hover{background:var(--primary-hover)}
.switch{display:inline-flex;align-items:center;gap:6px;font-size:13.5px;color:#334155;cursor:pointer;user-select:none}
.switch input{width:15px;height:15px;accent-color:var(--primary);cursor:pointer}
.voice-tip{font-size:12.5px;color:var(--muted);margin-top:6px;min-height:18px}

/* Collapsible Drawers */
.drawer{margin-top:12px;padding:12px 14px;border-radius:10px;background:#f8fafc;border:1px dashed #cbd5e1;display:none}
.drawer.open{display:block}
.api-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px}
.api-grid input{width:100%;padding:7px 10px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;background:#fff}

/* Chips inside collapsible drawer & missing-field fill */
.chips{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 0}
.chip{border:1px solid #cbd5e1;background:#fff;color:#1f2329;border-radius:20px;padding:5px 11px;
      font-size:13px;width:auto;margin:0;cursor:pointer}
.chip:hover{border-color:var(--primary);background:#eff6ff}
.groupname{font-size:12.5px;font-weight:600;color:#475569;margin:10px 0 2px}
#explain{margin-top:10px;font-size:13.5px;color:#334155;background:#fff;border-left:3px solid var(--primary);
         padding:8px 12px;border-radius:0 8px 8px 0;display:none}

/* Comparison Dual-Pane */
.compare-wrap{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
.cmp-card{border-radius:12px;padding:16px;background:#fff;border:1px solid var(--border);display:flex;flex-direction:column;gap:10px}
.cmp-ai{border-color:#fecaca;background:linear-gradient(180deg,#fffafa 0%,#ffffff 60px)}
.cmp-ours{border-color:#a7f3d0;background:linear-gradient(180deg,#f0fdf4 0%,#ffffff 60px)}
.cmp-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid #f1f5f9}
.cmp-title{font-weight:700;font-size:15px}
.cmp-ai .cmp-title{color:#991b1b}
.cmp-ours .cmp-title{color:#166534}
.cmp-mode{font-size:11.5px;padding:2px 8px;border-radius:999px;background:#f1f5f9;color:#475569}
.cmp-reply{font-size:14px;line-height:1.65;color:#334155;background:#f8fafc;border-radius:8px;padding:10px 12px;border:1px solid #e2e8f0;white-space:pre-wrap}
.flaw-list{display:flex;flex-direction:column;gap:6px;margin-top:2px}
.flaw-item{font-size:12.5px;padding:5px 9px;border-radius:7px;background:#fef2f2;color:#991b1b;border:1px solid #fecaca}
.pro-item{font-size:12.5px;padding:5px 9px;border-radius:7px;background:#ecfdf5;color:#166534;border:1px solid #bbf7d0}
.hero-total{font-size:28px;font-weight:800;color:#15803d;letter-spacing:-.3px}

/* Workspace Section Tabs */
.ws-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0;padding:8px 10px;background:#fff;border:1px solid var(--border);border-radius:10px}
.ws-tab{font-size:13px;padding:5px 12px;border-radius:7px;background:#f1f5f9;color:#334155;font-weight:500}
.ws-tab:hover{background:#e0e7ff;color:#1d4ed8;text-decoration:none}

/* Existing Report Components */
.total{font-size:28px;font-weight:700;color:#c0392b}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 6px;border-bottom:1px solid #eef0f3;text-align:left;vertical-align:top}
td.num,th.num{text-align:right;white-space:nowrap}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:12px;background:#e8f2ff;color:#2557c0;margin-left:6px}
.badge.ok{background:#e7f7ed;color:#1a7f45}
.badge.warn{background:#fff4e5;color:#b26a00}
.badge.unit{background:#fff4e5;color:#b26a00}
.badge.both{background:#eef3ff;color:#2557c0}
.badge.me{background:#e7f7ed;color:#1a7f45}
.badge.fail{background:#ffe8e8;color:#c0392b}
blockquote{margin:6px 0 0;padding:8px 12px;background:#f5f7fb;border-left:3px solid #cfd8e6;font-size:13.5px;color:#4b5563}
details{margin:6px 0}
summary{cursor:pointer;color:var(--primary);font-size:13.5px}
.ask{background:#fffbeb;border:1px solid #fde68a}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.cell{border:1px solid #e6e8ec;border-radius:10px;padding:8px 10px;font-size:13.5px;display:flex;flex-direction:column;gap:2px;background:#fbfcfd}
.cell .k{color:#6b7280;font-size:12.5px}
.cell .v{color:#1f2329;word-break:break-all}
.cell .m{font-size:12px;color:#8a919c}
.cell.ok{border-color:#bfe8cd;background:#f2fbf5}
.cell.ok .m{color:#1a7f45}
.cell.missing{border-color:#ffc9c9;background:#fff5f5}
.cell.missing .m{color:#c0392b}
.cell.optional{background:#f8f9fb}
.pct{font-size:15px;color:var(--primary);font-weight:600}
.verdict{display:inline-block;padding:4px 12px;border-radius:8px;font-size:14.5px;font-weight:600;margin:2px 0 8px}
.verdict.recommend{background:#e7f7ed;color:#1a7f45}
.verdict.better_alternative{background:#fff4e5;color:#b26a00}
.verdict.not_recommended{background:#f1f3f6;color:#4b5563}
.gate{border:1px solid #e6e8ec;border-radius:10px;padding:10px 12px;margin:8px 0;background:#fbfcfd}
.gate.pass{border-left:4px solid #1a7f45}
.gate.warn{border-left:4px solid #b26a00;background:#fffdf7}
.gate.fail{border-left:4px solid #c0392b;background:#fff7f7}
.gate.info{border-left:4px solid #8a919c}
.gate .t{font-weight:600;font-size:14px}
.gate .m{font-size:13.5px;color:#4b5563;margin:2px 0}
.gate ul{margin:4px 0 0;padding-left:18px;font-size:13px;color:#4b5563}
.bar{height:6px;background:#eef0f3;border-radius:4px;overflow:hidden;margin:2px 0 6px}
.bar i{display:block;height:100%;background:var(--primary)}
.dim{font-size:12.5px;color:#4b5563}
.ok-i{color:#1a7f45;font-weight:600}
.no-i{color:#c0392b;font-weight:600}
.stage{font-size:12.5px;color:var(--primary);font-weight:600}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.export-bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.export-btn{display:inline-block;padding:8px 14px;border-radius:8px;background:#f8fafc;border:1px solid #cbd5e1;
            color:#0f172a;font-size:13.5px;font-weight:500}
.export-btn:hover{background:#eff6ff;border-color:var(--primary);text-decoration:none}
.foot{color:#8a919c;font-size:12.5px;margin-top:24px}

@media (max-width:920px){
  .app-shell{flex-direction:column}
  .sidebar{width:100%;border-right:0;border-bottom:1px solid var(--side-border)}
  .compare-wrap,.two-col,.api-grid{grid-template-columns:1fr}
}
@media (max-width:520px){.grid{grid-template-columns:1fr}}
@media print{
  .sidebar,.topbar,.console-card,.ws-tabs,.compare-wrap,.chips,.noprint,form,button{display:none!important}
  .workspace{max-width:760px;margin:0 auto;padding:0}
  body{background:#fff}
}
"""


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def _money(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return esc(v)


CONSOLE_JS = r"""
<script>
(function () {
  var storyBox = document.getElementById('story');
  var form = storyBox ? storyBox.form : document.querySelector('form[action="/analyze"]');

  // 1. 左侧演示案例库一键填入并运行
  document.addEventListener('click', function (e) {
    var cbtn = e.target.closest('.case-btn');
    if (cbtn && storyBox && form) {
      storyBox.value = cbtn.dataset.story || '';
      var cmp = document.getElementById('compareCheck');
      if (cmp) cmp.checked = true;
      form.submit();
      return;
    }

    // 2. 缺失字段精准补全按钮 (.chip.fill)
    var fill = e.target.closest('.chip.fill');
    if (fill && storyBox) {
      var add = fill.dataset.text || '';
      var val = storyBox.value;
      var sep = (!val || /[\s，。；;,、]$/.test(val)) ? '' : '；';
      storyBox.value = val + sep + add;
      storyBox.focus();
      return;
    }

    // 3. 折叠抽屉中的术语引导芯片 (.chip)
    var chip = e.target.closest('.chip');
    if (chip && storyBox) {
      var term = chip.dataset.term || '';
      if (!term) return;
      var val2 = storyBox.value;
      storyBox.value = (val2 && !/[\s，。,;；]$/.test(val2)) ? val2 + '，' + term + '。' : val2 + term + '。';
      storyBox.focus();
      var ex = document.getElementById('explain');
      if (ex) {
        ex.style.display = 'block';
        ex.innerHTML = '<b>' + term + '</b><br>' + (chip.dataset.plain || '') +
                       '<br><span style="color:#64748b">什么时候用得上：' + (chip.dataset.when || '') + '</span>' +
                       '<br><span style="color:#64748b">为什么要说清楚：' + (chip.dataset.why || '') + '</span>';
      }
    }
  });

  // 4. 抽屉展开/收起（智能要素引导 & 实时对比 API 设置）
  function bindToggle(btnId, drawerId) {
    var btn = document.getElementById(btnId);
    var dr = document.getElementById(drawerId);
    if (!btn || !dr) return;
    btn.addEventListener('click', function () {
      dr.classList.toggle('open');
    });
  }
  bindToggle('toggleGuideBtn', 'chipsDrawer');
  bindToggle('toggleApiBtn', 'apiDrawer');

  var clearBtn = document.getElementById('clearStoryBtn');
  if (clearBtn && storyBox) {
    clearBtn.addEventListener('click', function () {
      storyBox.value = '';
      storyBox.focus();
    });
  }

  // 5. 浏览器原生中文语音输入 (Web Speech API)
  var voiceBtn = document.getElementById('voiceBtn');
  var voiceTip = document.getElementById('voiceTip');
  var SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  var rec = null;
  var listening = false;
  var baseText = '';

  if (voiceBtn) {
    if (!SpeechRec) {
      voiceBtn.addEventListener('click', function () {
        if (voiceTip) {
          voiceTip.textContent = '当前浏览器暂不支持原生语音听写，请使用 Chrome 或 Edge 浏览器体验语音输入，或直接打字/点击左侧演示案例。';
        }
      });
    } else {
      voiceBtn.addEventListener('click', function () {
        if (listening && rec) {
          rec.stop();
          return;
        }
        rec = new SpeechRec();
        rec.lang = 'zh-CN';
        rec.continuous = true;
        rec.interimResults = true;
        baseText = storyBox ? storyBox.value : '';
        if (baseText && !/[\s，。；;,]$/.test(baseText)) {
          baseText += '，';
        }

        rec.onstart = function () {
          listening = true;
          voiceBtn.classList.add('recording');
          voiceBtn.textContent = '⏹ 停止听写';
          if (voiceTip) voiceTip.textContent = '🔴 正在听写中文口述… 说完请点击「停止听写」，可随时手动修正日期和数字。';
        };

        rec.onresult = function (event) {
          var finalTxt = '';
          var interimTxt = '';
          for (var i = 0; i < event.results.length; i++) {
            var seg = event.results[i][0].transcript;
            if (event.results[i].isFinal) finalTxt += seg;
            else interimTxt += seg;
          }
          if (storyBox) storyBox.value = baseText + finalTxt + interimTxt;
        };

        rec.onerror = function (ev) {
          listening = false;
          voiceBtn.classList.remove('recording');
          voiceBtn.textContent = '🎙 语音输入';
          if (voiceTip) voiceTip.textContent = '语音识别未完成（' + (ev.error || '请检查麦克风权限') + '），可直接文字输入。';
        };

        rec.onend = function () {
          listening = false;
          voiceBtn.classList.remove('recording');
          voiceBtn.textContent = '🎙 语音输入';
          if (voiceTip && voiceTip.textContent.indexOf('正在听写') !== -1) {
            voiceTip.textContent = '语音已转入输入框，建议核对一下日期与薪资金额后点击测算。';
          }
        };

        rec.start();
      });
    }
  }

  // 6. 实时 API 配置仅暂存在当前浏览器会话中（不落服务端磁盘）
  ['apiKeyInput', 'apiBaseInput', 'apiModelInput'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el || !window.sessionStorage) return;
    var saved = sessionStorage.getItem('arb_' + id);
    if (saved && !el.value) el.value = saved;
    el.addEventListener('input', function () {
      sessionStorage.setItem('arb_' + id, el.value);
    });
  });
})();
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


def map_html(fields: dict, clickable: bool = False) -> str:
    """9 格完整度地图：已填的绿、必填缺失的红、可选的灰。"""
    c = completeness(fields)
    out = [f'<div class="card" id="sec-map"><h2>案件完整度 <span class="pct">{int(c["score"] * 100)}%</span></h2>']
    out.append('<p class="sub" style="margin:4px 0 10px">' + esc(summary_line(fields)) + "</p>")
    out.append('<div class="grid">')
    for r in c["rows"]:
        cls = "cell " + r["status"]
        mark = "✓" if r["status"] == "ok" else ("可选" if r["status"] == "optional" else "缺")
        val = esc(r["value"]) if r["value"] else esc(r["hint"].replace("例如：", "").replace("可选：", ""))
        out.append(
            f'<div class="{cls}"><span class="k">{esc(r["label"])}</span>'
            f'<span class="v">{val}</span><span class="m">{mark}</span></div>'
        )
    out.append("</div>")
    if clickable:
        miss = [r for r in c["rows"] if r["status"] == "missing"]
        if miss:
            out.append('<p class="sub" style="margin:12px 0 6px">缺失项快速补录（点一下插入上方输入框并修改数字）：</p><div class="chips">')
            for r in miss:
                out.append(f'<button type="button" class="chip fill" data-text="{esc(r["hint"])}">补：{esc(r["label"])}</button>')
            out.append("</div>")
    out.append("</div>")
    return "".join(out)


def evidence_html(rehearsal: dict | None) -> str:
    if not rehearsal or not rehearsal.get("evidence_checklist"):
        return ""
    rows_ = evidence_rows(rehearsal["evidence_checklist"])
    out = ['<div class="card" id="sec-evidence"><h2>五、证据清单（谁举证）</h2>']
    out.append('<p class="sub">' + esc(evidence_summary(rows_)) + "。依据《劳动争议调解仲裁法》第六条。</p>")
    out.append("<table><tr><th>证据</th><th>谁出</th><th>为什么</th></tr>")
    for r in rows_:
        badge = {
            "单位": '<span class="badge unit">单位举证</span>',
            "双方": '<span class="badge both">双方</span>',
            "你": '<span class="badge me">你自己准备</span>',
        }[r["who"]]
        out.append(f'<tr><td>{esc(r["name"])}</td><td>{badge}</td><td class="sub" style="margin:0">{esc(r["why"])}</td></tr>')
    out.append("</table></div>")
    return "".join(out)


def print_page(story: str, today=None, confirmed=()) -> str:
    """打印/导 PDF 用的整页 HTML（纯净版，不含左侧案例栏与 AI 对比视图）。"""
    r = analyze(story, today=today, mode="best_effort", confirmed=confirmed)
    page = render_page(r, story, show_compare=False, print_mode=True)
    tip = '<p class="noprint" style="color:#8a919c;font-size:13px">按 Ctrl+P（Mac 是 ⌘P）可存成 PDF。</p>'
    return page.replace("</body>", tip + "</body>")


def gates_html(gates: dict | None) -> str:
    """三道闸门：受案范围 → 资格 → 口径。每层都给出状态、理由与法条。"""
    if not gates:
        return ""
    layers = gates.get("layers") or []
    if not layers:
        return ""
    out = ['<div class="card" id="sec-gates"><h2>能不能申请（三道闸门）</h2>']
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
    """未确认读数：本单没有用它们算钱，勾选后重算。"""
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
    out.append('<button type="submit" class="btn-primary" style="margin-top:10px">确认后重算</button></form></div>')
    return "".join(out)


def materials_html(mats: list[dict], ev: dict | None) -> str:
    """证据强度 + 材料清单（谁举证、去哪开、你有没有）。"""
    if not mats:
        return ""
    out = ['<div class="card" id="sec-materials"><h2>六、要带什么（材料清单 + 谁举证）</h2>']
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
    out = ['<div class="card" id="sec-venue"><h2>七、去哪办（立案路径）</h2>']
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
    out = ['<div class="card" id="sec-worth"><h2>八、值不值得去（六维加权）</h2>']
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


def sidebar_html(active_story: str = "", has_report: bool = False) -> str:
    matched = match_demo_by_story(active_story)
    active_id = matched["id"] if matched else ""
    out = [
        '<aside class="sidebar">',
        '<div class="brand">',
        '<div class="brand-title">⚖️ 劳动仲裁维权助手</div>',
        '<span class="brand-pill">规则内核 · 零幻觉控制台</span>',
        "</div>",
        '<div><div class="side-label">演示案例库（点击即跑）</div><div class="case-list">',
    ]
    for c in DEMO_CASES:
        cls = "case-btn active" if c["id"] == active_id else "case-btn"
        out.append(
            f'<button type="button" class="{cls}" data-story="{esc(c["story"])}">'
            f'<div class="case-top"><span>{esc(c["title"])}</span>'
            f'<span class="case-tag {esc(c["badge_cls"])}">{esc(c["tag"])}</span></div>'
            f'<div class="case-desc">{esc(c["summary"])}</div></button>'
        )
    out.append("</div></div>")
    if has_report:
        out.append(
            '<div class="nav-links"><div class="side-label">工作台视图</div>'
            '<a class="nav-link" href="#sec-compare">🆚 普通 AI 对比视图</a>'
            '<a class="nav-link" href="#sec-calc">💰 分项金额与法条核验</a>'
            '<a class="nav-link" href="#sec-gates">🛡 三层闸门与完整度</a>'
            '<a class="nav-link" href="#sec-evidence">📋 举证、路径与导出</a>'
            '<a class="nav-link" href="/">↺ 重置控制台</a>'
            "</div>"
        )
    else:
        out.append(
            '<div class="nav-links"><div class="side-label">内核规格</div>'
            '<div class="nav-link">· 10 部法规 519 条原文</div>'
            '<div class="nav-link">· 京沪广深杭 5 城独立口径</div>'
            '<div class="nav-link">· 零第三方依赖 · 离线可用</div>'
            "</div>"
        )
    out.append("</aside>")
    return "".join(out)


def compare_html(report: dict, compare_data: dict) -> str:
    """渲染「普通通用 AI vs 本系统规则内核」双栏对比区。"""
    status = report.get("status")
    cite_audit = compare_data.get("cite_audit") or {}
    out = ['<div class="compare-wrap" id="sec-compare">']

    # 左栏：普通通用 AI
    out.append('<div class="cmp-card cmp-ai">')
    out.append(
        f'<div class="cmp-head"><span class="cmp-title">🤖 普通通用大模型（直接提问）</span>'
        f'<span class="cmp-mode">{esc(compare_data.get("mode_label"))}</span></div>'
    )
    if compare_data.get("error"):
        out.append(f'<div class="flaw-item">{esc(compare_data["error"])}</div>')
    out.append(f'<div class="cmp-reply">{esc(compare_data.get("reply"))}</div>')
    if cite_audit.get("items"):
        audit_badges = []
        for c in cite_audit["items"]:
            b_cls = "ok" if c["verified"] else "fail"
            mark = "核验通过" if c["verified"] else "库中未查到"
            audit_badges.append(f'<span class="badge {b_cls}">{esc(c["cite"])} · {mark}</span>')
        out.append('<div class="dim">法条核验结果：' + "".join(audit_badges) + "</div>")
    out.append('<div class="flaw-list">')
    for f in compare_data.get("flaws") or []:
        out.append(f'<div class="flaw-item">⚠ {esc(f)}</div>')
    out.append("</div></div>")

    # 右栏：本系统规则+法条内核
    out.append('<div class="cmp-card cmp-ours">')
    out.append(
        '<div class="cmp-head"><span class="cmp-title">🛡 本系统 · 规则 + 法条核验内核</span>'
        '<span class="cmp-mode" style="background:#dcfce7;color:#15803d">可复算 · 可溯源</span></div>'
    )
    if status == "ok":
        cites = [c for it in report.get("items", []) for c in it.get("cite_texts", [])]
        verified_cites = sum(1 for it in report.get("items", []) if it.get("cite_ok"))
        total_items = len(report.get("items", []))
        out.append(f'<div class="hero-total">合计可主张：¥{_money(report.get("total"))}</div>')
        out.append('<div class="cmp-reply" style="background:#f8fafc">')
        lines = []
        for it in report.get("items", []):
            lines.append(f'· {it["name"]}：¥{_money(it["amount"])}（{it["formula"]}）')
        out.append(esc("\n".join(lines)))
        out.append("</div>")
        out.append('<div class="flaw-list">')
        out.append(
            f'<div class="pro-item">✓ 法条原文回库核验：{verified_cites}/{total_items} 项全部匹配'
            f'（共挂载 {len(cites)} 条法规原文，下方可展开原文核对）</div>'
        )
        d = next((x for x in report.get("deadlines", []) if x.get("applicable")), None)
        if d:
            left = "已过期" if d["expired"] else f'还剩 {d["days_left"]} 天'
            out.append(f'<div class="pro-item">✓ 仲裁时效测算：{esc(d["label"])} 截止 {esc(d["deadline"])}（{esc(left)}）</div>')
        out.append('<div class="pro-item">✓ 三层闸门已校验 + 附举证责任清单、HR 抗辩预演与申请书导出</div>')
        out.append("</div>")
    elif status == "need_more":
        comp = completeness(report.get("fields") or {})
        out.append(f'<div class="hero-total" style="color:#b45309">已拒绝瞎猜（完整度 {int(comp["score"] * 100)}%）</div>')
        qs = "\n".join(f"· {q}" for q in report.get("questions") or [])
        out.append(f'<div class="cmp-reply">{esc(qs)}</div>')
        out.append(
            '<div class="flaw-list">'
            '<div class="pro-item">✓ 宁缺毋滥：缺少关键入离职/月薪要素时主动追问，绝不编造金额</div>'
            '<div class="pro-item">✓ 下方完整度地图已高亮缺失项，支持一键点选补录</div>'
            "</div>"
        )
    elif status == "out_of_scope":
        out.append('<div class="hero-total" style="color:#b45309">已识别：不归劳动仲裁直接管辖</div>')
        out.append(f'<div class="cmp-reply">{esc(report.get("redirect") or report["scope"].get("reason"))}</div>')
        out.append(
            '<div class="flaw-list">'
            '<div class="pro-item">✓ 红线守护：工伤/社保/公积金/胜诉率预测绝不硬算，只给正确受理路径</div>'
            "</div>"
        )
    else:
        out.append('<div class="hero-total" style="color:#b91c1c">资格闸门拦截（暂不可申请）</div>')
        bs = "\n".join(f"· {b}" for b in report.get("blockers") or [])
        out.append(f'<div class="cmp-reply">{esc(bs)}</div>')
        out.append(
            '<div class="flaw-list">'
            '<div class="pro-item">✓ 前置闸门拦截：先排障碍再谈金额，避免拿着假数字白跑一趟</div>'
            "</div>"
        )
    out.append("</div></div>")
    return "".join(out)


def input_console_html(story: str = "", show_compare: bool = True, report: dict | None = None) -> str:
    checked = "checked" if show_compare else ""
    btn_text = "再算与对比" if report is not None else "开始测算与对比"
    placeholder = (
        "例如：2020年3月1日入职一家电子厂，月薪9000，一直没签书面合同。"
        "2024年5月20日主管口头说不要我了，让我当天走人。我还有5天年假没休。"
    )
    out = [
        '<section class="card console-card">',
        '<div class="console-head"><span class="console-title">案情控制台（支持打字、语音口述，或点左侧演示案例）</span>'
        '<button type="button" class="clear-link" id="clearStoryBtn">清空重填</button></div>',
        '<form method="post" action="/analyze">',
        f'<textarea name="story" id="story" placeholder="{esc(placeholder)}">{esc(story)}</textarea>',
        '<div class="toolbar"><div class="tool-left">',
        '<button type="button" class="btn-tool" id="voiceBtn">🎙 语音输入</button>',
        '<button type="button" class="btn-tool" id="toggleGuideBtn">💡 智能要素引导（按需展开）▾</button>',
        '<button type="button" class="btn-tool" id="toggleApiBtn">⚙ 实时对比 API</button>',
        '</div><div class="tool-right">',
        f'<label class="switch"><input type="checkbox" id="compareCheck" name="compare" value="1" {checked}> 开启普通 AI 对比</label>',
        f'<button type="submit" class="btn-primary">{btn_text}</button>',
        "</div></div>",
        '<div class="voice-tip" id="voiceTip"></div>',
        '<div class="drawer" id="apiDrawer">',
        (
            f'<div class="dim"><b>已自动读取本地配置（{esc(llm.config()["model"])} @ {esc(llm.config()["base"])}）</b>'
            '，默认直接进行实时对比；如需临时改用其他模型，可在下方覆盖：</div>'
            if llm.config() else
            '<div class="dim"><b>可选：填入兼容 OpenAI 协议的 API 配置进行实时大模型 PK</b>（例如 DeepSeek：<code>https://api.deepseek.com/v1</code> + <code>deepseek-chat</code>；密钥仅用于当前会话，不落盘）</div>'
        ),
        '<div class="api-grid">',
        '<input type="password" name="api_key" id="apiKeyInput" placeholder="API Key（可选，如 sk-...）" autocomplete="off">',
        '<input type="text" name="base_url" id="apiBaseInput" placeholder="Base URL（如 https://api.deepseek.com/v1）">',
        '<input type="text" name="model" id="apiModelInput" placeholder="模型名（如 deepseek-chat）">',
        "</div></div>",
        '<div class="drawer" id="chipsDrawer">',
        '<p class="sub" style="margin:0 0 6px">不知道法律上怎么表达？点一个词插进输入框，下面会用<b>人话</b>解释含义与用途：</p>',
        chips_html(),
        '<div id="explain"></div>',
        "</div></form></section>",
    ]
    return "".join(out)


def render_page(
    report: dict | None = None,
    story: str = "",
    error: str = "",
    compare_data: dict | None = None,
    show_compare: bool = True,
    print_mode: bool = False,
) -> str:
    body: list[str] = []

    if not print_mode:
        body.append('<div class="app-shell">')
        body.append(sidebar_html(active_story=story, has_report=report is not None))
        body.append('<main class="workspace">')
        body.append(
            '<header class="topbar"><div>'
            '<div class="topbar-title">案件测算与 AI 对比工作台</div>'
            '<div class="topbar-sub">把大白话翻译成能立案的仲裁主张 · 金额按法条规则算清、不靠模型猜</div>'
            '</div><div class="status-pills">'
            '<span class="pill">京沪广深杭 5 城口径</span>'
            '<span class="pill green">10 部法规 519 条已加载</span>'
            + (
                f'<span class="pill green">实时对比已接入：{esc(llm.config()["model"])}</span>'
                if llm.config() else '<span class="pill slate">纯规则内核（离线对比）</span>'
            ) +
            "</div></header>"
        )
        if error:
            body.append(f'<div class="card ask">⚠️ {esc(error)}</div>')
        body.append(input_console_html(story=story, show_compare=show_compare, report=report))

    if report is None:
        body.append(
            '<div class="two-col">'
            '<div class="card"><h2>为什么需要专业规则控制台？</h2>'
            '<p class="sub" style="margin-bottom:6px">① <b>钱和时效绝不让大模型估算</b>：21.75 日薪折算、工龄分段、社平 3 倍封顶全由确定性代码计算；</p>'
            '<p class="sub" style="margin-bottom:6px">② <b>每条依据回库核验原文</b>：拒绝“《劳动合同法》第 X 条”的幻觉引用，直接给出可展开核对的法条原文；</p>'
            '<p class="sub" style="margin-bottom:0">③ <b>宁可追问、绝不乱答</b>：缺字段先问，超范围（工伤/社保）指路，问胜诉率当场拦截。</p>'
            '<p style="margin:12px 0 0;font-size:13.5px">👈 <b>快速演示</b>：直接点击左侧「演示案例库」中的任意案例，即可同屏查看「普通大模型 vs 本系统」对比效果。</p>'
            "</div>"
        )
        cities = covered_cities()
        city_rows = "、".join(
            f'{esc(c["city"])}（社平 {c["avg_wage_monthly"]:,.0f} 元/月，核验 {esc(c["verified_at"])}）'
            for c in cities
        )
        body.append(
            '<div class="card"><h2>城市口径与合规边界</h2>'
            f'<p class="sub" style="margin-bottom:8px">{city_rows or "暂无城市口径"}</p>'
            '<p class="sub" style="margin-bottom:6px">未收录城市时，受案范围、时效、解除合法性照样可判，但 3 倍封顶和最低工资<b>绝不跨城套用</b>，会明说「未覆盖」。</p>'
            '<p class="sub" style="margin-bottom:0">本工具只覆盖内地劳动争议仲裁，不构成正式法律意见。符合条件可拨 12348 申请法律援助。</p>'
            "</div></div>"
        )
    elif report["status"] == "out_of_scope":
        if show_compare and compare_data and not print_mode:
            body.append(compare_html(report, compare_data))
        body.append(f'<div class="card"><h1>这件事不归劳动仲裁管</h1><p class="sub">{esc(report["scope"]["reason"])}</p>')
        body.append('<h2>该去哪、带什么</h2>')
        body.append(f'<p>{esc(report.get("redirect") or "请补充更多细节")}</p>')
        for h in report.get("hints", []):
            body.append(f'<p>· {esc(h)}</p>')
        body.append("</div>")
        body.append(pending_html(report.get("pending") or [], story))
    elif report["status"] == "blocked":
        if show_compare and compare_data and not print_mode:
            body.append(compare_html(report, compare_data))
        body.append('<div class="card"><h1>现在还不能申请</h1>')
        body.append(
            '<p class="sub">这不是算不出来，而是这道门现在就进不去——'
            "所以我不给你一个看起来很像结论的金额。</p>"
        )
        for b in report.get("blockers") or []:
            body.append(f'<div class="gate fail"><b>硬性障碍：</b>{esc(b)}</div>')
        body.append("</div>")
        body.append(gates_html(report.get("gates")))
        if report.get("assumptions"):
            body.append('<div class="card"><h2>说明</h2>')
            for a in report["assumptions"]:
                body.append(f"<p>· {esc(a)}</p>")
            body.append("</div>")
    elif report["status"] == "need_more":
        if show_compare and compare_data and not print_mode:
            body.append(compare_html(report, compare_data))
        body.append('<div class="card ask"><h1>还差几个信息才能算</h1><h2>请补充以下核心要素</h2>')
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
    else:
        if not print_mode:
            body.append(
                '<div class="ws-tabs">'
                '<a class="ws-tab" href="#sec-compare">🆚 AI 对比</a>'
                '<a class="ws-tab" href="#sec-calc">💰 逐项金额与法条</a>'
                '<a class="ws-tab" href="#sec-deadline">⏱ 仲裁时效与完整度</a>'
                '<a class="ws-tab" href="#sec-evidence">📋 证据与抗辩预演</a>'
                '<a class="ws-tab" href="#sec-worth">🎯 路径与值得性</a>'
                '<a class="ws-tab" href="#sec-export">⬇ 下载与申请书</a>'
                "</div>"
            )
        if show_compare and compare_data and not print_mode:
            body.append(compare_html(report, compare_data))

        worth = report.get("worth") or {}
        body.append('<div class="card">')
        body.append(f'<h1>你能主张 <span class="total">{_money(report["total"])}</span> 元</h1>')
        if worth.get("decision_label"):
            body.append(
                f'<div class="verdict {esc(worth.get("decision"))}">'
                f'{esc(worth["decision_label"])}　<span class="dim">值得性 {esc(worth.get("score"))}/100</span></div>'
            )
        if report.get("scope", {}).get("hints"):
            body.append('<p class="sub">' + "；".join(esc(h) for h in report["scope"]["hints"][:2]) + "</p>")
        if story:
            body.append(f'<blockquote><b>案情原文：</b>{esc(story)}</blockquote>')
        body.append("</div>")

        body.append(pending_html(report.get("pending") or [], story))
        body.append(gates_html(report.get("gates")))

        body.append('<div class="card" id="sec-calc"><h2>一、逐项金额</h2><table><tr><th>项目</th><th class="num">金额（元）</th><th>算法</th></tr>')
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

        body.append(map_html(report.get("fields") or {}))

        if report.get("reference_cases"):
            body.append('<div class="card"><h2>类案参考</h2>'
                        '<p class="sub">按案由与案情线索选取。请结合本人证据与案件差异阅读。</p>')
            for case in report["reference_cases"]:
                body.append(f'<h3>{esc(case["title"])}</h3>')
                for label, key in (("争议焦点", "focus"), ("处理结果", "result"),
                                   ("可比点", "compare"), ("区别", "distinguish")):
                    body.append(f'<p style="margin:4px 0"><b>{label}</b>　{esc(case[key])}</p>')
                body.append(f'<p style="margin:4px 0 10px"><a href="{esc(case["url"])}" target="_blank" rel="noopener">{esc(case["source"])}</a></p>')
            body.append("</div>")

        body.append('<div class="card" id="sec-deadline"><h2>三、仲裁时效</h2><table><tr><th>请求</th><th>起算</th><th>截止</th><th class="num">剩余</th></tr>')
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

        q_story = urllib.parse.quote(story)
        body.append(
            f'<div class="card noprint" id="sec-export"><h2>报告导出与仲裁申请书</h2>'
            f'<div class="export-bar">'
            f'<a class="export-btn" href="/pdf?story={q_story}">⬇ 下载 PDF 报告</a>'
            f'<a class="export-btn" href="/print?story={q_story}" target="_blank">🖨 网页版打印</a>'
            f'<a class="export-btn" href="/report?story={q_story}">⬇ 下载 Markdown</a>'
            f'<a class="export-btn" href="/application?story={q_story}">📄 下载仲裁申请书草稿</a>'
            f"</div></div>"
        )
        body.append('<p class="foot">本单仅根据你提供的信息做初步测算，不构成法律意见，不能代替律师。正式申请前请核对工资流水、社保记录和劳动合同原件。</p>')

    if not print_mode:
        body.append("</main></div>")

    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>劳动仲裁维权助手 · 控制台</title><style>{CSS}</style></head><body>
{''.join(body)}
{'' if print_mode else CONSOLE_JS}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "arb/2.0"

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
        parsed = urllib.parse.urlparse(self.path)
        q = parsed.query
        if parsed.path == "/print":
            story, confirmed = self._q(q)
            self._send(200, print_page(story, confirmed=confirmed))
            return
        if parsed.path == "/application":
            story, confirmed = self._q(q)
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            txt = render_application(r) + chr(10) + chr(10) + render_notes(r)
            self._send(200, txt, "text/plain; charset=utf-8",
                       {"Content-Disposition": 'attachment; filename="arb-application.txt"'})
            return
        if parsed.path == "/report":
            story, confirmed = self._q(q)
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            md = render_markdown(r)
            name = f"arb-report-{date.today().isoformat()}.md"
            self._send(200, md, "text/markdown; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="{name}"'})
            return
        if parsed.path == "/pdf":
            story, confirmed = self._q(q)
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            data = render_pdf(r)
            name = f"arb-report-{date.today().isoformat()}.pdf"
            self._send(200, data, "application/pdf",
                       {"Content-Disposition": f'attachment; filename="{name}"'})
            return

        params = urllib.parse.parse_qs(q)
        case_id = params.get("case", [""])[0]
        preset = get_demo_case(case_id) if case_id else None
        if preset:
            story = preset["story"]
            r = analyze(story, mode="best_effort")
            cmp_data = compare_with_generic_ai(story, r)
            self._send(200, render_page(r, story, compare_data=cmp_data, show_compare=True))
            return
        self._send(200, render_page())

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        p = urllib.parse.parse_qs(raw)
        story = p.get("story", [""])[0].strip()
        confirmed = p.get("confirm", [])
        show_compare = p.get("compare", ["0"])[0] == "1"
        api_key = p.get("api_key", [""])[0]
        base_url = p.get("base_url", [""])[0]
        model = p.get("model", [""])[0]

        if not story:
            self._send(400, render_page(error="还没输入内容", show_compare=show_compare))
            return
        try:
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            cmp_data = (
                compare_with_generic_ai(story, r, api_key=api_key, base_url=base_url, model=model)
                if show_compare else None
            )
            self._send(200, render_page(r, story, compare_data=cmp_data, show_compare=show_compare))
        except Exception as e:  # 现场演示不能白屏
            self._send(500, render_page(error=f"出错了：{e}", story=story, show_compare=show_compare))

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
