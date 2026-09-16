"""Build identity must be honest: stamped when available, "unknown" when not."""
from __future__ import annotations

import importlib


def _fresh(monkeypatch, **env):
    """Reload version.py with a controlled environment (its lookups are cached)."""
    for k in ("SOURCE_COMMIT", "COOLIFY_BRANCH", "FASTHR_COMMIT",
              "FASTHR_BRANCH", "FASTHR_BUILD_DATE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import version
    importlib.reload(version)
    return version


def test_version_comes_from_the_version_file(fresh_db, monkeypatch):
    v = _fresh(monkeypatch)
    assert v.version() == v.VERSION_FILE.read_text().strip()
    assert v.version() == "0.4.0"


def test_authenticated_shell_shows_the_runtime_version(fresh_db, monkeypatch):
    v = _fresh(monkeypatch, FASTHR_COMMIT="abc1234")
    from web.layout import topbar
    rendered = str(topbar("test", "recruiter@example.com"))
    assert v.label() in rendered
    assert 'href="/about"' in rendered


def test_authenticated_sidebar_sections_are_collapsible(fresh_db):
    from web.layout import LAYOUT_JS, NAV_ITEMS, left_pane
    rendered = str(left_pane("payroll"))
    english = str(left_pane("payroll", lang="en"))
    assert rendered.count('class="nav-section"') == len(NAV_ITEMS)
    assert '<details open data-section="palk"' in rendered
    assert 'aria-label="Ava või sulge INIMESED"' in rendered
    assert 'href="/payroll"' in rendered
    assert 'nav-section-arrow' in rendered
    assert '<h4>PAY</h4><span aria-hidden="true" class="nav-section-arrow">' in english
    assert 'Payroll' in english
    assert 'Palgaarvestus' not in english
    assert 'TULEMUSLIKKUS' not in english
    assert 'nav-section-controls' not in rendered
    assert '&lt;&lt;' not in rendered
    assert '&gt;&gt;' not in rendered
    assert 'if(active)section.open=true;' in LAYOUT_JS


def test_ai_rail_is_localised_and_has_a_useful_empty_state(fresh_db):
    from fasthtml.common import Div
    from web.layout import page

    english = str(page("dashboard", "", "admin@fasthr.example", None, Div("content"), lang="en"))
    assert 'class="chat-empty-state"' in english
    assert "How can I help?" in english
    assert "Try asking" in english
    assert "Who is on leave today?" in english
    assert "Ask about HR or type /leave /help" in english
    assert "Kuidas saan aidata?" not in english


def test_env_stamp_wins_over_git(fresh_db, monkeypatch):
    """A deployed container has no git, so the stamp is the only source."""
    v = _fresh(monkeypatch, FASTHR_COMMIT="deadbeef99", FASTHR_BRANCH="main",
               FASTHR_BUILD_DATE="2026-08-04")
    assert v.commit() == "deadbeef99"
    assert v.branch() == "main"
    assert v.build_date() == "2026-08-04"
    assert v.label() == "v0.4.0"
    assert "deadbeef99" in v.detail()


def test_stamped_build_is_never_marked_dirty(fresh_db, monkeypatch):
    v = _fresh(monkeypatch, FASTHR_COMMIT="deadbeef99")
    assert v.dirty() is False
    assert "+" not in v.label()


def test_coolify_source_commit_wins_over_stale_manual_stamp(fresh_db, monkeypatch):
    v = _fresh(monkeypatch, SOURCE_COMMIT="2cebf26a2501088cc3c5487b2481d627933c4504",
               COOLIFY_BRANCH="main", FASTHR_COMMIT="9ad138f",
               FASTHR_BUILD_DATE="2026-08-04")
    assert v.commit() == "2cebf26a2501"
    assert v.branch() == "main"
    assert v.build_date() == ""
    assert v.dirty() is False


def test_unknown_provenance_says_so(fresh_db, monkeypatch):
    """With no stamp and no git, the build must admit it doesn't know."""
    v = _fresh(monkeypatch)
    monkeypatch.setattr(v, "_git", lambda *a: "")
    v.commit.cache_clear()
    v.branch.cache_clear()
    v.build_date.cache_clear()
    assert v.commit() == ""
    assert "unknown" in v.detail()
    assert v.label() == f"v{v.version()}", "label falls back to the version alone"


def test_info_exposes_everything_healthz_needs(fresh_db, monkeypatch):
    v = _fresh(monkeypatch, FASTHR_COMMIT="abc1234", FASTHR_BUILD_DATE="2026-08-04")
    info = v.info()
    for key in ("version", "commit", "branch", "build_date", "dirty", "label", "detail"):
        assert key in info


def test_version_file_matches_the_guide_stamp(fresh_db, monkeypatch):
    """build_user_guide.sh reads VERSION, so the docs and the app cannot disagree."""
    v = _fresh(monkeypatch)
    script = (v.ROOT / "scripts" / "build_user_guide.sh").read_text()
    assert "VERSION" in script, "the guide build must read the VERSION file"


def test_auth_return_paths_cannot_leave_the_site(fresh_db):
    from web.account_auth import _safe_next
    assert _safe_next("/payroll") == "/payroll"
    assert _safe_next("https://example.com") == "/"
    assert _safe_next("//example.com") == "/"
