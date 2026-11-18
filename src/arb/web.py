"""控制台版单页前端（纯标准库，零依赖）：python -m arb.web

特性：
- 英文优先双语控制台（默认打开英文界面，右上角一键切换 EN / 中文）
- 丰富和谐的多彩工作台配色 + 分板块 Tab 面板（01 总览对比 / 02 法条与完整度 / 03 时效与抗辩 / 04 路径与导出），告别冗长堆叠
- 左侧紧凑版「演示案例库」（8 个案例：5 个合规可算 + 3 个边界拦截）与模块导航联动
- 毫秒级先出规则结果 + /api/compare 异步加载 DeepSeek 实时对比，不再阻塞整页渲染
- 按需展开的智能要素引导 + 原生中英文语音输入（Web Speech API）
"""
from __future__ import annotations

import html
import json
import time
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import llm
from .application import render_application, render_notes
from .chips import BY_TERM, groups
from .cli import render_markdown
from .compare import (
    DEMO_CASES,
    _resolve_live_cfg,
    compare_with_generic_ai,
    get_demo_case,
    has_live_cache,
    match_demo_by_story,
)
from .evidence import rows as evidence_rows, summary as evidence_summary
from .i18n import (
    BURDEN_EN,
    CLARIFICATION_GUIDES,
    case_prompt,
    staged_prompts,
    t,
    tr_basis,
    tr_chip,
    tr_chip_group,
    tr_city,
    tr_deadline,
    tr_decision,
    tr_evidence_row,
    tr_evidence_summary,
    tr_field_hint,
    tr_field_label,
    tr_field_value,
    tr_fill_text,
    tr_formula,
    tr_gate,
    tr_item,
    tr_map_summary,
    tr_material_row,
    tr_question,
    tr_ref_case,
    tr_rehearsal_round,
    tr_scope_out,
    tr_statute_text,
    tr_venue_block,
    tr_worth_dim,
    tr_worth_level,
)
from .map import FIELD_LABELS, completeness, summary_line
from .pdf import render_pdf
from .pipeline import QUESTIONS, analyze, covered_cities

CSS = """
*{box-sizing:border-box}
:root{
  --bg:#f5f4f0;--card:#ffffff;--border:#e4e2dc;--text:#111827;--muted:#5b6472;
  --primary:#1d4ed8;--sapphire:#1e40af;--teal:#0f766e;--emerald:#059669;--amber:#b45309;--rose:#be123c;
}
body{margin:0;font:14.5px/1.6 -apple-system,"Inter","PingFang SC","Microsoft YaHei",sans-serif;
     color:var(--text);background:var(--bg);font-variant-numeric:tabular-nums}
a{color:var(--primary);text-decoration:none}
a:hover{text-decoration:underline}
h1{font-size:21px;margin:0 0 6px;line-height:1.35;letter-spacing:-.2px}
h2{font-size:15px;margin:0 0 12px;padding-left:10px;border-left:3px solid var(--primary);line-height:1.35;font-weight:700}
h3{font-size:14.5px;margin:12px 0 4px}
.sub{color:var(--muted);font-size:13px;margin:0 0 10px}
.case-findings{display:grid;grid-template-columns:minmax(0,1fr) minmax(230px,.52fr);gap:12px;align-items:start;scroll-margin-top:12px}
.case-findings>section{min-width:0;overflow-wrap:anywhere}
.scope-number{font-size:26px;line-height:1.25;color:var(--sapphire)}
.scope-number small{font-size:15px;color:var(--muted);font-weight:500}
.scope-meter{display:block;width:100%;height:12px;margin:5px 0 10px;accent-color:var(--primary)}
.case-findings p:last-child{margin-bottom:0}
.case-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:8px;margin:12px 0}
.case-facts div{padding:8px 10px;border:1px solid var(--border);border-radius:8px}
.case-facts dt{font-size:13px;color:var(--muted)}
.case-facts dd{margin:0;font-weight:650}
.case-conflict{padding:8px 10px;background:#fffbeb;color:#78350f;border-radius:8px}
.case-pay-wrap{overflow-x:auto;margin:8px 0}
.case-pay-table{width:100%;border-collapse:collapse;text-align:left;white-space:nowrap}
.case-pay-table th,.case-pay-table td{padding:5px 8px;border-bottom:1px solid var(--border)}
.case-supplement{margin-top:8px;padding:8px 10px;border:1px solid var(--border);border-radius:8px}
.case-supplement summary{cursor:pointer;color:var(--primary);font-weight:650}
.case-supplement form{margin:8px 0 0}
.case-entry{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:0 0 8px}
.case-entry label,.case-supplement label{display:block;font-size:13px}
.case-entry input,.case-supplement select,.case-supplement textarea{display:block;width:100%;padding:6px;border:1px solid var(--border);border-radius:6px;font:inherit;background:#fff}
.case-supplement button{margin-top:8px}
@media(max-width:720px){.case-findings{grid-template-columns:minmax(0,1fr)}#scopeAssessment{order:-1}}

/* Shell & Sidebar (Harmonized Soft Slate-Mist Frame) */
.app-shell{display:flex;min-height:100vh}
.sidebar{width:288px;flex-shrink:0;background:#eef2f7;
         color:#1e293b;padding:18px 14px 24px;display:flex;flex-direction:column;gap:16px;
         border-right:1px solid #d8e0eb}
.brand{padding:2px 4px 14px;border-bottom:1px solid #d8e0eb}
.brand-title{font-size:16px;font-weight:700;color:#0f172a;display:flex;align-items:center;gap:8px;letter-spacing:-.1px}
.brand-pill{display:inline-block;margin-top:6px;font-size:11.5px;padding:2px 8px;border-radius:6px;
            background:#d1fae5;color:#065f46;border:1px solid #a7f3d0;font-weight:600}
.side-label{font-size:11.5px;letter-spacing:.3px;color:#64748b;margin:2px 4px 6px;font-weight:600}

/* Sidebar Module Tabs */
.mod-nav{display:flex;flex-direction:column;gap:4px}
.mod-btn{width:100%;text-align:left;background:transparent;color:#334155;border:1px solid transparent;
         border-radius:8px;padding:8px 10px;font-size:13px;font-weight:500;cursor:pointer;transition:.12s;margin:0}
.mod-btn:hover{background:#e2e8f0;color:#0f172a}
.mod-btn.active{background:#1d4ed8;color:#fff;font-weight:600;box-shadow:0 2px 6px rgba(29,78,216,.22)}

/* Compact Demo Case Library with Status Dots */
.case-list{display:flex;flex-direction:column;gap:5px}
.case-btn{width:100%;text-align:left;background:#ffffff;color:#1e293b;
          border:1px solid #dbe2ec;border-radius:8px;padding:8px 10px;cursor:pointer;
          transition:.12s;margin:0;display:flex;align-items:center;justify-content:space-between;gap:8px}
.case-btn:hover{background:#f8fafc;border-color:#60a5fa}
.case-btn.active{background:#eff6ff;border-color:#2563eb;color:#1e40af;font-weight:600}
.case-left{display:flex;align-items:center;gap:7px;min-width:0}
.case-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.case-dot.ok{background:#10b981}
.case-dot.warn{background:#f59e0b}
.case-dot.fail{background:#f43f5e}
.case-name{font-size:12.5px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.case-tag{font-size:10.5px;color:#64748b;flex-shrink:0;font-weight:600}
.case-btn.active .case-tag{color:#1d4ed8}
.side-specs{margin-top:auto;padding-top:12px;border-top:1px solid #d8e0eb;font-size:12px;color:#64748b;line-height:1.7}
.side-reset{display:block;margin-top:8px;padding:7px 10px;border-radius:7px;background:#ffffff;border:1px solid #cbd5e1;
            color:#334155;font-size:12.5px;text-align:center;font-weight:600}
.side-reset:hover{background:#f8fafc;border-color:#94a3b8;text-decoration:none}

/* Workspace & Topbar (Full-Width Fluid Layout) */
.workspace{flex:1;min-width:0;width:100%;padding:20px 32px 56px}
.topbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;
        margin-bottom:16px;padding:14px 18px;background:#fff;border:1px solid var(--border);border-radius:10px}
.topbar-title{font-size:17.5px;font-weight:700;margin:0;color:var(--text);letter-spacing:-.2px}
.topbar-sub{font-size:12.5px;color:var(--muted);margin:2px 0 0}
.status-pills{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{font-size:11.5px;padding:3px 9px;border-radius:6px;background:#eff6ff;color:#1e40af;border:1px solid #dbeafe;font-weight:600}
.pill.green{background:#ecfdf5;color:#065f46;border-color:#a7f3d0}
.pill.violet{background:#f0fdfa;color:#0f766e;border-color:#99f6e4}
.pill.slate{background:#f3f4f6;color:#4b5563;border-color:#e5e7eb}

/* Language Switcher */
.lang-sw{display:inline-flex;border:1px solid #d1d5db;border-radius:7px;overflow:hidden;background:#f9fafb}
.lang-sw button{border:0;background:transparent;padding:4px 11px;font-size:12px;font-weight:600;color:#4b5563;cursor:pointer;margin:0}
.lang-sw button.on{background:#111827;color:#fff}

/* Console Input Card */
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 20px;margin:14px 0}
.console-card{margin-top:0}
.console-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
.console-title{font-weight:600;font-size:13.5px;color:var(--text)}
.clear-link{font-size:12.5px;color:var(--muted);cursor:pointer;background:none;border:0;padding:2px 6px;width:auto;margin:0}
.clear-link:hover{color:var(--rose)}
textarea{width:100%;min-height:86px;padding:11px 13px;border:1px solid #d1d5db;border-radius:8px;
         font-size:14.5px;line-height:1.55;background:#fafaf9;color:var(--text);resize:vertical;font-family:inherit}
textarea:focus{outline:none;background:#fff;border-color:var(--primary);box-shadow:0 0 0 3px rgba(29,78,216,.1)}
.toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-top:10px}
.tool-left,.tool-right{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.btn-tool{padding:6px 12px;border:1px solid #d1d5db;border-radius:7px;background:#fff;color:#1f2937;
          font-size:13px;font-weight:500;cursor:pointer;display:inline-flex;align-items:center;gap:6px;width:auto;margin:0}
.btn-tool:hover{background:#f3f4f6;border-color:#9ca3af}
.btn-tool.recording{background:#fef2f2;border-color:#dc2626;color:#b91c1c}
.btn-primary{padding:8px 18px;border:0;border-radius:7px;background:var(--primary);
             color:#fff;font-size:13.5px;font-weight:600;cursor:pointer;width:auto;margin:0}
.btn-primary:hover{background:var(--sapphire)}
.switch{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:#374151;cursor:pointer;user-select:none}
.switch input{width:15px;height:15px;accent-color:var(--primary);cursor:pointer}
.voice-tip{font-size:12px;color:var(--muted);margin-top:5px}
.voice-language{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--muted)}
.voice-language select{font:inherit;padding:5px 7px;border:1px solid #d1d5db;border-radius:6px;background:#fff;color:var(--text)}
.input-review{margin:10px 0;padding:12px;background:#fff;border:1px solid #bfdbfe;border-radius:8px}
.input-review p{margin:3px 0 8px}
.input-review p:empty{display:none}
.input-review label{display:block;font-size:13px;font-weight:600;margin:8px 0 4px}
.input-review .btn-tool{margin-top:7px}
.input-review .btn-tool:disabled{opacity:.55;cursor:default}

/* Drawers */
.drawer{margin-top:10px;padding:12px 14px;border-radius:8px;background:#fafaf9;border:1px solid var(--border);display:none}
.drawer.open{display:block}
.api-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px}
.api-grid input{width:100%;padding:7px 10px;border:1px solid #d1d5db;border-radius:7px;font-size:13px;background:#fff}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 0}
.chip{border:1px solid #d1d5db;background:#fff;color:#1f2937;border-radius:6px;padding:5px 10px;
      font-size:12.5px;width:auto;margin:0;cursor:pointer}
.chip:hover,.chip[aria-pressed="true"]{border-color:var(--primary);background:#eff6ff;color:var(--primary)}
.groupname{font-size:12px;font-weight:600;color:#4b5563;margin:10px 0 2px}
.guide-more{margin-top:10px}
.guide-more summary{font-size:13px;color:var(--primary);cursor:pointer}
.guide-shell{margin-top:10px;border:1px solid var(--border);border-radius:8px;background:#fafaf9}
.guide-summary{display:flex;align-items:center;justify-content:space-between;gap:8px;cursor:pointer;
               padding:10px 14px;font-weight:600;list-style:none}
.guide-summary::-webkit-details-marker{display:none}
.guide-summary span{font-size:12px;font-weight:500;color:var(--primary)}
.guide-summary .guide-close,.guide-shell[open] .guide-open{display:none}
.guide-shell[open] .guide-close{display:inline}
.guide-body{padding:0 14px 12px}
.guide-footer{margin-top:12px}
.voice-panel #voiceTip{margin:0 0 8px;font-size:13px;color:var(--text)}

/* KPI Strip — "One Bright Element" (Deep Jade Hero + Clean Crisp Peers) */
.kpi-grid{display:grid;grid-template-columns:1.25fr 1fr 1fr 1fr;gap:12px;margin:14px 0}
.kpi-card{border-radius:10px;padding:14px 16px;background:#fff;border:1px solid var(--border)}
.kpi-1{background:#064e3b;border-color:#065f46;color:#ecfdf5}
.kpi-1 .kpi-lbl{color:#a7f3d0}
.kpi-1 .kpi-val{color:#ffffff;font-size:23px}
.kpi-2{border-top:3px solid #1d4ed8}
.kpi-3{border-top:3px solid #d97706}
.kpi-4{border-top:3px solid #0f766e}
.kpi-lbl{font-size:12px;color:var(--muted);font-weight:600}
.kpi-val{font-size:20px;font-weight:700;margin-top:4px;color:var(--text);letter-spacing:-.3px}

/* Tab Bar & Panels */
.tab-bar{display:flex;flex-wrap:wrap;gap:4px;margin:14px 0 6px;padding:5px;background:#fff;
         border:1px solid var(--border);border-radius:9px}
.tab-btn{border:0;background:transparent;color:#4b5563;padding:7px 14px;border-radius:6px;font-size:13px;
         font-weight:600;cursor:pointer;margin:0}
.tab-btn:hover{background:#f3f4f6;color:var(--text)}
.tab-btn.active{background:#111827;color:#fff}
.tab-panel{display:none}
.tab-panel.active{display:block}

/* Side-by-Side Comparison */
.compare-wrap{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:12px 0 14px}
.cmp-card{border-radius:10px;padding:16px;background:#fff;border:1px solid var(--border);
          display:flex;flex-direction:column;gap:10px}
.cmp-ai{border-top:3px solid var(--rose)}
.cmp-ours{border-top:3px solid var(--emerald)}
.cmp-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:8px;border-bottom:1px solid #f1f5f9}
.cmp-title{font-weight:700;font-size:14px}
.cmp-ai .cmp-title{color:#9f1239}
.cmp-ours .cmp-title{color:#065f46}
.cmp-mode{font-size:11.5px;padding:2px 8px;border-radius:6px;background:#f3f4f6;color:#4b5563;font-weight:600}
.cmp-reply{font-size:13.5px;line-height:1.65;color:#1f2937;background:#fafaf9;border-radius:7px;
           padding:11px 13px;border:1px solid #e5e7eb;white-space:pre-wrap}
.cmp-spinner{display:inline-block;width:13px;height:13px;border:2px solid #d1d5db;border-top-color:var(--primary);
             border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
.flaw-list{display:flex;flex-direction:column;gap:5px}
.flaw-item{font-size:12.5px;padding:6px 10px;border-radius:6px;background:#fff1f2;color:#9f1239;border:1px solid #fecdd3}
.pro-item{font-size:12.5px;padding:6px 10px;border-radius:6px;background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0}
.hero-total{font-size:24px;font-weight:800;color:#065f46;letter-spacing:-.3px}

/* Report Cards & Tables */
.total{font-size:26px;font-weight:800;color:var(--rose)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:8px 6px;border-bottom:1px solid #eef2f7;text-align:left;vertical-align:top}
td.num,th.num{text-align:right;white-space:nowrap}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11.5px;background:#e0e7ff;color:#3730a3;margin-left:6px;font-weight:600}
.badge.ok{background:#d1fae5;color:#065f46}
.badge.warn{background:#fef3c7;color:#92400e}
.badge.unit{background:#fef3c7;color:#92400e}
.badge.both{background:#e0e7ff;color:#3730a3}
.badge.me{background:#d1fae5;color:#065f46}
.badge.fail{background:#ffe4e6;color:#9f1239}
blockquote{margin:6px 0 0;padding:8px 12px;background:#f8fafc;border-left:3px solid #94a3b8;font-size:13px;color:#475569}
details{margin:6px 0}
summary{cursor:pointer;color:var(--primary);font-size:13px;font-weight:500}
.ask{background:#fffbeb;border:1px solid #fde68a}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.cell{border:1px solid #e2e8f0;border-radius:9px;padding:8px 10px;font-size:13px;display:flex;flex-direction:column;gap:2px;background:#f8fafc}
.cell .k{color:#64748b;font-size:12px}
.cell .v{color:#0f172a;font-weight:500;word-break:break-word}
.cell .m{font-size:11.5px;color:#64748b}
.cell.ok{border-color:#a7f3d0;background:#ecfdf5}
.cell.ok .m{color:#047857;font-weight:600}
.cell.missing{border-color:#fecdd3;background:#fff1f2}
.cell.missing .m{color:#be123c;font-weight:600}
.pct{font-size:14.5px;color:var(--primary);font-weight:700}
.verdict{display:inline-block;padding:4px 12px;border-radius:8px;font-size:14px;font-weight:600;margin:2px 0 8px}
.verdict.recommend{background:#d1fae5;color:#065f46}
.verdict.better_alternative{background:#fef3c7;color:#92400e}
.verdict.not_recommended{background:#f1f5f9;color:#475569}
.gate{border:1px solid #e2e8f0;border-radius:9px;padding:9px 12px;margin:8px 0;background:#f8fafc}
.gate.pass{border-left:4px solid #10b981}
.gate.warn{border-left:4px solid #f59e0b;background:#fffbeb}
.gate.fail{border-left:4px solid #ef4444;background:#fef2f2}
.gate.info{border-left:4px solid #6366f1}
.gate .t{font-weight:600;font-size:13.5px}
.gate .m{font-size:13px;color:#475569;margin:2px 0}
.gate ul{margin:4px 0 0;padding-left:18px;font-size:12.5px;color:#475569}
.bar{height:7px;background:#e2e8f0;border-radius:999px;overflow:hidden;margin:3px 0 8px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#2563eb,#06b6d4)}
.dim{font-size:12.5px;color:#475569}
.ok-i{color:#059669;font-weight:700}
.no-i{color:#e11d48;font-weight:700}
.stage{font-size:12px;color:var(--violet);font-weight:700}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.export-bar{display:flex;flex-wrap:wrap;gap:10px}
.export-btn{display:inline-block;padding:8px 14px;border-radius:8px;background:linear-gradient(180deg,#fff,#f8fafc);
            border:1px solid #cbd5e1;color:#0f172a;font-size:13px;font-weight:600}
.export-btn:hover{background:#eff6ff;border-color:var(--primary);color:var(--primary);text-decoration:none}
.foot{color:#64748b;font-size:12px;margin-top:20px}

@media (max-width:1000px){
  .app-shell{flex-direction:column}
  .sidebar{width:100%;border-right:0}
  .kpi-grid{grid-template-columns:1fr 1fr}
  .compare-wrap,.two-col,.api-grid,.grid{grid-template-columns:1fr}
}
@media (max-width:600px){
  .console-card textarea,.voice-language select{font-size:16px}
  .console-card .btn-tool,.console-card .chip,.voice-language select,.guide-summary{min-height:44px}
}
@media print{
  .sidebar,.topbar,.accent-bar,.console-card,.tab-bar,.kpi-grid,.compare-wrap,.chips,.noprint,form,button{display:none!important}
  .tab-panel{display:block!important}
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


def _js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def console_js(lang: str, async_compare: dict | None = None) -> str:
    async_cfg = json.dumps(async_compare or {}, ensure_ascii=False)
    voice_labels = json.dumps({key: t(lang, f"voice_{key}") for key in (
        "btn", "stop", "connecting", "listening", "resuming", "idle", "finishing", "done", "relative_date", "unsupported",
        "no_speech", "not_allowed", "no_microphone", "network", "timeout", "secure", "bad_language",
        "failed", "keyboard_hint",
    )}, ensure_ascii=False)
    story_added = _js_str(t(lang, "story_added"))
    v_verified = _js_str(t(lang, "cmp_verified"))
    v_unverified = _js_str(t(lang, "cmp_unverified"))
    v_audit_lbl = _js_str(t(lang, "cmp_cite_audit"))

    return f"""
<script>
(function () {{
  var storyBox = document.getElementById('story');
  var form = storyBox ? storyBox.form : document.querySelector('form[action="/analyze"]');
  var langInput = document.getElementById('langInput');
  var storyFeedback = document.getElementById('storyFeedback');

  function appendStory(text) {{
    var original = storyBox.value;
    storyBox.value = original + (original && !original.endsWith('\\n') ? '\\n' : '') + text;
    storyBox.setSelectionRange(storyBox.value.length, storyBox.value.length);
    storyBox.scrollTop = storyBox.scrollHeight;
    storyFeedback.textContent = {story_added};
    storyBox.scrollIntoView({{block: 'nearest'}});
  }}

  storyBox.addEventListener('input', function () {{ storyFeedback.textContent = ''; }});
  var reviewSubmit = document.getElementById('reviewSubmit');
  var evidenceForm = document.getElementById('caseEvidenceForm');
  var payForm = document.getElementById('casePayForm');
  if (evidenceForm) evidenceForm.addEventListener('submit', function (e) {{
    e.preventDefault();
    var note = this.elements.note.value.trim().replace(/\\s+/g, ' ');
    if (!note) return;
    appendStory('【补证：' + this.elements.kind.value + '】' + note);
    form.requestSubmit(reviewSubmit);
  }});
  if (payForm) payForm.addEventListener('submit', function (e) {{
    e.preventDefault();
    var fields = this.elements;
    appendStory('【工资核对】' + fields.month.value + ' 应到账 ' +
      fields.due.valueAsNumber.toFixed(2) + ' 元，实际到账 ' + fields.received.valueAsNumber.toFixed(2) + ' 元。');
    form.requestSubmit(reviewSubmit);
  }});

  function activateTab(tabId) {{
    document.querySelectorAll('.tab-btn').forEach(function (b) {{
      b.classList.toggle('active', b.dataset.tab === tabId);
    }});
    document.querySelectorAll('.mod-btn').forEach(function (b) {{
      b.classList.toggle('active', b.dataset.tab === tabId);
    }});
    document.querySelectorAll('.tab-panel').forEach(function (p) {{
      p.classList.toggle('active', p.id === tabId);
    }});
  }}

  document.addEventListener('click', function (e) {{
    // 1. Tab switching (top bar + sidebar module nav)
    var tb = e.target.closest('[data-tab]');
    if (tb) {{
      activateTab(tb.dataset.tab);
      return;
    }}

    // 2. Demo case click -> fill story and submit
    var cbtn = e.target.closest('.case-btn');
    if (cbtn && storyBox && form) {{
      storyBox.value = cbtn.dataset.story || '';
      var cmp = document.getElementById('compareCheck');
      if (cmp) cmp.checked = true;
      form.submit();
      return;
    }}

    // 3. Language switch
    var lbtn = e.target.closest('.lang-sw button[data-lang]');
    if (lbtn) {{
      var newLang = lbtn.dataset.lang;
      if (langInput) langInput.value = newLang;
      if (storyBox && storyBox.value.trim() && form) {{
        // If current story matches a demo case, swap to the target language's demo text
        var cur = storyBox.value.trim();
        document.querySelectorAll('.case-btn').forEach(function (cb) {{
          if (cb.dataset.story === cur || cb.dataset.altStory === cur) {{
            if (cb.dataset.altStory && cb.dataset.lang !== newLang) {{
              storyBox.value = cb.dataset.altStory;
            }}
          }}
        }});
        form.submit();
      }} else {{
        window.location.href = '/?lang=' + encodeURIComponent(newLang);
      }}
      return;
    }}

  }});

  // Facts supplied here are added to the draft only when the user chooses Add.
  var guide = document.getElementById('chipsDrawer');
  var guidePrompt = document.getElementById('guidePrompt');
  var guideAnswer = document.getElementById('guideAnswer');
  var guideAdd = document.getElementById('guideAdd');
  var guideExample = document.getElementById('guideExample');
  var guideDrafts = new Map();
  var selectedChip = null;

  guide.addEventListener('click', function (e) {{
    var chip = e.target.closest('button[data-guide-question]');
    if (!chip) return;
    if (chip !== selectedChip) {{
      if (selectedChip) {{
        guideDrafts.set(selectedChip, guideAnswer.value);
        selectedChip.setAttribute('aria-pressed', 'false');
      }}
      selectedChip = chip;
      chip.setAttribute('aria-pressed', 'true');
      document.getElementById('guideTopic').textContent = chip.textContent;
      document.getElementById('guideQuestion').textContent = chip.dataset.guideQuestion;
      document.getElementById('guidePlain').textContent = chip.dataset.plain;
      guideExample.querySelector('span').textContent = chip.dataset.example;
      guideExample.hidden = !chip.dataset.example;
      guideAnswer.value = guideDrafts.get(chip) || '';
      guideAdd.disabled = !guideAnswer.value.trim();
    }}
    guidePrompt.hidden = false;
    guidePrompt.focus({{preventScroll: true}});
    guidePrompt.scrollIntoView({{block: 'nearest'}});
  }});
  guideAnswer.addEventListener('input', function () {{ guideAdd.disabled = !guideAnswer.value.trim(); }});
  guideAdd.addEventListener('click', function () {{
    var answer = guideAnswer.value.trim();
    if (!answer) return;
    guideAnswer.value = '';
    guideDrafts.delete(selectedChip);
    guideAdd.disabled = true;
    appendStory(answer);
    if (reviewSubmit) form.requestSubmit(reviewSubmit);
  }});

  var caseGuide = document.getElementById('caseGuide');
  var guideSummary = document.getElementById('toggleGuideBtn');
  document.getElementById('closeGuideBtn').addEventListener('click', function () {{
    caseGuide.open = false;
    guideSummary.focus();
  }});
  document.querySelectorAll('[data-open-case-guide]').forEach(function (link) {{
    link.addEventListener('click', function (e) {{
      e.preventDefault();
      caseGuide.open = true;
      if (selectedChip) {{
        guidePrompt.focus({{preventScroll: true}});
        guidePrompt.scrollIntoView({{block: 'nearest'}});
      }} else {{
        var firstQuestion = guide.querySelector('#guideSuggestions button');
        if (firstQuestion) firstQuestion.click();
      }}
    }});
  }});
  var apiBtn = document.getElementById('toggleApiBtn');
  apiBtn.addEventListener('click', function () {{
    var apiDrawer = document.getElementById('apiDrawer');
    apiBtn.setAttribute('aria-expanded', String(apiDrawer.classList.toggle('open')));
  }});

  var clearBtn = document.getElementById('clearStoryBtn');
  if (clearBtn && storyBox) {{
    clearBtn.addEventListener('click', function () {{
      storyBox.value = '';
      storyFeedback.textContent = '';
      storyBox.focus();
    }});
  }}

  // Web Speech API voice input
  var voiceBtn = document.getElementById('voiceBtn');
  var voicePanel = document.getElementById('voicePanel');
  var voiceTip = document.getElementById('voiceTip');
  var voiceLang = document.getElementById('voiceLanguage');
  var voiceReview = document.getElementById('voiceReview');
  var voiceText = document.getElementById('voiceText');
  var voiceAdd = document.getElementById('voiceAdd');
  var voiceDiscard = document.getElementById('voiceDiscard');
  var voiceKeyboard = document.getElementById('voiceKeyboard');
  var voiceClose = document.getElementById('voiceClose');
  var voiceLabels = {voice_labels};
  var SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  var activeVoice = null;
  if (/^zh(?:-|$)/i.test(navigator.language)) voiceLang.value = 'zh-CN';
  try {{
    var preferredVoice = sessionStorage.getItem('arb_voice_language');
    if (preferredVoice === 'zh-CN' || preferredVoice === 'en-US') voiceLang.value = preferredVoice;
  }} catch (err) {{ /* Dictation also works without browser storage. */ }}
  voiceLang.addEventListener('change', function () {{
    try {{ sessionStorage.setItem('arb_voice_language', voiceLang.value); }} catch (err) {{}}
  }});

  function updateVoicePreview() {{
    voiceReview.hidden = !voiceText.value.trim();
    voiceText.readOnly = !!activeVoice;
    voiceAdd.disabled = !!activeVoice || voiceReview.hidden;
    voiceDiscard.disabled = !!activeVoice;
    voiceKeyboard.disabled = !!activeVoice;
    voiceClose.disabled = !!activeVoice;
  }}

  function discardTranscript() {{
    voiceText.value = '';
    voiceTip.textContent = '';
    voicePanel.hidden = true;
    voiceBtn.setAttribute('aria-expanded', 'false');
    updateVoicePreview();
  }}

  function transcriptStatus() {{
    var relativeDate = /去年|前年|今年|明年|上个?月|上周|前几天|昨天|前天|今天|\\b(?:yesterday|today|last\\s+(?:week|month|year|january|february|march|april|may|june|july|august|september|october|november|december))\\b/i;
    return voiceLabels.done + (relativeDate.test(voiceText.value) ? ' ' + voiceLabels.relative_date : '');
  }}

  voiceText.addEventListener('input', function () {{
    voiceAdd.disabled = !voiceText.value.trim();
    voiceTip.textContent = voiceAdd.disabled ? '' : transcriptStatus();
  }});
  voiceAdd.addEventListener('click', function () {{
    var text = voiceText.value.trim();
    if (!text || activeVoice) return;
    appendStory(text);
    discardTranscript();
  }});
  voiceDiscard.addEventListener('click', discardTranscript);
  voiceKeyboard.addEventListener('click', function () {{
    voiceTip.textContent = voiceLabels.keyboard_hint;
    storyBox.focus();
  }});
  voiceClose.addEventListener('click', function () {{
    voicePanel.hidden = true;
    voiceBtn.setAttribute('aria-expanded', 'false');
    voiceBtn.focus();
  }});

  voiceBtn.addEventListener('click', function () {{
    voicePanel.hidden = false;
    voiceBtn.setAttribute('aria-expanded', 'true');
    voicePanel.scrollIntoView({{block: 'nearest'}});
    if (!window.isSecureContext) {{ voiceTip.textContent = voiceLabels.secure; return; }}
    if (!SpeechRec) {{ voiceTip.textContent = voiceLabels.unsupported; return; }}
    if (activeVoice) {{ activeVoice.stop(); return; }}

    var previous = voiceText.value.trim();
    var language = voiceLang.value;
    var separator = language === 'zh-CN' ? '' : ' ';
    var completed = '';
    var heard = '';
    var current = null;
    var connectionTimer, idleTimer, restartTimer;
    var quickDisconnects = 0;
    var stopping = false;
    var session = {{stop: stop}};

    function paragraph() {{
      return [completed, heard].filter(Boolean).join(separator);
    }}

    function transcript() {{
      return [previous, paragraph()].filter(Boolean).join('\\n');
    }}

    function finish(message) {{
      if (activeVoice !== session) return;
      clearTimeout(connectionTimer);
      clearTimeout(idleTimer);
      clearTimeout(restartTimer);
      activeVoice = null;
      current = null;
      voiceText.value = transcript();
      voiceLang.disabled = false;
      voiceBtn.classList.remove('recording');
      voiceBtn.querySelector('span').textContent = voiceLabels.btn;
      voiceTip.textContent = message || (voiceText.value.trim() ? transcriptStatus() : voiceLabels.no_speech);
      updateVoicePreview();
    }}

    function abortWithMessage(message) {{
      var recognizer = current;
      finish(message);
      if (recognizer) {{
        try {{ recognizer.abort(); }} catch (err) {{ /* The browser may have ended the recognizer already. */ }}
      }}
    }}

    function waitForBrowser(ms, message) {{
      clearTimeout(connectionTimer);
      connectionTimer = setTimeout(function () {{ abortWithMessage(message); }}, ms);
    }}

    function noteActivity() {{
      clearTimeout(idleTimer);
      idleTimer = setTimeout(function () {{
        abortWithMessage(paragraph() ? voiceLabels.idle : voiceLabels.no_speech);
      }}, 45000);
    }}

    function stop() {{
      if (stopping) return;
      stopping = true;
      clearTimeout(restartTimer);
      clearTimeout(idleTimer);
      if (!current) {{ finish(); return; }}
      voiceTip.textContent = voiceLabels.finishing;
      waitForBrowser(5000, voiceLabels.timeout);
      try {{ current.stop(); }} catch (err) {{ abortWithMessage(voiceLabels.failed); }}
    }}

    function listen() {{
      if (activeVoice !== session || stopping) return;
      var recognizer;
      try {{ recognizer = new SpeechRec(); }} catch (err) {{
        finish(voiceLabels.failed);
        return;
      }}
      current = recognizer;
      recognizer.lang = language;
      recognizer.continuous = true;
      recognizer.interimResults = true;
      var startedAt = Date.now();

      recognizer.onstart = function () {{
        if (current !== recognizer || stopping) return;
        clearTimeout(connectionTimer);
        voiceTip.textContent = voiceLabels.listening;
      }};
      recognizer.onspeechstart = function () {{
        if (current === recognizer && !stopping) noteActivity();
      }};
      recognizer.onresult = function (ev) {{
        if (current !== recognizer) return;
        var preview = Array.from(ev.results, function (result) {{ return result[0].transcript.trim(); }})
          .filter(Boolean).join(separator);
        if (preview && preview !== heard) {{
          heard = preview;
          if (!stopping) noteActivity();
        }}
        voiceText.value = transcript();
        updateVoicePreview();
      }};
      recognizer.onerror = function (ev) {{
        if (current !== recognizer) return;
        if (ev.error === 'no-speech' && !stopping) {{
          // A normal end event follows a silence error and can reconnect within this session.
          waitForBrowser(5000, voiceLabels.no_speech);
          return;
        }}
        if (stopping && (ev.error === 'aborted' || ev.error === 'no-speech')) {{
          finish();
          return;
        }}
        var messages = {{
          'not-allowed': 'not_allowed', 'service-not-allowed': 'not_allowed',
          'audio-capture': 'no_microphone', 'language-not-supported': 'bad_language', 'network': 'network'
        }};
        finish(voiceLabels[messages[ev.error]] || voiceLabels.failed);
      }};
      recognizer.onend = function () {{
        if (current !== recognizer) return;
        if (stopping || document.hidden) {{ finish(); return; }}
        clearTimeout(connectionTimer);
        current = null;
        quickDisconnects = !heard && Date.now() - startedAt < 750 ? quickDisconnects + 1 : 0;
        completed = paragraph();
        heard = '';
        if (quickDisconnects >= 3) {{ finish(voiceLabels.failed); return; }}
        voiceTip.textContent = voiceLabels.resuming;
        restartTimer = setTimeout(listen, 300);
      }};

      waitForBrowser(12000, voiceLabels.timeout);
      try {{ recognizer.start(); }} catch (err) {{ finish(voiceLabels.failed); }}
    }}

    activeVoice = session;
    voiceLang.disabled = true;
    voiceBtn.classList.add('recording');
    voiceBtn.querySelector('span').textContent = voiceLabels.stop;
    voiceTip.textContent = voiceLabels.connecting;
    updateVoicePreview();
    noteActivity();
    listen();
  }});

  // Persist optional API overrides in sessionStorage
  ['apiKeyInput', 'apiBaseInput', 'apiModelInput'].forEach(function (id) {{
    var el = document.getElementById(id);
    if (!el || !window.sessionStorage) return;
    var saved = sessionStorage.getItem('arb_' + id);
    if (saved && !el.value) el.value = saved;
    el.addEventListener('input', function () {{ sessionStorage.setItem('arb_' + id, el.value); }});
  }});

  // Async background LLM comparison (so rule engine renders instantaneously)
  var asyncCfg = {async_cfg};
  if (asyncCfg && asyncCfg.pending) {{
    var params = new URLSearchParams();
    params.set('story', asyncCfg.story || '');
    params.set('lang', asyncCfg.lang || 'en');
    var kEl = document.getElementById('apiKeyInput');
    var bEl = document.getElementById('apiBaseInput');
    var mEl = document.getElementById('apiModelInput');
    if (kEl && kEl.value) params.set('api_key', kEl.value);
    if (bEl && bEl.value) params.set('base_url', bEl.value);
    if (mEl && mEl.value) params.set('model', mEl.value);

    fetch('/api/compare', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: params.toString()
    }}).then(function (r) {{ return r.json(); }}).then(function (d) {{
      var badge = document.getElementById('aiModeBadge');
      var replyBox = document.getElementById('aiReplyBox');
      var auditBox = document.getElementById('aiAuditBox');
      var flawBox = document.getElementById('aiFlawBox');
      if (badge) badge.textContent = d.mode_label || '';
      if (replyBox) replyBox.textContent = d.reply || '';
      if (auditBox) {{
        auditBox.innerHTML = '';
        var items = (d.cite_audit && d.cite_audit.items) || [];
        if (items.length) {{
          var lbl = document.createElement('span');
          lbl.textContent = {v_audit_lbl} + ' ';
          auditBox.appendChild(lbl);
          items.forEach(function (c) {{
            var sp = document.createElement('span');
            sp.className = 'badge ' + (c.verified ? 'ok' : 'fail');
            sp.textContent = c.cite + ' · ' + (c.verified ? {v_verified} : {v_unverified});
            auditBox.appendChild(sp);
          }});
        }}
      }}
      if (flawBox) {{
        flawBox.innerHTML = '';
        if (d.error) {{
          var errDiv = document.createElement('div');
          errDiv.className = 'flaw-item';
          errDiv.textContent = d.error;
          flawBox.appendChild(errDiv);
        }}
        (d.flaws || []).forEach(function (f) {{
          var div = document.createElement('div');
          div.className = 'flaw-item';
          div.textContent = '⚠ ' + f;
          flawBox.appendChild(div);
        }});
      }}
    }}).catch(function () {{}});
  }}
}})();
</script>
"""


QUICK_TOPICS = ("违法解除劳动合同", "拖欠工资", "未签书面劳动合同二倍工资")


def guide_chip(label: str, question: str, example: str, plain: str = "", css: str = "chip") -> str:
    return (
        f'<button type="button" class="{css}" aria-controls="guidePrompt" aria-pressed="false" '
        f'data-guide-question="{esc(question)}" data-plain="{esc(plain)}" data-example="{esc(example)}">'
        f'{esc(label)}</button>'
    )


def topic_chip(raw_c: dict, lang: str) -> str:
    c = tr_chip(lang, raw_c)
    question, example = case_prompt(lang, raw_c["term"])
    return guide_chip(c["term"], question, example, c["plain"])


def chips_html(lang: str = "zh", exclude: tuple[str, ...] = ()) -> str:
    out = []
    for g, items in groups().items():
        out.append(f'<p class="groupname">{esc(tr_chip_group(lang, g))}</p><div class="chips">')
        for raw_c in items:
            if raw_c["term"] not in exclude:
                out.append(topic_chip(raw_c, lang))
        out.append("</div>")
    return "".join(out)


def followup_chips(report: dict | None, lang: str) -> list[str]:
    if not report or report["status"] not in ("ok", "need_more"):
        return []
    if report.get("staged_review"):
        prompts = staged_prompts(report["staged_review"], lang)
        return [guide_chip(title, question, example, css="chip fill") for title, question, example in prompts]
    if report.get("clarification"):
        _, _, _, _, prompts = CLARIFICATION_GUIDES[report["clarification"]][lang]
        return [guide_chip(title, question, example, css="chip fill") for title, question, example in prompts]
    missing = report.get("missing", [])
    sources = report.get("sources", {})
    suggestions = []
    for key, label, hint in FIELD_LABELS:
        if key not in QUESTIONS or (key not in missing and sources.get(key) != "assumed"):
            continue
        name = tr_field_label(lang, label)
        prefix = "补：" if lang == "zh" else "+ "
        example = tr_fill_text(lang, label, hint).removeprefix("例如：")
        suggestions.append(guide_chip(prefix + name, tr_question(lang, QUESTIONS[key]), example, css="chip fill"))
    return suggestions[:2]


def map_html(fields: dict, lang: str = "zh") -> str:
    """9 格完整度地图：已填的绿、必填缺失的红、可选的灰。"""
    c = completeness(fields)
    out = [f'<div class="card" id="sec-map"><h2>{esc(t(lang, "map_title"))} <span class="pct">{int(c["score"] * 100)}%</span></h2>']
    out.append('<p class="sub">' + esc(tr_map_summary(lang, summary_line(fields))) + "</p>")
    out.append('<div class="grid">')
    for r in c["rows"]:
        cls = "cell " + r["status"]
        if lang == "en":
            mark = "✓" if r["status"] == "ok" else ("Optional" if r["status"] == "optional" else "Missing")
        else:
            mark = "✓" if r["status"] == "ok" else ("可选" if r["status"] == "optional" else "缺")
        val = esc(tr_field_value(lang, str(r["value"]))) if r["value"] else esc(tr_field_hint(lang, r["label"], r["hint"]))
        out.append(
            f'<div class="{cls}"><span class="k">{esc(tr_field_label(lang, r["label"]))}</span>'
            f'<span class="v">{val}</span><span class="m">{mark}</span></div>'
        )
    out.append("</div></div>")
    return "".join(out)


def evidence_html(rehearsal: dict | None, lang: str = "zh") -> str:
    if not rehearsal or not rehearsal.get("evidence_checklist"):
        return ""
    rows_ = evidence_rows(rehearsal["evidence_checklist"])
    emp_n = sum(1 for r in rows_ if r["who"] == "单位")
    sum_txt = evidence_summary(rows_) if lang == "zh" else tr_evidence_summary(lang, len(rows_), emp_n)
    out = [f'<div class="card" id="sec-evidence"><h2>{esc(t(lang, "evidence_title"))}</h2>']
    out.append('<p class="sub">' + esc(sum_txt) + "</p>")
    out.append(
        f'<table><tr><th>{esc(t(lang, "col_ev"))}</th>'
        f'<th>{esc(t(lang, "col_who"))}</th><th>{esc(t(lang, "col_why"))}</th></tr>'
    )
    for r in rows_:
        name, who_lbl, why_txt = tr_evidence_row(lang, r)
        cls = {"单位": "unit", "双方": "both", "你": "me"}[r["who"]]
        out.append(
            f'<tr><td>{esc(name)}</td><td><span class="badge {cls}">{esc(who_lbl)}</span></td>'
            f'<td class="sub" style="margin:0">{esc(why_txt)}</td></tr>'
        )
    out.append("</table></div>")
    return "".join(out)


def print_page(story: str, today=None, confirmed=()) -> str:
    """打印/导 PDF 用的纯净版页面。"""
    r = analyze(story, today=today, mode="best_effort", confirmed=confirmed)
    page = render_page(r, story, show_compare=False, print_mode=True, lang="zh")
    tip = '<p class="noprint" style="color:#8a919c;font-size:13px">按 Ctrl+P（Mac 是 ⌘P）可存成 PDF。</p>'
    return page.replace("</body>", tip + "</body>")


def gates_html(gates: dict | None, lang: str = "zh") -> str:
    if not gates:
        return ""
    layers = gates.get("layers") or []
    if not layers:
        return ""
    out = [f'<div class="card" id="sec-gates"><h2>{esc(t(lang, "gates_title"))}</h2>']
    out.append(f'<p class="sub">{esc(t(lang, "gates_sub"))}</p>')
    for idx, g in enumerate(layers):
        cls = g.get("status") or "info"
        title, msg, details = tr_gate(lang, idx, g)
        out.append(f'<div class="gate {cls}"><div class="t">{esc(title)}</div>')
        out.append(f'<div class="m">{esc(msg)}</div>')
        if details:
            out.append("<ul>" + "".join(f"<li>{esc(d)}</li>" for d in details) + "</ul>")
        if g.get("cites"):
            cites_txt = "、".join(g["cites"]) if lang == "zh" else ", ".join(g["cites"])
            out.append(f'<div class="dim" style="margin-top:4px">{esc(cites_txt)}</div>')
        out.append("</div>")
    for b in gates.get("blockers") or []:
        out.append(f'<p class="gate fail"><b>{esc(t(lang, "blocker_label"))}</b> {esc(b)}</p>')
    out.append("</div>")
    return "".join(out)


def pending_html(pending: list[dict], story: str, lang: str = "zh") -> str:
    if not pending:
        return ""
    out = [f'<div class="card ask"><h2>{esc(t(lang, "pending_title"))}</h2>']
    out.append('<form method="post" action="/analyze">')
    out.append(f'<input type="hidden" name="story" value="{esc(story)}">')
    out.append(f'<input type="hidden" name="lang" value="{esc(lang)}">')
    for p in pending:
        if p.get("reason") == "conflict":
            tag = "说法不一致" if lang == "zh" else "Conflict Detected"
            out.append(
                f'<p style="margin:8px 0 2px"><b>{esc(p.get("label"))}</b>'
                f'<span class="badge warn">{tag}</span><br>'
                f'<span class="sub">{esc(p.get("from_story"))} vs {esc(p.get("suggested"))}</span></p>'
                f'<label class="sub"><input type="checkbox" name="confirm" value="{esc(p.get("key"))}"> '
                f'{esc(t(lang, "pending_btn"))}</label>'
            )
        else:
            out.append(
                f'<p style="margin:8px 0 2px"><b>{esc(p.get("label"))}</b> '
                f'<span class="badge">{esc(p.get("suggested"))}</span></p>'
                f'<label class="sub"><input type="checkbox" name="confirm" value="{esc(p.get("key"))}"> '
                f'{esc(t(lang, "pending_btn"))}</label>'
            )
    out.append(f'<button type="submit" class="btn-primary" style="margin-top:8px">{esc(t(lang, "pending_btn"))}</button></form></div>')
    return "".join(out)


def materials_html(mats: list[dict], ev: dict | None, lang: str = "zh") -> str:
    if not mats:
        return ""
    out = [f'<div class="card" id="sec-materials"><h2>{esc(t(lang, "materials_title"))}</h2>']
    ev = ev or {}
    if ev:
        pct = int(ev.get("score") or 0)
        lvl = tr_worth_level(lang, ev.get("level") or "")
        out.append(f'<p class="sub">{esc(t(lang, "ev_strength"))} <b>{pct}/100</b> ({esc(lvl)})</p>')
        out.append(f'<div class="bar"><i style="width:{pct}%"></i></div>')
    out.append(
        f'<table><tr><th>{esc(t(lang, "col_mat"))}</th>'
        f'<th>{esc(t(lang, "col_status"))}</th><th>{esc(t(lang, "col_how"))}</th></tr>'
    )
    for m in mats:
        flag = (
            f'<span class="ok-i">{esc(t(lang, "have"))}</span>'
            if m["have"] else f'<span class="no-i">{esc(t(lang, "missing"))}</span>'
        )
        m_name, m_purpose, m_how = tr_material_row(lang, m)
        out.append(
            f'<tr><td>{esc(m_name)}</td>'
            f'<td>{flag}</td>'
            f'<td class="sub" style="margin:0">{esc(m_purpose)}<br>'
            f'<span style="color:#64748b">{esc(m_how)}</span></td></tr>'
        )
    out.append("</table></div>")
    return "".join(out)


def venue_html(blocks: list[dict], lang: str = "zh") -> str:
    if not blocks:
        return ""
    out = [f'<div class="card" id="sec-venue"><h2>{esc(t(lang, "venue_title"))}</h2>']
    for b in blocks:
        st, vname, vwhere, vnote = tr_venue_block(lang, b)
        out.append(f'<div class="gate info"><span class="stage">{esc(st)}</span>')
        out.append(f'<div class="t">{esc(vname)}</div>')
        if vwhere:
            out.append(f'<div class="m">{esc(vwhere)}</div>')
        if b.get("hours") and lang == "zh":
            out.append(f'<div class="dim">{esc(b["hours"])}</div>')
        if vnote:
            out.append(f'<div class="dim" style="margin-top:4px">{esc(vnote)}</div>')
        acts = b.get("actions") or []
        if acts and lang == "zh":
            links = []
            for a in acts:
                kind, label, value = a.get("kind"), a.get("label"), a.get("value") or ""
                if kind == "tel":
                    links.append(f'<a href="tel:{esc(value)}">{esc(label)}</a>')
                elif kind == "url":
                    links.append(f'<a href="{esc(value)}" target="_blank" rel="noopener">{esc(label)}</a>')
                else:
                    links.append(f'<span class="dim">{esc(label)}: {esc(value)}</span>')
            out.append('<div style="margin-top:6px;font-size:13px">' + "　".join(links) + "</div>")
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def worth_html(worth: dict | None, one_final: str | None = None, lang: str = "zh") -> str:
    if not worth:
        return ""
    decision = worth.get("decision") or "not_recommended"
    label = tr_decision(lang, decision, worth.get("decision_label") or "")
    out = [f'<div class="card" id="sec-worth"><h2>{esc(t(lang, "worth_title"))}</h2>']
    out.append(f'<div class="verdict {esc(decision)}">{esc(label)} · {esc(worth.get("score"))}/100</div>')
    out.append(f'<p class="sub">{esc(t(lang, "worth_sub"))}</p>')
    out.append(
        f'<table><tr><th>{esc(t(lang, "col_dim"))}</th>'
        f'<th class="num">{esc(t(lang, "col_score"))}</th><th>{esc(t(lang, "col_note"))}</th></tr>'
    )
    for d in worth.get("dimensions") or []:
        dlbl, dnote = tr_worth_dim(lang, d)
        out.append(
            f'<tr><td>{esc(dlbl)} <span class="dim">({int(round(d["weight"] * 100))}%)</span></td>'
            f'<td class="num">{esc(d["score"])}</td>'
            f'<td class="sub" style="margin:0">{esc(dnote)}</td></tr>'
        )
    out.append("</table>")
    alt = worth.get("alternative")
    if alt and lang == "zh":
        out.append(
            f'<p class="gate warn" style="margin-top:10px"><b>{esc(alt.get("title"))}</b><br>'
            f'{esc(alt.get("why"))} · {esc(alt.get("tel"))}</p>'
        )
    if one_final and lang == "zh":
        out.append(f'<p class="sub">{esc(one_final)}</p>')
    out.append("</div>")
    return "".join(out)


def sidebar_html(active_story: str = "", has_report: bool = False, lang: str = "en") -> str:
    matched = match_demo_by_story(active_story)
    active_id = matched["id"] if matched else ""
    out = [
        '<aside class="sidebar">',
        '<div class="brand">',
        f'<div class="brand-title">{esc(t(lang, "brand_title"))}</div>',
        f'<span class="brand-pill">{esc(t(lang, "brand_pill"))}</span>',
        "</div>",
    ]
    if has_report:
        out.append(
            f'<div><div class="side-label">{esc(t(lang, "nav_modules"))}</div><div class="mod-nav">'
            f'<button type="button" class="mod-btn active" data-tab="tab-overview">{esc(t(lang, "mod_overview"))}</button>'
            f'<button type="button" class="mod-btn" data-tab="tab-statutes">{esc(t(lang, "mod_statutes"))}</button>'
            f'<button type="button" class="mod-btn" data-tab="tab-defense">{esc(t(lang, "mod_defense"))}</button>'
            f'<button type="button" class="mod-btn" data-tab="tab-filing">{esc(t(lang, "mod_filing"))}</button>'
            "</div></div>"
        )
    out.append(f'<div><div class="side-label">{esc(t(lang, "nav_cases"))}</div><div class="case-list">')
    for c in DEMO_CASES:
        cls = "case-btn active" if c["id"] == active_id else "case-btn"
        c_title = c["title"] if lang == "zh" else c.get("title_en", c["title"])
        c_tag = c["tag"] if lang == "zh" else c.get("tag_en", c["tag"])
        c_sum = c["summary"] if lang == "zh" else c.get("summary_en", c["summary"])
        c_story = c["story"] if lang == "zh" else c.get("story_en", c["story"])
        alt_story = c.get("story_en", c["story"]) if lang == "zh" else c["story"]
        out.append(
            f'<button type="button" class="{cls}" title="{esc(c_sum)}" '
            f'data-lang="{esc(lang)}" data-story="{esc(c_story)}" data-alt-story="{esc(alt_story)}">'
            f'<span class="case-left"><span class="case-dot {esc(c["badge_cls"])}"></span>'
            f'<span class="case-name">{esc(c_title)}</span></span>'
            f'<span class="case-tag">{esc(c_tag)}</span></button>'
        )
    out.append("</div></div>")
    out.append(
        f'<div class="side-specs"><div class="side-label" style="margin-left:0">{esc(t(lang, "nav_specs"))}</div>'
        f'<div>{esc(t(lang, "spec_laws"))}</div>'
        f'<div>{esc(t(lang, "spec_cities"))}</div>'
        f'<div>{esc(t(lang, "spec_offline"))}</div>'
        f'<a class="side-reset" href="/?lang={esc(lang)}">{esc(t(lang, "reset_btn"))}</a></div>'
    )
    out.append("</aside>")
    return "".join(out)


def compare_html(
    report: dict,
    compare_data: dict | None,
    lang: str = "en",
    rule_ms: int = 4,
    async_pending: bool = False,
    model_name: str = "deepseek-chat",
) -> str:
    """渲染「普通 AI vs 本系统规则内核」双栏对比区（支持异步骨架屏秒出）。"""
    status = report.get("status")
    compare_data = compare_data or {}
    cite_audit = compare_data.get("cite_audit") or {}
    out = ['<div class="compare-wrap" id="sec-compare">']

    # 左栏：普通通用大模型
    out.append('<div class="cmp-card cmp-ai">')
    mode_lbl = (
        f"Querying {model_name}..." if (async_pending and lang != "zh")
        else (f"正在实时请求 {model_name}…" if async_pending else compare_data.get("mode_label", ""))
    )
    out.append(
        f'<div class="cmp-head"><span class="cmp-title">{esc(t(lang, "cmp_ai_title"))}</span>'
        f'<span class="cmp-mode" id="aiModeBadge">{esc(mode_lbl)}</span></div>'
    )
    if async_pending:
        loading_txt = t(lang, "cmp_loading", model=model_name, ms=rule_ms)
        out.append(f'<div class="cmp-reply" id="aiReplyBox"><span class="cmp-spinner"></span>{esc(loading_txt)}</div>')
        out.append('<div class="dim" id="aiAuditBox"></div>')
        out.append('<div class="flaw-list" id="aiFlawBox"></div>')
    else:
        if compare_data.get("error"):
            out.append(f'<div class="flaw-item">{esc(compare_data["error"])}</div>')
        out.append(f'<div class="cmp-reply" id="aiReplyBox">{esc(compare_data.get("reply") or "")}</div>')
        out.append('<div class="dim" id="aiAuditBox">')
        if cite_audit.get("items"):
            badges = []
            for c in cite_audit["items"]:
                b_cls = "ok" if c["verified"] else "fail"
                mark = t(lang, "cmp_verified") if c["verified"] else t(lang, "cmp_unverified")
                badges.append(f'<span class="badge {b_cls}">{esc(c["cite"])} · {esc(mark)}</span>')
            out.append(f'{esc(t(lang, "cmp_cite_audit"))} ' + "".join(badges))
        out.append("</div><div class=\"flaw-list\" id=\"aiFlawBox\">")
        for f in compare_data.get("flaws") or []:
            out.append(f'<div class="flaw-item">⚠ {esc(f)}</div>')
        out.append("</div>")
    out.append("</div>")

    # 右栏：本系统规则内核
    out.append('<div class="cmp-card cmp-ours">')
    out.append(
        f'<div class="cmp-head"><span class="cmp-title">{esc(t(lang, "cmp_ours_title"))}</span>'
        f'<span class="cmp-mode" style="background:#d1fae5;color:#065f46">{esc(t(lang, "cmp_ours_badge"))} · {rule_ms} ms</span></div>'
    )
    if status == "ok":
        cites = [c for it in report.get("items", []) for c in it.get("cite_texts", [])]
        verified_cites = sum(1 for it in report.get("items", []) if it.get("cite_ok"))
        total_items = len(report.get("items", []))
        out.append(f'<div class="hero-total">¥{_money(report.get("total"))}</div>')
        lines = [
            f'· {tr_item(lang, it["name"])}: ¥{_money(it["amount"])} ({tr_formula(lang, it["formula"])})'
            for it in report.get("items", [])
        ]
        out.append(f'<div class="cmp-reply">{esc(chr(10).join(lines))}</div>')
        out.append('<div class="flaw-list">')
        if lang == "zh":
            out.append(f'<div class="pro-item">✓ 法条原文核验：{verified_cites}/{total_items} 项全匹配（挂载 {len(cites)} 条法规原文）</div>')
        else:
            out.append(f'<div class="pro-item">✓ Statute DB Verification: {verified_cites}/{total_items} items matched ({len(cites)} PRC articles linked)</div>')
        d = next((x for x in report.get("deadlines", []) if x.get("applicable")), None)
        if d:
            left = t(lang, "expired") if d["expired"] else t(lang, "days_left", n=d["days_left"])
            out.append(f'<div class="pro-item">✓ {esc(t(lang, "kpi_deadline"))}: {esc(d["deadline"])} ({esc(left)})</div>')
        out.append("</div>")
    elif report.get("staged_review"):
        title = "实习与转正欠薪初步分析" if lang == "zh" else "Initial wage assessment"
        summary = SCOPE_TEXT[report["scope_assessment"]["kind"]][int(lang != "zh")]
        view = "查看初步分析" if lang == "zh" else "View assessment"
        out.append(f'<div class="hero-total" style="color:#92400e">{title}</div>')
        out.append(f'<div class="cmp-reply">{esc(summary)}</div>')
        out.append(f'<p><a class="export-btn" href="#caseProgress">{view}</a></p>')
    elif status == "need_more":
        if report.get("clarification"):
            title, reason, _, _, prompts = CLARIFICATION_GUIDES[report["clarification"]][lang]
            qs = [reason] + [question for _, question, _ in prompts[:2]]
        else:
            title = t(lang, "need_more_title")
            qs = [tr_question(lang, q) for q in (report.get("questions") or [])]
        out.append(f'<div class="hero-total" style="color:#92400e">{esc(title)}</div>')
        out.append(f'<div class="cmp-reply">{esc(chr(10).join("· " + q for q in qs))}</div>')
        out.append(
            f'<p><a class="export-btn" href="#caseGuide" data-open-case-guide>{esc(t(lang, "guide_continue"))}</a></p>'
        )
    elif status == "out_of_scope":
        title = "查看处理方向" if lang == "zh" else "See your options"
        kind = report["scope_assessment"]["kind"]
        if report.get("redirect") or report["scope"]["cause"] == "red_line":
            _, summary, _ = tr_scope_out(lang, report)
        else:
            summary = SCOPE_TEXT[kind][int(lang != "zh")]
        out.append(f'<div class="cmp-reply">{esc(summary)}</div>')
        out.append(f'<p><a class="export-btn" href="#caseProgress">{title}</a></p>')
    else:
        out.append(f'<div class="hero-total" style="color:#e11d48">{esc(t(lang, "blocked_title"))}</div>')
        out.append(f'<div class="cmp-reply">{esc(chr(10).join("· " + b for b in report.get("blockers") or []))}</div>')
        out.append(f'<div class="flaw-list"><div class="pro-item">✓ {esc(t(lang, "blocked_sub"))}</div></div>')
    out.append("</div></div>")
    return "".join(out)


def input_console_html(story: str = "", show_compare: bool = True, report: dict | None = None, lang: str = "en") -> str:
    checked = "checked" if show_compare else ""
    btn_text = t(lang, "recalc_btn") if report is not None else t(lang, "submit_btn")
    zh_selected = " selected" if lang == "zh" else ""
    en_selected = " selected" if lang != "zh" else ""
    suggested = followup_chips(report, lang)
    guide_open = " open" if suggested else ""
    guide_intro = "guide_followup" if suggested else "guide_intro"
    guide_copy = t(lang, guide_intro)
    staged = bool(report and report.get("staged_review"))
    if staged and suggested:
        guide_copy = (
            "已有信息已用于初步分析。选一个问题补充，提交后会更新结果。"
            if lang == "zh" else "Your initial assessment is ready. Answer a question to update it."
        )
    excluded = () if suggested else QUICK_TOPICS
    quick_chips = suggested or [topic_chip(BY_TERM[term], lang) for term in QUICK_TOPICS]
    cfg = llm.config()
    api_note = (
        t(lang, "api_connected_note", model=cfg["model"], base=cfg["base"])
        if cfg else t(lang, "api_note")
    )
    out = [
        '<section class="card console-card">',
        f'<div class="console-head"><span class="console-title">{esc(t(lang, "console_head"))}</span>'
        f'<button type="button" class="clear-link" id="clearStoryBtn">{esc(t(lang, "clear_btn"))}</button></div>',
        '<form method="post" action="/analyze">',
        f'<input type="hidden" name="lang" id="langInput" value="{esc(lang)}">',
        f'<textarea name="story" id="story" aria-describedby="storyFeedback" '
        f'placeholder="{esc(t(lang, "placeholder"))}">{esc(story)}</textarea>',
        '<div class="voice-tip" id="storyFeedback" role="status"></div>',
        '<div class="toolbar"><div class="tool-left">',
        '<button type="button" class="btn-tool" id="voiceBtn" aria-controls="voicePanel" aria-expanded="false">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
        '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>'
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>'
        f'<span>{esc(t(lang, "voice_btn"))}</span></button>',
        f'<label class="voice-language">{esc(t(lang, "voice_language"))}'
        '<select id="voiceLanguage">'
        f'<option lang="zh-CN" value="zh-CN"{zh_selected}>普通话</option>'
        f'<option lang="en" value="en-US"{en_selected}>English</option>'
        '</select></label>',
        f'<button type="button" class="btn-tool" id="toggleApiBtn" '
        f'aria-controls="apiDrawer" aria-expanded="false">{esc(t(lang, "api_btn"))}</button>',
        '</div><div class="tool-right">',
        f'<label class="switch"><input type="checkbox" id="compareCheck" name="compare" value="1" {checked}> {esc(t(lang, "compare_toggle"))}</label>',
        f'<button type="submit" class="btn-primary">{esc(btn_text)}</button>',
        ('<button type="submit" id="reviewSubmit" name="review_update" value="1" '
         'formaction="/analyze#caseProgress" hidden></button>') if staged else "",
        "</div></div>",
        '<section class="input-review voice-panel" id="voicePanel" hidden>',
        '<p class="voice-tip" id="voiceTip" role="status"></p>',
        '<div id="voiceReview" hidden>',
        f'<label for="voiceText">{esc(t(lang, "voice_review"))}</label>',
        '<textarea id="voiceText" rows="3" aria-describedby="voiceTip"></textarea>',
        f'<button type="button" class="btn-tool" id="voiceAdd" disabled>{esc(t(lang, "story_add"))}</button> ',
        f'<button type="button" class="btn-tool" id="voiceDiscard">{esc(t(lang, "voice_discard"))}</button>',
        '</div>',
        f'<button type="button" class="btn-tool" id="voiceKeyboard">{esc(t(lang, "voice_keyboard"))}</button> ',
        f'<button type="button" class="btn-tool" id="voiceClose">{esc(t(lang, "voice_close"))}</button>',
        '</section>',
        '<div class="drawer" id="apiDrawer">',
        f'<div class="dim"><b>{esc(api_note)}</b></div>',
        '<div class="api-grid">',
        '<input type="password" name="api_key" id="apiKeyInput" placeholder="API Key (sk-...)" autocomplete="off">',
        '<input type="text" name="base_url" id="apiBaseInput" placeholder="Base URL (https://api.deepseek.com/v1)">',
        '<input type="text" name="model" id="apiModelInput" placeholder="Model (deepseek-chat)">',
        "</div></div>",
        f'<details class="guide-shell" id="caseGuide"{guide_open}>',
        f'<summary class="guide-summary" id="toggleGuideBtn">{esc(t(lang, "guide_btn"))}'
        f'<span class="guide-open" aria-hidden="true">{esc(t(lang, "guide_open"))} ▾</span>'
        f'<span class="guide-close" aria-hidden="true">{esc(t(lang, "guide_close"))} ▴</span></summary>',
        '<div class="guide-body" id="chipsDrawer">',
        f'<p class="sub" style="margin:0 0 6px">{esc(guide_copy)}</p>',
        f'<div class="chips" id="guideSuggestions">{"".join(quick_chips)}</div>',
        '<section class="input-review" id="guidePrompt" tabindex="-1" aria-labelledby="guideTopic" '
        'aria-describedby="guideQuestion" hidden>',
        '<strong id="guideTopic"></strong>',
        '<p id="guideQuestion"></p>',
        '<p class="sub" id="guidePlain"></p>',
        f'<p class="sub" id="guideExample" hidden>{esc(t(lang, "guide_example"))} · <span></span></p>',
        f'<label for="guideAnswer">{esc(t(lang, "guide_answer"))}</label>',
        '<textarea id="guideAnswer" rows="3" aria-describedby="guideQuestion guideExample"></textarea>',
        f'<button type="button" class="btn-tool" id="guideAdd" disabled>{esc(t(lang, "story_add"))}</button>',
        '</section>',
        '<details class="guide-more" id="moreGuideTopics">',
        f'<summary>{esc(t(lang, "guide_more"))}</summary>',
        chips_html(lang=lang, exclude=excluded),
        '</details>',
        f'<div class="guide-footer"><button type="button" class="btn-tool" id="closeGuideBtn">'
        f'{esc(t(lang, "guide_close"))}</button></div>',
        "</div></details></form></section>",
    ]
    return "".join(out)


SCOPE_TEXT = {
    "staged": ("已出现转正和欠薪线索。转正后的岗位和管理方式会影响劳动关系判断。",
               "The account describes conversion to a regular role and possible unpaid wages. Duties and supervision matter."),
    "staged_supported": ("已登记转正时间和用工或考勤材料，劳动关系判断有了可核对的线索。",
                         "A conversion date and records of employment or attendance give you facts to check."),
    "labor": ("描述中有可进一步核对的劳动争议事项。具体受理仍取决于事实、请求和管辖。",
              "The description identifies a potential labor dispute. Filing depends on the facts, requested remedy and jurisdiction."),
    "mixed": ("有可单独核对的劳动争议，也有适合走行政渠道的事项，可分开处理。",
              "The account identifies a possible labor claim and a separate issue for an administrative agency."),
    "administrative": ("这件事与用工有关，当前请求优先向相应主管部门核实。",
                       "The issue is work-related. Check the request with the relevant agency first."),
    "unclear": ("看到了用工线索。可先整理谁安排工作、约定了什么、发生了什么，以及希望对方怎么处理。",
                "There are signs of a work arrangement. Note who assigned the work, what was agreed, what happened and what remedy you want."),
    "unidentified": ("当前描述尚未出现可识别的劳动争议事项。如果已经发生纠纷，可保留原始记录，并拨 12348 咨询处理途径。",
                     "The account does not identify a labor dispute. If a dispute has arisen, keep the original records and ask 12348 which route applies."),
    "rental": ("描述更接近租赁纠纷。保留租约、付款和交接记录，书面列明退款或履约请求；可通过 12348 咨询调解或民事处理。",
               "This looks like a rental dispute. Keep the lease, payment and handover records, state your request in writing and ask 12348 about civil options."),
    "loan": ("描述更接近借款纠纷。保存借条、转账和还款约定，书面核对余额和到期时间；可通过 12348 咨询催讨或调解渠道。",
             "This looks like a loan dispute. Keep the loan and transfer records, confirm the balance and due date in writing and ask 12348 about civil options."),
    "consumer": ("描述更接近消费纠纷。保存订单、商品页面及沟通记录，先向商家或平台提出退款或履约请求；有争议可向 12315 咨询。",
                 "This looks like a consumer dispute. Keep the order, listing and messages, contact the seller or platform and ask 12315 if it remains unresolved."),
    "family": ("描述更接近婚姻家庭或继承纠纷。整理关系、财产和相关书面记录，可向 12348 咨询适用的调解或民事途径。",
               "This looks like a family or inheritance dispute. Gather the relevant relationship and property records and ask 12348 about mediation or civil options."),
}

CLAIM_STEPS = {
    "unpaid_wage": ("欠薪或少发工资。按月保留工资约定、工资条和流水，可向劳动监察或劳动仲裁机构核实。",
                    "Unpaid or underpaid wages. Keep pay agreements, payslips and bank records by month. Ask labor inspection or the arbitration office."),
    "illegal_dismissal": ("辞退争议。保存解除通知、聊天记录和最后工作日期，核对解除理由及通知时间。",
                          "Dismissal. Keep the notice and messages, record your last work day and confirm when and why you were dismissed."),
    "double_wage": ("书面劳动合同争议。保存入职记录和合同签署或补签时间。",
                    "Written employment contract. Keep records of when work started and when a contract was signed."),
    "overtime": ("加班争议。保留排班、打卡及公司安排加班的原始记录，按日期整理。",
                 "Overtime. Keep schedules, time records and employer instructions, organized by date."),
    "annual_leave": ("年休假争议。核对有权享受的假期、申请记录和已休天数。",
                     "Annual leave. Check leave entitlement, requests and the days actually taken."),
    "injury_benefits": ("已提到工伤认定材料。可凭认定决定、费用票据和待遇核定单，向人社部门或当地劳动仲裁机构核实由谁支付，以及待遇争议的处理渠道。",
                        "You mention a recognized work injury. Bring the decision, bills and benefits statement to the labor authority or arbitration office to check who pays and how to resolve a benefits dispute."),
    "severance": ("经济补偿争议。核对劳动关系何时、因何结束，保留合同及工资记录。",
                  "Severance. Record when and why employment ended, and keep the contract and pay records."),
    "pregnant_protection": ("孕产期用工争议。保存相关证明与单位调整岗位、待遇或解除的记录。",
                            "Maternity-related employment dispute. Keep supporting records and any notice of a change to duties, pay or employment."),
    "mutual_agreement": ("协商协议争议。保留协议版本、沟通记录及实际履行情况。",
                         "Settlement dispute. Keep the agreement versions, messages and proof of performance."),
}


def scope_panel(report: dict, lang: str) -> str:
    assessment = report["scope_assessment"]
    idx = int(lang != "zh")
    title = ("劳动仲裁相关度", "Labor arbitration relevance")[idx]
    note = ("按当前描述和已登记材料给出的参考分。是否受理由办理机构判断。",
            "Rule-based estimate from this account and its listed records. The relevant office decides whether to accept a filing.")[idx]
    score = assessment["score"]
    explanation = SCOPE_TEXT[assessment["kind"]][idx]
    if assessment["kind"] in ("unclear", "unidentified", "rental", "loan", "consumer", "family"):
        explanation = (
            ("已有用工线索，争议事项待明确。", "The account suggests employment. The dispute still needs to be identified.")[idx]
            if assessment["kind"] == "unclear" else
            ("现有描述里的劳动争议信号较少。", "The account contains few signs of a labor dispute.")[idx]
        )
    return (
        f'<section class="card" id="scopeAssessment" aria-labelledby="scopeTitle"><h2 id="scopeTitle">{title}</h2>'
        f'<strong class="scope-number">{score}<small> / 100</small></strong>'
        f'<meter class="scope-meter" min="0" max="100" value="{score}" aria-labelledby="scopeTitle"></meter>'
        f'<p>{esc(explanation)}</p><p class="sub">{note}</p></section>'
    )


def first_steps_panel(report: dict, lang: str) -> str:
    idx = int(lang != "zh")
    assessment = report["scope_assessment"]
    kind = assessment["kind"]
    status = report["status"]
    title = ("你现在可以做什么", "What you can do now")[idx]
    out = [f'<section class="card"><h1>{title}</h1>']
    if report.get("redirect") or report.get("scope", {}).get("cause") == "red_line":
        _, redirect, _ = tr_scope_out(lang, report)
        out.append(f'<p>{esc(redirect)}</p>')
    for cause in assessment["causes"]:
        if cause in CLAIM_STEPS:
            out.append(f'<p>{esc(CLAIM_STEPS[cause][idx])}</p>')
    if kind == "labor" and not assessment["causes"]:
        out.append(
            '<p>保留劳动合同、工资和考勤记录，写清争议发生的时间和希望解决的问题，可向当地劳动仲裁机构咨询。</p>'
            if not idx else
            '<p>Keep employment, pay and attendance records. Write down what happened, when and what you want the local arbitration office to resolve.</p>'
        )
    if kind in ("unclear", "unidentified", "rental", "loan", "consumer", "family"):
        out.append(f'<p>{esc(SCOPE_TEXT[kind][idx])}</p>')
    if status == "ok":
        out.append(f'<p><a href="#caseCalculation">{("查看金额测算", "View the calculation")[idx]}</a></p>')
    out.append("</section>")
    return "".join(out)


def staged_panel(review: dict, lang: str, print_mode: bool) -> str:
    def label(zh: str, en: str) -> str:
        return zh if lang == "zh" else en

    def fact_money(value) -> str | None:
        return f"¥{_money(value)}" if value is not None else None

    evidence = review["evidence"]
    month_names = "、".join(review["paid_months"])
    paid_count = review["paid_count"]
    facts = [
        (label("开始实习", "Internship began"), review["internship"]),
        (label("转正时间", "Regular role began"), review["conversion"]),
        (label("口述约定月薪", "Stated monthly pay"), fact_money(review["agreed"])),
        (label("口述扣款后到账", "Stated net pay"), fact_money(review["net"])),
        (label("口述已发工资", "Reported paid months"), month_names or (
            label(f"{paid_count} 个月", f"{paid_count} months") if paid_count else None
        )),
    ]
    out = [
        f'<section class="card" aria-labelledby="stagedHeading"><h1 id="stagedHeading">{label("实习与转正欠薪初步分析", "Initial wage assessment")}</h1>'
        f'<p>{label("你描述了转正及部分工资未付。若转正后实际按公司安排从事有报酬的工作，可向当地劳动仲裁机构核实劳动关系及欠薪。实习阶段如属学校安排，先看实习协议里的报酬约定，可拨 12348 咨询。", "You describe a move to a regular role and unpaid wages. If you performed paid work under the company’s supervision, ask the local arbitration office about employment status and wages. For a school-arranged internship, start with its agreement and ask 12348.")}</p>',
    ]
    if any(value for _, value in facts):
        out.append('<dl class="case-facts">')
        out.extend(f'<div><dt>{name}</dt><dd>{esc(value)}</dd></div>' for name, value in facts if value)
        out.append("</dl>")
    if review["agreed"] is not None and review["net"] is not None:
        out.append(f'<p>{label("把约定工资、工资条扣款和银行到账分开核对。约定月薪与扣款后到账金额的差额，需要先核对计薪口径。", "Check the agreed pay, payroll deductions and deposits separately before interpreting the difference.")}</p>')
    if review["reversed_dates"]:
        first, last = review["first"], review["last"]
        conflict = label(f"你描述的 {first} 到 {last} 顺序有冲突。请核对结束年份，确认前可先核对具体月份。",
                         f"The end of {first} to {last} comes before the start. Check the end year. You can still review individual months.")
        out.append(f'<p class="case-conflict" id="caseDateConflict">{esc(conflict)}</p>')
    elif review["first"] and review["last"]:
        out.append(f'<p id="casePayPeriod">{label("已登记的工资核对期间", "Recorded pay period")} <strong>{esc(review["first"])} – {esc(review["last"])}</strong></p>')
    if review["payment_conflict"]:
        out.append(f'<p class="case-conflict">{label("已发工资的月份与月数或核对期间有出入，请核对。", "The paid months conflict with the stated count or pay period. Please check them.")}</p>')
    if review["unreviewed"]:
        remaining = "、".join(review["unreviewed"])
        out.append(f'<p id="caseUnreviewed">{label("可优先核对这些月份的到账记录", "Check payments for these months first")} <strong>{esc(remaining)}</strong></p>')

    if review["monthly"]:
        out.append(
            f'<h2>{label("已核对月份的到账差额", "Payment shortfall for entered months")} '
            f'<strong id="caseDifference">¥{_money(review["difference"])}</strong></h2>'
            '<div class="case-pay-wrap"><table class="case-pay-table"><thead><tr>'
            f'<th scope="col">{label("月份", "Month")}</th><th scope="col">{label("应到账", "Net due")}</th>'
            f'<th scope="col">{label("实际到账", "Received")}</th><th scope="col">{label("差额", "Shortfall")}</th>'
            '</tr></thead><tbody>'
        )
        for month, row in review["monthly"].items():
            out.append(f'<tr><th scope="row">{esc(month)}</th><td>¥{_money(row["due"])}</td><td>¥{_money(row["received"])}</td><td>¥{_money(row["difference"])}</td></tr>')
        out.append(f'</tbody></table></div><p class="sub">{label("仅合计你填写的月份，实际主张金额仍需核对工资和用工材料。同月再次提交会更新该月。", "This total covers entered months. Check pay and employment records before claiming an amount. Re-enter a month to update it.")}</p>')

    evidence_labels = {
        "用工": label("劳动合同或转正通知", "Employment contract or conversion notice"),
        "工资约定": label("工资条或薪资约定", "Payslip or pay agreement"),
        "付款": label("银行流水或转账记录", "Bank or transfer record"),
        "考勤": label("排班或考勤记录", "Schedule or attendance"),
    }
    if evidence:
        changes = {
            "用工": label("可用来核对转正日期和用工约定。", "Use these to check conversion dates and employment terms."),
            "工资约定": label("可用来核对计薪标准、应发工资和扣款。", "Use these to check agreed pay, gross amounts and deductions."),
            "付款": label("可用来核对每月实际到账和欠付差额。", "Use these to check monthly deposits and any shortfall."),
            "考勤": label("可用来核对哪些月份实际工作及单位如何管理。", "Use these to check when and under whose supervision you worked."),
        }
        out.append(f'<h2 id="caseEvidence">{label("已登记的证据线索", "Evidence noted")}</h2>')
        for kind, notes in evidence.items():
            out.append(f'<h3>{evidence_labels[kind]}</h3><ul>')
            out.extend(f'<li>{esc(note)}</li>' for note in notes)
            out.append(f'</ul><p class="sub">{changes[kind]}</p>')
    if not print_mode:
        out.append(f'<details class="case-supplement"><summary>{label("补充证据", "Add evidence")}</summary>'
                   f'<form id="caseEvidenceForm"><label>{label("证据类型", "Record type")}<select name="kind">')
        out.extend(f'<option value="{kind}">{name}</option>' for kind, name in evidence_labels.items())
        out.append(
            f'</select></label><label>{label("材料能说明什么（可写日期或金额）", "What does the record show? Include a date or amount if known.")}'
            '<textarea name="note" rows="2" maxlength="400" required></textarea></label>'
            f'<button class="btn-primary" type="submit">{label("登记证据并更新分析", "Save evidence and update")}</button></form></details>'
            f'<details class="case-supplement"><summary>{label("核对某月工资", "Check a month of pay")}</summary>'
            '<form id="casePayForm"><div class="case-entry">'
            f'<label>{label("工资月份", "Pay month")}<input name="month" type="month" min="2000-01" max="2099-12" required></label>'
            f'<label>{label("应到账（元）", "Net due (RMB)")}<input name="due" type="number" min="0" max="99999999.99" step="0.01" required></label>'
            f'<label>{label("实际到账（元）", "Received (RMB)")}<input name="received" type="number" min="0" max="99999999.99" step="0.01" required></label>'
            f'</div><p class="sub">{label("按扣款后的同一口径填写，确实没收到时填 0。", "Use amounts after deductions for both fields. Enter 0 if you received nothing.")}</p>'
            f'<button class="btn-primary" type="submit">{label("更新该月差额", "Update this month")}</button></form></details>'
        )
        if review["gaps"]:
            out.append(f'<p><a id="continueGuide" class="export-btn" href="#caseGuide" data-open-case-guide>{esc(t(lang, "guide_continue"))}</a></p>')
    out.append("</section>")
    return "".join(out)


def render_page(
    report: dict | None = None,
    story: str = "",
    error: str = "",
    compare_data: dict | None = None,
    show_compare: bool = True,
    print_mode: bool = False,
    lang: str = "zh",
    rule_ms: int = 4,
    async_compare: dict | None = None,
    review_only: bool = False,
) -> str:
    body: list[str] = []
    cfg = llm.config()
    display_compare = show_compare and not print_mode and not review_only

    if not print_mode:
        body.append('<div class="app-shell">')
        body.append(sidebar_html(active_story=story, has_report=report is not None, lang=lang))
        body.append('<main class="workspace">')
        en_cls = "on" if lang != "zh" else ""
        zh_cls = "on" if lang == "zh" else ""
        live_pill = (
            f'<span class="pill violet">{esc(t(lang, "pill_live"))} {esc(cfg["model"])}</span>'
            if cfg else f'<span class="pill slate">{esc(t(lang, "pill_offline"))}</span>'
        )
        body.append(
            '<header class="topbar"><div>'
            f'<div class="topbar-title">{esc(t(lang, "topbar_title"))}</div>'
            f'<div class="topbar-sub">{esc(t(lang, "topbar_sub"))}</div>'
            '</div><div class="status-pills">'
            f'<span class="pill">{esc(t(lang, "pill_cities"))}</span>'
            f'<span class="pill green">{esc(t(lang, "pill_laws"))}</span>'
            f'{live_pill}'
            f'<div class="lang-sw"><button type="button" class="{en_cls}" data-lang="en">EN</button>'
            f'<button type="button" class="{zh_cls}" data-lang="zh">中文</button></div>'
            "</div></header>"
        )
        if error:
            body.append(f'<div class="card ask">⚠️ {esc(error)}</div>')
        body.append(input_console_html(story=story, show_compare=show_compare, report=report, lang=lang))

    if report is not None:
        initial = (
            staged_panel(report["staged_review"], lang, print_mode)
            if report.get("staged_review") else first_steps_panel(report, lang)
        )
        body.append(f'<div class="case-findings" id="caseProgress">{initial}{scope_panel(report, lang)}</div>')

    if report is None:
        body.append(
            '<div class="two-col">'
            f'<div class="card"><h2>{esc(t(lang, "welcome_why_title"))}</h2>'
            f'<p class="sub">① {esc(t(lang, "welcome_why_1"))}</p>'
            f'<p class="sub">② {esc(t(lang, "welcome_why_2"))}</p>'
            f'<p class="sub">③ {esc(t(lang, "welcome_why_3"))}</p>'
            f'<p style="margin:10px 0 0;font-size:13px;color:var(--primary);font-weight:600">{esc(t(lang, "welcome_tip"))}</p>'
            "</div>"
        )
        cities = covered_cities()
        city_rows = " · ".join(
            f'{esc(tr_city(lang, c["city"]))} (¥{c["avg_wage_monthly"]:,.0f}/mo, {esc(c["verified_at"])})'
            for c in cities
        )
        body.append(
            f'<div class="card"><h2>{esc(t(lang, "welcome_city_title"))}</h2>'
            f'<p class="sub">{city_rows or "—"}</p>'
            f'<p class="sub">{esc(t(lang, "welcome_city_note"))}</p>'
            f'<p class="sub" style="margin-bottom:0">{esc(t(lang, "welcome_foot"))}</p>'
            "</div></div>"
        )
    elif report["status"] == "out_of_scope":
        if display_compare:
            body.append(compare_html(
                report, compare_data, lang=lang, rule_ms=rule_ms,
                async_pending=bool((async_compare or {}).get("pending")),
                model_name=(cfg or {}).get("model", "deepseek-chat"),
            ))
        body.append(pending_html(report.get("pending") or [], story, lang=lang))
    elif report["status"] == "blocked":
        if display_compare:
            body.append(compare_html(
                report, compare_data, lang=lang, rule_ms=rule_ms,
                async_pending=bool((async_compare or {}).get("pending")),
                model_name=(cfg or {}).get("model", "deepseek-chat"),
            ))
        body.append(
            f'<div class="card"><h1>{esc(t(lang, "blocked_title"))}</h1>'
            f'<p class="sub">{esc(t(lang, "blocked_sub"))}</p>'
        )
        for b in report.get("blockers") or []:
            body.append(f'<div class="gate fail"><b>{esc(t(lang, "blocker_label"))}</b> {esc(b)}</div>')
        body.append("</div>")
        body.append(gates_html(report.get("gates"), lang=lang))
    elif report["status"] == "need_more":
        if display_compare:
            body.append(compare_html(
                report, compare_data, lang=lang, rule_ms=rule_ms,
                async_pending=bool((async_compare or {}).get("pending")),
                model_name=(cfg or {}).get("model", "deepseek-chat"),
            ))
        clarification = report.get("clarification")
        if not report.get("staged_review") and clarification:
            title, reason, records, next_steps, prompts = CLARIFICATION_GUIDES[clarification][lang]
            questions = [question for _, question, _ in prompts]
            body.append(f'<div class="card ask"><h1>{esc(title)}</h1><p>{esc(reason)}</p>')
            if records:
                body.append(f'<p>{esc(records)}</p>')
            if next_steps:
                body.append(f'<p>{esc(next_steps)}</p>')
        elif not report.get("staged_review"):
            questions = [tr_question(lang, q) for q in report["questions"]]
            body.append(
                f'<div class="card ask"><h1>{esc(t(lang, "need_more_title"))}</h1>'
                f'<p>{esc(t(lang, "need_more_sub"))}</p>'
            )
        if not report.get("staged_review") and print_mode:
            for q in questions:
                body.append(f'<p style="margin:4px 0">· {esc(q)}</p>')
        elif not report.get("staged_review"):
            body.append(
                f'<p><a id="continueGuide" class="export-btn" href="#caseGuide" data-open-case-guide>'
                f'{esc(t(lang, "guide_continue"))}</a></p>'
            )
        if not report.get("staged_review"):
            if lang == "zh":
                for x in report.get("relative") or []:
                    body.append(f'<p style="margin:4px 0">· {esc(x)}</p>')
            body.append("</div>")
        if not clarification:
            body.append(map_html(report.get("fields") or {}, lang=lang))
        body.append(gates_html(report.get("gates"), lang=lang))
        body.append(pending_html(report.get("pending") or [], story, lang=lang))
    else:
        body.append('<div id="caseCalculation"></div>')
        worth = report.get("worth") or {}
        cites = [c for it in report["items"] for c in it.get("cite_texts", [])]
        verified_n = sum(1 for it in report["items"] if it["cite_ok"])
        d_first = next((x for x in report["deadlines"] if x.get("applicable")), report["deadlines"][0])
        dl_txt = t(lang, "expired") if d_first["expired"] else (
            f'{d_first["days_left"]} {t(lang, "days_unit")}' if d_first["days_left"] is not None else "—"
        )

        # Tab bar
        if not print_mode:
            body.append(
                '<div class="kpi-grid">'
                f'<div class="kpi-card kpi-1"><div class="kpi-lbl">{esc(t(lang, "kpi_total"))}</div>'
                f'<div class="kpi-val">¥{_money(report["total"])}</div></div>'
                f'<div class="kpi-card kpi-2"><div class="kpi-lbl">{esc(t(lang, "kpi_cites"))}</div>'
                f'<div class="kpi-val">{verified_n}/{len(report["items"])} ({len(cites)})</div></div>'
                f'<div class="kpi-card kpi-3"><div class="kpi-lbl">{esc(t(lang, "kpi_deadline"))}</div>'
                f'<div class="kpi-val">{esc(dl_txt)}</div></div>'
                f'<div class="kpi-card kpi-4"><div class="kpi-lbl">{esc(t(lang, "kpi_worth"))}</div>'
                f'<div class="kpi-val">{esc(worth.get("score") or "—")}{esc(t(lang, "score_unit"))}</div></div>'
                "</div>"
            )
            body.append(
                '<div class="tab-bar">'
                f'<button type="button" class="tab-btn active" data-tab="tab-overview">{esc(t(lang, "mod_overview"))}</button>'
                f'<button type="button" class="tab-btn" data-tab="tab-statutes">{esc(t(lang, "mod_statutes"))}</button>'
                f'<button type="button" class="tab-btn" data-tab="tab-defense">{esc(t(lang, "mod_defense"))}</button>'
                f'<button type="button" class="tab-btn" data-tab="tab-filing">{esc(t(lang, "mod_filing"))}</button>'
                "</div>"
            )

        # TAB 1: Overview & AI Compare
        body.append('<div class="tab-panel active" id="tab-overview">')
        if display_compare:
            body.append(compare_html(
                report, compare_data, lang=lang, rule_ms=rule_ms,
                async_pending=bool((async_compare or {}).get("pending")),
                model_name=(cfg or {}).get("model", "deepseek-chat"),
            ))
        body.append('<div class="card">')
        body.append(f'<h1>{esc(t(lang, "total_prefix"))}: <span class="total">¥{_money(report["total"])}</span></h1>')
        if worth.get("decision_label"):
            dlbl = tr_decision(lang, worth.get("decision") or "", worth["decision_label"])
            body.append(
                f'<div class="verdict {esc(worth.get("decision"))}">{esc(dlbl)} · '
                f'{esc(worth.get("score"))}/100</div>'
            )
        if story:
            body.append(f'<blockquote><b>{esc(t(lang, "story_label"))}</b> {esc(story)}</blockquote>')
        body.append("</div>")
        body.append(pending_html(report.get("pending") or [], story, lang=lang))
        body.append(
            f'<div class="card" id="sec-calc"><h2>{esc(t(lang, "items_title"))}</h2>'
            f'<table><tr><th>{esc(t(lang, "col_item"))}</th>'
            f'<th class="num">{esc(t(lang, "col_amount"))}</th>'
            f'<th>{esc(t(lang, "col_formula"))}</th></tr>'
        )
        for it in report["items"]:
            body.append(
                f'<tr><td>{esc(tr_item(lang, it["name"]))}</td>'
                f'<td class="num">{_money(it["amount"])}</td>'
                f'<td>{esc(tr_formula(lang, it["formula"]))}</td></tr>'
            )
        body.append(f'<tr><th>{esc(t(lang, "col_total"))}</th><th class="num">{_money(report["total"])}</th><th></th></tr></table></div>')
        body.append("</div>")

        # TAB 2: Statutes & Case Map
        body.append('<div class="tab-panel" id="tab-statutes">')
        body.append(map_html(report.get("fields") or {}, lang=lang))
        body.append(f'<div class="card"><h2>{esc(t(lang, "laws_title"))}</h2>')
        for it in report["items"]:
            flag = (
                f'<span class="badge ok">{esc(t(lang, "cite_ok"))}</span>'
                if it["cite_ok"] else f'<span class="badge warn">{esc(t(lang, "cite_warn"))}</span>'
            )
            body.append(
                f'<p style="margin:10px 0 2px"><b>{esc(tr_item(lang, it["name"]))}</b>{flag}'
                f'<br><span class="sub" style="margin:0">{esc(tr_basis(lang, it["basis"]))}</span></p>'
            )
            for c in it.get("cite_texts", []):
                cite_lbl = c["cite"] if lang == "zh" else tr_basis(lang, c["cite"])
                st_text = tr_statute_text(lang, c["cite"], c["text"])
                body.append(
                    f'<details><summary>{esc(cite_lbl)} · {esc(t(lang, "original_text"))}</summary>'
                    f'<blockquote>{esc(st_text)}</blockquote></details>'
                )
        body.append("</div>")
        if report.get("reference_cases"):
            body.append(f'<div class="card"><h2>{esc(t(lang, "ref_title"))}</h2><p class="sub">{esc(t(lang, "ref_sub"))}</p>')
            ref_labels = (
                (("争议焦点", "focus"), ("处理结果", "result"), ("可比点", "compare"), ("区别", "distinguish"))
                if lang == "zh" else
                (("Focus", "focus"), ("Outcome", "result"), ("Similarity", "compare"), ("Distinction", "distinguish"))
            )
            for raw_case in report["reference_cases"]:
                case = tr_ref_case(lang, raw_case)
                body.append(f'<h3>{esc(case["title"])}</h3>')
                for label, key in ref_labels:
                    body.append(f'<p style="margin:3px 0"><b>{label}</b>　{esc(case[key])}</p>')
                body.append(f'<p style="margin:4px 0 10px"><a href="{esc(case["url"])}" target="_blank" rel="noopener">{esc(case["source"])}</a></p>')
            body.append("</div>")
        body.append("</div>")

        # TAB 3: Deadlines, Evidence & Defense Prep
        body.append('<div class="tab-panel" id="tab-defense">')
        body.append(
            f'<div class="card" id="sec-deadline"><h2>{esc(t(lang, "deadlines_title"))}</h2>'
            f'<table><tr><th>{esc(t(lang, "col_claim"))}</th><th>{esc(t(lang, "col_anchor"))}</th>'
            f'<th>{esc(t(lang, "col_deadline"))}</th><th class="num">{esc(t(lang, "col_left"))}</th></tr>'
        )
        for d in report["deadlines"]:
            dlbl, danchor = tr_deadline(lang, d)
            left = "—" if d["days_left"] is None else (
                t(lang, "expired") if d["expired"] else t(lang, "days_left", n=d["days_left"])
            )
            body.append(f'<tr><td>{esc(dlbl)}</td><td>{esc(danchor)}</td><td>{esc(d["deadline"])}</td><td class="num">{esc(left)}</td></tr>')
        body.append("</table></div>")
        if report.get("rehearsal"):
            body.append(f'<div class="card"><h2>{esc(t(lang, "rehearsal_title"))}</h2>')
            for rd_raw in report["rehearsal"]["rounds"]:
                rd = tr_rehearsal_round(lang, rd_raw)
                sep = "、" if lang == "zh" else ", "
                body.append(f'<p style="margin:10px 0 2px"><b>{esc(t(lang, "hr_says"))}</b> {esc(rd["hr_says"])}</p>')
                body.append(f'<p style="margin:0"><span class="sub">{esc(t(lang, "hr_why"))}</span> {esc(rd["why"])}</p>')
                body.append(f'<p style="margin:0"><span class="sub">{esc(t(lang, "hr_counter"))}</span> {esc(rd["counter"])}</p>')
                body.append(f'<p class="sub" style="margin:2px 0 0">{esc(t(lang, "hr_need"))} ' + sep.join(esc(n) for n in rd["need"]) + "</p>")
            if lang == "zh":
                body.append(f'<p class="sub">{esc(report["rehearsal"]["tip"])}</p>')
            body.append("</div>")
            body.append(evidence_html(report.get("rehearsal"), lang=lang))
        body.append("</div>")

        # TAB 4: Filing Path, Worth & Export
        body.append('<div class="tab-panel" id="tab-filing">')
        body.append(gates_html(report.get("gates"), lang=lang))
        body.append(worth_html(report.get("worth"), report.get("one_final_note"), lang=lang))
        body.append(materials_html(report.get("materials") or [], report.get("evidence_score"), lang=lang))
        body.append(venue_html(report.get("venue") or [], lang=lang))
        if report.get("assumptions") and lang == "zh":
            body.append(f'<div class="card ask"><h2>{esc(t(lang, "assumptions_title"))}</h2>')
            for a in report["assumptions"]:
                body.append(f'<p style="margin:3px 0">· {esc(a)}</p>')
            body.append("</div>")
        q_story = urllib.parse.quote(story)
        body.append(
            f'<div class="card noprint" id="sec-export"><h2>{esc(t(lang, "export_title"))}</h2>'
            f'<div class="export-bar">'
            f'<a class="export-btn" href="/pdf?story={q_story}">{esc(t(lang, "dl_pdf"))}</a>'
            f'<a class="export-btn" href="/print?story={q_story}" target="_blank">{esc(t(lang, "dl_print"))}</a>'
            f'<a class="export-btn" href="/report?story={q_story}">{esc(t(lang, "dl_md"))}</a>'
            f'<a class="export-btn" href="/application?story={q_story}">{esc(t(lang, "dl_app"))}</a>'
            f"</div></div>"
        )
        body.append("</div>")
        body.append(f'<p class="foot">{esc(t(lang, "foot_note"))}</p>')

    if not print_mode:
        body.append("</main></div>")

    return f"""<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(t(lang, "page_title"))}</title><style>{CSS}</style></head><body>
{''.join(body)}
{'' if print_mode else console_js(lang=lang, async_compare=async_compare)}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "arb/2.1"

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
        p = urllib.parse.parse_qs(query)
        return p.get("story", [""])[0], p.get("confirm", [])

    def _run_with_compare(
        self,
        story: str,
        confirmed: list[str],
        show_compare: bool,
        lang: str,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> tuple[dict, dict | None, int, dict | None]:
        t0 = time.perf_counter()
        r = analyze(story, mode="best_effort", confirmed=confirmed)
        rule_ms = max(1, int(round((time.perf_counter() - t0) * 1000)))
        if not show_compare:
            return r, None, rule_ms, None

        live_cfg = _resolve_live_cfg(api_key=api_key, base_url=base_url, model=model)
        if live_cfg and not has_live_cache(story, api_key=api_key, base_url=base_url, model=model, lang=lang):
            # 毫秒级先渲染页面，由前端 /api/compare 异步拉取大模型回答，避免卡住首屏
            return r, None, rule_ms, {"pending": True, "story": story, "lang": lang}
        cmp_data = compare_with_generic_ai(
            story, r, api_key=api_key, base_url=base_url, model=model, lang=lang,
        )
        return r, cmp_data, rule_ms, None

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
        lang = "zh" if params.get("lang", ["en"])[0] == "zh" else "en"
        case_id = params.get("case", [""])[0]
        preset = get_demo_case(case_id) if case_id else None
        if preset:
            story = preset["story"] if lang == "zh" else preset.get("story_en", preset["story"])
            r, cmp_data, rule_ms, async_cmp = self._run_with_compare(story, [], True, lang)
            self._send(200, render_page(
                r, story, compare_data=cmp_data, show_compare=True,
                lang=lang, rule_ms=rule_ms, async_compare=async_cmp,
            ))
            return
        self._send(200, render_page(lang=lang))

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        p = urllib.parse.parse_qs(raw)
        story = p.get("story", [""])[0].strip()
        confirmed = p.get("confirm", [])
        lang = "zh" if p.get("lang", ["en"])[0] == "zh" else "en"
        show_compare = p.get("compare", ["0"])[0] == "1"
        review_only = p.get("review_update", ["0"])[0] == "1"
        api_key = p.get("api_key", [""])[0]
        base_url = p.get("base_url", [""])[0]
        model = p.get("model", [""])[0]

        if parsed.path == "/api/compare":
            if not story:
                self._send(400, json.dumps({"error": "empty story"}), "application/json; charset=utf-8")
                return
            r = analyze(story, mode="best_effort", confirmed=confirmed)
            cmp_data = compare_with_generic_ai(
                story, r, api_key=api_key, base_url=base_url, model=model, lang=lang,
            )
            self._send(200, json.dumps(cmp_data, ensure_ascii=False), "application/json; charset=utf-8")
            return

        if not story:
            self._send(400, render_page(error=t(lang, "empty_err"), show_compare=show_compare, lang=lang))
            return
        try:
            r, cmp_data, rule_ms, async_cmp = self._run_with_compare(
                story, confirmed, show_compare and not review_only, lang,
                api_key=api_key, base_url=base_url, model=model,
            )
            self._send(200, render_page(
                r, story, compare_data=cmp_data, show_compare=show_compare,
                lang=lang, rule_ms=rule_ms, async_compare=async_cmp, review_only=review_only,
            ))
        except Exception as e:
            self._send(500, render_page(error=f"Error: {e}", story=story, show_compare=show_compare, lang=lang))

    def log_message(self, fmt, *args):
        print(f"[web] {fmt % args}")


def main(port: int = 8765) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Labor Arbitration Console started: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    import sys

    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
