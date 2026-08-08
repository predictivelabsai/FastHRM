"""Public and in-app developer documentation for FastHRM."""
from fasthtml.common import *

from .api import RESOURCES
from .landing import FAVICON
from .seo import seo_meta

ACCENT = "#0891b2"
TINT = "#ecfeff"
BASE_URL = "https://hrm.fastsme.com"
REPOSITORY = "https://github.com/predictivelabsai/FastHRM"
API_RELEASE = "2026-08-08"

DEVELOPER_CSS = """
.dev-docs{--dev-accent:#0891b2;--dev-tint:#ecfeff;--dev-ink:#111827;--dev-muted:#667085;--dev-line:#e7eaf0;color:var(--dev-ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
.dev-docs *{box-sizing:border-box} .dev-wrap{max-width:1120px;margin:auto;padding:56px 24px 80px}
.dev-eyebrow{color:var(--dev-accent);font-size:12px;font-weight:750;text-transform:uppercase;letter-spacing:.16em}
.dev-docs h1{font-size:clamp(40px,6vw,68px);line-height:1.02;letter-spacing:-.05em;max-width:850px;margin:18px 0}
.dev-lede{font-size:19px;line-height:1.65;color:var(--dev-muted);max-width:760px}
.dev-actions{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0 46px} .dev-btn{display:inline-flex;padding:10px 16px;border-radius:999px;text-decoration:none;font-size:14px;font-weight:700;border:1px solid var(--dev-line);color:var(--dev-ink);background:white} .dev-btn.primary{background:var(--dev-accent);color:white;border-color:var(--dev-accent)}
.dev-note{background:var(--dev-tint);border:1px solid color-mix(in srgb,var(--dev-accent) 18%,white);border-radius:18px;padding:20px 22px;line-height:1.6;margin-bottom:42px} .dev-note strong{color:var(--dev-accent)}
.dev-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:18px 0 46px} .dev-card{background:white;border:1px solid var(--dev-line);border-radius:18px;padding:22px;box-shadow:0 8px 24px rgba(17,24,39,.04)} .dev-card h2{font-size:19px;margin:0 0 8px} .dev-card p{color:var(--dev-muted);line-height:1.55;min-height:48px} .dev-route{display:block;background:#111827;color:#f8fafc;padding:9px 11px;border-radius:8px;margin-top:8px;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;overflow:auto} .dev-method{color:#86efac;font-weight:800}
.dev-example{background:#111827;color:#e5e7eb;border-radius:16px;padding:22px;overflow:auto;font:13px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace} .dev-docs h3{font-size:24px;margin:42px 0 14px} .dev-small{color:var(--dev-muted);font-size:13px;line-height:1.6}
.dev-table{display:block;width:100%;max-width:100%;overflow-x:auto;border-collapse:collapse;margin:12px 0 38px;font-size:14px}.dev-table th,.dev-table td{text-align:left;padding:12px;border-bottom:1px solid var(--dev-line);vertical-align:top}.dev-table th{color:var(--dev-muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.dev-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--dev-accent)}
.dev-public-nav{height:68px;display:flex;align-items:center;justify-content:space-between;max-width:1120px;margin:auto;padding:0 24px;border-bottom:1px solid var(--dev-line)} .dev-brand{display:flex;align-items:center;gap:10px;color:var(--dev-ink);text-decoration:none;font-weight:750} .dev-diamond{width:28px;height:28px;border-radius:8px;background:var(--dev-accent);transform:rotate(45deg);display:inline-block}
@media(max-width:720px){.dev-grid{grid-template-columns:1fr}.dev-docs h1{font-size:42px}.dev-public-nav{padding:10px 16px;height:auto}.dev-public-nav .dev-actions{gap:6px}.dev-public-nav .dev-btn{padding:8px 10px}.dev-brand span:last-child{display:none}}
"""


def developer_content():
    cards = []
    for resource in RESOURCES:
        cards.append(
            Article(
                H2(resource.title),
                P(resource.description),
                Code(Span("GET", cls="dev-method"), f" /api/v1/{resource.slug}", cls="dev-route"),
                Code(Span("GET", cls="dev-method"), f" /api/v1/{resource.slug}/{{id}}", cls="dev-route"),
                cls="dev-card",
            )
        )
    return Div(
        Style(DEVELOPER_CSS),
        Div(
            Span("Developer platform · API v1", cls="dev-eyebrow"),
            H1("Build with the FastHRM API."),
            P("Read the live demo database through a typed, versioned API. Selected integration writes are implemented behind bearer-token authentication.", cls="dev-lede"),
            Div(
                A("Open Swagger UI", href="/api/docs", cls="dev-btn primary"),
                A("Open ReDoc", href="/api/redoc", cls="dev-btn"),
                A("Download swagger.json", href="/swagger.json", cls="dev-btn"),
                A("View on GitHub", href=REPOSITORY, target="_blank", rel="noreferrer", cls="dev-btn"),
                cls="dev-actions",
            ),
            Div(
                Strong("Public preview access. "),
                "GET endpoints require no authentication. Writes return 503 until FASTSME_API_TOKEN is configured; enabled clients send Authorization: Bearer <token>.",
                cls="dev-note",
            ),
            H3("API contract"),
            Table(
                Thead(Tr(Th("Concern"), Th("Contract"))),
                Tbody(
                    Tr(Td("Base URL"), Td(Code(f"{BASE_URL}/api", cls="dev-code"))),
                    Tr(Td("Version"), Td(Code("v1", cls="dev-code"), f" · schema refreshed {API_RELEASE}")),
                    Tr(Td("Pagination"), Td(Code("?limit=20&offset=0", cls="dev-code"), " · maximum limit 200")),
                    Tr(Td("Filtering"), Td(Code("?q=search&status=value", cls="dev-code"), " · available fields are documented per operation")),
                    Tr(Td("Errors"), Td(Code('{"error":{"code":"…","message":"…","details":{}}}', cls="dev-code"))),
                    Tr(Td("Writes"), Td(Code("Authorization: Bearer <token>", cls="dev-code"), " · POST/PATCH/DELETE only where declared in OpenAPI")),
                ),
                cls="dev-table",
            ),
            H3("Resources"),
            Div(*cards, cls="dev-grid"),
            H3("Quick start"),
            Pre(Code(f"""curl "{BASE_URL}/api/v1/{RESOURCES[0].slug}?limit=20"

python - <<'PY'
import requests
rows = requests.get("{BASE_URL}/api/v1/{RESOURCES[0].slug}", timeout=20).json()
print(rows["data"])
PY"""), cls="dev-example"),
            H3("Authenticated write example"),
            Pre(Code(f"""curl -X PATCH \\
  -H 'Authorization: Bearer <token>' \\
  -H 'Content-Type: application/json' \\
  -d '{{"status":"Approved"}}' \\
  '{BASE_URL}/api/v1/leave/1'"""), cls="dev-example"),
            P("Only fields listed in the operation schema are accepted. Unknown fields return a structured validation error; destructive writes remain token-gated.", cls="dev-small"),
            P("Runtime OpenAPI: /api/openapi.json · Stable compatibility schema: /swagger.json · Interactive docs: /api/docs", cls="dev-small"),
            cls="dev-wrap",
        ),
        cls="dev-docs",
    )


def developer_page():
    return Html(
        Head(
            Title("FastHRM Developers · FastSME"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="description", content="Developer API documentation for FastHRM."),
            *seo_meta(
                path="/developers",
                title="FastHRM Developer API · FastSME",
                description="Build integrations with the public FastHRM API, OpenAPI schemas, examples, and token-gated writes.",
            ),
            Link(rel="icon", type="image/svg+xml", href=FAVICON),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;750&display=swap"),
        ),
        Body(
            Nav(
                A(Span(cls="dev-diamond"), Span("FastHRM Developers"), href="/developers", cls="dev-brand"),
                Div(A("Features", href="/features", cls="dev-btn"), A("Compare", href="/compare", cls="dev-btn"), A("Back to product", href="/", cls="dev-btn"), cls="dev-actions", style="margin:0"),
                cls="dev-public-nav dev-docs",
            ),
            developer_content(),
            style="margin:0;background:#fff",
        ),
    )
