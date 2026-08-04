"""Build identity must be honest: stamped when available, "unknown" when not."""
from __future__ import annotations

import importlib


def _fresh(monkeypatch, **env):
    """Reload version.py with a controlled environment (its lookups are cached)."""
    for k in ("FASTHR_COMMIT", "FASTHR_BRANCH", "FASTHR_BUILD_DATE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import version
    importlib.reload(version)
    return version


def test_version_comes_from_the_version_file(fresh_db, monkeypatch):
    v = _fresh(monkeypatch)
    assert v.version() == v.VERSION_FILE.read_text().strip()
    assert v.version()[0].isdigit()


def test_env_stamp_wins_over_git(fresh_db, monkeypatch):
    """A deployed container has no git, so the stamp is the only source."""
    v = _fresh(monkeypatch, FASTHR_COMMIT="deadbeef99", FASTHR_BRANCH="main",
               FASTHR_BUILD_DATE="2026-08-04")
    assert v.commit() == "deadbeef99"
    assert v.branch() == "main"
    assert v.build_date() == "2026-08-04"
    assert "deadbeef99" in v.label()


def test_stamped_build_is_never_marked_dirty(fresh_db, monkeypatch):
    v = _fresh(monkeypatch, FASTHR_COMMIT="deadbeef99")
    assert v.dirty() is False
    assert "+" not in v.label()


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
