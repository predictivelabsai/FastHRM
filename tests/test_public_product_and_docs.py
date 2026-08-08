import asyncio
import json
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _public_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "public-pages.sqlite"))
    monkeypatch.setenv("FASTSME_AUTH_DB", str(tmp_path / "accounts.sqlite"))
    from web import account_auth, landing, developer
    importlib.reload(account_auth)
    importlib.reload(landing)
    importlib.reload(developer)
    return landing, developer


def test_feature_catalog_prices_every_module_as_free_and_marks_delivery(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.features_page())
    assert len(landing.FEATURE_CATALOG) >= 20
    assert rendered.count('class="pc-price">Free<') == len(landing.FEATURE_CATALOG)
    assert "Available" in rendered
    assert "Coming soon" in rendered
    assert "Careers publishing" in rendered
    assert "/jobs/" not in rendered  # no fabricated public role is advertised
    assert 'href="https://hrm.fastsme.com/features"' in rendered
    assert 'rel="canonical"' in rendered


def test_public_landing_links_to_features_and_comparison(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page())
    assert 'href="/features"' in rendered
    assert 'href="/compare"' in rendered


def test_login_surface_uses_the_current_google_and_registration_flow(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page(open_auth=True))
    assert "Continue with Google" in rendered
    assert "Create your FastHRM account" in rendered
    assert "/auth/local/forgot" in rendered
    assert "authOpen('login')" in rendered


def test_public_pages_show_the_runtime_version_in_the_footer(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    import version
    for page in (landing.landing_page, landing.features_page, landing.comparison_page):
        rendered = str(page())
        assert version.label() in rendered
        assert 'href="/about"' in rendered


def test_comparison_uses_requested_vendors_and_aeo_schema(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.comparison_page())
    for vendor in ("FastHRM", "Gusto", "BambooHR", "Rippling", "Deel", "Zoho People", "Odoo HR"):
        assert vendor in rendered
    assert "Capterra" not in rendered
    assert "FAQPage" in rendered
    assert "ItemList" in rendered
    assert 'href="https://hrm.fastsme.com/compare"' in rendered
    assert 'rel="canonical"' in rendered


def test_sitemap_and_llms_cover_every_public_discovery_page(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "seo.sqlite"))
    from web import seo
    monkeypatch.setattr(seo.recruitment, "public_jobs", lambda: [{"slug": "product-designer"}])
    sitemap = asyncio.run(seo.sitemap()).body.decode()
    for path in ("/features", "/compare", "/careers", "/developers", "/privacy", "/jobs/product-designer"):
        assert f"https://hrm.fastsme.com{path}" in sitemap
    assert "https://hrm.fastsme.com/products" not in sitemap
    llms = asyncio.run(seo.llms()).body.decode()
    assert "[Features](https://hrm.fastsme.com/features)" in llms
    assert "[How we compare](https://hrm.fastsme.com/compare)" in llms


def test_developer_page_exposes_current_contract_and_examples(tmp_path, monkeypatch):
    _, developer = _public_modules(tmp_path, monkeypatch)
    rendered = str(developer.developer_page())
    assert developer.API_RELEASE in rendered
    assert "/api/openapi.json" in rendered
    assert "Authorization: Bearer" in rendered
    assert "limit=20&amp;offset=0" in rendered


def test_committed_swagger_matches_runtime_openapi(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "api.sqlite"))
    from web.api import api
    committed = json.loads((ROOT / "swagger.json").read_text(encoding="utf-8"))
    assert committed == api.openapi()
