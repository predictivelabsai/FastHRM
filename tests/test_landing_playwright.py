"""Browser checks for the responsive public landing navigation."""
from __future__ import annotations

import importlib

import pytest

playwright = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is optional in local FastHR development environments",
)


@pytest.fixture(scope="module")
def chromium_browser():
    """Use Chromium when installed; otherwise leave the browser test skipped."""
    with playwright.sync_playwright() as runner:
        try:
            browser = runner.chromium.launch()
        except playwright.Error as exc:
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        yield browser
        browser.close()


@pytest.mark.parametrize("width", [1280, 375])
def test_landing_has_one_visible_nav_control_set(
    tmp_path, monkeypatch, chromium_browser, width,
):
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "landing-browser.sqlite"))
    monkeypatch.setenv("FASTSME_AUTH_DB", str(tmp_path / "accounts-browser.sqlite"))
    from web import account_auth, landing

    importlib.reload(account_auth)
    importlib.reload(landing)
    rendered = str(landing.landing_page())

    page = chromium_browser.new_page(viewport={"width": width, "height": 900})
    page.route("**/*", lambda route: route.abort())
    page.set_content(rendered, wait_until="domcontentloaded")

    nav = page.locator(".fs-nav")
    assert nav.locator("[data-nav-brand]:visible").count() == 1

    if width == 375:
        assert nav.locator("[data-language-control]:visible").count() == 0
        assert nav.locator("[data-sign-in-action]:visible").count() == 0
        nav.locator(".fs-menu-toggle").click()

    assert nav.locator("[data-language-control]:visible").count() == 1
    assert nav.locator("[data-sign-in-action]:visible").count() == 1
    page.close()
