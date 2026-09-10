"""Public FastHRM landing, feature, and comparison pages."""
import json
from dataclasses import replace
from urllib.parse import quote

from fasthtml.common import *
import version

from .account_auth import AUTH_CSS, AUTH_JS, auth_modal
from .seo import seo_meta
from .design import (DESIGN_CSS, FONT_LINKS, fs_button, fs_footer,
                     fs_nav, fs_eyebrow, accent_style)
from .design.system import FASTHRM, MOBILE_NAV_JS
from .i18n import t

FAVICON = "data:image/svg+xml," + quote(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0b1d17"/><path fill="#c2f24f" d="M16 4 28 16 16 28 4 16Z"/><path fill="#0b1d17" d="M11 10h11v4h-7v3h6v4h-6v5h-4Z"/></svg>""",
    safe="",
)

FEATURE_CATALOG = (
    ("Core HR", "Employee records, departments, reporting lines and organisation data.", "/employees", True),
    ("Leave & attendance", "Leave balances, requests, approvals and daily attendance reporting.", "/leave", True),
    ("Palgalehed ja palgapäevad", "Täielikult ridade kaupa ettevalmistatud palgapäevad koos tööandja kulude ja uuesti ettevalmistamisega.", "/payroll", True),
    ("Recruiting ATS", "Requisitions, candidates, pipelines, scorecards, approvals and offers.", "/talent/jobs", True),
    ("Careers publishing", "Branded careers pages and individual, search-ready job specification pages.", None, True),
    ("Candidate CRM", "Talent pools, saved views, profiles, tags, tasks, search and bulk workflows.", "/talent/platform?section=operations", True),
    ("Communications", "Recruiting mailboxes, templates, scheduled messages, automations and surveys.", "/talent/platform?section=communications", True),
    ("Interview scheduling", "Availability, self-service booking and calendar/video integration contracts.", "/talent/platform?section=scheduling", True),
    ("Recruitment marketing", "Campaign pages, media, job-board distribution and social assets.", "/talent/platform?section=marketing", True),
    ("Recruitment analytics", "Funnels, attribution, benchmarks, experiments, dashboards and CSV exports.", "/talent/platform?section=analytics", True),
    ("Performance", "Goals, alignment, continuous feedback, reviews and explainable people signals.", "/performance/goals", True),
    ("Employee lifecycle", "Onboarding, employee changes, separations, cases and organisation planning.", "/lifecycle/onboarding", True),
    ("Enterprise recruiting", "Multi-brand sites, localisation, SSO/SCIM adapters and policy controls.", "/talent/platform?section=enterprise", True),
    ("AI for HR", "CV extraction, candidate ranking, screening controls, writing and grounded HR Q&A.", "/ai", True),
    ("Developer API", "Versioned OpenAPI resources for people, recruiting and enterprise integrations.", "/developers", True),
    ("Expenses & travel", "Expense claims, employee advances, approvals and travel requests.", "/expenses", True),
    ("Shifts & time clocks", "Rostering, check-in/out, auto-attendance and location-aware time capture.", "/shifts", True),
    ("Benefits administration", "Benefit plans, eligibility, employee enrolment and employer contributions flow into pay runs.", "/benefits", True),
    ("Learning & development", "Learning plans, course tracking, certifications and skills development.", None, False),
    ("Workforce planning", "Budgeted positions, scenarios and approval-led headcount planning.", None, False),
    ("Employee self-service", "A dedicated employee portal for pay, leave, time, goals and onboarding.", "/me", True),
    ("Eesti seadusjärgne palk (TÖR, TSD)", "TÖR-i ja TSD ekspordid ning puhkuse- ja töövõimetustasu arvestus on kasutatavad koos palgapäevade ja palgalehtedega.", "/payroll", True),
    ("Live provider integrations", "Live credential checks and HRIS directory export are shipped; remaining adapters need partner approval.", "/settings/integrations", True),
    ("Granular RBAC & security", "Per-module roles with view and edit permissions are shipped in Settings.", "/settings/roles", True),
)


COMPARISON_TABLE_CSS = """
/* comparison table */
.ct-wrap{position:relative;overflow-x:auto;border:1px solid var(--line);border-radius:18px;background:var(--card);box-shadow:var(--shadow-sm);padding-inline:8px;scrollbar-gutter:stable}
.ct-wrap::after{content:"";position:absolute;z-index:4;top:0;right:0;bottom:0;width:34px;pointer-events:none;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--card) 92%,transparent));opacity:1;transition:opacity var(--step-fast)}
.ct-wrap.is-at-end::after{opacity:0}
.ct-scroll-hint{position:absolute;right:8px;bottom:10px;z-index:5;width:18px;height:18px;pointer-events:none;opacity:.7}
.ct-scroll-hint::before{content:"";display:block;width:8px;height:8px;border-top:2px solid var(--accent-strong);border-right:2px solid var(--accent-strong);transform:rotate(45deg)}
.ct-wrap.is-at-end .ct-scroll-hint{opacity:0}
.ct-wrap:focus-visible{outline:2.5px solid var(--accent-strong);outline-offset:4px}
.ct{width:100%;border-collapse:collapse;min-width:820px}
.ct th,.ct td{padding:14px 14px;text-align:center;border-top:1px solid var(--line);font-size:14px}
.ct thead th{border-top:0;font-family:var(--font-display);font-weight:700;padding:20px 14px;color:var(--text)}
.ct .ct-feat{position:sticky;left:0;z-index:3;text-align:left;font-family:var(--font-body);font-weight:600;font-size:14px;color:var(--text);white-space:nowrap;background-color:var(--card);box-shadow:8px 0 12px -8px rgba(11,29,23,.18);border-right:1px solid var(--line)}
.ct th.ct-feat{font-size:16px}
.ct thead .ct-feat{z-index:6}
.ct-fh{background:color-mix(in srgb,var(--accent) 14%,var(--card))}
.ct thead .ct-fh{border-radius:12px 12px 0 0}
.ct thead .ct-fh span{display:block;font-family:var(--font-display);font-weight:700;font-size:16px;
  letter-spacing:normal;text-transform:none;color:var(--text);margin-top:3px}
.ct-mark{font-size:17px;font-weight:800;line-height:1}
.ct-yes{color:var(--accent-strong)}
.ct-soon{color:#8a5a16}
.ct-no{color:#8f3028}
.ct-pricerow td{font-family:var(--font-display);font-weight:800;background:var(--paper);border-top:2px solid var(--line)}
.ct-pricerow .ct-fh{background:color-mix(in srgb,var(--accent) 26%,var(--card));color:var(--ink);border-radius:0 0 12px 12px}
.ct-foot{display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px;margin-top:18px;color:var(--muted);font-size:13px}
.ct-legend{display:flex;gap:16px;flex-wrap:wrap}
.ct-legend-item{display:inline-flex;align-items:center;gap:6px}
.ct-cta{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:4px 0;margin-left:auto;color:var(--accent-strong);font-weight:700;text-decoration:none;white-space:nowrap}
.ct-cta:hover{text-decoration:underline}

"""


LANDING_CSS = """
/* ---------- hero (dark) ---------- */
.lh-hero{background:radial-gradient(120% 120% at 82% -10%,var(--ink-3) 0%,var(--ink) 46%,#081611 100%);
  color:var(--on-ink);position:relative;overflow:hidden}
.lh-hero::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(60% 40% at 50% 6%,color-mix(in srgb,var(--accent) 16%,transparent),transparent 70%)}
.lh-hero-inner{position:relative;z-index:1;text-align:center;padding-block:clamp(56px,9vw,104px) 0;max-width:920px;margin:0 auto}
.lh-hero h1{font-size:clamp(40px,6.4vw,74px);font-weight:800;line-height:1.04;margin:22px auto 0;max-width:16ch}
.lh-hi{color:var(--accent)}
.lh-sub{color:var(--on-ink-muted);font-size:clamp(16px,2vw,20px);line-height:1.6;max-width:60ch;margin:22px auto 0}
.lh-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin:32px 0 16px}
.lh-trust{color:var(--on-ink-muted);font-size:13px;font-weight:600;letter-spacing:.02em}
.lh-hero-inner .fs-eyebrow{justify-content:center}

/* ---------- dashboard mockup ---------- */
.lh-mock-wrap{max-width:1060px;margin:clamp(40px,6vw,64px) auto -90px;padding:0 clamp(18px,4vw,40px);position:relative;z-index:2}
.lh-mock{background:var(--card);border:1px solid var(--line);border-radius:16px;
  box-shadow:var(--shadow-lg);overflow:hidden;color:var(--text);text-align:left}
.lh-mock-bar{display:flex;align-items:center;gap:7px;padding:12px 16px;border-bottom:1px solid var(--line);background:var(--paper)}
.lh-dot{width:11px;height:11px;border-radius:50%;background:#d7d3c6}
.lh-mock-url{margin-left:12px;font-size:12px;color:var(--muted);font-weight:600}
.lh-mock-body{display:grid;grid-template-columns:230px minmax(0,1fr) 260px;min-height:430px}
.lh-appbar{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 14px;border-bottom:1px solid var(--line);background:#fff}
.lh-app-brand{display:flex;align-items:center;gap:6px;font-family:var(--font-display);font-size:13px;font-weight:800}
.lh-app-dot{width:7px;height:7px;border-radius:50%;background:#3da46c}
.lh-app-brand-fast{color:var(--accent-strong)}
.lh-app-brand-hrm{color:var(--ink)}
.lh-app-meta{display:flex;align-items:center;gap:7px;font-size:9px;font-weight:750;white-space:nowrap}
.lh-badge{padding:4px 7px;border-radius:999px;background:#e9f7ef;color:#24704a;letter-spacing:.08em}
.lh-version{padding:4px 7px;border-radius:999px;background:var(--paper-2);color:var(--muted)}
.lh-logout{padding:4px 8px;border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--muted);font:inherit}
.lh-side{background:color-mix(in srgb,var(--paper) 72%,var(--card));border-right:1px solid var(--line);padding:13px 10px;overflow:hidden}
.lh-side-group{margin-bottom:9px}
.lh-side-label{display:block;padding:0 8px 4px;color:#89968d;font-size:7px;font-weight:800;letter-spacing:.13em}
.lh-side a{display:flex;align-items:center;gap:7px;color:#55625b;font-size:9px;font-weight:650;padding:4px 8px;border-left:3px solid transparent;text-decoration:none;white-space:nowrap}
.lh-side a span{font-size:11px;line-height:1}
.lh-side a.on{background:#e6f5eb;color:#207248;border-left-color:#43a66b}
.lh-main{padding:17px 18px;background:#fff;min-width:0}
.lh-hello{font-family:var(--font-display);font-weight:800;font-size:17px}
.lh-hello-sub{color:var(--muted);font-family:var(--font-body);font-weight:500;font-size:10px;display:block;margin-top:2px}
.lh-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:15px 0}
.lh-kpi{border:1px solid var(--line);padding:9px 10px;min-width:0}
.lh-kpi.green{border-right-color:#43a66b}.lh-kpi.red{border-right-color:#d46b67}
.lh-kpi small{display:block;color:var(--muted);font-size:7px;font-weight:800;letter-spacing:.07em}
.lh-kpi b{font-family:var(--font-display);font-weight:800;font-size:20px;display:block;margin-top:4px}
.lh-kpi em{font-style:normal;color:var(--muted);font-size:8px;white-space:nowrap}
.lh-panels{display:grid;grid-template-columns:1.08fr 1fr;gap:10px}
.lh-panel{border:1px solid var(--line);padding:11px;min-width:0}
.lh-panel-title{font-family:var(--font-display);font-size:11px;font-weight:700;line-height:1.04;margin:0 0 10px}
.lh-bar{display:grid;grid-template-columns:74px 1fr 16px;align-items:center;gap:6px;margin:7px 0;font-size:8px;color:var(--muted)}
.lh-bar i{height:5px;background:#59b47d;border-radius:0 4px 4px 0;display:block}
.lh-bar b{font-size:8px;color:var(--ink);text-align:right}
.lh-row{display:flex;align-items:center;gap:6px;padding:7px 0;border-top:1px solid var(--line);font-size:8px;white-space:nowrap}
.lh-row:first-of-type{border-top:0}
.lh-row-txt{min-width:0;overflow:hidden;text-overflow:ellipsis}
.lh-row-txt b{display:block;font-weight:700;overflow:hidden;text-overflow:ellipsis}
.lh-row-txt small{display:block;color:var(--muted);font-size:8px}
.lh-tag{margin-left:auto;flex:none;font-size:7px;font-weight:800;padding:3px 5px;border-radius:999px;background:#eaf7ef;color:#28784e}
.lh-tag.sick{background:#fff0ef;color:#ba5b58}
.lh-ai{border-left:1px solid var(--line);padding:17px 14px;background:var(--paper-2);display:flex;flex-direction:column;min-width:0}
.lh-ai-title{font-family:var(--font-display);font-size:14px;font-weight:700;line-height:1.04;margin:0 0 4px}.lh-ai p{color:var(--muted);font-size:9px;line-height:1.4;margin:0 0 13px}
.lh-chips{display:flex;flex-wrap:wrap;gap:5px}.lh-chip{border:1px solid #cfe5d6;border-radius:999px;padding:5px 7px;color:#347555;background:#f6fcf8;font-size:8px}
.lh-chat{display:flex;gap:5px;margin-top:auto}.lh-chat input{min-width:0;width:100%;border:1px solid var(--line);padding:6px 7px;font:inherit;font-size:8px;background:#fff}.lh-chat button{border:0;background:#3da46c;color:#fff;padding:0 8px;font-family:var(--font-body);font-size:8px;font-weight:800}

/* ---------- light sections ---------- */
.lh-sec{padding:clamp(70px,9vw,120px) 0}
.lh-sec.pad-top{padding-top:clamp(72px,9vw,110px)}
.lh-alt{background:var(--paper-2)}
.lh-head{max-width:640px;margin-bottom:clamp(30px,4vw,48px)}
.lh-head h2{font-size:clamp(28px,4vw,40px);margin:14px 0 12px}
.lh-head p{color:var(--muted);font-size:clamp(16px,1.6vw,18px)}
.lh-features-head{display:grid;grid-template-columns:.85fr 1.15fr;gap:clamp(30px,5vw,64px);align-items:end;max-width:none}
.lh-features-head .lh-head{margin-bottom:0}
.lh-features-head>p{margin:0 0 12px;max-width:58ch}
.lh-head.center{max-width:680px;margin-left:auto;margin-right:auto;text-align:center}
.lh-head.center .fs-eyebrow{justify-content:center}
.lh-real-demo-frame{max-width:980px;margin:0 auto;border:1px solid var(--line);border-radius:var(--radius-lg);
  background:var(--card);box-shadow:var(--shadow-md);overflow:hidden}
.lh-real-demo-frame .lh-mock-bar{padding:12px 16px}
.lh-real-demo-body{padding:10px;background:var(--paper-2);border-top:1px solid var(--line)}
.lh-real-demo-body img{width:100%;height:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}
.lh-suite{background:var(--paper-2);border-block:1px solid var(--line);padding:27px 0}
.lh-suite-inner{display:flex;align-items:center;justify-content:space-between;gap:24px}
.lh-suite-label{color:var(--muted);font-size:12px;font-weight:800;letter-spacing:normal;max-width:34ch;text-align:center}
.lh-suite-logos{display:flex;align-items:center;justify-content:flex-end;gap:10px 18px;flex-wrap:wrap;color:var(--muted);font-family:var(--font-display);font-size:15px;font-weight:700;letter-spacing:-.02em}
.lh-suite-logos span{font-size:15px}

.lh-feats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.lh-feat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 24px;
  transition:transform var(--step-fast),box-shadow var(--step-fast)}
.lh-feat:hover{transform:translateY(-3px);box-shadow:var(--shadow-md)}
.lh-feat h3{margin-bottom:8px}
.lh-feat p{color:var(--muted);font-size:15px}
.lh-feat i{display:grid;place-items:center;width:40px;height:40px;border-radius:11px;margin-bottom:16px;
  background:var(--ink);color:var(--accent);font-style:normal;font-weight:800;font-size:14px;
  letter-spacing:.02em;font-family:var(--font-display)}

/* statutory, asymmetric split */
.lh-stat{display:grid;grid-template-columns:.85fr 1.15fr;gap:clamp(30px,5vw,64px);align-items:start}
.lh-stat-list{display:grid;grid-template-columns:1fr 1fr;gap:2px 28px}
.lh-stat-item{padding:18px 0;border-top:1px solid var(--line)}
.lh-stat-item b{font-family:var(--font-display);font-size:16px;display:flex;align-items:center;gap:9px}
.lh-stat-item b::before{content:"";width:9px;height:9px;border-radius:2px;background:var(--accent-strong)}
.lh-stat-item p{color:var(--muted);font-size:14px;margin-top:6px}

/* pricing */
.lh-prices{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.lh-price{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:30px}
.lh-price.feature{background:var(--ink);color:var(--on-ink);border-color:var(--ink)}
.lh-price .fs-eyebrow{color:var(--accent-strong)}
.lh-price.feature .fs-eyebrow{color:var(--accent)}
.lh-price h3{margin:12px 0 4px}
.lh-price .amt{font-family:var(--font-display);font-weight:800;font-size:40px;letter-spacing:-.03em;margin:8px 0 14px}
.lh-price.feature .amt .per{color:var(--accent)}
.lh-price p{color:var(--muted);font-size:15px}
.lh-price.feature p{color:var(--on-ink-muted)}

/* compare teaser */
.lh-cmp{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:clamp(30px,5vw,52px);
  display:grid;grid-template-columns:1fr auto;align-items:center;gap:30px}
.lh-cmp-names{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.lh-cmp-names span{border:1px solid var(--line);border-radius:999px;padding:7px 13px;font-size:13px;font-weight:600;color:var(--muted)}

""" + COMPARISON_TABLE_CSS + """
/* faq */
.lh-faqs{max-width:820px}
.lh-faq{border-top:1px solid var(--line);padding:24px 0}
.lh-faq:last-child{border-bottom:1px solid var(--line)}
.lh-faq h3{margin-bottom:8px}
.lh-faq p{color:var(--muted);font-size:16px;max-width:70ch}

/* cta band */
.lh-ctaband{background:var(--ink);color:var(--on-ink);border-radius:24px;
  padding:clamp(44px,7vw,80px) clamp(24px,5vw,64px);text-align:center;position:relative;overflow:hidden}
.lh-ctaband::before{content:"";position:absolute;inset:0;
  background:radial-gradient(70% 120% at 50% 0%,color-mix(in srgb,var(--accent) 18%,transparent),transparent 60%)}
.lh-ctaband>*{position:relative}
.lh-ctaband h2{font-size:clamp(28px,4vw,40px)}
.lh-ctaband p{color:var(--on-ink-muted);font-size:18px;margin:16px auto 30px;max-width:52ch}
.lh-ctaband .lh-actions{margin-bottom:0}

@media(max-width:900px){
  .lh-feats{grid-template-columns:1fr 1fr}
  .lh-stat,.lh-cmp,.lh-features-head{grid-template-columns:1fr}
  .lh-suite-inner{align-items:flex-start;flex-direction:column;gap:12px}
  .lh-mock-body{grid-template-columns:190px minmax(0,1fr)}
  .lh-ai{display:none}
}
@media(max-width:680px){
  .lh-feats,.lh-prices,.lh-panels,.lh-stat-list{grid-template-columns:1fr}
  .lh-kpis{grid-template-columns:1fr 1fr}
  .lh-mock-body{grid-template-columns:78px minmax(0,1fr)}
  .lh-side{padding-inline:5px}
  .lh-side-label{padding-inline:4px;font-size:6px}
  .lh-side a{padding:5px 4px;font-size:8px;gap:4px;white-space:normal}
  .lh-side a span{font-size:10px}
  .lh-main{padding:13px 10px}
  .lh-kpi b{font-size:16px}
  .lh-kpi em{font-size:7px}
  .lh-panels{grid-template-columns:1fr}
  .lh-mock-wrap{margin-bottom:-60px}
}
@media(max-width:760px){
.lh-hero-inner .fs-eyebrow,.lh-head .fs-eyebrow{font-size:12px}
  .lh-trust,.lh-suite-label,.ct-foot{font-size:14px}
  .lh-mock-wrap{padding-inline:12px}
  .lh-mock-bar{padding:10px 12px}
  .lh-mock-url{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .lh-appbar{min-width:0;padding:10px}
  .lh-app-meta{min-width:0;overflow:hidden}
  .lh-mock-secondary{display:none}
  .lh-main{padding:16px 12px}
  .lh-hello{font-size:20px}
  .lh-hello-sub{font-size:12px}
  .lh-kpi{padding:11px 10px}
  .lh-kpi small{font-size:10px}
  .lh-kpi b{font-size:22px}
  .lh-kpi em{font-size:10px;white-space:normal}
  .lh-panel{padding:12px}
  .lh-panel-title{font-size:14px}
  .lh-bar{grid-template-columns:68px minmax(0,1fr) 18px;font-size:11px;gap:5px}
  .lh-bar b{font-size:11px}
  .lh-row{font-size:11px;white-space:normal;align-items:flex-start}
  .lh-row-txt small{font-size:10px}
  .lh-tag{font-size:9px}
  .lh-actions .fs-btn{min-height:44px}
}
"""


TABLE_SCROLL_JS = """
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.ct-wrap').forEach(function (wrap) {
    function updateHint() {
      wrap.classList.toggle('is-at-end', wrap.scrollLeft + wrap.clientWidth >= wrap.scrollWidth - 1);
    }
    wrap.addEventListener('scroll', updateHint, {passive: true});
    window.addEventListener('resize', updateHint);
    updateHint();
  });
});
"""


def _lang_switch(lang: str, path: str = "/"):
    return Div(
        A("ET", href=f"{path}?lang=et", cls="active" if lang == "et" else ""),
        A("EN", href=f"{path}?lang=en", cls="active" if lang == "en" else ""),
        cls="fs-lang",
    )


# Estonian HR competitors compared on the landing page. States per row are ordered
# (Persona, Wemply, HRM4Baltics, hours24, Yester, FastHRM).
# Competitor states reflect public information (see docs footnote) and stay honest,
# where we are behind today, we say "soon" rather than overclaim.
CMP_PRODUCTS = ("FastHR", "Persona", "Wemply", "HRM4Baltics", "hours24", "Yester")
CMP_ROWS = (
    ("core",        ("yes", "yes", "yes", "yes", "yes", "yes")),
    ("leave",       ("yes", "yes", "yes", "yes", "yes", "yes")),
    ("time",        ("yes", "yes", "yes", "yes", "yes", "yes")),
    ("shifts",      ("yes", "yes", "yes", "yes", "yes", "yes")),
    ("epayroll",    ("yes", "yes", "yes", "yes", "no",  "yes")),
    ("expenses",    ("yes", "yes", "yes", "yes", "no",  "yes")),
    ("selfservice", ("yes", "yes", "yes", "yes", "yes", "yes")),
    ("ats",         ("yes", "no",  "no",  "no",  "no",  "no")),
    ("perf",        ("yes", "no",  "no",  "no",  "no",  "no")),
    ("ai",          ("yes", "no",  "no",  "no",  "yes", "no")),
    ("api",         ("yes", "no",  "yes", "no",  "no",  "no")),
    ("oss",         ("yes", "no",  "no",  "no",  "no",  "no")),
    ("selfhost",    ("yes", "no",  "no",  "no",  "no",  "no")),
)
CMP_GLYPH = {"yes": "✓", "soon": "◐", "no": "✕"}

GLOBAL_PRODUCTS = ("FastHR", "Gusto", "BambooHR", "Rippling", "Deel",
                   "Zoho People", "Odoo HR")
GLOBAL_ROW_STATES = {
    "core": ("yes", "yes", "yes", "yes", "yes", "yes", "yes"),
    "leave": ("yes", "yes", "yes", "yes", "yes", "yes", "yes"),
    "time": ("yes", "yes", "yes", "yes", "yes", "yes", "yes"),
    "payroll": ("yes", "yes", "yes", "yes", "yes", "no", "yes"),
    "expenses": ("yes", "no", "no", "yes", "yes", "no", "yes"),
    "selfservice": ("yes", "yes", "yes", "yes", "yes", "yes", "yes"),
    "ats": ("yes", "no", "yes", "no", "no", "no", "yes"),
    "perf": ("yes", "no", "yes", "yes", "no", "yes", "yes"),
    "ai": ("yes", "no", "no", "yes", "no", "no", "no"),
    "api": ("yes", "yes", "yes", "yes", "yes", "yes", "soon"),
    "oss": ("yes", "no", "no", "no", "no", "no", "soon"),
    "selfhost": ("yes", "no", "no", "no", "no", "no", "soon"),
}
GLOBAL_ROWS = tuple(GLOBAL_ROW_STATES.items())

COMPARE_TOGGLE_JS = """
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-compare-toggle]').forEach(function (toggle) {
    var root = toggle.closest('[data-compare-switcher]');
    var panels = root.querySelectorAll('[data-compare-panel]');
    toggle.addEventListener('click', function () {
      var selected = toggle.getAttribute('data-compare-toggle');
      root.querySelectorAll('[data-compare-toggle]').forEach(function (button) {
        var active = button.getAttribute('data-compare-toggle') === selected;
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      panels.forEach(function (panel) {
        var active = panel.getAttribute('data-compare-panel') === selected;
        panel.hidden = !active;
        panel.setAttribute('aria-hidden', active ? 'false' : 'true');
      });
    });
  });
});
"""


def _glyph_compare_table(c, rows, products, labels, prices, legend,
                         items=None, heading=None, sub=None, note=None,
                         cta=None, table_label=None, caption=None):
    prods = list(products)

    headers = [Th(caption or "", cls="ct-feat")]
    for i, product in enumerate(prods):
        headers.append(Th(Span(product, cls="pg-name"),
                          cls="ct-fh" if i == 0 else ""))

    body = []
    for key, states in rows:
        cells = []
        for i, s in enumerate(states):
            title = legend[s]
            cells.append(Td(Span(CMP_GLYPH[s], cls=f"ct-mark ct-{s}", title=title,
                                 **{"aria-label": title}),
                            cls="ct-fh" if i == 0 else ""))
        body.append(Tr(Td(labels[key], cls="ct-feat"), *cells))

    price_row = Tr(
        Td(c["cmp2_price_label"], cls="ct-feat"),
        *[Td(v, cls="ct-fh" if i == 0 else "")
          for i, v in enumerate(prices)],
        cls="ct-pricerow")

    legend_row = Div(
        *[Span(Span(CMP_GLYPH[k], cls=f"ct-mark ct-{k}"), " ", lbl, cls="ct-legend-item")
          for k, lbl in legend.items()],
        cls="ct-legend")

    return Div(
        Div(fs_eyebrow(c["cmp2_eyebrow"]), H2(heading or c["cmp2_h2"]),
            P(sub or c["cmp2_sub"]), cls="lh-head") if heading or not items else None,
        Div(Table(Caption(caption) if caption else None, Thead(Tr(*headers)),
                  Tbody(*body, price_row), cls="ct"),
            Span(cls="ct-scroll-hint", aria_hidden="true"), cls="ct-wrap", tabindex="0",
            role="region", aria_label=table_label or c["cmp2_table_label"]),
        Div(legend_row, Span(note or c["cmp2_note"]),
            A(cta or c["cmp2_cta"], href="/compare", cls="ct-cta") if cta is not False else None,
            cls="ct-foot"),
        cls="fs-wrap")


def _compare_table(c):
    return _glyph_compare_table(
        c, CMP_ROWS, CMP_PRODUCTS, c["cmp2_labels"], c["cmp2_prices"],
        dict(c["cmp2_legend"]), heading=c["cmp2_h2"], sub=c["cmp2_sub"],
        note=c["cmp2_note"], cta=c["cmp2_cta"],
        table_label=c["cmp2_table_label"], caption=None,
    )


def _global_compare_table(c, heading=None, include_heading=True, items=None):
    items = list(items or c["comparisons"])
    items.sort(key=lambda item: item["name"] != "FastHR")
    products = tuple(item["name"] for item in items)
    return _glyph_compare_table(
        c, GLOBAL_ROWS, products, c["cmp_global_labels"],
        [c["cmp2_prices"][0]] + [""] * (len(products) - 1),
        dict(c["cmp_global_legend"]), items=items,
        heading=heading or c["cmp_pg_global_heading"] if include_heading else None,
        sub=c["cmp_global_sub"] if include_heading else None,
        note=c["cmp_global_note"], cta=False,
        table_label=c["cmp_global_table_label"],
        caption=c["cmp_pg_caption"] if include_heading else None,
    )


def _dashboard_mock(c):
    """A light, brand-controlled view of the real FastHRM dashboard."""
    mock = c["dashboard_mock"]
    groups, bars, leave = mock["groups"], mock["bars"], mock["leave"]
    return Div(Div(
        Div(Span(cls="lh-dot"), Span(cls="lh-dot"), Span(cls="lh-dot"),
            Span("app.fasthr.eu/dashboard", cls="lh-mock-url"), cls="lh-mock-bar"),
        Div(
            Div(
            Div(Span(cls="lh-app-dot"), Span("Fast", cls="lh-app-brand-fast"), Span("HR", cls="lh-app-brand-hrm"),
                    cls="lh-app-brand"),
                 Div(Span("FASTR", cls="lh-badge"), Span(version.label(), cls="lh-version lh-mock-secondary"),
                    Button(mock["logout"], cls="lh-logout"), cls="lh-app-meta"),
                cls="lh-appbar"),
            Div(*[Div(Span(label, cls="lh-side-label"),
                      *[A(Span(icon), name, cls="on" if name == groups[0][1][0][1] else "")
                        for icon, name in items], cls="lh-side-group")
                for label, items in groups], cls="lh-side"),
            Div(
                Div(mock["dashboard"], Span(mock["dashboard_sub"], cls="lh-hello-sub"),
                    cls="lh-hello"),
                Div(
                    Div(Small(mock["headcount"]), B("64"), Em(mock["departments"]), cls="lh-kpi green"),
                    Div(Small(mock["present"]), B("56"), Em(mock["on_leave"]), cls="lh-kpi green"),
                    Div(Small(mock["attendance"]), B("89%"), Em(" "), cls="lh-kpi"),
                    Div(Small(mock["pending"]), B("10"), Em(mock["awaiting"]), cls="lh-kpi red"),
                    cls="lh-kpis"),
                Div(
                    Div(Div(mock["headcount_chart"], cls="lh-panel-title"),
                        *[Div(Span(name), I(style=f"width:{width}%"), B(str(count)), cls="lh-bar")
                          for name, count, width in bars], cls="lh-panel"),
                    Div(Div(mock["leave_requests"], cls="lh-panel-title"),
                        *[Div(Div(B(name), cls="lh-row-txt"),
                              Span(kind, cls=f"lh-tag {tone}"), Span(date), cls="lh-row")
                          for name, kind, date, tone in leave], cls="lh-panel"),
                    cls="lh-panels"),
                cls="lh-main"),
                Div(Div(mock["ai"], cls="lh-ai-title"), P(mock["ai_prompt"]),
                Div(Span(mock["chip_leave"], cls="lh-chip"),
                    Span(mock["chip_team"], cls="lh-chip"), cls="lh-chips"),
                Form(Input(placeholder=mock["ask"]), Button(mock["send"], type="submit"), cls="lh-chat"),
                cls="lh-ai"),
            cls="lh-mock-body"),
        cls="lh-mock", inert=True, aria_hidden="true"), cls="lh-mock-wrap")


def _landing_head(c):
    return Head(
        Title(c["meta_title"]), Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=c["meta_desc"]),
        *seo_meta(),
        Link(rel="icon", type="image/svg+xml", href=FAVICON),
        *FONT_LINKS,
        Style(DESIGN_CSS + LANDING_CSS + AUTH_CSS),
        accent_style(FASTHRM),
    )


def landing_page(open_auth=False, lang="et"):
    c = t(lang)
    product = replace(FASTHRM, tagline=c["foot_tagline"])
    nav = fs_nav(
        product,
        c["nav"],
        [_lang_switch(lang),
         Button(c["signin"], type="button", onclick="authOpen('login')", cls="fs-btn fs-btn-ghost")],
        menu_label=c["menu"],
    )

    hero = Section(
        Div(
            fs_eyebrow(c["hero_eyebrow"], on_ink=True),
            H1(c["hero_h1_a"], " ", Span(c["hero_h1_hi"], cls="lh-hi")),
            P(c["hero_sub"], cls="lh-sub"),
            Div(fs_button(c["hero_cta1"], variant="lime", size="lg", onclick="authOpen('register')"),
                fs_button(c["hero_cta2"], href="#demo", variant="ghost", size="lg"),
                cls="lh-actions"),
            P(c["hero_trust"], cls="lh-trust"),
            cls="lh-hero-inner fs-wrap",
        ),
        _dashboard_mock(c),
        cls="lh-hero",
    )

    logos = Section(Div(Span(c["logos_label"], cls="lh-suite-label"),
                        Div(*[Span(name) for name in
                              ["FastMail", "FastOffice", "FastDrive", "FastMeet", "FastAccounts", "FastBooks"]],
                            cls="fs-logos lh-suite-logos"),
                        cls="lh-suite-inner fs-wrap"), cls="lh-suite")

    features = Section(Div(
        Div(Div(fs_eyebrow(c["feat_eyebrow"]), H2(c["feat_h2"]), cls="lh-head"),
            P(c["feat_sub"]), cls="lh-features-head"),
        Div(*[Div(I(f"{i + 1:02d}"), H3(title), P(desc), cls="lh-feat")
              for i, (title, desc) in enumerate(c["features"])], cls="lh-feats"),
        cls="fs-wrap"), cls="lh-sec")

    demo = Section(Div(
        Div(H2(c["demo_h2"]), P(c["demo_sub"]), cls="lh-head center"),
        Div(
            Div(Span(cls="lh-dot"), Span(cls="lh-dot"), Span(cls="lh-dot"),
                Span("app.fasthr.eu/dashboard", cls="lh-mock-url"), cls="lh-mock-bar"),
            Div(Picture(
                Source(type="image/webp",
                       srcset=("/static/product-demo-880.webp 880w, "
                               "/static/product-demo-1100.webp 1100w"),
                       sizes="(min-width: 1100px) 1060px, 92vw"),
                Img(src="/static/product-demo.gif", alt=c["demo_alt"], loading="lazy",
                    decoding="async", width=1100, height=689),
            ), cls="lh-real-demo-body"),
            cls="lh-real-demo-frame"),
        cls="fs-wrap"), id="demo", cls="lh-sec")

    statutory = Section(Div(
        Div(
            Div(fs_eyebrow(c["stat_eyebrow"]), H2(c["stat_h2"]), P(c["stat_sub"]), cls="lh-head"),
            Div(*[Div(B(name), P(desc), cls="lh-stat-item") for name, desc in c["statutory"]],
                cls="lh-stat-list"),
            cls="lh-stat"),
        cls="fs-wrap"), cls="lh-sec lh-alt")

    pricing = Section(Div(
        Div(fs_eyebrow(c["price_eyebrow"]), H2(c["price_h2"]), P(c["price_sub"]), cls="lh-head center"),
        Div(
            *[Div(fs_eyebrow(eb), H3(title), Div(amt, cls="amt"), P(desc),
                  cls="lh-price feature" if i == 1 else "lh-price")
               for i, (eb, title, amt, desc) in enumerate(c["price_cards"])],
            cls="lh-prices"),
        P(c["price_example"], cls="lh-price-example"),
        cls="fs-wrap"), id="pricing", cls="lh-sec")

    estonia_active = lang == "et"
    estonia_table = Div(
        _glyph_compare_table(
            c, CMP_ROWS, CMP_PRODUCTS, c["cmp2_labels"], c["cmp2_prices"],
            dict(c["cmp2_legend"]), heading=c["cmp2_h2"], sub=c["cmp2_sub"],
            note=c["cmp2_note"], cta=c["cmp2_cta"],
            table_label=c["cmp2_table_label"],
        ), cls="lh-compare-panel", id="landing-compare-estonia",
        data_compare_panel="estonia", aria_hidden="false" if estonia_active else "true",
        hidden=not estonia_active)
    global_table = Div(
        _global_compare_table(c), cls="lh-compare-panel", id="landing-compare-global",
        data_compare_panel="global", aria_hidden="true" if estonia_active else "false",
        hidden=estonia_active)
    compare = Section(
        Div(
            H2(c["cmp_toggle_heading"], cls="sr-only"),
            Div(
                Button(c["cmp_toggle_estonia"], type="button",
                       data_compare_toggle="estonia", aria_pressed="true" if estonia_active else "false"),
                Button(c["cmp_toggle_global"], type="button",
                       data_compare_toggle="global", aria_pressed="false" if estonia_active else "true"),
                cls="lh-compare-tabs", role="group",
                aria_label=c["cmp_toggle_label"],
            ),
            estonia_table, global_table,
            cls="fs-wrap", data_compare_switcher="true",
        ), cls="lh-sec lh-alt lh-cmp-section")

    faq = Section(Div(
        Div(fs_eyebrow(c["faq_eyebrow"]), H2(c["faq_h2"]), cls="lh-head"),
        Div(*[Div(H3(q), P(a), cls="lh-faq") for q, a in c["faqs"]], cls="lh-faqs"),
        cls="fs-wrap"), cls="lh-sec lh-faq-section")

    cta = Section(Div(Div(
        H2(c["cta_h2"]), P(c["cta_sub"]),
        Div(fs_button(c["cta_btn"], variant="lime", size="lg", onclick="authOpen('register')"),
            fs_button(c["cta_btn2"], href=FASTHRM.github_url, variant="ghost", size="lg",
                      target="_blank", rel="noopener noreferrer"),
            cls="lh-actions"),
        cls="lh-ctaband"), cls="fs-wrap"), cls="lh-sec")

    footer = fs_footer(
        product,
        c["foot_cols"],
        c["foot_rights"],
        [version.label()],
    )

    return Html(
        _landing_head(c),
        Body(
            A("Skip to content", href="#main-content", cls="fs-skip"),
            nav,
            Script(MOBILE_NAV_JS),
            Script(TABLE_SCROLL_JS),
            Script(COMPARE_TOGGLE_JS),
            Main(hero, logos, features, demo, statutory, pricing, compare, faq, cta,
                 id="main-content"),
            footer,
            auth_modal("FastHR", lang=lang),
            Script(AUTH_JS),
            Script("document.addEventListener('DOMContentLoaded',()=>authOpen('login'));" if open_auth else ""),
        ),
        lang=c["html_lang"],
    )


PUBLIC_PAGE_CSS = """
.pg-page .fs-lang a.active{color:var(--ink)}
.pg-page .fs-nav.on-ink .fs-lang a.active{background:var(--accent);color:var(--ink)}
.pg-hero{background:var(--ink);color:var(--on-ink);padding:clamp(52px,8vw,96px) 0}
.pg-hero h1{font-size:clamp(38px,6vw,70px);max-width:19ch;margin:22px 0;font-weight:800;overflow-wrap:anywhere}
.pg-lede{max-width:65ch;color:var(--on-ink-muted);font-size:clamp(17px,2vw,20px)}
.pg-summary{display:flex;flex-wrap:wrap;gap:10px;margin-top:30px}
.pg-chip{border:1px solid var(--ink-line);border-radius:var(--radius-pill);
  padding:9px 15px;font-size:14px;color:var(--on-ink-muted)}
.pg-chip strong{color:var(--accent)}
.pg-section{padding-top:clamp(40px,6vw,72px);padding-bottom:clamp(40px,6vw,72px)}
.pg-heading{display:grid;grid-template-columns:1fr 1.2fr;gap:24px;margin-bottom:32px;align-items:start}
.pg-heading h2,.pg-faq h2{font-size:clamp(28px,4vw,40px)}
.pg-heading p{color:var(--muted);max-width:65ch}
.pg-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.pg-card{padding:26px;border:1px solid var(--line);border-radius:var(--radius);
  background:var(--card);display:flex;flex-direction:column;min-width:0}
.pg-card.soon{background:var(--paper)}
.pg-meta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;align-items:center}
.pg-status{padding:5px 10px;border-radius:var(--radius-pill);font-size:12px;font-weight:700;
  background:var(--accent);color:var(--ink)}
.pg-card.soon .pg-status{background:var(--paper-2);color:var(--muted)}
.pg-price{color:var(--accent-strong);font-size:13px;font-weight:700}
.pg-card h3{margin:24px 0 10px}
.pg-card p{color:var(--muted);font-size:15px}
.pg-card a{align-self:flex-start;margin-top:auto;padding-top:20px;
  color:var(--accent-strong);font-weight:700;text-underline-offset:4px}
.pg-note{border-top:1px solid var(--line);margin-top:32px;padding-top:24px;color:var(--muted);max-width:70ch}
.pg-note strong{color:var(--text)}
.pg-compare{min-width:1150px;table-layout:fixed}
.pg-compare caption{text-align:left;padding:20px;color:var(--muted);font-size:13px}
.pg-compare th,.pg-compare td{vertical-align:top;text-align:left;line-height:1.5;padding-inline:10px}
.pg-compare .ct-feat{width:190px;min-width:190px;white-space:normal}
.pg-compare thead th:not(.ct-feat){min-width:190px}
.pg-compare thead th{font-size:18px}
.pg-compare .pg-name{display:inline-flex;align-items:center;min-height:40px;padding-block:8px;color:var(--text)}
.pg-compare-section h2{font-size:clamp(28px,4vw,40px);margin-bottom:22px}
.pg-compare .ct-pricerow th{background:var(--paper);border-top:2px solid var(--line)}
.pg-compare .ct-mark{display:inline-block;margin-right:7px}
.pg-compare .ct-no,.pg-legend .ct-no,.pg-mobile-row .ct-no{color:#8f3028}
.pg-compare .ct-soon,.pg-legend .ct-soon{color:#8a5a16}
.pg-faq{border-top:1px solid var(--line)}
.pg-faq-list{max-width:820px;margin-top:32px}
.pg-faq article{padding:24px 0;border-top:1px solid var(--line)}
.pg-faq h3{margin-bottom:12px}
.pg-faq p{color:var(--muted);max-width:70ch}
.lh-sec#pricing{padding-bottom:clamp(30px,5vw,56px)}
.lh-cmp-section{padding-top:clamp(30px,5vw,56px);padding-bottom:clamp(30px,5vw,56px)}
.lh-compare-tabs{display:inline-flex;gap:4px;margin-bottom:24px;padding:4px;border:1px solid var(--line);border-radius:var(--radius-pill);background:var(--card)}
.lh-compare-tabs button{min-height:44px;padding:8px 16px;border:0;border-radius:var(--radius-pill);background:transparent;color:var(--muted);font:inherit;font-weight:700;cursor:pointer}
.lh-compare-tabs button[aria-pressed="true"]{background:var(--ink);color:var(--on-ink)}
.lh-compare-tabs button:focus-visible{outline:2.5px solid var(--accent-strong);outline-offset:2px}
.lh-compare-panel[hidden]{display:none}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.lh-faq-section{padding-bottom:clamp(30px,5vw,56px)}
@media(max-width:900px){.pg-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){
  .pg-grid,.pg-heading{grid-template-columns:1fr}
  .pg-page .fs-nav-inner{height:auto;min-height:70px;flex-wrap:wrap;padding-top:12px;padding-bottom:12px}
  .pg-page .fs-nav-right{gap:8px;flex-wrap:wrap}
  .pg-page .fs-btn{padding:11px 15px}
}
@media(max-width:639px){
  body > main p{padding-inline:clamp(18px,4vw,40px)}
  .pg-compare-wrap{display:none}
  .pg-mobile-compare{display:grid;gap:14px}
  .pg-mobile-card{border:1px solid var(--line);border-radius:var(--radius);background:var(--card);padding:18px}
  .pg-mobile-card h3{margin:0 0 4px}
  .pg-name{display:inline-flex;align-items:center;padding-block:8px}
  .pg-mobile-row{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:12px;padding:10px 0;border-top:1px solid var(--line);line-height:1.4}
  .pg-mobile-row b{font-size:13px;color:var(--muted)}
   .pg-mobile-row span{font-size:14px}
   .pg-mobile-row .ct-mark{margin-right:5px}
   .pg-mobile-row .ct-no{color:#8f3028}
}
@media(min-width:640px){.pg-mobile-compare{display:none}}
"""


def public_head(c: dict, prefix: str, path: str, *structured_data,
                extra_css="", include_comparison_css=True, title=None,
                description=None):
    title = title or c[f"{prefix}_meta_title"]
    description = description or c[f"{prefix}_meta_desc"]
    return Head(
        Title(title), Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=description),
        *seo_meta(path=path, title=title, description=description),
        *structured_data,
        Link(rel="icon", type="image/svg+xml", href=FAVICON),
        *FONT_LINKS,
        Style(DESIGN_CSS + extra_css
              + (COMPARISON_TABLE_CSS if include_comparison_css else "")
              + PUBLIC_PAGE_CSS),
        accent_style(FASTHRM),
    )


def public_nav(c: dict, path: str):
    return Div(
        fs_nav(
            FASTHRM, c["nav"],
            [_lang_switch(c["html_lang"], path),
             fs_button(c["signin"], href=f"/login?lang={c['html_lang']}",
                       variant="ghost")],
            menu_label=c["menu"],
        ),
        Script(MOBILE_NAV_JS),
    )


def public_footer(c: dict):
    return fs_footer(
        replace(FASTHRM, tagline=c["foot_tagline"]),
        c["foot_cols"], c["foot_rights"],
        [version.label()],
    )


# Compatibility aliases for existing public page call sites.
_page_head = public_head
_page_nav = public_nav
_page_footer = public_footer


def _page_hero(c: dict, prefix: str, chips):
    return Section(Div(
        fs_eyebrow(c[f"{prefix}_eyebrow"], on_ink=True),
        H1(c[f"{prefix}_h1"]),
        P(c[f"{prefix}_lede"], cls="pg-lede"),
        Div(*[Span(Strong(value), " ", label, cls="pg-chip")
              for value, label in chips], cls="pg-summary"),
        cls="fs-wrap"), cls="pg-hero")


def features_page(lang: str = "et"):
    c = t(lang)
    available = sum(1 for feature in FEATURE_CATALOG if feature[3])
    coming = len(FEATURE_CATALOG) - available
    cards = []
    for name, description, href, implemented in FEATURE_CATALOG:
        if name == "Palgalehed ja palgapäevad":
            name, description = c["feat_payroll_workflow_name"], c["feat_payroll_workflow_desc"]
        elif name == "Eesti seadusjärgne palk (TÖR, TSD)":
            name, description = c["feat_payroll_statutory_name"], c["feat_payroll_statutory_desc"]
        action = A(c["feat_pg_open"], href=href) if href else None
        cards.append(Article(
            Div(
                Span(c["feat_pg_status_avail"] if implemented
                     else c["feat_pg_status_soon"], cls="pg-status"),
                Span(c["feat_pg_free"], cls="pg-price"),
                cls="pg-meta",
            ),
            H3(name, lang="en"), P(description, lang="en"), action,
            cls="pg-card" + ("" if implemented else " soon"),
        ))
    hero = _page_hero(c, "feat_pg", [
        (str(available), c["feat_pg_chip_avail"]),
        (str(coming), c["feat_pg_chip_soon"]),
        (c["feat_pg_chip_free_s"], c["feat_pg_chip_free"]),
    ])
    catalogue = Section(
        Div(H2(c["feat_pg_cat_h"]), P(c["feat_pg_cat_p"]), cls="pg-heading"),
        Div(*cards, cls="pg-grid"),
        P(Strong(c["feat_pg_note_s"]), c["feat_pg_note"], cls="pg-note"),
        cls="pg-section fs-wrap",
    )
    return Html(
        _page_head(c, "feat_pg", "/features"),
        Body(A("Skip to content", href="#main-content", cls="fs-skip"),
             _page_nav(c, "/features"), Main(hero, catalogue, id="main-content"),
             _page_footer(c),
             cls="pg-page"),
        lang=c["html_lang"],
    )


def comparison_page(lang: str = "et"):
    c = t(lang)
    faq_schema = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
            for question, answer in c["comparison_faqs"]
        ],
    }
    list_schema = {
        "@context": "https://schema.org", "@type": "ItemList", "name": "FastHR alternatives comparison",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["name"]}
            for index, item in enumerate(c["comparisons"], 1)
        ],
    }
    return Html(
        _page_head(
            c, "cmp_pg", "/compare",
            Script(NotStr(json.dumps(faq_schema, separators=(",", ":"))),
                   type="application/ld+json"),
            Script(NotStr(json.dumps(list_schema, separators=(",", ":"))),
                   type="application/ld+json"),
        ),
        Body(
            A("Skip to content", href="#main-content", cls="fs-skip"),
            _page_nav(c, "/compare"),
            Script(TABLE_SCROLL_JS),
            Main(
                _page_hero(c, "cmp_pg", c["cmp_pg_chips"]),
                _glyph_compare_table(
                    c, CMP_ROWS, CMP_PRODUCTS, c["cmp2_labels"], c["cmp2_prices"],
                    dict(c["cmp2_legend"]), items=c["comparison_estonia"],
                    heading=c["cmp_pg_estonia_heading"], sub=c["cmp2_sub"],
                    note=c["cmp2_note"], cta=False,
                    table_label=c["cmp2_table_label"],
                    caption=c["cmp_pg_caption"],
                ),
                _global_compare_table(c, c["cmp_pg_global_heading"]),
                Section(
                    H2(c["cmp_pg_faq_h"]),
                    Div(*[Article(H3(question), P(answer))
                          for question, answer in c["comparison_faqs"]],
                        cls="pg-faq-list", lang=c["html_lang"]),
                    cls="pg-faq pg-section fs-wrap",
                ),
                id="main-content",
            ),
            _page_footer(c),
            cls="pg-page",
        ),
        lang=c["html_lang"],
    )
