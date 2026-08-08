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


def test_product_catalog_prices_every_module_as_free_and_marks_delivery(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    rendered = str(landing.products_page())
    assert len(landing.PRODUCTS) >= 20
    assert rendered.count('class="pc-price">Free<') == len(landing.PRODUCTS)
    assert "Available" in rendered
    assert "Coming soon" in rendered
    assert "Careers publishing" in rendered
    assert "/jobs/" not in rendered  # no fabricated public role is advertised


def test_public_landing_links_to_products(tmp_path, monkeypatch):
    landing, _ = _public_modules(tmp_path, monkeypatch)
    assert 'href="/products"' in str(landing.landing_page())


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
