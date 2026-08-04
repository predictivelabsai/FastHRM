"""ATS data layer — requisitions, candidates, applications, parsed CV entities.

Same style as db.py: raw SQL through db.rows/one/scalar, no ORM. Kept in its own
module so db.py stays the three-pillar core.
"""
from __future__ import annotations

import json

import db

STAGES = ["Applied", "Screen", "Interview", "Offer", "Hired", "Rejected"]
OPEN_STAGES = STAGES[:4]
TERMINAL_STAGES = {"Hired", "Rejected"}
JOB_STATUSES = ["Draft", "Open", "On Hold", "Closed", "Filled"]
APP_STATUSES = ["Active", "Hired", "Rejected", "Withdrawn"]
SOURCES = ["Direct", "Referral", "Job Board", "Agency", "Import"]
DOC_KINDS = ["CV", "Cover Letter", "Portfolio", "Other"]


# --- audit ------------------------------------------------------------------

def log_event(entity_type: str, entity_id: int, *, actor: str = "system",
              from_state: str | None = None, to_state: str | None = None, **payload):
    """Append to the shared history spine (plan §A3/F3)."""
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO lifecycle_events(entity_type,entity_id,actor,from_state,to_state,payload_json,created)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (entity_type, entity_id, actor, from_state, to_state,
             json.dumps(payload) if payload else None))


def events_for(entity_type: str, entity_id: int, limit: int = 50):
    return db.rows("""SELECT * FROM lifecycle_events WHERE entity_type=? AND entity_id=?
                      ORDER BY id DESC LIMIT ?""", (entity_type, entity_id, limit))


# --- job openings -----------------------------------------------------------

def jobs(status: str = "All"):
    clause, params = ("", ())
    if status != "All":
        clause, params = ("WHERE j.status=?", (status,))
    return db.rows(f"""SELECT j.*, d.name dept,
                              m.first_name||' '||m.last_name hiring_manager,
                              (SELECT COUNT(*) FROM applications a
                               WHERE a.job_id=j.id AND a.status='Active') active_applicants,
                              (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.id) total_applicants
                       FROM job_openings j
                       LEFT JOIN departments d ON d.id=j.dept_id
                       LEFT JOIN employees m ON m.id=j.hiring_manager_id
                       {clause} ORDER BY (j.status!='Open'), j.opened_on DESC""", params)


def job(job_id: int):
    return db.one("""SELECT j.*, d.name dept, m.first_name||' '||m.last_name hiring_manager
                     FROM job_openings j
                     LEFT JOIN departments d ON d.id=j.dept_id
                     LEFT JOIN employees m ON m.id=j.hiring_manager_id
                     WHERE j.id=?""", (job_id,))


def job_stages(job_id: int) -> list[str]:
    """Stage list for a req — configurable per opening, defaulting to STAGES."""
    j = db.one("SELECT stages_json FROM job_openings WHERE id=?", (job_id,))
    if j and j["stages_json"]:
        try:
            parsed = json.loads(j["stages_json"])
            if isinstance(parsed, list) and parsed:
                return [str(s) for s in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
    return STAGES


def jobs_min():
    return db.rows("""SELECT id, title, code FROM job_openings
                      WHERE status IN ('Open','Draft') ORDER BY title""")


def pipeline_counts(job_id: int) -> dict:
    got = db.rows("SELECT stage, COUNT(*) n FROM applications WHERE job_id=? GROUP BY stage", (job_id,))
    return {r["stage"]: r["n"] for r in got}


# --- candidates -------------------------------------------------------------

def candidates(q: str = "", status: str = "All", job_id: int | None = None):
    where, params = [], []
    if status != "All":
        where.append("c.status=?")
        params.append(status)
    if q:
        where.append("(c.first_name LIKE ? OR c.last_name LIKE ? OR c.email LIKE ? "
                     "OR c.current_title LIKE ? OR c.current_employer LIKE ? OR c.headline LIKE ?)")
        params += [f"%{q}%"] * 6
    if job_id:
        where.append("EXISTS (SELECT 1 FROM applications a WHERE a.candidate_id=c.id AND a.job_id=?)")
        params.append(job_id)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return db.rows(f"""SELECT c.*,
                              (SELECT COUNT(*) FROM candidate_skills s WHERE s.candidate_id=c.id) n_skills,
                              (SELECT COUNT(*) FROM applications a WHERE a.candidate_id=c.id) n_applications,
                              (SELECT a.stage FROM applications a WHERE a.candidate_id=c.id
                               ORDER BY a.id DESC LIMIT 1) latest_stage,
                              (SELECT j.title FROM applications a JOIN job_openings j ON j.id=a.job_id
                               WHERE a.candidate_id=c.id ORDER BY a.id DESC LIMIT 1) latest_job,
                              (SELECT d.file_name FROM candidate_documents d
                               WHERE d.candidate_id=c.id ORDER BY d.id DESC LIMIT 1) latest_document,
                              (SELECT r.status FROM extraction_runs r
                               WHERE r.candidate_id=c.id ORDER BY r.id DESC LIMIT 1) extraction_status
                       FROM candidates c {clause}
                       ORDER BY c.created DESC, c.id DESC LIMIT 300""", tuple(params))


def candidate(cid: int):
    return db.one("""SELECT c.*, e.first_name||' '||e.last_name referrer,
                            (SELECT d.file_name FROM candidate_documents d
                             WHERE d.candidate_id=c.id ORDER BY d.id DESC LIMIT 1) latest_document
                     FROM candidates c LEFT JOIN employees e ON e.id=c.referred_by
                     WHERE c.id=?""", (cid,))


def candidate_profile(cid: int) -> dict:
    """Everything the detail page needs, in one call."""
    return {
        "candidate": candidate(cid),
        "skills": db.rows("SELECT * FROM candidate_skills WHERE candidate_id=? ORDER BY years DESC, skill", (cid,)),
        "experience": db.rows("""SELECT * FROM candidate_experience WHERE candidate_id=?
                                 ORDER BY sort_order, start_date DESC""", (cid,)),
        "education": db.rows("SELECT * FROM candidate_education WHERE candidate_id=? ORDER BY end_year DESC", (cid,)),
        "documents": db.rows("SELECT * FROM candidate_documents WHERE candidate_id=? ORDER BY id DESC", (cid,)),
        "applications": db.rows("""SELECT a.*, j.title job_title, j.code job_code
                                   FROM applications a JOIN job_openings j ON j.id=a.job_id
                                   WHERE a.candidate_id=? ORDER BY a.id DESC""", (cid,)),
        "runs": db.rows("SELECT * FROM extraction_runs WHERE candidate_id=? ORDER BY id DESC LIMIT 10", (cid,)),
    }


def create_candidate(*, first_name="", last_name="", email="", phone="", source="Direct",
                     referred_by=None, consent=False, **extra) -> int:
    cols = {"first_name": first_name.strip(), "last_name": last_name.strip(),
            "email": (email or "").strip().lower(), "phone": phone, "source": source,
            "referred_by": referred_by}
    cols.update({k: v for k, v in extra.items() if k in
                 ("location", "headline", "current_title", "current_employer",
                  "years_experience", "linkedin_url", "notes")})
    names = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    with db.cursor() as conn:
        cur = conn.execute(
            f"""INSERT INTO candidates({names}, consent_at, status, created)
                VALUES ({marks}, {"datetime('now')" if consent else "NULL"}, 'Active', datetime('now'))""",
            tuple(cols.values()))
        cid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("candidate", cid, to_state="Active", source=source)
    return cid


def display_name(row: dict, fallback: str = "Unnamed candidate") -> str:
    """A candidate's name, or a sensible stand-in while extraction is still running."""
    name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
    return name or (row.get("latest_document") or fallback)


def find_candidate_by_email(email: str):
    if not email:
        return None
    return db.one("SELECT * FROM candidates WHERE lower(email)=?", (email.strip().lower(),))


# --- applications -----------------------------------------------------------

def applications_for_job(job_id: int, stage: str = "All"):
    clause, params = "", [job_id]
    if stage != "All":
        clause = "AND a.stage=?"
        params.append(stage)
    return db.rows(f"""SELECT a.*, c.first_name, c.last_name, c.email, c.current_title,
                              c.current_employer, c.years_experience
                       FROM applications a JOIN candidates c ON c.id=a.candidate_id
                       WHERE a.job_id=? {clause}
                       ORDER BY a.rating DESC NULLS LAST, a.applied_on DESC""", tuple(params))


def apply_to_job(candidate_id: int, job_id: int, *, actor: str = "system") -> int | None:
    """Idempotent: one live application per candidate per req."""
    existing = db.one("SELECT id FROM applications WHERE candidate_id=? AND job_id=?", (candidate_id, job_id))
    if existing:
        return existing["id"]
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO applications(candidate_id,job_id,stage,status,applied_on,stage_entered_on,created)
               VALUES (?,?,'Applied','Active',date('now'),date('now'),datetime('now'))""",
            (candidate_id, job_id))
        aid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("application", aid, actor=actor, to_state="Applied", job_id=job_id, candidate_id=candidate_id)
    return aid


def set_stage(app_id: int, stage: str, *, actor: str = "system") -> bool:
    """Move an application. Terminal stages also close the application status.

    A thin, ATS-local state machine — slice 1 replaces this with the shared
    workflow engine (plan §F3) without changing the call sites.
    """
    a = db.one("SELECT * FROM applications WHERE id=?", (app_id,))
    if not a or stage not in job_stages(a["job_id"]):
        return False
    was = a["stage"]
    if was == stage:
        return True
    status = {"Hired": "Hired", "Rejected": "Rejected"}.get(stage, "Active")
    with db.cursor() as conn:
        conn.execute("""UPDATE applications SET stage=?, status=?, stage_entered_on=date('now')
                        WHERE id=?""", (stage, status, app_id))
    log_event("application", app_id, actor=actor, from_state=was, to_state=stage)
    return True


# --- parsed CV persistence --------------------------------------------------

_PROFILE_FIELDS = ("first_name", "last_name", "email", "phone", "location", "headline",
                   "current_title", "current_employer", "years_experience", "linkedin_url")


def save_extracted_profile(candidate_id: int, data: dict, *, overwrite: bool = False) -> dict:
    """Persist a parsed CV onto a candidate.

    Existing values win unless ``overwrite`` — a recruiter's manual correction is
    never silently clobbered by a re-parse. Child rows (skills, experience,
    education) are replaced wholesale, since they came from this document.
    """
    profile = data.get("candidate") or {}
    current = candidate(candidate_id) or {}
    updates = {}
    for f in _PROFILE_FIELDS:
        val = profile.get(f)
        if val in (None, "", []):
            continue
        if overwrite or not current.get(f):
            updates[f] = val

    with db.cursor() as conn:
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE candidates SET {sets} WHERE id=?",
                         (*updates.values(), candidate_id))
        for table in ("candidate_skills", "candidate_experience", "candidate_education"):
            conn.execute(f"DELETE FROM {table} WHERE candidate_id=?", (candidate_id,))
        for s in data.get("skills") or []:
            conn.execute("""INSERT INTO candidate_skills(candidate_id,skill,level,years,evidence,source)
                            VALUES (?,?,?,?,?,'cv-extraction')""",
                         (candidate_id, s.get("skill"), s.get("level"), s.get("years"), s.get("evidence")))
        for i, x in enumerate(data.get("experience") or []):
            conn.execute("""INSERT INTO candidate_experience
                            (candidate_id,employer,title,start_date,end_date,location,summary,sort_order)
                            VALUES (?,?,?,?,?,?,?,?)""",
                         (candidate_id, x.get("employer"), x.get("title"), x.get("start_date"),
                          x.get("end_date"), x.get("location"), x.get("summary"), i))
        for ed in data.get("education") or []:
            conn.execute("""INSERT INTO candidate_education
                            (candidate_id,institution,qualification,field,end_year)
                            VALUES (?,?,?,?,?)""",
                         (candidate_id, ed.get("institution"), ed.get("qualification"),
                          ed.get("field"), ed.get("end_year")))

    counts = {"fields": len(updates), "skills": len(data.get("skills") or []),
              "experience": len(data.get("experience") or []),
              "education": len(data.get("education") or [])}
    log_event("candidate", candidate_id, to_state="Parsed", **counts)
    return counts


def save_document(candidate_id: int, *, file_name: str, mime: str, size: int,
                  stored_path: str, text: str, kind: str = "CV") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO candidate_documents
               (candidate_id,kind,file_name,mime,bytes,stored_path,text_content,uploaded_on)
               VALUES (?,?,?,?,?,?,?,datetime('now'))""",
            (candidate_id, kind, file_name, mime, size, stored_path, text))
        return cur.execute("SELECT last_insert_rowid()").fetchone()[0]


def start_run(candidate_id: int, document_id: int, *, prompt_key: str,
              prompt_version: int, model: str) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO extraction_runs
               (candidate_id,document_id,prompt_key,prompt_version,model,status,created)
               VALUES (?,?,?,?,?,'pending',datetime('now'))""",
            (candidate_id, document_id, prompt_key, prompt_version, model))
        return cur.execute("SELECT last_insert_rowid()").fetchone()[0]


def finish_run(run_id: int, *, status: str, latency_ms: int = 0,
               raw_response: str = "", error: str = ""):
    with db.cursor() as conn:
        conn.execute("""UPDATE extraction_runs
                        SET status=?, latency_ms=?, raw_response=?, error=? WHERE id=?""",
                     (status, latency_ms, (raw_response or "")[:20000], error or None, run_id))


# --- prompt store -----------------------------------------------------------

def active_prompt(key: str) -> dict | None:
    return db.one("""SELECT * FROM prompts WHERE key=? AND is_active=1
                     ORDER BY version DESC LIMIT 1""", (key,))


def prompt_versions(key: str):
    return db.rows("SELECT * FROM prompts WHERE key=? ORDER BY version DESC", (key,))


def save_prompt(key: str, content: str, *, title: str = "", updated_by: str = "") -> int:
    """New version, never an in-place edit — prompt history is the audit trail."""
    latest = db.scalar("SELECT MAX(version) FROM prompts WHERE key=?", (key,)) or 0
    with db.cursor() as conn:
        conn.execute("UPDATE prompts SET is_active=0 WHERE key=?", (key,))
        cur = conn.execute(
            """INSERT INTO prompts(key,version,title,content,is_active,updated_by,updated)
               VALUES (?,?,?,?,1,?,datetime('now'))""",
            (key, latest + 1, title or key, content, updated_by))
        pid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("prompt", pid, actor=updated_by or "system", to_state=f"v{latest + 1}", key=key)
    return latest + 1


def activate_prompt(key: str, version: int) -> bool:
    row = db.one("SELECT id FROM prompts WHERE key=? AND version=?", (key, version))
    if not row:
        return False
    with db.cursor() as conn:
        conn.execute("UPDATE prompts SET is_active=0 WHERE key=?", (key,))
        conn.execute("UPDATE prompts SET is_active=1 WHERE key=? AND version=?", (key, version))
    log_event("prompt", row["id"], to_state=f"v{version} active", key=key)
    return True


# --- metrics ----------------------------------------------------------------

def ats_kpis() -> dict:
    open_reqs = db.scalar("SELECT COUNT(*) FROM job_openings WHERE status='Open'") or 0
    open_headcount = db.scalar("SELECT COALESCE(SUM(headcount-filled),0) FROM job_openings WHERE status='Open'") or 0
    active = db.scalar("SELECT COUNT(*) FROM applications WHERE status='Active'") or 0
    in_process = db.scalar("""SELECT COUNT(*) FROM applications
                              WHERE status='Active' AND stage NOT IN ('Applied')""") or 0
    parsed = db.scalar("SELECT COUNT(DISTINCT candidate_id) FROM extraction_runs WHERE status='ok'") or 0
    total_cands = db.scalar("SELECT COUNT(*) FROM candidates") or 0
    return {"open_reqs": open_reqs, "open_headcount": open_headcount,
            "active_applications": active, "in_process": in_process,
            "candidates": total_cands, "parsed": parsed}
