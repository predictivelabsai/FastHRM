import asyncio
import json
import importlib
import asyncio
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _public_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "public-pages.sqlite"))
    monkeypatch.setenv("FASTSME_AUTH_DB", str(tmp_path / "accounts.sqlite"))
    from web import account_auth, landing, developer
    importlib.reload(account_auth)
    importlib.reload(landing)
    importlib.reload(developer)
    return landing, developer


@pytest.mark.parametrize("lang", ["et", "en"])
def test_feature_catalog_prices_every_module_as_free_and_marks_delivery(
    tmp_path, monkeypatch, lang,
):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.features_page(lang=lang))
    copy = landing.t(lang)
    assert len(landing.FEATURE_CATALOG) >= 20
    free_label = f'class="pg-price">{copy["feat_pg_free"]}<'
    assert rendered.count(free_label) == len(landing.FEATURE_CATALOG)
    assert copy["feat_pg_status_avail"] in rendered
    assert copy["feat_pg_status_soon"] in rendered
    assert "Careers publishing" in rendered
    assert "/jobs/" not in rendered  # no fabricated public role is advertised
    assert 'href="https://fasthr.eu/features"' in rendered
    assert 'rel="canonical"' in rendered


def test_public_landing_links_to_features_and_comparison(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page())
    assert 'href="/features"' in rendered
    assert 'href="/compare"' in rendered


def test_public_landing_uses_local_font_assets_and_responsive_demo(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page())
    assert 'rel="preload"' in rendered
    assert rendered.count('as="font"') == 2
    assert '/static/fonts/bricolagegrotesque-latin.woff2' in rendered
    assert '/static/fonts/hankengrotesk-latin.woff2' in rendered
    assert 'href="/static/fonts/fonts.css"' in rendered
    assert 'href="https://fonts.googleapis.com' not in rendered
    assert 'href="https://fonts.gstatic.com' not in rendered
    assert '<picture>' in rendered
    assert 'type="image/webp"' in rendered
    assert '/static/product-demo-880.webp 880w' in rendered
    assert '/static/product-demo-1100.webp 1100w' in rendered
    assert 'src="/static/product-demo.gif"' in rendered


@pytest.mark.parametrize(
    ("lang", "price_example", "faq_question", "faq_answer"),
    [
        ("et", "30 inimese tiim maksab 30 € kuus. Kõik funktsioonid kaasas.",
         "Kas FastHR on tasuta?", "Jah. Kõik saadaolevad FastHR-i funktsioonid on tasuta"),
        ("en", "A 30-person team pays €30 a month, all features included.",
         "Is FastHR free?", "Yes. Every available FastHR feature is free"),
    ],
)
def test_public_landing_uses_owner_requested_copy_and_fast_hr_header(
    tmp_path, monkeypatch, lang, price_example, faq_question, faq_answer,
):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page(lang=lang))
    assert price_example in rendered
    assert faq_question in rendered
    assert faq_answer in rendered
    assert '<th class="ct-fh"><span class="pg-name">FastHR</span></th>' in rendered
    assert '<span>FastHR<span>Meie</span></span>' not in rendered
    assert '<span>FastHR<span>Us</span></span>' not in rendered
    assert "FASTHRUS" not in rendered
    assert "font-family:var(--font-display);font-weight:700;font-size:16px" in landing.COMPARISON_TABLE_CSS
    assert "letter-spacing:normal;text-transform:none;color:var(--text)" in landing.COMPARISON_TABLE_CSS


@pytest.mark.parametrize("lang", ["et", "en"])
def test_public_landing_uses_runtime_mock_version_and_only_shows_fast_hr_price(
    tmp_path, monkeypatch, lang,
):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    import version

    runtime_label = "v9.9.9 · runtime-sentinel+"
    monkeypatch.setattr(version, "label", lambda: runtime_label)
    rendered = str(landing.landing_page(lang=lang))
    assert runtime_label in rendered
    assert "deff1fb" not in rendered
    prices = landing.t(lang)["cmp2_prices"]
    assert len(prices) == 6
    assert prices[0] in rendered
    assert prices[1:] == [""] * 5


@pytest.mark.parametrize(("lang", "active", "inactive"), [
    ("et", "estonia", "global"), ("en", "global", "estonia"),
])
def test_landing_comparison_switcher_localizes_and_defaults_by_language(
    tmp_path, monkeypatch, lang, active, inactive,
):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page(lang=lang))
    copy = landing.t(lang)
    assert copy["cmp_toggle_estonia"] in rendered
    assert copy["cmp_toggle_global"] in rendered
    assert 'data-compare-switcher="true"' in rendered
    assert f'data-compare-panel="{active}"' in rendered
    assert f'data-compare-panel="{inactive}"' in rendered
    assert "data-compare-toggle" in rendered
    assert "aria-pressed" in rendered
    assert "aria-hidden" in rendered
    assert "GLOBAL_PRODUCTS" not in rendered


def test_comparison_tables_use_glyph_rows_and_leave_competitor_prices_empty(
    tmp_path, monkeypatch,
):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.comparison_page())
    assert rendered.count("class=\"ct-pricerow\"") == 2
    assert rendered.count("class=\"ct-mark ct-yes\"") > 20
    assert "Quote-based" not in rendered
    assert "Inquiry-based or quote-based" not in rendered
    assert "Official source" not in rendered
    assert "Ametlik allikas" not in rendered
    assert 'class="pg-name" href=' not in rendered
    assert "persona.ee" not in rendered


@pytest.mark.parametrize("lang", ["et", "en"])
def test_auth_surface_uses_localized_copy_and_current_registration_flow(
    tmp_path, monkeypatch, lang,
):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.landing_page(open_auth=True, lang=lang))
    copy = landing.t(lang)
    assert copy["auth_google"] in rendered
    assert copy["auth_login_title"].format(app_name="FastHR") in rendered
    assert copy["auth_register_title"].format(app_name="FastHR") in rendered
    assert "/auth/local/forgot" in rendered
    assert "authOpen('login')" in rendered


def test_public_pages_show_the_runtime_version_in_the_footer(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    import version
    for page in (landing.landing_page, landing.features_page, landing.comparison_page):
        rendered = str(page())
        assert version.label() in rendered
        assert 'href="/about"' not in rendered


def test_public_pages_have_skip_links_and_shared_developer_shell(tmp_path, monkeypatch):
    landing, developer = _public_modules(tmp_path, monkeypatch)
    pages = (landing.landing_page(), landing.features_page(), landing.comparison_page(), developer.developer_page())
    for page in pages:
        rendered = str(page)
        assert 'class="fs-skip"' in rendered
        assert 'href="#main-content"' in rendered
        assert 'id="main-content"' in rendered
    rendered = str(developer.developer_page())
    assert 'class="fs-nav' in rendered
    assert 'class="dev-docs"' not in rendered
    assert 'lang="et"' in rendered


def test_public_touch_targets_use_shared_adaptation_rules(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    from web.careers import CAREERS_CSS
    from web.design import DESIGN_CSS

    assert "@media(pointer:coarse)" in DESIGN_CSS
    for selector in (".fs-brand", ".fs-nav-link", ".fs-lang a", ".fs-foot-col a",
                     ".fs-btn-ghost", ".ct-cta", ".pg-name"):
        assert selector in DESIGN_CSS
    assert ".fs-foot-col a{display:flex;align-items:center;min-height:40px" in DESIGN_CSS
    assert ".ct-cta{display:inline-flex;align-items:center;justify-content:center;min-height:44px" in landing.LANDING_CSS
    assert ".pg-compare .pg-name{display:inline-flex;align-items:center;min-height:40px;padding-block:8px" in landing.PUBLIC_PAGE_CSS
    assert ".c-link{" in CAREERS_CSS and "min-height:44px" in CAREERS_CSS


def test_public_typography_roles_are_consolidated(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    from web.account_auth import AUTH_CSS
    from web.design import DESIGN_CSS

    assert "h2{font-size:clamp(28px,4vw,40px)}" in DESIGN_CSS
    assert "h3{font-size:20px}" in DESIGN_CSS
    assert "line-height:1.04" in DESIGN_CSS
    assert "line-height:1.25" not in landing.PUBLIC_PAGE_CSS
    assert "line-height:1.15" not in landing.PUBLIC_PAGE_CSS
    assert ".fs-footer-legal{flex-basis:100%;max-width:72ch" in DESIGN_CSS
    assert ".lh-suite-label{" in landing.LANDING_CSS
    assert "max-width:34ch" in landing.LANDING_CSS
    assert "letter-spacing:normal" in landing.LANDING_CSS
    assert ".lh-suite-label{color:var(--muted);font-size:12px;font-weight:800;letter-spacing:normal;max-width:34ch;text-align:center}" in landing.LANDING_CSS
    assert ".lh-trust,.lh-suite-label,.ct-foot{font-size:14px}" in landing.LANDING_CSS
    assert ".pg-note{" in landing.PUBLIC_PAGE_CSS and "max-width:70ch" in landing.PUBLIC_PAGE_CSS
    assert ".pg-faq p{" in landing.PUBLIC_PAGE_CSS and "max-width:70ch" in landing.PUBLIC_PAGE_CSS
    assert ".ct .ct-feat{" in landing.COMPARISON_TABLE_CSS
    assert "font-family:var(--font-body);font-weight:600;font-size:14px" in landing.COMPARISON_TABLE_CSS
    assert ".ct th.ct-feat{font-size:16px}" in landing.COMPARISON_TABLE_CSS
    assert "font-family:var(--font-body);font-size:8px" in landing.LANDING_CSS
    assert "font-weight:600;color:var(--ink)" in AUTH_CSS


def test_retired_public_careers_landing_redirects_home(tmp_path, monkeypatch):
    db_path = tmp_path / "careers-redirect.sqlite"
    shutil.copyfile(ROOT / "fasthr.sqlite", db_path)
    monkeypatch.setenv("FASTHR_DB", str(db_path))
    monkeypatch.setenv("FASTSME_AUTH_DB", str(tmp_path / "careers-redirect-accounts.sqlite"))
    import db
    importlib.reload(db)
    import web_app
    from starlette.testclient import TestClient

    response = TestClient(web_app.app).get("/careers", follow_redirects=False)
    assert response.status_code in (301, 302, 303, 307)
    assert response.headers["location"] == "/"


def test_public_pricing_redirects_to_landing_anchor(tmp_path, monkeypatch):
    db_path = tmp_path / "pricing-redirect.sqlite"
    shutil.copyfile(ROOT / "fasthr.sqlite", db_path)
    monkeypatch.setenv("FASTHR_DB", str(db_path))
    monkeypatch.setenv("FASTSME_AUTH_DB", str(tmp_path / "pricing-redirect-accounts.sqlite"))
    import db
    importlib.reload(db)
    import web_app
    from starlette.testclient import TestClient

    response = TestClient(web_app.app).get("/pricing", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/#pricing"


def test_comparison_uses_requested_vendors_and_aeo_schema(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.comparison_page())
    for vendor in ("FastHR", "Persona", "Wemply", "HRM4Baltics", "hours24", "Yester", "Gusto", "BambooHR", "Rippling", "Deel", "Zoho People", "Odoo HR"):
        assert vendor in rendered
    assert "Capterra" not in rendered
    assert "FAQPage" in rendered
    assert "ItemList" in rendered
    assert 'href="https://fasthr.eu/compare"' in rendered
    assert 'rel="canonical"' in rendered


def test_sitemap_and_llms_cover_every_public_discovery_page(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "seo.sqlite"))
    from web import seo
    monkeypatch.setattr(seo.recruitment, "public_jobs", lambda: [{"slug": "product-designer"}])
    sitemap = asyncio.run(seo.sitemap()).body.decode()
    for path in ("/features", "/compare", "/developers", "/privacy", "/jobs/product-designer"):
        assert f"https://fasthr.eu{path}" in sitemap
    assert "https://fasthr.eu/products" not in sitemap
    llms = asyncio.run(seo.llms()).body.decode()
    assert "[Features](https://fasthr.eu/features)" in llms
    assert "[How we compare](https://fasthr.eu/compare)" in llms


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
