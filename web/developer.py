"""Public and in-app developer documentation for FastHRM."""
from __future__ import annotations

from fasthtml.common import *

from .api import RESOURCES
from .design import MOBILE_NAV_JS, fs_button
from .i18n import t
from .landing import public_footer, public_head, public_nav

BASE_URL = "https://fasthr.eu"
REPOSITORY = "https://github.com/predictivelabsai/FastHRM"
API_RELEASE = "2026-08-08"

DEVELOPER_CSS = """
.dev-wrap{max-width:1120px;margin:auto;padding:56px 24px 80px}
.dev-wrap h1{font-size:clamp(40px,6vw,68px);line-height:1.02;letter-spacing:-.05em;max-width:850px;margin:0 0 18px}
.dev-lede{font-size:19px;line-height:1.65;color:var(--muted);max-width:760px}
.dev-actions{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0 46px}
.dev-note{background:var(--paper-2);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px;line-height:1.6;margin-bottom:42px}
.dev-note strong{color:var(--accent-strong)}
.dev-table-wrap{max-width:100%;overflow-x:auto;margin:12px 0 38px;border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}
.dev-table{width:100%;min-width:680px;border-collapse:collapse;font-size:14px}
.dev-table th,.dev-table td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}
.dev-table tr:last-child td{border-bottom:0}.dev-table th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}
.dev-code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent-strong);overflow-wrap:anywhere}
.dev-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:18px 0 46px}
.dev-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px;min-width:0}
.dev-card h2{font-size:19px;margin:0 0 8px}.dev-card p{color:var(--muted);line-height:1.55}
.dev-route{display:block;background:var(--ink);color:var(--on-ink);padding:9px 11px;border-radius:8px;margin-top:8px;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;overflow:auto;overflow-wrap:anywhere}
.dev-method{color:var(--accent);font-weight:800}.dev-wrap h3{font-size:24px;margin:42px 0 14px}
.dev-example{background:var(--ink);color:var(--on-ink);border-radius:var(--radius);padding:22px;overflow:auto;font:13px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre;max-width:100%}
.dev-example code{overflow-wrap:anywhere}.dev-small{color:var(--muted);font-size:13px;line-height:1.6}
@media(max-width:720px){.dev-grid{grid-template-columns:1fr}.dev-wrap{padding-inline:18px}}
"""


def developer_content() -> object:
    cards = [
        Article(
            H2(resource.title, lang="en"), P(resource.description, lang="en"),
            Code(Span("GET", cls="dev-method"), f" /api/v1/{resource.slug}", cls="dev-route"),
            Code(Span("GET", cls="dev-method"), f" /api/v1/{resource.slug}/{{id}}", cls="dev-route"),
            cls="dev-card",
        ) for resource in RESOURCES
    ]
    return Div(
        Div(
            H1("Build with the FastHR API.", lang="en"),
            P("Read the live demo database through a typed, versioned API. Selected integration writes are implemented behind bearer-token authentication.", cls="dev-lede", lang="en"),
            Div(
                fs_button("Open Swagger UI", href="/api/docs", variant="lime"),
                fs_button("Open ReDoc", href="/api/redoc", variant="outline"),
                fs_button("Download swagger.json", href="/swagger.json", variant="outline"),
                fs_button("View on GitHub", href=REPOSITORY, variant="outline", target="_blank", rel="noreferrer"),
                cls="dev-actions", lang="en",
            ),
            Div(Strong("Public preview access. ", lang="en"),
                "GET endpoints require no authentication. Writes return 503 until FASTSME_API_TOKEN is configured; enabled clients send Authorization: Bearer <token>.",
                cls="dev-note", lang="en"),
            H3("API contract", lang="en"),
            Div(Table(
                Thead(Tr(Th("Concern"), Th("Contract"))),
                Tbody(
                    Tr(Td("Base URL"), Td(Code(f"{BASE_URL}/api", cls="dev-code"))),
                    Tr(Td("Version"), Td(Code("v1", cls="dev-code"), f" · schema refreshed {API_RELEASE}")),
                    Tr(Td("Pagination"), Td(Code("?limit=20&offset=0", cls="dev-code"), " · maximum limit 200")),
                    Tr(Td("Filtering"), Td(Code("?q=search&status=value", cls="dev-code"), " · available fields are documented per operation")),
                    Tr(Td("Errors"), Td(Code('{"error":{"code":"…","message":"…","details":{}}}', cls="dev-code"))),
                    Tr(Td("Writes"), Td(Code("Authorization: Bearer <token>", cls="dev-code"), " · POST/PATCH/DELETE only where declared in OpenAPI")),
                ), cls="dev-table",
            ), cls="dev-table-wrap", lang="en"),
            H3("Resources", lang="en"), Div(*cards, cls="dev-grid", lang="en"),
            H3("Quick start", lang="en"),
            Pre(Code(f'''curl "{BASE_URL}/api/v1/{RESOURCES[0].slug}?limit=20"

python - <<'PY'
import requests
rows = requests.get("{BASE_URL}/api/v1/{RESOURCES[0].slug}", timeout=20).json()
print(rows["data"])
PY'''), cls="dev-example", lang="en"),
            H3("Authenticated write example", lang="en"),
            Pre(Code(f'''curl -X PATCH \\
  -H 'Authorization: Bearer <token>' \\
  -H 'Content-Type: application/json' \\
  -d '{{"status":"Approved"}}' \\
  '{BASE_URL}/api/v1/leave/1'''), cls="dev-example", lang="en"),
            P("Only fields listed in the operation schema are accepted. Unknown fields return a structured validation error; destructive writes remain token-gated.", cls="dev-small", lang="en"),
            P("Runtime OpenAPI: /api/openapi.json · Stable compatibility schema: /swagger.json · Interactive docs: /api/docs", cls="dev-small", lang="en"),
            cls="dev-wrap",
        ), Style(DEVELOPER_CSS),
    )


def developer_page(lang: str = "et"):
    c = t(lang)
    return Html(
        public_head(
            c, "meta", "/developers", title="FastHR Developers · FastSME",
            description="Developer API documentation for FastHR.",
            extra_css=DEVELOPER_CSS, include_comparison_css=False,
        ),
        Body(
            A("Skip to content", href="#main-content", cls="fs-skip"),
            public_nav(c, "/developers"), Script(MOBILE_NAV_JS),
            Main(developer_content(), id="main-content"), public_footer(c),
        ), lang=c["html_lang"],
    )
