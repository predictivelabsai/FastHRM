"""Search metadata, structured data, sitemap, and crawler policy."""
from __future__ import annotations

import json

from fasthtml.common import Link, Meta, NotStr, Script
from starlette.responses import Response

import recruitment

PRODUCT = 'FastHRM'
BASE_URL = 'https://hrm.fastsme.com'
DESCRIPTION = 'Manage employee records, departments, leave, attendance, payroll, and payslips without enterprise-suite overhead.'
KEYWORDS = ('FastHRM', 'open source people operations', 'people operations software', 'SME people operations', 'Employee records', 'Leave and attendance', 'Payroll and payslips', 'FastSME', 'open source business software')
FEATURES = ('Employee records', 'Leave and attendance', 'Payroll and payslips', 'Recruiting ATS', 'Performance management', 'Employee lifecycle')
SITEMAP_ENTRIES = (
    ('/', 'weekly', '1.0'),
    ('/features', 'weekly', '0.9'),
    ('/compare', 'weekly', '0.8'),
    ('/careers', 'daily', '0.8'),
    ('/developers', 'monthly', '0.6'),
    ('/privacy', 'yearly', '0.3'),
)
SITEMAP_PATHS = tuple(path for path, _frequency, _priority in SITEMAP_ENTRIES)


def seo_meta(
    *,
    path: str = "/",
    title: str | None = None,
    description: str | None = None,
):
    canonical = BASE_URL + (path if path != "/" else "")
    page_title = title or f"{PRODUCT} · Open-source {KEYWORDS[2].title()}"
    page_description = description or DESCRIPTION
    structured = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": PRODUCT,
        "url": canonical,
        "description": page_description,
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "isAccessibleForFree": True,
        "license": "https://opensource.org/license/mit",
        "sameAs": "https://github.com/predictivelabsai/FastHRM",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD", "availability": "https://schema.org/InStock"},
        "featureList": list(FEATURES),
        "publisher": {
            "@type": "Organization",
            "name": "FastSME",
            "url": "https://fastsme.com",
        },
    }
    return (
        Link(rel="canonical", href=canonical),
        Meta(name="robots", content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"),
        Meta(name="keywords", content=", ".join(KEYWORDS)),
        Meta(property="og:type", content="website"),
        Meta(property="og:site_name", content="FastSME"),
        Meta(property="og:title", content=page_title),
        Meta(property="og:description", content=page_description),
        Meta(property="og:url", content=canonical),
        Meta(name="twitter:card", content="summary"),
        Meta(name="twitter:title", content=page_title),
        Meta(name="twitter:description", content=page_description),
        Script(NotStr(json.dumps(structured, separators=(",", ":"))), type="application/ld+json"),
    )


async def sitemap():
    entries = [*SITEMAP_ENTRIES]
    entries.extend((f"/jobs/{job['slug']}", 'daily', '0.8') for job in recruitment.public_jobs())
    urls = "\n".join(
        f'  <url><loc>{BASE_URL}{path}</loc><changefreq>{frequency}</changefreq><priority>{priority}</priority></url>'
        for path, frequency, priority in entries
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
"""
    return Response(xml, media_type="application/xml")


async def llms():
    body = f"""# FastHRM

> Free, MIT-licensed people operations, recruiting, performance, and employee lifecycle software for SMEs and startups.

## Public pages

- [Home]({BASE_URL}/): Product overview and access.
- [Features]({BASE_URL}/features): Available and coming-soon capabilities; every listed feature is Free.
- [How we compare]({BASE_URL}/compare): Source-linked comparison with Gusto, BambooHR, Rippling, Deel, Zoho People, and Odoo HR.
- [Careers]({BASE_URL}/careers): Published roles and individual job specification pages.
- [Developers]({BASE_URL}/developers): Public API resources, examples, OpenAPI, Swagger UI, and ReDoc.
- [Privacy]({BASE_URL}/privacy): Candidate privacy information.

## Key facts

- FastHRM is open source under the MIT licence: https://github.com/predictivelabsai/FastHRM
- Every available feature is Free; coming-soon labels describe availability, not paid tiers.
- Public job pages are discoverable through {BASE_URL}/sitemap.xml.
- API reads are public; supported writes require a configured bearer token.
"""
    return Response(body, media_type="text/plain")


async def robots():
    body = f"""User-agent: *
Allow: /
Disallow: /admin
Disallow: /app
Disallow: /auth/
Disallow: /login
Disallow: /register
Disallow: /api/

Sitemap: {BASE_URL}/sitemap.xml
"""
    return Response(body, media_type="text/plain")


def register_seo_routes(app):
    paths = {getattr(route, "path", None) for route in app.routes}
    if "/sitemap.xml" not in paths:
        app.route("/sitemap.xml", methods=["GET"])(sitemap)
        app.routes.insert(0, app.routes.pop())
    if "/robots.txt" not in paths:
        app.route("/robots.txt", methods=["GET"])(robots)
        app.routes.insert(0, app.routes.pop())
    if "/llms.txt" not in paths:
        app.route("/llms.txt", methods=["GET"])(llms)
        app.routes.insert(0, app.routes.pop())
