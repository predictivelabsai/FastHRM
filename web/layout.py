"""FastHRM 3-pane layout — emerald palette, SSE AI rail."""
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
.nav-icon{width:18px;display:inline-block;text-align:center;}
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
.sample-card::before{content:"💬";flex-shrink:0;} .sample-card:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-light);}
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
"""

NAV_ITEMS = [
    ("OVERVIEW", [("dashboard", "Dashboard", "📊", "/"), ("ai", "AI Assistant", "🤖", "/ai")]),
    ("PEOPLE", [("employees", "Employees", "👥", "/employees"),
                ("departments", "Departments", "🏢", "/departments")]),
    ("TIME", [("leave", "Leave", "🌴", "/leave"), ("attendance", "Attendance", "🕘", "/attendance")]),
    ("PAY", [("payroll", "Payroll", "💷", "/payroll")]),
    ("TALENT", [("platform", "Recruiting platform", "🧭", "/talent/platform"),
                ("jobs", "Requisitions", "📌", "/talent/jobs"),
                ("candidates", "Candidates", "🎯", "/talent/candidates"),
                ("offers", "Offers", "📨", "/talent/offers"),
                ("talent-analytics", "Analytics", "📈", "/talent/analytics")]),
    ("PERFORMANCE", [("goals", "Goals & OKRs", "🎯", "/performance/goals"),
                     ("feedback", "Feedback", "💬", "/performance/feedback"),
                     ("reviews", "Review cycles", "📝", "/performance/reviews"),
                     ("signals", "Signals", "📡", "/performance/signals")]),
    ("LIFECYCLE", [("onboarding", "Onboarding", "🚀", "/lifecycle/onboarding"),
                   ("changes", "Changes", "🔀", "/lifecycle/changes"),
                   ("separations", "Separations", "👋", "/lifecycle/separations"),
                   ("cases", "Cases", "🗂", "/lifecycle/cases"),
                   ("org", "Org chart", "🌳", "/lifecycle/org")]),
    ("SETTINGS", [("integrations", "Integrations", "🔌", "/settings/integrations"),
                  ("prompts", "AI Prompts", "✎", "/talent/prompts"),
                  ("roles", "Roles & access", "🔑", "/settings/roles")]),
    ("HELP", [("guide", "User Guide", "📖", "/guide"),
              ("developers", "Developers", "⌘", "/developers")]),
]
SAMPLE_QUESTIONS = ["Who's on leave today?", "Which team is biggest?", "How many leave requests are pending?"]


def topbar(env, user_email):
    import version
    right = Div(
        Button(NotStr("&laquo; Chat"), id="copilot-topbar-toggle", cls="btn", onclick="toggleCopilot()") if user_email else None,
        Span(env, cls="env-pill"),
        # Which build am I looking at? Answerable without opening a terminal.
        A(version.label(), href="/about", cls="ver-pill", title=version.detail()) if user_email else None,
        Span(user_email or "", style="color:var(--text-mute);font-size:12px;") if user_email else None,
        A("Logout", href="/logout", cls="btn") if user_email else None, cls="actions")
    return Div(Div(Span(cls="brand-dot"), Span("Fast", style="font-weight:800;"),
                   Span("HRM", style="color:var(--accent);font-weight:700;letter-spacing:.5px;"), cls="brand"),
               right, cls="topbar")


def left_pane(active):
    sections = []
    for name, items in NAV_ITEMS:
        links = [A(Span(icon, cls="nav-icon"), Span(label), href=href,
                   cls=f"nav-item {'active' if active == key else ''}") for key, label, icon, href in items]
        sections.append(
            Details(
                Summary(H4(name), Span(cls="nav-section-arrow", aria_hidden="true"),
                        cls="nav-section-toggle", aria_label=f"Expand or collapse {name.title()}"),
                Div(*links, cls="nav-section-items"),
                open=True, cls="nav-section", data_section=name.lower(),
            )
        )
    controls = Div(
        Button("<<", type="button", id="nav-collapse-all", title="Minimise all menu sections",
               aria_label="Minimise all menu sections"),
        Button(">>", type="button", id="nav-expand-all", title="Expand all menu sections",
               aria_label="Expand all menu sections"),
        cls="nav-section-controls",
    )
    return Div(controls, *sections, cls="left-pane")


def _sample_cards():
    cards = [Button(Span(q), cls="sample-card", onclick=f"fillChat({q!r});sendMessage(null);", title=q) for q in SAMPLE_QUESTIONS]
    return Div(Div(Span("Try asking:", cls="sample-cards-label")), Div(*cards), cls="sample-cards")


def right_pane_chat(thread_id):
    return Div(
        Div(H3("AI Assistant"),
            Div(Button("New", cls="btn", hx_get="/chat/new", hx_target="#chat-body", hx_swap="innerHTML"),
                Button(NotStr("&laquo;"), id="copilot-exp-btn", cls="copilot-exp", onclick="toggleExpand()"),
                Button(NotStr("&rsaquo;"), cls="copilot-min", onclick="toggleCopilot()"), cls="tabs"),
            cls="right-header"),
        Div(Div(P("Ask about headcount, leave or attendance — or use /headcount /leave /help.",
                  cls="chat-empty-hint"), id="chat-body", cls="chat-body"),
            Form(Input(type="hidden", name="thread_id", value=thread_id, id="thread-id"),
                 Div(Input(type="text", name="message", id="chat-input",
                           placeholder="Ask HR a question or /leave /help …", autocomplete="off"),
                     Button("Send", type="submit", cls="chat-send-btn", id="chat-send-btn"), cls="chat-input-row"),
                 onsubmit="return streamChat(event)", cls="chat-input"),
            _sample_cards(),
            style="display:flex;flex-direction:column;flex:1;overflow:hidden;"),
        cls="right-pane")


def page(active, env, user_email, thread_id, *content, right_override=None):
    right = right_override if right_override is not None else right_pane_chat(thread_id)
    return (Title("FastHRM"),
            Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
            Script(src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"),
            Style(LAYOUT_CSS),
            Div(topbar(env, user_email), left_pane(active), Div(*content, cls="center-pane"), right,
                Div(NotStr("&lsaquo; AI Assistant"), id="copilot-reopen", onclick="toggleCopilot()"), cls="app"),
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
  var tb=document.getElementById('copilot-topbar-toggle');if(tb){tb.innerHTML=col?'\\u00AB Chat':'Chat \\u203A';}}
function toggleCopilot(){var app=document.querySelector('.app');if(!app)return;app.classList.toggle('right-collapsed');
  if(app.classList.contains('right-collapsed'))app.classList.remove('right-expanded');
  try{localStorage.setItem('hrCollapsed',app.classList.contains('right-collapsed')?'1':'0');}catch(e){}_sync();}
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
  _thinker.el.innerHTML='<span class="dot"></span> Thinking…';cb.appendChild(_thinker.el);_scroll();}
function hideThinking(){if(_thinker){if(_thinker.el.parentNode)_thinker.el.parentNode.removeChild(_thinker.el);_thinker=null;}}
async function streamChat(ev){if(ev&&ev.preventDefault)ev.preventDefault();if(_streaming)return false;
  var input=document.getElementById('chat-input');var msg=input?input.value.trim():'';if(!msg)return false;
  _streaming=true;var btn=document.getElementById('chat-send-btn');if(btn)btn.disabled=true;
  addBubble('user',_esc(msg));input.value='';
  var tid=(document.getElementById('thread-id')||{}).value||'';var bubble=null,acc='';showThinking();
  try{var resp=await fetch('/chat/stream',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({message:msg,thread_id:tid})});
    if(!resp.ok){hideThinking();addBubble('assistant','Error: '+resp.status);_streaming=false;if(btn)btn.disabled=false;return false;}
    var reader=resp.body.getReader(),dec=new TextDecoder(),buf='';
    while(true){var r=await reader.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});
      var idx;while((idx=buf.indexOf('\\n\\n'))!==-1){var raw=buf.slice(0,idx);buf=buf.slice(idx+2);
        if(raw.indexOf('data: ')!==0)continue;var p={};try{p=JSON.parse(raw.slice(6));}catch(e){}
        if(p.token){if(acc===''){hideThinking();bubble=addBubble('assistant','');}acc+=p.token;bubble.innerHTML=_md(acc);_scroll();}
        else if(p.error){hideThinking();addBubble('assistant','⚠ '+p.error);}}}
  }catch(e){hideThinking();addBubble('assistant','⚠ '+e);}
  hideThinking();_streaming=false;if(btn)btn.disabled=false;return false;}
"""
