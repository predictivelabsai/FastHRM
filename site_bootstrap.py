"""Idempotent, config-driven provisioning of a branded careers instance.

A separate FastHR deployment (for example Predictive Labs' hr.* domains) points
``FASTHR_BOOTSTRAP`` at a JSON file. On boot this ensures the organisation,
one brand per custom domain, the multilingual careers site and its jobs exist.
Existing rows are left alone unless ``FASTHR_BOOTSTRAP_FORCE=1`` so edits made
in the admin UI are not overwritten on every restart. Nothing runs when the
variable is unset, so the main fasthr.eu instance is unaffected.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import db
import recruitment
import recruitment_enterprise

logger = logging.getLogger("fasthr.bootstrap")
ACTOR = "site-bootstrap"
JOB_FIELDS = ("public_title", "summary", "description", "requirements", "benefits",
              "seo_title", "seo_description")


def load_config(path: str | os.PathLike) -> dict:
    target = Path(path)
    if not target.is_absolute():
        target = Path(__file__).parent / target
    return json.loads(target.read_text(encoding="utf-8"))


def _ensure_brand(org_id: int, brand: dict, domain: dict, force: bool) -> int:
    slug = domain.get("brand_slug") or f"{brand['slug']}-{domain['host'].replace('.', '-')}"
    host = domain["host"].strip().lower()
    row = db.one("SELECT id FROM brands WHERE lower(custom_domain)=? OR (organization_id=? AND slug=?)",
                 (host, org_id, slug))
    if row and not force:
        return row["id"]
    if row:
        with db.cursor() as conn:
            conn.execute(
                """UPDATE brands SET name=?,logo_url=?,favicon_url=?,primary_color=?,accent_color=?,
                   custom_domain=?,updated=datetime('now') WHERE id=?""",
                (brand["name"], brand.get("logo_url", ""), brand.get("favicon_url", ""),
                 brand["primary_color"], brand["accent_color"], host, row["id"]))
        return row["id"]
    return recruitment_enterprise.create_brand(
        org_id, brand["name"], slug, logo_url=brand.get("logo_url", ""),
        favicon_url=brand.get("favicon_url", ""), primary_color=brand["primary_color"],
        accent_color=brand["accent_color"], custom_domain=host)


def _ensure_site(brand_ids: list[tuple[int, str]], brand: dict, site: dict, force: bool) -> int:
    default_locale = site.get("default_locale", "en")
    headline = site.get("headline", {}).get(default_locale, "")
    intro = site.get("introduction", {}).get(default_locale, "")
    row = db.one("SELECT id FROM career_sites WHERE slug=?", (site["slug"],))
    if row:
        site_id = row["id"]
        if force:
            with db.cursor() as conn:
                conn.execute(
                    """UPDATE career_sites SET name=?,headline=?,introduction=?,brand_color=?,accent_color=?,
                       logo_url=?,privacy_policy_url=?,is_active=1,updated=datetime('now') WHERE id=?""",
                    (site["name"], headline, intro, brand["primary_color"], brand["accent_color"],
                     brand.get("logo_url", ""), site.get("privacy_policy_url", "/privacy"), site_id))
    else:
        first_brand, first_locale = brand_ids[0]
        site_id = recruitment_enterprise.create_career_site(
            first_brand, site["name"], site["slug"], locale=first_locale,
            headline=headline, introduction=intro)
        if site.get("privacy_policy_url"):
            with db.cursor() as conn:
                conn.execute("UPDATE career_sites SET privacy_policy_url=? WHERE id=?",
                             (site["privacy_policy_url"], site_id))
    with db.cursor() as conn:
        for brand_id, locale in brand_ids:
            conn.execute("INSERT OR IGNORE INTO career_site_brands(career_site_id,brand_id,locale) VALUES (?,?,?)",
                         (site_id, brand_id, locale))
    for locale in site.get("locales", []):
        if locale == default_locale:
            continue
        for key, values in (("headline", site.get("headline", {})), ("introduction", site.get("introduction", {}))):
            if values.get(locale):
                recruitment_enterprise.save_translation("career_site", site_id, locale, key,
                                                        values[locale], actor=ACTOR)
    return site_id


def _ensure_job(site_id: int, primary_brand: int, job: dict, force: bool) -> int:
    primary = job.get("primary_locale", "en")
    content = job["locales"][primary]
    row = db.one("SELECT id FROM job_openings WHERE code=?", (job["code"],))
    values = {
        "title": job["title"], "location": job.get("location", ""),
        "remote_policy": job.get("remote_policy", "Hybrid"),
        "employment_type": job.get("employment_type", "Permanent"),
        "currency": job.get("currency", "EUR"), "comp_min": job.get("comp_min"),
        "comp_max": job.get("comp_max"), "application_deadline": job.get("application_deadline"),
        "slug": content["slug"], **{k: content.get(k, "") for k in JOB_FIELDS},
    }
    if row and not force:
        return row["id"]
    if row:
        job_id = row["id"]
        recruitment.save_job(job_id, values, actor=ACTOR)
    else:
        job_id = recruitment.create_job(values, actor=ACTOR)
        with db.cursor() as conn:
            conn.execute("UPDATE job_openings SET code=? WHERE id=?", (job["code"], job_id))
    posting = recruitment.ensure_posting(job_id, actor=ACTOR)
    with db.cursor() as conn:
        conn.execute("UPDATE job_postings SET career_site_id=? WHERE id=?", (site_id, posting["id"]))
    for locale, loc in job["locales"].items():
        recruitment_enterprise.distribute_job(job_id, site_id, brand_id=primary_brand,
                                              locale=locale, slug=loc["slug"],
                                              status=job.get("status", "Published"))
        if locale != primary:
            for key in JOB_FIELDS:
                if loc.get(key):
                    recruitment_enterprise.save_translation("job_posting", posting["id"], locale, key,
                                                            loc[key], actor=ACTOR)
    if job.get("status", "Published") == "Published" and posting["publication_status"] != "Published":
        recruitment.transition(job_id, "Published", actor=ACTOR)
    return job_id


def apply_config(config: dict, *, force: bool = False) -> dict:
    org_cfg = config["organization"]
    org = recruitment_enterprise.ensure_organization(
        org_cfg["name"], slug=org_cfg["slug"], default_locale=org_cfg.get("default_locale", "en"),
        timezone_name=org_cfg.get("timezone", "Europe/Tallinn"))
    brand = config["brand"]
    brand_ids = [(_ensure_brand(org["id"], brand, d, force), d.get("locale", "en"))
                 for d in config["domains"]]
    site_id = _ensure_site(brand_ids, brand, config["site"], force)
    job_ids = [_ensure_job(site_id, brand_ids[0][0], job, force) for job in config.get("jobs", [])]
    return {"organization_id": org["id"], "brand_ids": [b for b, _ in brand_ids],
            "site_id": site_id, "job_ids": job_ids}


def run_from_env() -> dict | None:
    path = os.getenv("FASTHR_BOOTSTRAP", "").strip()
    if not path:
        return None
    try:
        result = apply_config(load_config(path), force=os.getenv("FASTHR_BOOTSTRAP_FORCE", "0") == "1")
    except Exception:  # never block boot on a bad bootstrap file
        logger.exception("Site bootstrap from %s failed", path)
        return None
    logger.info("Site bootstrap applied from %s: %s", path, result)
    return result
