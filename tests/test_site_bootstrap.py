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
