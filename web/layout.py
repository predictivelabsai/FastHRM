"""FastHR 3-pane layout — emerald palette, SSE AI rail."""
from __future__ import annotations

from fasthtml.common import (
    Div, H1, H3, H4, P, Span, A, Button, Details, Summary, Form, Input, Title, Link, Script, Style, NotStr,
)

LAYOUT_CSS = """
:root{
  --bg:#f3faf6; --surface:#ffffff; --surface-2:#e9f5ef; --border:#d8eae2; --text:#16241d;
  --text-dim:#46584f; --text-mute:#84988d; --accent:#059669; --accent-hover:#047857;
  --accent-light:#d1fae5; --ok:#16a34a; --warn:#d97706; --warn-light:#fef3c7; --danger:#e11d48; --danger-light:#ffe4e6;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;height:100%;background:var(--bg);color:var(--text);
  font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:14px;}
a{color:var(--accent);text-decoration:none;} a:hover{text-decoration:underline;}
.app{display:grid;grid-template-columns:230px 1fr var(--rail,340px);grid-template-rows:52px 1fr;
  grid-template-areas:"top top top" "left center right";height:100vh;overflow:hidden;transition:grid-template-columns .18s ease;}
.app.right-expanded{--rail:clamp(420px,42vw,720px);} .app.right-collapsed{--rail:0px;} .app.right-collapsed .right-pane{display:none;}
#copilot-reopen{position:fixed;right:0;bottom:26px;display:none;align-items:center;gap:6px;cursor:pointer;z-index:60;
  background:var(--accent);color:#fff;font-size:13px;font-weight:600;padding:9px 14px;border-radius:8px 0 0 8px;box-shadow:0 2px 10px rgba(0,0,0,.18);}
.app.right-collapsed #copilot-reopen{display:inline-flex;}
.copilot-min,.copilot-exp{cursor:pointer;border:1px solid var(--border);background:var(--surface);border-radius:6px;padding:4px 9px;font-size:13px;line-height:1;color:var(--text-mute);}
.topbar{grid-area:top;display:flex;align-items:center;justify-content:space-between;padding:0 20px;background:var(--surface);border-bottom:1px solid var(--border);}
.brand{font-weight:700;letter-spacing:.3px;display:flex;align-items:center;gap:8px;font-size:16px;}
.brand-dot{width:11px;height:11px;background:var(--accent);border-radius:50%;display:inline-block;}
.env-pill{background:var(--accent-light);color:var(--accent-hover);padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;}
.ver-pill{background:var(--surface-2);color:var(--text-mute);border:1px solid var(--border);padding:3px 9px;border-radius:999px;font-size:11px;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap;}
.ver-pill:hover{color:var(--accent-hover);border-color:var(--accent);text-decoration:none;}
.topbar .actions{display:flex;gap:10px;align-items:center;}
.left-pane{grid-area:left;background:var(--surface);border-right:1px solid var(--border);padding:12px 0;overflow-y:auto;}
.nav-section-controls{display:flex;justify-content:flex-end;gap:6px;padding:0 12px 8px}.nav-section-controls button{min-width:34px;padding:4px 8px;border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text-mute);font-size:11px;cursor:pointer}.nav-section-controls button:hover{color:var(--accent-hover);border-color:var(--accent)}
.nav-section{border-bottom:1px solid var(--border)}.nav-section:last-child{border-bottom:0}.nav-section-toggle{display:flex;align-items:center;justify-content:space-between;list-style:none;cursor:pointer;padding:8px 16px 4px}.nav-section-toggle::-webkit-details-marker{display:none}.nav-section-toggle h4{margin:0;font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--text-mute);font-weight:700}.nav-section-toggle:hover h4{color:var(--accent-hover)}.nav-section-arrow::after{content:">>";color:var(--text-mute);font-size:10px;font-weight:900}.nav-section[open]>.nav-section-toggle .nav-section-arrow::after{content:"<<"}.nav-section-items{padding-bottom:8px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 16px;color:var(--text-dim);cursor:pointer;border-left:3px solid transparent;}
.nav-item:hover{background:var(--surface-2);color:var(--text);text-decoration:none;}
.nav-item.active{background:var(--accent-light);color:var(--accent-hover);border-left-color:var(--accent);font-weight:600;}
.nav-icon{width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;flex:none;}
.nav-icon svg{width:20px;height:20px;display:block;overflow:visible;}
.center-pane{grid-area:center;overflow-y:auto;padding:20px 24px;}
.page-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
.page-title h1{margin:0;font-size:22px;font-weight:700;} .page-title .sub{color:var(--text-mute);font-size:13px;margin-top:3px;}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px;}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;position:relative;overflow:hidden;}
.kpi .label{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--text-mute);font-weight:600;}
.kpi .value{font-size:24px;font-weight:700;margin-top:4px;} .kpi .trend{font-size:12px;color:var(--text-mute);margin-top:2px;}
.kpi::after{content:'';position:absolute;top:0;right:0;bottom:0;width:4px;background:var(--accent);}
.kpi.warn::after{background:var(--warn);} .kpi.danger::after{background:var(--danger);}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px;margin-bottom:16px;}
.card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;} .card-header h3{margin:0;font-size:15px;font-weight:700;}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
table.tbl{width:100%;border-collapse:collapse;font-size:13px;}
table.tbl th{text-align:left;padding:8px 10px;background:var(--surface-2);color:var(--text-dim);font-weight:600;border-bottom:1px solid var(--border);}
table.tbl td{padding:8px 10px;border-bottom:1px solid var(--border);} table.tbl tr:last-child td{border-bottom:0;} table.tbl tr:hover td{background:var(--surface-2);}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;background:var(--surface-2);color:var(--text-dim);white-space:nowrap;}
.pill.active,.pill.approved,.pill.present,.pill.paid{background:var(--accent-light);color:var(--accent-hover);}
.pill.pending,.pill.halfday,.pill.probation,.pill.workfromhome{background:var(--warn-light);color:#92400e;}
.pill.rejected,.pill.absent{background:var(--danger-light);color:#9f1239;}
.pill.onleave,.pill.cancelled{background:#e0e7ff;color:#4338ca;}
.funnel-row{display:grid;grid-template-columns:150px 1fr 50px;align-items:center;gap:10px;margin-bottom:7px;font-size:13px;}
.funnel-bar{height:18px;border-radius:5px;background:var(--accent);min-width:2px;} .funnel-row .v{text-align:right;color:var(--text-dim);}
.detail-grid{display:grid;grid-template-columns:1fr 320px;gap:16px;}
.kv{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;font-size:13px;} .kv .k{color:var(--text-mute);}
.kv .pill{justify-self:start;}  /* grid items stretch by default; a pill should hug its text */
.avatar{width:40px;height:40px;border-radius:50%;background:var(--accent-light);color:var(--accent-hover);display:inline-flex;align-items:center;justify-content:center;font-weight:700;}
.emp-head{display:flex;align-items:center;gap:14px;margin-bottom:8px;}
.bal-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;}
.bal{border:1px solid var(--border);border-radius:8px;padding:10px 12px;background:var(--surface);}
.bal .lt{font-size:12px;color:var(--text-mute);} .bal .rem{font-size:20px;font-weight:700;color:var(--accent-hover);} .bal .of{font-size:11px;color:var(--text-mute);}
.att-strip{display:flex;gap:3px;flex-wrap:wrap;} .att-cell{width:22px;height:22px;border-radius:4px;font-size:9px;display:flex;align-items:center;justify-content:center;color:#fff;}
.att-present{background:var(--accent);} .att-wfh{background:#10b981;} .att-leave{background:#6366f1;} .att-half{background:var(--warn);} .att-absent{background:var(--danger);}
.seg{display:inline-flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;}
.seg a{padding:6px 12px;border:1px solid var(--border);border-radius:8px;color:var(--text-dim);background:var(--surface);font-size:13px;}
.seg a.active{background:var(--accent);color:#fff;border-color:var(--accent);}
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap;}
.toolbar input[type=search]{padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;min-width:240px;}
.btn{padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;font-size:13px;}
.btn:hover{background:var(--surface-2);} .btn.primary{background:var(--accent);color:#fff;border-color:var(--accent);} .btn.primary:hover{background:var(--accent-hover);}
.btn.sm{padding:3px 9px;font-size:12px;}
.inline-form{display:flex;gap:8px;align-items:center;}
.hr-inp{padding:7px 10px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--surface);}
.login-wrap{height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#e3f5ec 0%,#d1fae5 100%);}
.login-card{background:#fff;padding:36px 40px;border-radius:14px;width:360px;box-shadow:0 20px 40px rgba(15,23,42,.08);}
.login-card h1{margin:0 0 4px;font-size:22px;} .login-card p{margin:0 0 20px;color:var(--text-mute);font-size:13px;}
.login-card input{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:10px;font-size:14px;}
.login-card button{width:100%;padding:10px;font-weight:600;} .login-card .error{color:var(--danger);font-size:12px;margin:6px 0;} .login-card .hint{font-size:11.5px;color:var(--text-mute);margin-top:10px;text-align:center;}
.right-pane{grid-area:right;background:var(--surface);border-left:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;}
.right-header{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;} .right-header h3{margin:0;font-size:14px;font-weight:700;} .right-header .tabs{display:flex;gap:6px;}
.chat-body{flex:1;overflow-y:auto;padding:14px 16px;display:flex;flex-direction:column;gap:12px;}
.msg{max-width:90%;padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.55;overflow-wrap:anywhere;}
.msg.user{background:var(--accent);color:#fff;align-self:flex-end;border-bottom-right-radius:3px;white-space:pre-wrap;}
.msg.assistant{background:var(--surface-2);border:1px solid var(--border);color:var(--text);align-self:flex-start;border-bottom-left-radius:3px;}
.msg table{width:100%;table-layout:fixed;font-size:11.5px;border-collapse:collapse;border:1px solid var(--border);margin:6px 0;}
.msg th{background:var(--text);color:#fff;font-size:10.5px;} .msg th,.msg td{text-align:left;padding:5px 7px;border:1px solid var(--border);overflow-wrap:anywhere;}
.msg code{background:rgba(0,0,0,.06);padding:1px 4px;border-radius:3px;font-size:12px;}
.chat-input{border-top:1px solid var(--border);padding:10px;background:var(--surface);} .chat-input-row{display:flex;gap:8px;align-items:stretch;}
.chat-input-row input{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;outline:none;}
.chat-input-row input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light);}
.chat-send-btn{display:inline-flex;align-items:center;background:var(--accent);color:#fff;border:none;border-radius:8px;padding:0 16px;font-weight:600;font-size:13px;cursor:pointer;} .chat-send-btn:disabled{background:var(--text-mute);}
.chat-empty-hint{color:var(--text-mute);font-size:12.5px;line-height:1.5;text-align:center;padding:18px 14px;}
.sample-cards{padding:.4rem 1rem .8rem;background:var(--surface);border-top:1px solid var(--border);}
.sample-cards-label{display:inline-block;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;color:var(--text-mute);margin-bottom:6px;}
.sample-card{display:flex;align-items:center;gap:8px;background:var(--bg);border:1px solid var(--border);padding:9px 12px;border-radius:10px;font-size:12.5px;cursor:pointer;color:var(--text-dim);width:100%;text-align:left;line-height:1.35;margin-bottom:6px;font-family:inherit;}
.sample-card:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-light);}
.thinking-indicator{display:flex;align-items:center;gap:8px;padding:6px 14px;font-size:12.5px;color:var(--text-mute);align-self:flex-start;}
.thinking-indicator .dot{width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 1.2s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:.35;transform:scale(.85);}50%{opacity:1;transform:scale(1.1);}}

/* --- talent / ATS --- */
.pill.open,.pill.hired,.pill.filled,.pill.ok{background:var(--accent-light);color:var(--accent-hover);}
.pill.screen,.pill.interview,.pill.onhold,.pill.draft{background:var(--warn-light);color:#92400e;}
.pill.error,.pill.withdrawn{background:var(--danger-light);color:#9f1239;}
.pill.offer,.pill.applied{background:#e0e7ff;color:#4338ca;}
.stage-bar{display:flex;gap:4px;margin:4px 0 14px;}
.stage-seg{flex:1;border:1px solid var(--border);border-radius:8px;padding:9px 11px;background:var(--surface);text-align:left;}
.stage-seg .n{font-size:19px;font-weight:700;} .stage-seg .s{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--text-mute);font-weight:600;}
.stage-seg.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-light);}
.stage-seg.terminal .n{color:var(--text-mute);}
.chips{display:flex;flex-wrap:wrap;gap:6px;}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--surface-2);border-radius:999px;padding:4px 11px;font-size:12px;}
.chip .yrs{color:var(--text-mute);font-size:11px;}
.chip.expert{border-color:var(--accent);background:var(--accent-light);color:var(--accent-hover);}
.timeline{border-left:2px solid var(--border);margin-left:6px;padding-left:16px;}
.tl-item{position:relative;padding-bottom:16px;}
.tl-item::before{content:'';position:absolute;left:-23px;top:4px;width:10px;height:10px;border-radius:50%;background:var(--accent);border:2px solid var(--surface);}
.tl-item .role{font-weight:600;} .tl-item .org{color:var(--text-dim);} .tl-item .when{font-size:11.5px;color:var(--text-mute);font-variant-numeric:tabular-nums;}
.tl-item .what{font-size:12.5px;color:var(--text-dim);margin-top:3px;}
.drop-zone{border:2px dashed var(--border);border-radius:12px;padding:22px;text-align:center;background:var(--surface-2);}
.drop-zone.hot{border-color:var(--accent);background:var(--accent-light);}
.drop-zone .big{font-size:15px;font-weight:600;margin-bottom:3px;} .drop-zone .small{font-size:12px;color:var(--text-mute);}
.flag{display:block;border-left:3px solid var(--warn);background:var(--warn-light);color:#92400e;padding:7px 11px;border-radius:0 7px 7px 0;font-size:12.5px;margin-bottom:6px;}
.prompt-box{width:100%;min-height:380px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;line-height:1.6;padding:14px;border:1px solid var(--border);border-radius:10px;background:var(--surface);resize:vertical;}
.contract-box{background:#0f172a;color:#cbd5e1;border-radius:10px;padding:14px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;line-height:1.55;overflow-x:auto;white-space:pre;}

/* --- integrations --- */
.int-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;}
.int-card{border:1px solid var(--border);border-radius:10px;padding:14px 16px;background:var(--surface);display:flex;flex-direction:column;gap:8px;}
.int-card.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-light);}
.int-card.err{border-color:var(--danger);}
.int-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;}
.int-head .nm{font-weight:700;font-size:14px;} .int-blurb{font-size:12.2px;color:var(--text-dim);line-height:1.45;}
.int-meta{font-size:11.5px;color:var(--text-mute);font-variant-numeric:tabular-nums;}
.int-key{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;color:var(--text-dim);background:var(--surface-2);padding:2px 7px;border-radius:5px;display:inline-block;}
.int-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:auto;padding-top:4px;}

/* --- progress bars, goals --- */
.bar{height:8px;border-radius:99px;background:var(--surface-2);overflow:hidden;min-width:90px;}
.bar > i{display:block;height:100%;background:var(--accent);border-radius:99px;}
.bar.warn > i{background:var(--warn);} .bar.danger > i{background:var(--danger);}
.goal-row{display:grid;grid-template-columns:1fr 140px 74px 100px;gap:12px;align-items:center;padding:9px 0;border-bottom:1px solid var(--border);}
.goal-row:last-child{border-bottom:0;}
.goal-row .t{font-weight:600;font-size:13px;} .goal-row .m{font-size:11.5px;color:var(--text-mute);}
.goal-tree{margin:0;} .goal-tree .kid{margin-left:22px;border-left:2px solid var(--border);padding-left:14px;}

/* --- org chart --- */
.org{font-size:13px;} .org ul{list-style:none;margin:0;padding-left:20px;border-left:1px solid var(--border);}
.org li{padding:3px 0;position:relative;}
.org .node{display:inline-flex;align-items:center;gap:8px;padding:4px 10px;border:1px solid var(--border);border-radius:8px;background:var(--surface);}
.org .node .r{font-size:11px;color:var(--text-mute);} .org .node .n{font-weight:600;}
.org .node .sz{background:var(--accent-light);color:var(--accent-hover);border-radius:99px;padding:1px 7px;font-size:10.5px;font-weight:700;}

/* --- checklists & feed --- */
.check{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px;}
.check:last-child{border-bottom:0;} .check.done .lbl{color:var(--text-mute);text-decoration:line-through;}
.check .lbl{flex:1;} .check .due{font-size:11.5px;color:var(--text-mute);white-space:nowrap;}
.check .due.late{color:var(--danger);font-weight:600;}
.feed-item{border-left:3px solid var(--accent);background:var(--surface-2);border-radius:0 8px 8px 0;padding:9px 12px;margin-bottom:8px;}
.feed-item .who{font-size:12px;color:var(--text-mute);margin-bottom:3px;}
.feed-item .body{font-size:13px;line-height:1.5;}
.factors{margin:4px 0 0;padding-left:16px;font-size:11.8px;color:var(--text-dim);line-height:1.5;}
.score-cell{font-variant-numeric:tabular-nums;font-weight:700;}
.heat{display:inline-block;min-width:34px;text-align:center;border-radius:5px;padding:2px 6px;font-weight:700;font-size:12px;}

/* --- recruiting platform --- */
.pipeline-board{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(220px,1fr);gap:12px;overflow-x:auto;padding-bottom:12px;margin-bottom:14px;}
.pipeline-col{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:10px;min-height:260px;}
.pipeline-col h4{margin:2px 2px 10px;}.pipeline-drop{min-height:220px;display:grid;align-content:start;gap:8px;}
.pipeline-card{display:grid;gap:3px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px;cursor:grab;box-shadow:var(--shadow);}
.pipeline-card:active{cursor:grabbing}.row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px solid var(--border);}
.note{border-left:3px solid var(--accent);padding:7px 10px;background:var(--surface-2);border-radius:0 7px 7px 0;}
.slot{display:inline-flex;margin:5px}.public-card,.campaign-public{max-width:760px;margin:60px auto;padding:32px;border:1px solid var(--border);border-radius:16px;background:var(--surface);}

/* --- mobile nav trigger + backdrop (hidden on desktop) --- */
.nav-toggle{display:none;align-items:center;justify-content:center;width:38px;height:38px;flex:0 0 38px;
  margin-right:6px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--text-dim);
  cursor:pointer;padding:0;font-size:18px;line-height:1;}
.nav-toggle:hover{border-color:var(--accent);color:var(--accent-hover);}
.topbar-left{display:flex;align-items:center;gap:2px;min-width:0;}
#app-backdrop{display:none;position:fixed;inset:52px 0 0 0;background:rgba(11,29,23,.42);z-index:70;border:0;margin:0;padding:0;width:100%;cursor:pointer;}

/* ======================= RESPONSIVE / MOBILE ======================= */
@media (max-width:900px){
  .app{grid-template-columns:1fr;grid-template-rows:52px 1fr;grid-template-areas:"top" "center";height:100vh;height:100dvh;}
  .nav-toggle{display:inline-flex;}
  /* left nav -> off-canvas drawer */
  .left-pane{position:fixed;top:52px;left:0;bottom:0;width:min(286px,84vw);z-index:80;
    transform:translateX(-100%);transition:transform .22s ease;box-shadow:0 12px 40px rgba(11,29,23,.28);
    will-change:transform;}
  .app.nav-open .left-pane{transform:translateX(0);}
  /* right AI rail -> slide-in overlay, hidden until opened */
  .right-pane{position:fixed;top:52px;right:0;bottom:0;width:min(440px,94vw);z-index:80;display:flex;
    transform:translateX(100%);transition:transform .22s ease;box-shadow:0 12px 40px rgba(11,29,23,.28);
    border-left:1px solid var(--border);will-change:transform;}
  .app.chat-open .right-pane{transform:translateX(0);}
  .app.right-collapsed .right-pane,.app.right-expanded .right-pane{display:flex;}
  .app.nav-open #app-backdrop,.app.chat-open #app-backdrop{display:block;}
  #copilot-reopen{display:none!important;}
  .app.right-collapsed #copilot-reopen{display:none!important;}
  /* topbar tightening */
  .topbar{padding:0 12px;gap:8px;}
  .topbar .actions{gap:6px;}
  .topbar .actions>span{display:none;}
  .topbar .ver-pill{display:none;}
  .brand{font-size:15px;gap:6px;}
  /* center pane full width, comfortable padding */
  .center-pane{padding:16px 14px;}
  .page-title{flex-wrap:wrap;gap:8px;}
  .page-title h1{font-size:20px;}
  /* content grids collapse */
  .kpi-grid{grid-template-columns:repeat(2,1fr);gap:10px;}
  .grid-2,.detail-grid{grid-template-columns:1fr;}
  .bal-grid{grid-template-columns:repeat(2,1fr);}
  .goal-row{grid-template-columns:1fr;row-gap:4px;padding:11px 0;}
  .funnel-row{grid-template-columns:96px 1fr 38px;}
  .kv{grid-template-columns:104px 1fr;}
  .stage-bar{flex-wrap:wrap;gap:6px;}
  .stage-seg{flex:1 1 44%;}
  /* wide tables scroll horizontally instead of overflowing the page */
  .center-pane .card>table.tbl,.center-pane>table.tbl,.center-pane table.tbl{display:block;width:100%;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;}
  /* toolbars / search wrap and fill */
  .toolbar{gap:8px;}
  .toolbar input[type=search],.hr-inp{min-width:0;width:100%;}
  .inline-form{flex-wrap:wrap;}
  /* admin login card */
  .login-card{width:min(360px,92vw);padding:28px 22px;}
  /* AI rail message width can grow on the overlay */
  .msg{max-width:94%;}
}
@media (max-width:480px){
  .kpi-grid{grid-template-columns:1fr;}
  .bal-grid{grid-template-columns:1fr;}
  .center-pane{padding:14px 12px;}
  .card{padding:14px;}
  .stage-seg{flex:1 1 100%;}
}
/* larger, finger-friendly hit areas on touch devices */
@media (pointer:coarse){
  .btn,.seg a,.chat-send-btn,.chat-input-row input{min-height:40px;}
  .btn.sm{min-height:34px;}
  .nav-item{padding-top:11px;padding-bottom:11px;}
  .nav-section-toggle{padding-top:12px;padding-bottom:8px;}
}
"""

NAV_ITEMS = [
    ("Ülevaade", [("dashboard", "Töölaud", "layout-dashboard", "/"), ("ai", "AI-abiline", "sparkles", "/ai"),
                   ("employee-portal", "Töötaja portaal", "user-round", "/me")]),
    ("Inimesed", [("employees", "Töötajad", "users-round", "/employees"),
                  ("departments", "Osakonnad", "building-2", "/departments")]),
    ("Aeg", [("leave", "Puhkused", "palmtree", "/leave"), ("attendance", "Kohalolek", "clock-3", "/attendance"),
             ("shifts", "Vahetused", "calendar-days", "/shifts"), ("timeclock", "Tööaja märkimine", "timer", "/timeclock")]),
    ("Palk", [("payroll", "Palgaarvestus", "banknote", "/payroll"),
              ("benefits", "Soodustused", "gift", "/benefits"),
              ("expenses", "Kulud ja avansid", "receipt", "/expenses"),
              ("travel", "Lähetused", "plane", "/travel")]),
    ("Värbamine", [("platform", "Värbamise platvorm", "compass", "/talent/platform"),
                   ("jobs", "Ametikohad", "briefcase-business", "/talent/jobs"),
                   ("candidates", "Kandidaadid", "target", "/talent/candidates"),
                   ("offers", "Pakkumised", "mail-plus", "/talent/offers"),
                   ("talent-analytics", "Analüütika", "chart-no-axes-combined", "/talent/analytics")]),
    ("Tulemuslikkus", [("goals", "Eesmärgid ja OKR-id", "goal", "/performance/goals"),
                       ("feedback", "Tagasiside", "message-circle", "/performance/feedback"),
                       ("reviews", "Ülevaatustsüklid", "file-pen-line", "/performance/reviews"),
                       ("signals", "Signaalid", "radio", "/performance/signals"),
                       ("learning", "Õpe ja areng", "graduation-cap", "/learning")]),
    ("Töötaja elukaar", [("onboarding", "Sisseelamine", "rocket", "/lifecycle/onboarding"),
                         ("changes", "Muudatused", "git-branch", "/lifecycle/changes"),
                         ("separations", "Lahkumised", "door-open", "/lifecycle/separations"),
                         ("workforce", "Tööjõu planeerimine", "calculator", "/workforce"),
                         ("cases", "Juhtumid", "folder-kanban", "/lifecycle/cases"),
                         ("org", "Organisatsiooni skeem", "network", "/lifecycle/org")]),
    ("Seaded", [("integrations", "Integratsioonid", "plug", "/settings/integrations"),
                ("prompts", "AI-juhised", "pencil-line", "/talent/prompts"),
                ("roles", "Rollid ja juurdepääs", "key-round", "/settings/roles")]),
    ("Abi", [("guide", "Kasutusjuhend", "book-open", "/guide"),
             ("developers", "Arendajad", "code-2", "/developers")]),
]

NAV_ICON_PATHS = {
    "layout-dashboard": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "sparkles": '<path d="m12 3-1.2 4.2L7 8.5l3.8 1.3L12 14l1.2-4.2L17 8.5l-3.8-1.3L12 3Z"/><path d="m19 14-.6 2.1L16.5 17l1.9.9L19 20l.6-2.1 1.9-.9-1.9-.9L19 14Z"/>',
    "user-round": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "users-round": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "building-2": '<path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M2 21h20M8 7h2m2 0h2M8 11h2m2 0h2M8 15h2m2 0h2M9 21v-3h4v3"/>',
    "palmtree": '<path d="M12 22V9M12 9C8 9 5 7 4 4c3-.2 6 .7 8 3M12 9c4 0 7-2 8-5-3-.2-6 .7-8 3M12 9c0-3 1-6 4-8-3-.4-5 1-4 8Z"/>',
    "clock-3": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendar-days": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>',
    "timer": '<path d="M10 2h4M12 14V9M7 4.5a9 9 0 1 0 10 0"/><path d="m16 5 2-2"/>',
    "banknote": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    "gift": '<rect x="3" y="8" width="18" height="13" rx="2"/><path d="M12 8v13M3 12h18M12 8H7.5a2.5 2.5 0 1 1 0-5C11 3 12 8 12 8Zm0 0h4.5a2.5 2.5 0 1 0 0-5C13 3 12 8 12 8Z"/>',
    "receipt": '<path d="M4 2h16v20l-4-2-4 2-4-2-4 2V2Z"/><path d="M8 7h8M8 11h8M8 15h5"/>',
    "plane": '<path d="m3 11 18-5-5 18-4-8-9-5Z"/><path d="m12 16 3-7"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"/>',
    "briefcase-business": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "mail-plus": '<rect x="3" y="5" width="14" height="14" rx="2"/><path d="m3 7 7 5 7-5M19 12v6M16 15h6"/>',
    "chart-no-axes-combined": '<path d="M3 3v18h18"/><path d="m7 16 4-5 3 3 5-7"/>',
    "goal": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 4-4"/>',
    "message-circle": '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 9.3 9.3 0 0 1-4-.9L3 21l1.9-4A8.3 8.3 0 0 1 3 11.5 8.5 8.5 0 0 1 12 3a8.5 8.5 0 0 1 9 8.5Z"/>',
    "file-pen-line": '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M13 2v7h7M8 18h2l6.5-6.5a1.4 1.4 0 0 0-2-2L8 16v2Z"/>',
    "radio": '<circle cx="12" cy="12" r="2"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.9 4.9a10 10 0 0 0 0 14.2M19.1 4.9a10 10 0 0 1 0 14.2"/>',
    "graduation-cap": '<path d="m2 10 10-5 10 5-10 5L2 10Z"/><path d="M6 12.5V17c3 2 9 2 12 0v-4.5M22 10v6"/>',
    "rocket": '<path d="M14.5 4.5C17 2 20 2 22 2c0 2 0 5-2.5 7.5L14 15l-5-5 4.5-5.5Z"/><path d="m9 10-4 1-3 3 6 1M14 15l-1 4-3 3-1-6M7 17l-3 3"/><circle cx="17" cy="7" r="1"/>',
    "git-branch": '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M6 7v4a4 4 0 0 0 4 4h6M18 7v10"/>',
    "door-open": '<path d="M13 3H5a2 2 0 0 0-2 2v16h12V3Z"/><path d="M15 21h6M15 21V5a2 2 0 0 0-2-2M7 12h.01"/>',
    "calculator": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M8 6h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15h.01M8 19h.01M12 19h4"/>',
    "folder-kanban": '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/><path d="M8 11v5M12 11v3M16 11v1"/>',
    "network": '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-3h14v3"/>',
    "plug": '<path d="M8 12h8M10 2v5M14 2v5M7 7h10v3a5 5 0 0 1-10 0V7ZM12 15v7"/>',
    "pencil-line": '<path d="m14 4 6 6M4 20l4.5-1L19 8.5a2.1 2.1 0 0 0-3-3L5.5 16 4 20Z"/><path d="M4 22h16"/>',
    "key-round": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 6l2 2M14 8l2 2"/>',
    "book-open": '<path d="M2 4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v17a3 3 0 0 0-3-3H4a2 2 0 0 0-2 2V4ZM22 4a2 2 0 0 0-2-2h-6a2 2 0 0 0-2 2v17a3 3 0 0 1 3-3h5a2 2 0 0 1 2 2V4Z"/>',
    "code-2": '<path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14"/>',
}


def nav_icon(name):
    return NotStr(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{NAV_ICON_PATHS[name]}</svg>')
SAMPLE_QUESTIONS = ["Kes on täna puhkusel?", "Milline meeskond on suurim?", "Mitu puhkuse taotlust on ootel?"]


def topbar(env, user_email):
    import version
    right = Div(
        Button(NotStr("&laquo; Vestlus"), id="copilot-topbar-toggle", cls="btn", onclick="toggleCopilot()") if user_email else None,
        Span(env, cls="env-pill") if env else None,
        # Which build am I looking at? Answerable without opening a terminal.
        A(version.label(), href="/about", cls="ver-pill", title=version.detail()) if user_email else None,
        Span(user_email or "", style="color:var(--text-mute);font-size:12px;") if user_email else None,
        A("Logi välja", href="/logout", cls="btn") if user_email else None, cls="actions")
    brand = Div(Span(cls="brand-dot"), Span("FastHR", style="font-weight:800;"), cls="brand")
    left = Div(
        Button(NotStr("&#9776;"), type="button", id="nav-toggle", cls="nav-toggle",
               aria_label="Ava menüü", aria_expanded="false",
               onclick="toggleNav()") if user_email else None,
        brand, cls="topbar-left")
    return Div(left, right, cls="topbar")


def left_pane(active):
    sections = []
    for name, items in NAV_ITEMS:
        links = [A(Span(nav_icon(icon), cls="nav-icon"), Span(label), href=href,
                   cls=f"nav-item {'active' if active == key else ''}") for key, label, icon, href in items]
        sections.append(
            Details(
                Summary(H4(name), Span(cls="nav-section-arrow", aria_hidden="true"),
                        cls="nav-section-toggle", aria_label=f"Ava või sulge {name}"),
                Div(*links, cls="nav-section-items"),
                open=True, cls="nav-section", data_section=name.lower(),
            )
        )
    controls = Div(
        Button("<<", type="button", id="nav-collapse-all", title="Ahenda kõik menüüjaotised",
               aria_label="Ahenda kõik menüüjaotised"),
        Button(">>", type="button", id="nav-expand-all", title="Ava kõik menüüjaotised",
               aria_label="Ava kõik menüüjaotised"),
        cls="nav-section-controls",
    )
    return Div(controls, *sections, cls="left-pane")


def _sample_cards():
    cards = [Button(Span(q), cls="sample-card", onclick=f"fillChat({q!r});sendMessage(null);", title=q) for q in SAMPLE_QUESTIONS]
    return Div(Div(Span("Proovi küsida:", cls="sample-cards-label")), Div(*cards), cls="sample-cards")


def right_pane_chat(thread_id):
    return Div(
        Div(H3("AI-abiline"),
            Div(Button("Uus", cls="btn", hx_get="/chat/new", hx_target="#chat-body", hx_swap="innerHTML"),
                Button(NotStr("&laquo;"), id="copilot-exp-btn", cls="copilot-exp", onclick="toggleExpand()"),
                Button(NotStr("&rsaquo;"), cls="copilot-min", onclick="toggleCopilot()"), cls="tabs"),
            cls="right-header"),
        Div(Div(P("Küsi töötajate, puhkuste või kohaloleku kohta. Võid kasutada ka /headcount, /leave või /help.",
                  cls="chat-empty-hint"), id="chat-body", cls="chat-body"),
            Form(Input(type="hidden", name="thread_id", value=thread_id, id="thread-id"),
                 Div(Input(type="text", name="message", id="chat-input",
                           placeholder="Küsi HR-i kohta või kirjuta /leave /help …", autocomplete="off"),
                     Button("Saada", type="submit", cls="chat-send-btn", id="chat-send-btn"), cls="chat-input-row"),
                 onsubmit="return streamChat(event)", cls="chat-input"),
            _sample_cards(),
            style="display:flex;flex-direction:column;flex:1;overflow:hidden;"),
        cls="right-pane")


def page(active, env, user_email, thread_id, *content, right_override=None):
    right = right_override if right_override is not None else right_pane_chat(thread_id)
    return (Title("FastHR"),
            Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
            Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
            Style(LAYOUT_CSS),
            Div(topbar(env, user_email), left_pane(active), Div(*content, cls="center-pane"), right,
                Button(type="button", id="app-backdrop", aria_hidden="true", tabindex="-1", onclick="closeOverlays()"),
                Div(NotStr("&lsaquo; AI-abiline"), id="copilot-reopen", onclick="toggleCopilot()"), cls="app"),
            Script(LAYOUT_JS))


def kpi_card(label, value, trend="", tone=""):
    return Div(Div(label, cls="label"),
               Div(f"{value:,}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value), cls="value"),
               Div(trend, cls="trend") if trend else None, cls=f"kpi {tone}")


def money(v):
    v = v or 0
    return f"£{v/1_000_000:.2f}M" if v >= 1_000_000 else (f"£{v/1_000:.0f}k" if v >= 1_000 else f"£{v:,.0f}")


LAYOUT_JS = """
function _sync(){var app=document.querySelector('.app');if(!app)return;
  var ex=app.classList.contains('right-expanded'),col=app.classList.contains('right-collapsed');
  var eb=document.getElementById('copilot-exp-btn');if(eb){eb.innerHTML=ex?'\\u00BB':'\\u00AB';}
  var tb=document.getElementById('copilot-topbar-toggle');if(tb){tb.innerHTML=col?'\\u00AB Vestlus':'Vestlus \\u203A';}}
function isMobileNav(){return window.matchMedia('(max-width:900px)').matches;}
function closeOverlays(){var app=document.querySelector('.app');if(!app)return;
  app.classList.remove('nav-open','chat-open');
  var nt=document.getElementById('nav-toggle');if(nt)nt.setAttribute('aria-expanded','false');}
function toggleNav(){var app=document.querySelector('.app');if(!app)return;
  var open=app.classList.toggle('nav-open');app.classList.remove('chat-open');
  var nt=document.getElementById('nav-toggle');if(nt)nt.setAttribute('aria-expanded',open?'true':'false');}
function toggleCopilot(){var app=document.querySelector('.app');if(!app)return;
  if(isMobileNav()){app.classList.remove('nav-open');app.classList.toggle('chat-open');_sync();return;}
  app.classList.toggle('right-collapsed');
  if(app.classList.contains('right-collapsed'))app.classList.remove('right-expanded');
  try{localStorage.setItem('hrCollapsed',app.classList.contains('right-collapsed')?'1':'0');}catch(e){}_sync();}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeOverlays();});
window.addEventListener('resize',function(){if(!isMobileNav())closeOverlays();});
function toggleExpand(){var app=document.querySelector('.app');if(!app)return;app.classList.remove('right-collapsed');app.classList.toggle('right-expanded');
  try{localStorage.setItem('hrExpanded',app.classList.contains('right-expanded')?'1':'0');localStorage.setItem('hrCollapsed','0');}catch(e){}_sync();}
(function(){try{var app=document.querySelector('.app');if(!app)return;
  if(localStorage.getItem('hrCollapsed')==='1')app.classList.add('right-collapsed');
  else if(localStorage.getItem('hrExpanded')==='1')app.classList.add('right-expanded');}catch(e){}})();
(function(){
  var sections=[...document.querySelectorAll('.nav-section')];
  function key(section){return 'fasthrm:nav:'+section.dataset.section;}
  function save(section){try{localStorage.setItem(key(section),section.open?'1':'0');}catch(e){}}
  sections.forEach(function(section){try{var stored=localStorage.getItem(key(section));if(stored!==null)section.open=stored==='1';}catch(e){}
    section.addEventListener('toggle',function(){save(section);});});
  var collapse=document.getElementById('nav-collapse-all'),expand=document.getElementById('nav-expand-all');
  if(collapse)collapse.addEventListener('click',function(){sections.forEach(function(section){section.open=false;save(section);});});
  if(expand)expand.addEventListener('click',function(){sections.forEach(function(section){section.open=true;save(section);});});
})();
document.addEventListener('DOMContentLoaded',_sync);
function fillChat(t){var el=document.getElementById('chat-input');if(el){el.value=t;el.focus();}}
function sendMessage(ev){return streamChat(ev);}
var _streaming=false,_thinker=null;
function _esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function _md(t){try{return marked.parse(t);}catch(e){return _esc(t);}}
function _scroll(){var cb=document.getElementById('chat-body');if(cb)cb.scrollTop=cb.scrollHeight;}
function addBubble(role,html){var cb=document.getElementById('chat-body');if(!cb)return null;
  var h=cb.querySelector('.chat-empty-hint');if(h)h.style.display='none';
  var d=document.createElement('div');d.className='msg '+role;d.innerHTML=html||'';cb.appendChild(d);_scroll();return d;}
function showThinking(){var cb=document.getElementById('chat-body');if(!cb)return;
  _thinker={el:document.createElement('div')};_thinker.el.className='thinking-indicator';
  _thinker.el.innerHTML='<span class="dot"></span> Mõtlen…';cb.appendChild(_thinker.el);_scroll();}
function hideThinking(){if(_thinker){if(_thinker.el.parentNode)_thinker.el.parentNode.removeChild(_thinker.el);_thinker=null;}}
async function streamChat(ev){if(ev&&ev.preventDefault)ev.preventDefault();if(_streaming)return false;
  var input=document.getElementById('chat-input');var msg=input?input.value.trim():'';if(!msg)return false;
  _streaming=true;var btn=document.getElementById('chat-send-btn');if(btn)btn.disabled=true;
  addBubble('user',_esc(msg));input.value='';
  var tid=(document.getElementById('thread-id')||{}).value||'';var bubble=null,acc='';showThinking();
  try{var resp=await fetch('/chat/stream',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({message:msg,thread_id:tid})});
    if(!resp.ok){hideThinking();addBubble('assistant','Viga: '+resp.status);_streaming=false;if(btn)btn.disabled=false;return false;}
    var reader=resp.body.getReader(),dec=new TextDecoder(),buf='';
    while(true){var r=await reader.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});
      var idx;while((idx=buf.indexOf('\\n\\n'))!==-1){var raw=buf.slice(0,idx);buf=buf.slice(idx+2);
        if(raw.indexOf('data: ')!==0)continue;var p={};try{p=JSON.parse(raw.slice(6));}catch(e){}
        if(p.token){if(acc===''){hideThinking();bubble=addBubble('assistant','');}acc+=p.token;bubble.innerHTML=_md(acc);_scroll();}
        else if(p.error){hideThinking();addBubble('assistant','⚠ '+p.error);}}}
  }catch(e){hideThinking();addBubble('assistant','⚠ '+e);}
  hideThinking();_streaming=false;if(btn)btn.disabled=false;return false;}
"""
