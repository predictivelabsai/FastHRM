"""Config-driven branded careers instance (e.g. Predictive Labs hr.* domains)."""
from __future__ import annotations

import importlib
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "deploy" / "predictivelabs" / "site.json"


def _modules():
    import recruitment
    import recruitment_enterprise
    import site_bootstrap
    importlib.reload(recruitment)
    importlib.reload(recruitment_enterprise)
    return recruitment, recruitment_enterprise, importlib.reload(site_bootstrap)


def test_bootstrap_creates_brands_site_and_bilingual_job_idempotently(fresh_db):
    recruitment, ent, boot = _modules()
    config = boot.load_config(CONFIG)
    first = boot.apply_config(config)
    second = boot.apply_config(config)
    assert first == second
    assert len(first["brand_ids"]) == 4

    ee = ent.resolve_brand(host="hr.predictivelabs.ee")
    ai = ent.resolve_brand(host="HR.PredictiveLabs.ai:443")
    assert ee["site_slug"] == ai["site_slug"] == "predictivelabs"
    assert ee["default_locale"] == "et" and ai["default_locale"] == "en"

    et_jobs = ent.public_site_jobs("predictivelabs", "et")
    en_jobs = ent.public_site_jobs("predictivelabs", "en")
    assert [j["public_title"] for j in et_jobs] == ["Riigihangete spetsialist (EL)"]
    assert [j["public_title"] for j in en_jobs] == ["Public Procurement Specialist (EU)"]
    assert "2000 € neto" in et_jobs[0]["benefits"]
    assert ent.site_alternates("predictivelabs") == {
        "et": "/sites/predictivelabs/et", "en": "/sites/predictivelabs/en"}
    alternates = ent.job_alternates("predictivelabs", et_jobs[0]["posting_id"])
    assert alternates["et"].endswith("/riigihangete-spetsialist-el")
    assert alternates["en"].endswith("/public-procurement-specialist-eu")
    site = ent.localized_site(ent.public_career_site("predictivelabs", "et"), "et")
    assert site["headline"].startswith("Aita meil")


def test_bootstrap_is_a_no_op_without_env(fresh_db, monkeypatch):
    _, _, boot = _modules()
    monkeypatch.delenv("FASTHR_BOOTSTRAP", raising=False)
    assert boot.run_from_env() is None


def test_estonian_careers_page_renders_localized_labels(fresh_db):
    _, ent, boot = _modules()
    boot.apply_config(boot.load_config(CONFIG))
    from web import careers
    importlib.reload(careers)
    job = ent.public_distributed_job("predictivelabs", "et", "riigihangete-spetsialist-el")
    html = str(careers.job_page(job, locale="et",
                                alternates=ent.job_alternates("predictivelabs", job["posting_id"])))
    for text in ("Ametikohast", "Keda me otsime", "Saada avaldus", "Powered by FastHR"):
        assert text in html
    english = str(careers.job_page(
        ent.public_distributed_job("predictivelabs", "en", "public-procurement-specialist-eu")))
    assert "About the role" in english and "Submit application" in english


def test_site_colours_override_careers_css_defaults(fresh_db):
    _, ent, boot = _modules()
    boot.apply_config(boot.load_config(CONFIG))
    from web import careers
    importlib.reload(careers)
    html = str(careers.job_page(
        ent.public_distributed_job("predictivelabs", "en", "public-procurement-specialist-eu")))
    assert html.rindex("--brand:#0D2A70") > html.rindex("--brand:#0891b2")


def test_ensure_admin_roles_is_idempotent_and_dedupes_sources(fresh_db, monkeypatch):
    _, _, boot = _modules()
    monkeypatch.setenv("FASTHR_ADMIN_EMAIL", "hr-admin@predictivelabs.ai")
    monkeypatch.setenv(
        "FASTHR_ADMIN_EMAILS",
        "kaljuvee@gmail.com, joosep.laats@gmail.com, kaljuvee@gmail.com",
    )
    monkeypatch.setenv("GOOGLE_ALLOWED_EMAILS", "daniel.raissar@gmail.com,kaljuvee@gmail.com")
    first = boot.ensure_admin_roles()
    second = boot.ensure_admin_roles()
    assert set(first) == {
        "hr-admin@predictivelabs.ai",
        "kaljuvee@gmail.com",
        "joosep.laats@gmail.com",
        "daniel.raissar@gmail.com",
    }
    assert second == []
    rows = fresh_db.rows(
        "SELECT account_email, role, scope FROM account_roles ORDER BY account_email")
    assert [dict(r) for r in rows] == [
        {"account_email": "daniel.raissar@gmail.com", "role": "admin", "scope": "all"},
        {"account_email": "hr-admin@predictivelabs.ai", "role": "admin", "scope": "all"},
        {"account_email": "joosep.laats@gmail.com", "role": "admin", "scope": "all"},
        {"account_email": "kaljuvee@gmail.com", "role": "admin", "scope": "all"},
    ]


def test_ensure_admin_role_for_only_allowlisted_emails(fresh_db, monkeypatch):
    _, _, boot = _modules()
    monkeypatch.setenv("FASTHR_ADMIN_EMAIL", "")
    monkeypatch.setenv("FASTHR_ADMIN_EMAILS", "kaljuvee@gmail.com")
    monkeypatch.delenv("GOOGLE_ALLOWED_EMAILS", raising=False)
    assert boot.ensure_admin_role_for("stranger@example.com") is False
    assert boot.ensure_admin_role_for("kaljuvee@gmail.com") is True
    assert boot.ensure_admin_role_for("kaljuvee@gmail.com") is False
    rows = fresh_db.rows("SELECT account_email, role FROM account_roles")
    assert [dict(r) for r in rows] == [
        {"account_email": "kaljuvee@gmail.com", "role": "admin"}]


def test_careers_home_shows_login_only_on_branded_instance(fresh_db, monkeypatch):
    _, ent, boot = _modules()
    boot.apply_config(boot.load_config(CONFIG))
    from web import careers
    importlib.reload(careers)
    site = ent.localized_site(ent.public_career_site("predictivelabs", "et"), "et")
    view = {**site, "name": site.get("name") or site.get("brand_name"),
            "brand_color": site.get("primary_color") or site.get("brand_color"),
            "accent_color": site.get("accent_color"),
            "logo_url": site.get("brand_logo") or site.get("logo_url")}
    jobs = ent.public_site_jobs("predictivelabs", "et")
    monkeypatch.delenv("FASTHR_BOOTSTRAP", raising=False)
    monkeypatch.delenv("FASTHR_CAREERS_SHOW_LOGIN", raising=False)
    importlib.reload(careers)
    html = str(careers.careers_page(view, jobs, careers_path="/sites/predictivelabs/et",
                                    job_prefix="/sites/predictivelabs/et/jobs", locale="et"))
    assert 'href="/login' not in html
    assert "Logi sisse" not in html

    monkeypatch.setenv("FASTHR_CAREERS_SHOW_LOGIN", "1")
    importlib.reload(careers)
    html = str(careers.careers_page(view, jobs, careers_path="/sites/predictivelabs/et",
                                    job_prefix="/sites/predictivelabs/et/jobs", locale="et"))
    assert 'class="c-nav"' in html
    nav = html.split('class="c-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/login"' in nav
    assert "next=" not in nav
    assert ">Logi sisse</a>" in nav
    footer = html.split('class="c-foot"', 1)[1] if 'class="c-foot"' in html else html.split("c-footer", 1)[-1]
    assert 'class="c-footer-auth"' in html
    assert ">Logi sisse</a>" in footer

    en = str(careers.careers_page(view, jobs, locale="en"))
    assert ">Log in</a>" in en
    assert "Logi sisse" not in en

    admin = str(careers.careers_page(
        view, jobs, careers_path="/sites/predictivelabs/et", locale="et",
        viewer={"is_admin": True, "workspace_href": "/talent/candidates"}))
    assert ">HR töölaud</a>" in admin
    assert 'href="/talent/candidates"' in admin
    assert 'href="/logout"' in admin
    assert "Logi sisse" not in admin


def test_job_page_admin_workspace_points_at_the_requisition(fresh_db, monkeypatch):
    _, ent, boot = _modules()
    boot.apply_config(boot.load_config(CONFIG))
    monkeypatch.setenv("FASTHR_CAREERS_SHOW_LOGIN", "1")
    from web import careers
    importlib.reload(careers)
    job = ent.public_distributed_job("predictivelabs", "et", "riigihangete-spetsialist-el")
    html = str(careers.job_page(
        job, locale="et", job_path="/sites/predictivelabs/et/jobs/riigihangete-spetsialist-el",
        viewer={"is_admin": True, "workspace_href": f"/talent/jobs/{job['job_id']}"}))
    assert f'href="/talent/jobs/{job["job_id"]}"' in html
    assert ">HR töölaud</a>" in html
    assert 'href="/logout"' in html
