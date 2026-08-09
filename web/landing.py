"""Public FastHRM landing, feature, and comparison pages."""
import json
from urllib.parse import quote

from fasthtml.common import *
import version

from .account_auth import AUTH_CSS, AUTH_JS, auth_modal
from .seo import seo_meta

ACCENT = "#0891b2"
TINT = "#ecfeff"
FAVICON = "data:image/svg+xml," + quote(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0891b2"/><path fill="white" d="M16 4 28 16 16 28 4 16Z"/><path fill="#0891b2" d="M11 10h11v4h-7v3h6v4h-6v5h-4Z"/></svg>""",
    safe="",
)

PARTNERS = (
    ("SAASPASS", "https://saaspass.com/", "https://saaspass.com/_next/static/assets/0176aeff921f6359fee88e796be31ace.png", "Full-stack identity and access management spanning MFA, SSO, passwordless access and integration APIs."),
    ("Sixty Four", "https://sixtyfour.ee/", "https://sixtyfour.ee/favicon.ico", "A senior Tallinn technology studio delivering software, AI consultancy, service design and public-sector programmes."),
    ("EDI Labs", "https://edilabs.tech/", "https://edilabs.tech/static/favicon.svg", "AI and data engineering for document intelligence, forecasting, geospatial systems and agentic workflows."),
    ("Predictive Labs", "https://predictivelabs.ai/", "https://predictivelabs.ai/static/favicon.svg", "Auditable AI systems for health, defence, public management, mobility and financial services."),
    ("Consistente", "https://consistente.tech/", "https://consistente.tech/static/favicon.svg", "Enterprise AI delivery across financial services, healthcare, the public sector and technology."),
    ("Manmouna Technologies", "https://manmouna.tech/", "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%230B1E14'/%3E%3Cpath d='M32 12 52 32 32 52 12 32Z' fill='%2334D399'/%3E%3Cpath d='M32 22 42 32 32 42 22 32Z' fill='%230B1E14'/%3E%3C/svg%3E", "Auditable-by-design AI systems for European public services across health, defence, public management and mobility."),
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
.lp-partners{max-width:1180px;margin:auto;padding:72px 24px;scroll-margin-top:80px}.lp-partners-head{max-width:720px}.lp-partners-head h2{font-size:32px;letter-spacing:-.03em;margin:10px 0 12px}.lp-partners-head p{color:var(--muted);line-height:1.65;margin:0}.lp-partner-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-top:32px}.lp-partner{min-width:0;color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:18px;padding:20px;background:#fff;transition:transform .18s,border-color .18s,box-shadow .18s}.lp-partner:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--accent) 40%,white);box-shadow:0 14px 34px rgba(17,24,39,.08)}.lp-partner-top{display:flex;align-items:center;justify-content:space-between;gap:12px}.lp-partner-logo{width:46px;height:46px;object-fit:contain}.lp-partner-type{color:var(--accent);font-size:10px;font-weight:750;text-transform:uppercase;letter-spacing:.1em;text-align:right}.lp-partner h3{font-size:18px;margin:18px 0 8px}.lp-partner p{color:var(--muted);font-size:13px;line-height:1.55;margin:0}.lp-partner-visit{display:block;color:var(--accent);font-size:12px;font-weight:700;margin-top:16px}
.lp-developers{max-width:1180px;margin:auto;padding:72px 24px;display:grid;grid-template-columns:1fr auto;align-items:center;gap:32px} .lp-developers h2{font-size:32px;letter-spacing:-.03em;margin:8px 0 12px} .lp-developers p{color:var(--muted);line-height:1.65;max-width:680px;margin:0}
.lp-footer{max-width:1180px;margin:auto;padding:30px 24px 48px;color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:20px}.lp-footer-links{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.lp-footer a{color:var(--accent);text-decoration:none}.lp-footer .lp-version{color:var(--muted)}.lp-footer .lp-version:hover{color:var(--accent)}
.pc-hero{max-width:1180px;margin:auto;padding:82px 24px 44px}.pc-hero h1{font-size:clamp(40px,6vw,68px);line-height:1.04;letter-spacing:-.05em;max-width:900px;margin:20px 0}.pc-summary{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}.pc-chip{border:1px solid var(--line);border-radius:999px;padding:9px 14px;color:var(--muted);font-size:13px;font-weight:650}.pc-chip strong{color:var(--accent)}
.pc-section{max-width:1180px;margin:auto;padding:24px 24px 66px}.pc-heading{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:22px}.pc-heading h2{font-size:30px;letter-spacing:-.035em;margin:0}.pc-heading p{color:var(--muted);margin:0;max-width:560px;line-height:1.55}.pc-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.pc-card{border:1px solid var(--line);border-radius:18px;padding:22px;background:white;display:flex;flex-direction:column;min-height:218px}.pc-card.soon{background:#f8fafc}.pc-meta{display:flex;justify-content:space-between;align-items:center;gap:8px}.pc-status,.pc-price{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;border-radius:999px;padding:6px 9px}.pc-status{color:#047857;background:#ecfdf5}.pc-card.soon .pc-status{color:#92400e;background:#fffbeb}.pc-price{color:var(--accent);background:var(--tint)}.pc-card h3{font-size:19px;margin:25px 0 8px}.pc-card p{color:var(--muted);line-height:1.55;margin:0}.pc-card a{color:var(--accent);font-weight:700;text-decoration:none;margin-top:auto;padding-top:18px;font-size:13px}.pc-note{max-width:1180px;margin:0 auto 50px;padding:0 24px}.pc-note>div{background:var(--tint);border:1px solid color-mix(in srgb,var(--accent) 18%,white);border-radius:18px;padding:22px;line-height:1.6;color:var(--muted)}
.cmp-wrap{max-width:1180px;margin:auto;padding:12px 24px 68px}.cmp-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:20px}.cmp-table{width:100%;min-width:1500px;border-collapse:collapse;background:white}.cmp-table caption{text-align:left;padding:18px 20px;color:var(--muted);font-size:13px}.cmp-table th,.cmp-table td{text-align:left;padding:18px 16px;border-top:1px solid var(--line);vertical-align:top;line-height:1.5}.cmp-table th{background:#f8fafc;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.cmp-table td{font-size:14px}.cmp-table tr.cmp-fast td{background:var(--tint)}.cmp-name{font-size:16px;font-weight:800;color:var(--ink)}.cmp-name a{color:inherit}.cmp-badge{display:inline-flex;border-radius:999px;padding:5px 8px;margin:4px 4px 0 0;font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.06em}.cmp-badge.open,.cmp-badge.free{background:#ecfdf5;color:#047857}.cmp-badge.mixed{background:#fffbeb;color:#92400e}.cmp-badge.closed{background:#fef2f2;color:#b91c1c}.cmp-source{color:var(--accent);font-size:12px;font-weight:700}.cmp-note{color:var(--muted);font-size:13px;line-height:1.6;margin:16px 2px 0}.cmp-faq{max-width:960px;margin:auto;padding:12px 24px 76px}.cmp-faq h2{font-size:32px;letter-spacing:-.035em}.cmp-faq article{border-top:1px solid var(--line);padding:22px 0}.cmp-faq h3{font-size:18px;margin:0 0 8px}.cmp-faq p{color:var(--muted);line-height:1.65;margin:0}
@media(max-width:980px){.lp-partner-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.lp-nav{height:60px}.lp-nav-actions{gap:10px}.lp-nav-link{font-size:13px}.lp-hero{padding-top:72px}.lp-grid,.lp-partner-grid{grid-template-columns:1fr}.lp-developers{grid-template-columns:1fr}.lp-footer{flex-direction:column}}
@media(max-width:900px){.pc-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.pc-grid{grid-template-columns:1fr}.pc-heading{display:block}.pc-heading p{margin-top:10px}.lp-nav-actions{gap:9px}.lp-nav-actions .lp-nav-link:nth-child(3),.lp-nav-actions .lp-nav-link:nth-child(5){display:none}}
"""

FEATURE_CATALOG = (
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

COMPARISONS = (
    {
        "name": "FastHRM", "best_for": "SMEs and startups wanting broad HR and recruiting without licence fees",
        "team": "Small and growing teams", "price": "Free — every listed feature", "price_class": "free",
        "free_option": "All available features", "source_model": "Yes · MIT", "source_class": "open",
        "payroll_global": "Payslips and HR workflows; statutory payroll is coming soon",
        "limits": "Granular RBAC hardening and live provider adapters remain on the roadmap",
        "source": "https://github.com/predictivelabsai/FastHRM", "highlight": True,
    },
    {
        "name": "Gusto", "best_for": "US startups prioritising full-service payroll, tax and benefits",
        "team": "Typically 1–50", "price": "$49/month + $6/person", "price_class": "closed",
        "free_option": "No permanent free plan", "source_model": "No public open-source edition", "source_class": "closed",
        "payroll_global": "Strong US payroll; international contractor payments are an add-on",
        "limits": "Primarily US-focused; deeper HR features require higher plans",
        "source": "https://gusto.com/product/pricing", "highlight": False,
    },
    {
        "name": "BambooHR", "best_for": "Growing teams wanting a polished, dedicated core HRIS",
        "team": "Typically 10–200", "price": "Core from $10/employee/month", "price_class": "closed",
        "free_option": "Trial; no permanent free plan", "source_model": "No · proprietary", "source_class": "closed",
        "payroll_global": "Payroll and benefits are subscribed services; limited global employment scope",
        "limits": "Per-employee pricing; advanced capabilities and services increase total cost",
        "source": "https://www.bamboohr.com/pricing/", "highlight": False,
    },
    {
        "name": "Rippling", "best_for": "Fast-scaling teams combining HR, IT, devices, apps and payroll",
        "team": "Typically 20–500+", "price": "From $8/user/month + $40 base fee", "price_class": "closed",
        "free_option": "Demo and custom quote", "source_model": "No public open-source edition", "source_class": "closed",
        "payroll_global": "US and global payroll options with deep workforce automation",
        "limits": "Required platform plus modular products can raise cost and setup effort",
        "source": "https://www.rippling.com/solutions/small-businesses", "highlight": False,
    },
    {
        "name": "Deel", "best_for": "Distributed teams hiring employees and contractors internationally",
        "team": "Any size; global-first", "price": "$49/contractor or $599/EOR employee monthly", "price_class": "closed",
        "free_option": "Free demo; no general free plan", "source_model": "No public open-source edition", "source_class": "closed",
        "payroll_global": "EOR, contractors and payroll across 130+ countries",
        "limits": "EOR and contractor compliance fees add up; core HR is not the main differentiator",
        "source": "https://www.deel.com/pricing/", "highlight": False,
    },
    {
        "name": "Zoho People", "best_for": "Budget-conscious SMEs and existing Zoho customers",
        "team": "5–200+", "price": "Free for 5 users; paid from $1.25/user/month annually", "price_class": "mixed",
        "free_option": "Permanent free plan for 5 users", "source_model": "No public open-source edition", "source_class": "closed",
        "payroll_global": "Multi-language HR; payroll is a separate Zoho product",
        "limits": "Advanced attendance, performance and talent features sit in higher tiers",
        "source": "https://www.zoho.com/people/zohopeople-pricing.html", "highlight": False,
    },
    {
        "name": "Odoo HR", "best_for": "Teams wanting modular HR inside a broader ERP suite",
        "team": "Small to mid-market", "price": "One App Free; all-app plans from $24.90/user/month annually", "price_class": "mixed",
        "free_option": "One App Free and Community edition", "source_model": "Community: LGPLv3; Enterprise: proprietary", "source_class": "mixed",
        "payroll_global": "Broad modular HR/ERP with regional configuration",
        "limits": "A complete HR stack spans multiple apps; API/customisation require the paid Custom plan",
        "source": "https://www.odoo.com/pricing", "license_source": "https://www.odoo.com/documentation/18.0/legal/licenses.html", "highlight": False,
    },
)

COMPARISON_FAQS = (
    ("Is FastHRM free?", "Yes. Every available FastHRM feature is Free, and coming-soon scope is also labelled Free rather than reserved for a paid tier."),
    ("Is FastHRM open source?", "Yes. FastHRM is published under the MIT licence, can be inspected and modified, and is designed to be self-hosted."),
    ("Which compared HR systems are open source?", "FastHRM is MIT-licensed open source. Odoo Community is LGPLv3 open source, while Odoo Enterprise is proprietary. BambooHR is proprietary; Gusto, Rippling, Deel and Zoho People do not publish open-source editions."),
    ("Does free software mean zero operating cost?", "No. Software can be Free while hosting, implementation, support, migration and third-party provider usage still incur costs. The comparison separates software price from those operating choices."),
    ("Are coming-soon FastHRM features available today?", "No. Coming soon is an availability label, not a pricing tier. The Features page distinguishes shipped functionality from roadmap scope."),
)


def partner_section():
    return Section(
        Div(Span("Partners", cls="lp-kicker"), H2("Connect with trusted integration specialists."), P("Identity, software delivery, data engineering and applied-AI expertise for FastSME implementations."), cls="lp-partners-head"),
        Div(*[
            A(Div(Img(src=logo, alt=f"{name} logo", loading="lazy", cls="lp-partner-logo"), Span("Integration Partner", cls="lp-partner-type"), cls="lp-partner-top"), H3(name), P(description), Span("Visit website ↗", cls="lp-partner-visit"), href=url, target="_blank", rel="noopener noreferrer", cls="lp-partner")
            for name, url, logo, description in PARTNERS
        ], cls="lp-partner-grid"),
        id="partners", cls="lp-partners",
    )


def _public_nav():
    return Nav(
        A(Span("F", cls="lp-mark"), Span("FastHRM"), href="/", cls="lp-brand"),
        Div(
            A("Features", href="/features", cls="lp-nav-link"),
            A("How we compare", href="/compare", cls="lp-nav-link"),
            A("Careers", href="/careers", cls="lp-nav-link"),
            A("Partners", href="/#partners", cls="lp-nav-link"),
            A("Developers", href="/developers", cls="lp-nav-link"),
            Button("Sign In", type="button", onclick="authOpen('login')", cls="lp-signin"),
            cls="lp-nav-actions",
        ),
        cls="lp-nav",
    )


def _public_footer(message, link_text, href):
    """Keep public pages tied to the same runtime build identity as the app shell."""
    return Footer(
        Span(message),
        Div(
            A(link_text, href=href),
            A(version.label(), href="/about", cls="lp-version", title=version.detail()),
            cls="lp-footer-links",
        ),
        cls="lp-footer",
    )


def landing_page(open_auth=False):
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
                partner_section(),
                Section(Div(Span("Developers", cls="lp-kicker"),
                            H2("Build on FastHRM."),
                            P("Explore the public read API, typed schemas, examples, and token-gated integration writes.")),
                        A("Read the API documentation →", href="/developers", cls="lp-primary"),
                        cls="lp-developers"),
            ),
            _public_footer(
                "FastHRM is part of the open-source FastSME suite.",
                "View all products",
                "https://fastsme.com/products",
            ),
            auth_modal("FastHRM"),
            Script(AUTH_JS),
            Script("document.addEventListener('DOMContentLoaded',()=>authOpen('login'));" if open_auth else ""),
        ),
    )


def features_page():
    available = sum(1 for feature in FEATURE_CATALOG if feature[3])
    coming = len(FEATURE_CATALOG) - available
    cards = []
    for name, description, href, implemented in FEATURE_CATALOG:
        action = A("Open feature →", href=href) if href else None
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
            Title("FastHRM Features & Pricing · Free"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="description", content="Explore every FastHRM feature. All available and planned modules are Free."),
            *seo_meta(
                path="/features",
                title="FastHRM Features & Pricing · Free",
                description="Explore available and coming-soon FastHRM features. Every module is Free.",
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
                    Span("Features & pricing", cls="lp-kicker"),
                    H1("Every people feature. Free."),
                    P("Use the modules that are ready today and see what is coming next. There are no paid tiers or per-module upgrades.", cls="lp-lede"),
                    Div(
                        Span(Strong(str(available)), " available features", cls="pc-chip"),
                        Span(Strong(str(coming)), " coming soon", cls="pc-chip"),
                        Span(Strong("Free"), " across the catalogue", cls="pc-chip"),
                        cls="pc-summary",
                    ),
                    cls="pc-hero",
                ),
                Section(
                    Div(H2("Feature catalogue"), P("Availability reflects the current FastHRM implementation. Coming-soon modules are visible so teams can plan without mistaking roadmap scope for shipped software."), cls="pc-heading"),
                    Div(*cards, cls="pc-grid"),
                    cls="pc-section",
                ),
                Section(Div(Strong("Pricing: Free. "), "Every feature shown here is offered at no charge. “Coming soon” describes delivery status only, not a future paid plan."), cls="pc-note"),
            ),
            _public_footer(
                "FastHRM is part of the open-source FastSME suite.",
                "Developer API",
                "/developers",
            ),
            auth_modal("FastHRM"),
            Script(AUTH_JS),
        ),
    )


def comparison_page():
    rows = []
    for item in COMPARISONS:
        source_links = [A("Official source ↗", href=item["source"], target="_blank", rel="noreferrer", cls="cmp-source")]
        if item.get("license_source"):
            source_links.append(A("Licence ↗", href=item["license_source"], target="_blank", rel="noreferrer", cls="cmp-source"))
        rows.append(
            Tr(
                Td(Div(item["name"], cls="cmp-name"), *source_links),
                Td(item["best_for"]),
                Td(item["team"]),
                Td(Span(item["price"], cls=f"cmp-badge {item['price_class']}")),
                Td(item["free_option"]),
                Td(Span(item["source_model"], cls=f"cmp-badge {item['source_class']}")),
                Td(item["payroll_global"]),
                Td(item["limits"]),
                cls="cmp-fast" if item["highlight"] else "",
            )
        )
    faq_schema = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
            for question, answer in COMPARISON_FAQS
        ],
    }
    list_schema = {
        "@context": "https://schema.org", "@type": "ItemList", "name": "FastHRM alternatives comparison",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["name"], "url": item["source"]}
            for index, item in enumerate(COMPARISONS, 1)
        ],
    }
    return Html(
        Head(
            Title("FastHRM vs Open-Source and Proprietary HRM Software"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="description", content="Compare FastHRM with Gusto, BambooHR, Rippling, Deel, Zoho People, and Odoo HR across price, source model, payroll, and scope."),
            *seo_meta(
                path="/compare",
                title="FastHRM Comparison · Free and Open-Source HRM",
                description="Compare FastHRM with six leading open-source, open-core, and proprietary HR platforms.",
            ),
            Script(NotStr(json.dumps(faq_schema, separators=(",", ":"))), type="application/ld+json"),
            Script(NotStr(json.dumps(list_schema, separators=(",", ":"))), type="application/ld+json"),
            Link(rel="icon", type="image/svg+xml", href=FAVICON),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;750&display=swap"),
            Style(CSS + AUTH_CSS),
        ),
        Body(
            _public_nav(),
            Main(
                Section(
                    Span("How we compare", cls="lp-kicker"),
                    H1("Free and open by default."),
                    P("A source-linked comparison of FastHRM with six close alternatives. Software price, source availability and operating costs are shown separately.", cls="lp-lede"),
                    Div(Span(Strong("Free"), " FastHRM features", cls="pc-chip"), Span(Strong("MIT"), " open-source licence", cls="pc-chip"), Span(Strong("No"), " paid tiers", cls="pc-chip"), cls="pc-summary"),
                    cls="pc-hero",
                ),
                Section(
                    Div(
                        Table(
                            Caption("Public pricing and licensing observed 8 August 2026. Prices exclude implementation, infrastructure, support and optional services unless stated."),
                            Thead(Tr(Th("Platform"), Th("Best for"), Th("Ideal team"), Th("Starting price"), Th("Free option"), Th("Open source"), Th("Payroll / global"), Th("Limitations"))),
                            Tbody(*rows),
                            cls="cmp-table",
                        ),
                        cls="cmp-scroll",
                    ),
                    P("Comparison is based on official vendor pages linked in each row. “Free” describes the software or named plan, not unavoidable infrastructure or implementation work.", cls="cmp-note"),
                    cls="cmp-wrap",
                ),
                Section(H2("Questions people ask"), *[Article(H3(question), P(answer)) for question, answer in COMPARISON_FAQS], cls="cmp-faq"),
            ),
            _public_footer(
                "FastHRM is Free and open source.",
                "See every feature",
                "/features",
            ),
            auth_modal("FastHRM"),
            Script(AUTH_JS),
        ),
    )
