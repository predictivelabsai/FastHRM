"""Recruiter job authoring, public publishing, applications, and consent."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date

import db
import talent

PUBLICATION_STATUSES = ("Draft", "In review", "Published", "Closed", "Archived")


def _slug(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "job"


def _unique_slug(value: str, *, posting_id: int | None = None) -> str:
    base = _slug(value)
    candidate, suffix = base, 2
    while True:
        row = db.one("SELECT id FROM job_postings WHERE slug=?", (candidate,))
        if not row or row["id"] == posting_id:
            return candidate
        candidate, suffix = f"{base}-{suffix}", suffix + 1


def _number(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ensure_default_site() -> dict:
    site = db.one("SELECT * FROM career_sites WHERE is_active=1 ORDER BY id LIMIT 1")
    if site:
        return site
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO career_sites
               (name,slug,headline,introduction,brand_color,accent_color,
                privacy_policy_url,is_active,created,updated)
               VALUES ('FastHRM Careers','careers','Do work that matters.',
                       'Explore open roles and find your next team.','#0891b2','#0e7490',
                       '/privacy',1,datetime('now'),datetime('now'))"""
        )
    return db.one("SELECT * FROM career_sites WHERE slug='careers'")


def career_site() -> dict:
    return ensure_default_site()


def save_career_site(values: dict, *, actor: str) -> dict:
    site = ensure_default_site()
    color = values.get("brand_color") or site["brand_color"]
    accent = values.get("accent_color") or site["accent_color"]
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = site["brand_color"]
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = site["accent_color"]
    with db.cursor() as conn:
        conn.execute(
            """UPDATE career_sites SET name=?,headline=?,introduction=?,brand_color=?,
                      accent_color=?,logo_url=?,privacy_policy_url=?,updated=datetime('now')
               WHERE id=?""",
            ((values.get("name") or site["name"]).strip(),
             (values.get("headline") or "").strip(),
             (values.get("introduction") or "").strip(), color, accent,
             (values.get("logo_url") or "").strip(),
             (values.get("privacy_policy_url") or "").strip(), site["id"]),
        )
    talent.log_event("career_site", site["id"], actor=actor, to_state="Updated")
    return career_site()


def departments() -> list[dict]:
    return db.rows("SELECT id,name FROM departments ORDER BY name")


def hiring_managers() -> list[dict]:
    return db.rows(
        """SELECT id, first_name||' '||last_name name FROM employees
           WHERE status IN ('Active','Probation') ORDER BY first_name,last_name"""
    )


def posting_for_job(job_id: int) -> dict | None:
    return db.one(
        """SELECT p.*, j.code,j.title,j.dept_id,j.hiring_manager_id,j.headcount,j.filled,
                  j.comp_min,j.comp_max,j.currency,j.location,j.remote_policy,
                  j.employment_type,j.status job_status,j.stages_json,
                  d.name department, e.first_name||' '||e.last_name hiring_manager,
                  s.name career_site_name,s.brand_color,s.accent_color,s.logo_url,
                  s.privacy_policy_url
           FROM job_postings p JOIN job_openings j ON j.id=p.job_id
           LEFT JOIN departments d ON d.id=j.dept_id
           LEFT JOIN employees e ON e.id=j.hiring_manager_id
           LEFT JOIN career_sites s ON s.id=p.career_site_id WHERE p.job_id=?""",
        (job_id,),
    )


def _snapshot(conn, posting_id: int, actor: str) -> None:
    row = conn.execute("SELECT * FROM job_postings WHERE id=?", (posting_id,)).fetchone()
    version = conn.execute(
        "SELECT COALESCE(MAX(version),0)+1 FROM job_posting_versions WHERE job_posting_id=?",
        (posting_id,),
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO job_posting_versions(job_posting_id,version,snapshot_json,actor,created)
           VALUES (?,?,?,?,datetime('now'))""",
        (posting_id, version, json.dumps(dict(row), default=str), actor),
    )


def create_job(values: dict, *, actor: str) -> int:
    title = (values.get("title") or "").strip()
    if not title:
        raise ValueError("A job title is required.")
    site = ensure_default_site()
    with db.cursor() as conn:
        next_code = (conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM job_openings").fetchone()[0])
        cur = conn.execute(
            """INSERT INTO job_openings
               (code,title,dept_id,hiring_manager_id,headcount,filled,comp_min,comp_max,
                currency,location,remote_policy,employment_type,status,description,
                requirements,stages_json,target_date,created)
               VALUES (?,?,?,?,?,0,?,?,?,?,?,?,'Draft',?,?,?, ?,datetime('now'))""",
            (f"REQ-{2000 + next_code}", title, values.get("dept_id") or None,
             values.get("hiring_manager_id") or None, max(1, int(values.get("headcount") or 1)),
             _number(values.get("comp_min")), _number(values.get("comp_max")),
             values.get("currency") or "GBP", (values.get("location") or "").strip(),
             values.get("remote_policy") or "Hybrid",
             values.get("employment_type") or "Permanent",
             (values.get("description") or "").strip(),
             (values.get("requirements") or "").strip(), json.dumps(talent.STAGES),
             values.get("target_date") or None),
        )
        job_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
        slug = _unique_slug(values.get("slug") or title)
        cur = conn.execute(
            """INSERT INTO job_postings
               (job_id,career_site_id,slug,public_title,summary,description,requirements,
                benefits,seo_title,seo_description,application_deadline,publication_status,
                created_by,updated_by,created,updated)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'Draft',?,?,datetime('now'),datetime('now'))""",
            (job_id, site["id"], slug, (values.get("public_title") or title).strip(),
             (values.get("summary") or "").strip(),
             (values.get("description") or "").strip(),
             (values.get("requirements") or "").strip(),
             (values.get("benefits") or "").strip(),
             (values.get("seo_title") or "").strip(),
             (values.get("seo_description") or "").strip(),
             values.get("application_deadline") or None, actor, actor),
        )
        posting_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
        _snapshot(conn, posting_id, actor)
    talent.log_event("job_opening", job_id, actor=actor, to_state="Draft")
    return job_id


def ensure_posting(job_id: int, *, actor: str = "system") -> dict:
    existing = posting_for_job(job_id)
    if existing:
        return existing
    job = talent.job(job_id)
    if not job:
        raise ValueError("No such requisition.")
    site = ensure_default_site()
    slug = _unique_slug(job["title"])
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO job_postings
               (job_id,career_site_id,slug,public_title,summary,description,requirements,
                publication_status,created_by,updated_by,created,updated)
               VALUES (?,?,?,?,?,?,?,'Draft',?,?,datetime('now'),datetime('now'))""",
            (job_id, site["id"], slug, job["title"], "", job.get("description") or "",
             job.get("requirements") or "", actor, actor),
        )
        _snapshot(conn, cur.execute("SELECT last_insert_rowid()").fetchone()[0], actor)
    return posting_for_job(job_id)


def save_job(job_id: int, values: dict, *, actor: str) -> dict:
    posting = ensure_posting(job_id, actor=actor)
    title = (values.get("title") or posting["title"]).strip()
    if not title:
        raise ValueError("A job title is required.")
    slug = _unique_slug(values.get("slug") or posting["slug"] or title,
                        posting_id=posting["id"])
    description = (values.get("description") or "").strip()
    requirements = (values.get("requirements") or "").strip()
    with db.cursor() as conn:
        conn.execute(
            """UPDATE job_openings SET title=?,dept_id=?,hiring_manager_id=?,headcount=?,
                      comp_min=?,comp_max=?,currency=?,location=?,remote_policy=?,employment_type=?,
                      description=?,requirements=?,target_date=? WHERE id=?""",
            (title, values.get("dept_id") or None, values.get("hiring_manager_id") or None,
             max(1, int(values.get("headcount") or 1)), _number(values.get("comp_min")),
             _number(values.get("comp_max")), values.get("currency") or "GBP",
             (values.get("location") or "").strip(), values.get("remote_policy") or "Hybrid",
             values.get("employment_type") or "Permanent", description, requirements,
             values.get("target_date") or None, job_id),
        )
        conn.execute(
            """UPDATE job_postings SET slug=?,public_title=?,summary=?,description=?,
                      requirements=?,benefits=?,seo_title=?,seo_description=?,
                      application_deadline=?,updated_by=?,updated=datetime('now') WHERE id=?""",
            (slug, (values.get("public_title") or title).strip(),
             (values.get("summary") or "").strip(), description, requirements,
             (values.get("benefits") or "").strip(), (values.get("seo_title") or "").strip(),
             (values.get("seo_description") or "").strip(),
             values.get("application_deadline") or None, actor, posting["id"]),
        )
        _snapshot(conn, posting["id"], actor)
    talent.log_event("job_opening", job_id, actor=actor, to_state="Edited")
    return posting_for_job(job_id)


def transition(job_id: int, status: str, *, actor: str) -> dict:
    if status not in PUBLICATION_STATUSES:
        raise ValueError("Invalid publication status.")
    posting = ensure_posting(job_id, actor=actor)
    if status == "Published" and not all(
        (posting["public_title"], posting["description"], posting["requirements"])
    ):
        raise ValueError("A public title, description, and requirements are required to publish.")
    old = posting["publication_status"]
    job_status = "Open" if status == "Published" else "Closed" if status in ("Closed", "Archived") else "Draft"
    with db.cursor() as conn:
        conn.execute(
            """UPDATE job_postings SET publication_status=?,
                      published_at=CASE WHEN ?='Published' THEN COALESCE(published_at,datetime('now')) ELSE published_at END,
                      closed_at=CASE WHEN ? IN ('Closed','Archived') THEN datetime('now') ELSE NULL END,
                      updated_by=?,updated=datetime('now') WHERE id=?""",
            (status, status, status, actor, posting["id"]),
        )
        conn.execute(
            """UPDATE job_openings SET status=?,
                      opened_on=CASE WHEN ?='Open' THEN COALESCE(opened_on,date('now')) ELSE opened_on END
               WHERE id=?""",
            (job_status, job_status, job_id),
        )
        _snapshot(conn, posting["id"], actor)
    talent.log_event("job_posting", posting["id"], actor=actor,
                     from_state=old, to_state=status, job_id=job_id)
    return posting_for_job(job_id)


def schedule_transition(job_id: int, status: str, scheduled_at: str, *, actor: str) -> int:
    if status not in PUBLICATION_STATUSES:
        raise ValueError("Invalid publication status.")
    if not posting_for_job(job_id):
        ensure_posting(job_id, actor=actor)
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO publication_schedules(job_id,action,scheduled_at,status,requested_by,created)
               VALUES (?,?,?,'Pending',?,datetime('now'))""",
            (job_id, status, scheduled_at, actor),
        )
        return cur.lastrowid


def process_publication_schedules(*, actor: str = "publication-worker") -> dict:
    due = db.rows(
        """SELECT * FROM publication_schedules WHERE status='Pending'
           AND scheduled_at<=datetime('now') ORDER BY scheduled_at,id"""
    )
    completed, failed = 0, 0
    for item in due:
        try:
            transition(item["job_id"], item["action"], actor=actor)
            status, error, completed = "Completed", None, completed + 1
        except Exception as exc:
            status, error, failed = "Failed", str(exc), failed + 1
        with db.cursor() as conn:
            conn.execute(
                """UPDATE publication_schedules SET status=?,error=?,processed_at=datetime('now') WHERE id=?""",
                (status, error, item["id"]),
            )
    return {"processed": len(due), "completed": completed, "failed": failed}


def public_jobs() -> list[dict]:
    ensure_default_site()
    return db.rows(
        """SELECT p.*,j.location,j.remote_policy,j.employment_type,j.currency,
                  j.comp_min,j.comp_max,d.name department
           FROM job_postings p JOIN job_openings j ON j.id=p.job_id
           LEFT JOIN departments d ON d.id=j.dept_id
           WHERE p.publication_status='Published'
             AND (p.application_deadline IS NULL OR p.application_deadline>=date('now'))
           ORDER BY p.published_at DESC,p.id DESC"""
    )


def public_job(slug: str, *, include_unpublished: bool = False) -> dict | None:
    clause = "" if include_unpublished else (
        "AND p.publication_status='Published' "
        "AND (p.application_deadline IS NULL OR p.application_deadline>=date('now'))"
    )
    return db.one(
        f"""SELECT p.*,j.code,j.location,j.remote_policy,j.employment_type,j.currency,
                   j.comp_min,j.comp_max,j.headcount,d.name department,
                   e.first_name||' '||e.last_name hiring_manager,s.name career_site_name,
                   s.headline career_headline,s.brand_color,s.accent_color,s.logo_url,
                   s.privacy_policy_url
            FROM job_postings p JOIN job_openings j ON j.id=p.job_id
            LEFT JOIN departments d ON d.id=j.dept_id
            LEFT JOIN employees e ON e.id=j.hiring_manager_id
            LEFT JOIN career_sites s ON s.id=p.career_site_id
            WHERE p.slug=? {clause}""",
        (slug,),
    )


def apply(slug: str, values: dict, *, proof: dict | None = None) -> dict:
    posting = public_job(slug)
    if not posting:
        return {"ok": False, "error": "This job is not accepting applications."}
    first_name = (values.get("first_name") or "").strip()
    last_name = (values.get("last_name") or "").strip()
    email = (values.get("email") or "").strip().lower()
    if not first_name or not last_name or "@" not in email:
        return {"ok": False, "error": "Your name and a valid email address are required."}
    if not values.get("consent"):
        return {"ok": False, "error": "You must acknowledge the recruitment privacy notice."}
    from recruiting_ops import validate_application_form
    valid, form_error, dynamic_answers = validate_application_form(posting["job_id"], values)
    if not valid:
        return {"ok": False, "error": form_error}

    candidate = talent.find_candidate_by_email(email)
    if candidate:
        candidate_id = candidate["id"]
        with db.cursor() as conn:
            conn.execute(
                """UPDATE candidates SET first_name=CASE WHEN first_name='' OR first_name IS NULL THEN ? ELSE first_name END,
                          last_name=CASE WHEN last_name='' OR last_name IS NULL THEN ? ELSE last_name END,
                          phone=CASE WHEN phone='' OR phone IS NULL THEN ? ELSE phone END,
                          location=CASE WHEN location='' OR location IS NULL THEN ? ELSE location END,
                          consent_at=COALESCE(consent_at,datetime('now')) WHERE id=?""",
                (first_name, last_name, (values.get("phone") or "").strip(),
                 (values.get("location") or "").strip(), candidate_id),
            )
    else:
        candidate_id = talent.create_candidate(
            first_name=first_name, last_name=last_name, email=email,
            phone=(values.get("phone") or "").strip(), source="Direct", consent=True,
            location=(values.get("location") or "").strip(),
        )
    application_id = talent.apply_to_job(candidate_id, posting["job_id"], actor="public-application")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO application_answers(application_id,field_key,label,value_text,created)
               VALUES (?,'cover_note','Cover note',?,datetime('now'))
               ON CONFLICT(application_id,field_key) DO UPDATE SET value_text=excluded.value_text""",
            (application_id, (values.get("cover_note") or "").strip()),
        )
        for answer in dynamic_answers:
            conn.execute(
                """INSERT INTO application_answers(application_id,field_key,label,value_text,created)
                   VALUES (?,?,?,?,datetime('now')) ON CONFLICT(application_id,field_key)
                   DO UPDATE SET label=excluded.label,value_text=excluded.value_text""",
                (application_id, answer["field_key"], answer["label"], answer["value_text"]),
            )
        conn.execute(
            """INSERT INTO candidate_consents
               (candidate_id,application_id,purpose,lawful_basis,privacy_policy_url,
                consented_at,expires_at,proof_json)
               VALUES (?,?,?,'consent',?,datetime('now'),date('now','+12 months'),?)""",
            (candidate_id, application_id, "Recruitment for " + posting["public_title"],
             posting.get("privacy_policy_url") or "", json.dumps(proof or {})),
        )
    talent.log_event("application", application_id, actor="public-application",
                     to_state="Submitted", posting_id=posting["id"])
    return {"ok": True, "candidate_id": candidate_id, "application_id": application_id,
            "job_id": posting["job_id"]}


def versions(job_id: int) -> list[dict]:
    posting = ensure_posting(job_id)
    return db.rows(
        """SELECT version,actor,created FROM job_posting_versions
           WHERE job_posting_id=? ORDER BY version DESC""",
        (posting["id"],),
    )
