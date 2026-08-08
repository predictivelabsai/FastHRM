"""Public FastHRM product landing page."""
from urllib.parse import quote

from fasthtml.common import *

from .account_auth import AUTH_CSS, AUTH_JS, auth_modal
from .seo import seo_meta

ACCENT = "#0891b2"
TINT = "#ecfeff"
FAVICON = "data:image/svg+xml," + quote(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0891b2"/><path fill="white" d="M16 4 28 16 16 28 4 16Z"/><path fill="#0891b2" d="M11 10h11v4h-7v3h6v4h-6v5h-4Z"/></svg>""",
    safe="",
)

CSS = """
:root{--accent:#0891b2;--tint:#ecfeff;--ink:#111827;--muted:#667085;--line:#e7eaf0}
*{box-sizing:border-box} body{margin:0;background:#fff;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
.lp-nav{height:68px;display:flex;align-items:center;justify-content:space-between;max-width:1180px;margin:auto;padding:0 24px;border-bottom:1px solid var(--line)}
.lp-brand{display:flex;align-items:center;gap:10px;font-weight:750;color:var(--ink);text-decoration:none} .lp-mark{width:30px;height:30px;border-radius:10px;background:var(--accent);display:grid;place-items:center;color:white}
.lp-nav-actions{display:flex;align-items:center;gap:18px} .lp-nav-link{color:var(--muted);text-decoration:none;font-size:14px;font-weight:650} .lp-nav-link:hover{color:var(--accent)}
.lp-signin,.lp-primary{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:10px 17px;text-decoration:none;font-weight:650;font-size:14px;cursor:pointer} .lp-signin{border:1px solid var(--line);color:var(--ink);background:white} .lp-primary{background:var(--accent);color:white;border:0}
.lp-hero{max-width:1180px;margin:auto;padding:104px 24px 76px} .lp-kicker{color:var(--accent);font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.16em}
.lp-hero h1{font-size:clamp(42px,7vw,78px);line-height:1.02;letter-spacing:-.055em;max-width:920px;margin:22px 0} .lp-lede{font-size:20px;line-height:1.65;color:var(--muted);max-width:720px}
.lp-actions{display:flex;gap:12px;margin-top:32px;flex-wrap:wrap} .lp-secondary{color:var(--ink);font-weight:650;text-decoration:none;padding:10px 4px}
.lp-demo{max-width:960px;margin:0 auto 76px;padding:0 24px} .lp-demo-frame{padding:10px;background:#fff;border:1px solid var(--line);border-radius:22px;box-shadow:0 24px 70px rgba(17,24,39,.10)}
.lp-demo img{display:block;width:100%;height:auto;border-radius:14px;background:var(--tint)} .lp-demo p{margin:13px 0 2px;text-align:center;color:var(--muted);font-size:13px}
.lp-band{background:var(--tint);border-block:1px solid color-mix(in srgb,var(--accent) 15%,white)} .lp-grid{max-width:1180px;margin:auto;padding:64px 24px;display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.lp-card{background:rgba(255,255,255,.82);border:1px solid color-mix(in srgb,var(--accent) 15%,white);border-radius:20px;padding:26px} .lp-num{color:var(--accent);font-size:12px;font-weight:750} .lp-card h2{font-size:20px;margin:24px 0 8px} .lp-card p{color:var(--muted);line-height:1.6;margin:0}
.lp-developers{max-width:1180px;margin:auto;padding:72px 24px;display:grid;grid-template-columns:1fr auto;align-items:center;gap:32px} .lp-developers h2{font-size:32px;letter-spacing:-.03em;margin:8px 0 12px} .lp-developers p{color:var(--muted);line-height:1.65;max-width:680px;margin:0}
.lp-footer{max-width:1180px;margin:auto;padding:30px 24px 48px;color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:20px}
.pc-hero{max-width:1180px;margin:auto;padding:82px 24px 44px}.pc-hero h1{font-size:clamp(40px,6vw,68px);line-height:1.04;letter-spacing:-.05em;max-width:900px;margin:20px 0}.pc-summary{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}.pc-chip{border:1px solid var(--line);border-radius:999px;padding:9px 14px;color:var(--muted);font-size:13px;font-weight:650}.pc-chip strong{color:var(--accent)}
.pc-section{max-width:1180px;margin:auto;padding:24px 24px 66px}.pc-heading{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:22px}.pc-heading h2{font-size:30px;letter-spacing:-.035em;margin:0}.pc-heading p{color:var(--muted);margin:0;max-width:560px;line-height:1.55}.pc-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.pc-card{border:1px solid var(--line);border-radius:18px;padding:22px;background:white;display:flex;flex-direction:column;min-height:218px}.pc-card.soon{background:#f8fafc}.pc-meta{display:flex;justify-content:space-between;align-items:center;gap:8px}.pc-status,.pc-price{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;border-radius:999px;padding:6px 9px}.pc-status{color:#047857;background:#ecfdf5}.pc-card.soon .pc-status{color:#92400e;background:#fffbeb}.pc-price{color:var(--accent);background:var(--tint)}.pc-card h3{font-size:19px;margin:25px 0 8px}.pc-card p{color:var(--muted);line-height:1.55;margin:0}.pc-card a{color:var(--accent);font-weight:700;text-decoration:none;margin-top:auto;padding-top:18px;font-size:13px}.pc-note{max-width:1180px;margin:0 auto 50px;padding:0 24px}.pc-note>div{background:var(--tint);border:1px solid color-mix(in srgb,var(--accent) 18%,white);border-radius:18px;padding:22px;line-height:1.6;color:var(--muted)}
@media(max-width:760px){.lp-nav{height:60px}.lp-nav-actions{gap:10px}.lp-nav-link{font-size:13px}.lp-hero{padding-top:72px}.lp-grid{grid-template-columns:1fr}.lp-developers{grid-template-columns:1fr}.lp-footer{flex-direction:column}}
@media(max-width:900px){.pc-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.pc-grid{grid-template-columns:1fr}.pc-heading{display:block}.pc-heading p{margin-top:10px}.lp-nav-actions{gap:9px}.lp-nav-actions .lp-nav-link:nth-child(2),.lp-nav-actions .lp-nav-link:nth-child(3){display:none}}
"""

PRODUCTS = (
    ("Core HR", "Employee records, departments, reporting lines and organisation data.", "/employees", True),
    ("Leave & attendance", "Leave balances, requests, approvals and daily attendance reporting.", "/leave", True),
    ("Payroll & payslips", "Pay runs and itemised employee payslips for operational HR teams.", "/payroll", True),
    ("Recruiting ATS", "Requisitions, candidates, pipelines, scorecards, approvals and offers.", "/talent/jobs", True),
    ("Careers publishing", "Branded careers pages and individual, search-ready job specification pages.", "/careers", True),
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
    ("Expenses & travel", "Expense claims, employee advances, approvals and travel requests.", None, False),
    ("Shifts & time clocks", "Rostering, check-in/out, auto-attendance and location-aware time capture.", None, False),
    ("Benefits administration", "Benefit enrolment, eligibility, employer contributions and employee choices.", None, False),
    ("Learning & development", "Learning plans, course tracking, certifications and skills development.", None, False),
    ("Workforce planning", "Budgeted positions, scenarios and approval-led headcount planning.", None, False),
    ("Employee self-service", "A dedicated employee portal for pay, leave, time, goals and onboarding.", None, False),
    ("Statutory payroll", "Country-specific tax calculations, filings, benefits, loans and advances.", None, False),
    ("Live provider integrations", "Production adapters for HRIS, calendars, job boards and communications.", None, False),
    ("Granular RBAC & security", "Tenant-scoped authorization, enforced record visibility, 2FA and audit exports.", None, False),
)


def _public_nav():
    return Nav(
        A(Span("F", cls="lp-mark"), Span("FastHRM"), href="/", cls="lp-brand"),
        Div(
            A("Products", href="/products", cls="lp-nav-link"),
            A("Careers", href="/careers", cls="lp-nav-link"),
            A("Developers", href="/developers", cls="lp-nav-link"),
            Button("Sign In", type="button", onclick="authOpen('login')", cls="lp-signin"),
            cls="lp-nav-actions",
        ),
        cls="lp-nav",
    )

def landing_page():
    features = ['Employee records', 'Leave and attendance', 'Payroll and payslips',
                'Recruitment and AI CV screening', 'Goals and performance', 'Onboarding to exit']
    return Html(
        Head(Title("FastHRM · FastSME"), Meta(charset="utf-8"),
             Meta(name="viewport", content="width=device-width, initial-scale=1"),
             Meta(name="description", content="Manage employee records, departments, leave, attendance, payroll, and payslips without enterprise-suite overhead."),
             *seo_meta(),
             Link(rel="icon", type="image/svg+xml", href=FAVICON),
             Link(rel="preconnect", href="https://fonts.googleapis.com"),
             Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;750&display=swap"),
             Style(CSS + AUTH_CSS)),
        Body(
            _public_nav(),
            Main(
                Section(Span("People operations", cls="lp-kicker"), H1("A clearer home for every people process."),
                        P("Manage employee records, departments, leave, attendance, payroll, and payslips without enterprise-suite overhead.", cls="lp-lede"),
                        Div(Button("Sign In or Register", type="button", onclick="authOpen('login')", cls="lp-primary"),
                            A("Explore the open-source suite →", href="https://fastsme.com/products", cls="lp-secondary"),
                            cls="lp-actions"), cls="lp-hero"),
                Section(Div(Img(src="/static/product-demo.gif",
                                alt="FastHRM product tour — people operations, public careers, "
                                    "recruiting workflows, analytics and AI-assisted hiring",
                                loading="eager", width="1100", height="689"),
                            P("Product tour · people, time, pay, public careers and recruiting automation"),
                            cls="lp-demo-frame"), cls="lp-demo", aria_label="FastHRM product tour"),
                Section(Div(*[Article(Span(f"0{i}", cls="lp-num"), H2(title),
                                      P("Everything you need for " + title.lower() + ", in one focused workspace."),
                                      cls="lp-card") for i, title in enumerate(features, 1)],
                            cls="lp-grid"), cls="lp-band"),
                Section(Div(Span("Developers", cls="lp-kicker"),
                            H2("Build on FastHRM."),
                            P("Explore the public read API, typed schemas, examples, and token-gated integration writes.")),
                        A("Read the API documentation →", href="/developers", cls="lp-primary"),
                        cls="lp-developers"),
            ),
            Footer(Span("FastHRM is part of the open-source FastSME suite."),
                   A("View all products", href="https://fastsme.com/products", style="color:var(--accent)"),
                   cls="lp-footer"),
            auth_modal("FastHRM"),
            Script(AUTH_JS),
        ),
    )


def products_page():
    available = sum(1 for product in PRODUCTS if product[3])
    coming = len(PRODUCTS) - available
    cards = []
    for name, description, href, implemented in PRODUCTS:
        action = A("Open product →", href=href) if href else None
        cards.append(
            Article(
                Div(
                    Span("Available" if implemented else "Coming soon", cls="pc-status"),
                    Span("Free", cls="pc-price"),
                    cls="pc-meta",
                ),
                H3(name),
                P(description),
                action,
                cls="pc-card" + ("" if implemented else " soon"),
            )
        )
    return Html(
        Head(
            Title("FastHRM Products & Pricing · Free"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="description", content="Explore every FastHRM product. All available and planned modules are Free."),
            *seo_meta(
                path="/products",
                title="FastHRM Products & Pricing · Free",
                description="Explore available and coming-soon FastHRM products. Every module is Free.",
            ),
            Link(rel="icon", type="image/svg+xml", href=FAVICON),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;750&display=swap"),
            Style(CSS + AUTH_CSS),
        ),
        Body(
            _public_nav(),
            Main(
                Section(
                    Span("Products & pricing", cls="lp-kicker"),
                    H1("Every people product. Free."),
                    P("Use the modules that are ready today and see what is coming next. There are no paid tiers or per-module upgrades.", cls="lp-lede"),
                    Div(
                        Span(Strong(str(available)), " available products", cls="pc-chip"),
                        Span(Strong(str(coming)), " coming soon", cls="pc-chip"),
                        Span(Strong("Free"), " across the catalogue", cls="pc-chip"),
                        cls="pc-summary",
                    ),
                    cls="pc-hero",
                ),
                Section(
                    Div(H2("Product catalogue"), P("Availability reflects the current FastHRM implementation. Coming-soon modules are visible so teams can plan without mistaking roadmap scope for shipped software."), cls="pc-heading"),
                    Div(*cards, cls="pc-grid"),
                    cls="pc-section",
                ),
                Section(Div(Strong("Pricing: Free. "), "Every product shown here is offered at no charge. “Coming soon” describes delivery status only, not a future paid plan."), cls="pc-note"),
            ),
            Footer(Span("FastHRM is part of the open-source FastSME suite."), A("Developer API", href="/developers", style="color:var(--accent)"), cls="lp-footer"),
            auth_modal("FastHRM"),
            Script(AUTH_JS),
        ),
    )
