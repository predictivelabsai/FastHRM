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


# --- interviewing -----------------------------------------------------------

INTERVIEW_KINDS = ["Screen", "Technical", "Culture", "Panel", "Final"]
INTERVIEW_MODES = ["Video", "Onsite", "Phone"]
RECOMMENDATIONS = ["Strong hire", "Hire", "No decision", "No hire", "Strong no hire"]
REC_SCORE = {"Strong hire": 2, "Hire": 1, "No decision": 0, "No hire": -1, "Strong no hire": -2}


def competencies(category: str = "All"):
    clause, params = ("", ()) if category == "All" else ("WHERE category=?", (category,))
    return db.rows(f"SELECT * FROM competencies {clause} ORDER BY category, name", params)


def interviews_for(app_id: int):
    return db.rows("""SELECT i.*, e.first_name||' '||e.last_name interviewer,
                             (SELECT COUNT(*) FROM scorecards s WHERE s.interview_id=i.id) n_scores,
                             (SELECT AVG(s.score) FROM scorecards s WHERE s.interview_id=i.id) avg_score
                      FROM interviews i LEFT JOIN employees e ON e.id=i.interviewer_id
                      WHERE i.application_id=? ORDER BY i.scheduled_at""", (app_id,))


def interviews_for_job(job_id: int):
    return db.rows("""SELECT i.*, c.first_name, c.last_name, c.id candidate_id,
                             e.first_name||' '||e.last_name interviewer,
                             (SELECT AVG(s.score) FROM scorecards s WHERE s.interview_id=i.id) avg_score
                      FROM interviews i
                      JOIN applications a ON a.id=i.application_id
                      JOIN candidates c ON c.id=a.candidate_id
                      LEFT JOIN employees e ON e.id=i.interviewer_id
                      WHERE a.job_id=? ORDER BY i.scheduled_at DESC""", (job_id,))


def schedule_interview(app_id: int, *, interviewer_id: int | None, kind: str, scheduled_at: str,
                       mode: str = "Video", duration: int = 45, actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO interviews(application_id,interviewer_id,kind,scheduled_at,
                   duration_min,mode,status,created)
               VALUES (?,?,?,?,?,?,'Scheduled',datetime('now'))""",
            (app_id, interviewer_id or None, kind if kind in INTERVIEW_KINDS else "Screen",
             scheduled_at, duration, mode if mode in INTERVIEW_MODES else "Video"))
        iid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("interview", iid, actor=actor, to_state="Scheduled", application_id=app_id)
    return iid


def record_scorecard(interview_id: int, scores: dict[int, float], *, comment_by: dict | None = None,
                     recommendation: str = "", notes: str = "", actor: str = "system") -> bool:
    """Save one interviewer's competency scores and recommendation."""
    iv = db.one("SELECT * FROM interviews WHERE id=?", (interview_id,))
    if not iv:
        return False
    comments = comment_by or {}
    with db.cursor() as conn:
        conn.execute("DELETE FROM scorecards WHERE interview_id=?", (interview_id,))
        for comp_id, score in scores.items():
            conn.execute("""INSERT INTO scorecards(interview_id,competency_id,score,comment)
                            VALUES (?,?,?,?)""",
                         (interview_id, comp_id, score, comments.get(comp_id)))
        conn.execute("""UPDATE interviews SET status='Completed', recommendation=?, notes=?
                        WHERE id=?""",
                     (recommendation if recommendation in RECOMMENDATIONS else None,
                      notes or iv["notes"], interview_id))
    log_event("interview", interview_id, actor=actor, from_state=iv["status"],
              to_state="Completed", recommendation=recommendation)
    _refresh_rating(iv["application_id"])
    return True


def _refresh_rating(app_id: int):
    """An application's rating is the mean of its completed scorecards."""
    avg = db.scalar("""SELECT AVG(s.score) FROM scorecards s
                       JOIN interviews i ON i.id=s.interview_id
                       WHERE i.application_id=? AND i.status='Completed'""", (app_id,))
    if avg is not None:
        with db.cursor() as conn:
            conn.execute("UPDATE applications SET rating=? WHERE id=?", (round(avg, 2), app_id))


def calibration(job_id: int):
    """Every candidate's scores side by side, per competency — the calibration view."""
    rows_ = db.rows("""SELECT a.id app_id, c.first_name||' '||c.last_name candidate,
                              a.candidate_id, a.stage, comp.name competency, comp.id comp_id,
                              AVG(s.score) score, COUNT(s.id) n
                       FROM applications a
                       JOIN candidates c ON c.id=a.candidate_id
                       JOIN interviews i ON i.application_id=a.id AND i.status='Completed'
                       JOIN scorecards s ON s.interview_id=i.id
                       JOIN competencies comp ON comp.id=s.competency_id
                       WHERE a.job_id=?
                       GROUP BY a.id, comp.id
                       ORDER BY candidate, comp.name""", (job_id,))
    by_cand: dict[str, dict] = {}
    comps: list[str] = []
    for r in rows_:
        entry = by_cand.setdefault(r["candidate"], {"app_id": r["app_id"], "stage": r["stage"],
                                                    "candidate_id": r["candidate_id"], "scores": {}})
        entry["scores"][r["competency"]] = r["score"]
        if r["competency"] not in comps:
            comps.append(r["competency"])
    for entry in by_cand.values():
        vals = list(entry["scores"].values())
        entry["mean"] = sum(vals) / len(vals) if vals else 0
    return sorted(comps), dict(sorted(by_cand.items(), key=lambda kv: -kv[1]["mean"]))


# --- offers -----------------------------------------------------------------

OFFER_STATUSES = ["Draft", "Pending approval", "Approved", "Sent", "Accepted", "Declined", "Withdrawn"]


def offers_for_job(job_id: int):
    return db.rows("""SELECT o.*, c.first_name, c.last_name, c.id candidate_id, j.title job_title
                      FROM offers o JOIN applications a ON a.id=o.application_id
                      JOIN candidates c ON c.id=a.candidate_id
                      JOIN job_openings j ON j.id=a.job_id
                      WHERE a.job_id=? ORDER BY o.id DESC""", (job_id,))


def all_offers(status: str = "All"):
    clause, params = ("", ()) if status == "All" else ("WHERE o.status=?", (status,))
    return db.rows(f"""SELECT o.*, c.first_name, c.last_name, c.id candidate_id,
                              j.title job_title, j.code job_code
                       FROM offers o JOIN applications a ON a.id=o.application_id
                       JOIN candidates c ON c.id=a.candidate_id
                       JOIN job_openings j ON j.id=a.job_id
                       {clause} ORDER BY (o.status!='Pending approval'), o.id DESC""", params)


def offer(offer_id: int):
    return db.one("""SELECT o.*, a.candidate_id, a.job_id, c.first_name, c.last_name, c.email,
                            j.title job_title, j.code job_code, j.dept_id, d.name dept
                     FROM offers o JOIN applications a ON a.id=o.application_id
                     JOIN candidates c ON c.id=a.candidate_id
                     JOIN job_openings j ON j.id=a.job_id
                     LEFT JOIN departments d ON d.id=j.dept_id
                     WHERE o.id=?""", (offer_id,))


def offer_for_application(app_id: int):
    return db.one("SELECT * FROM offers WHERE application_id=? ORDER BY id DESC LIMIT 1", (app_id,))


def draft_offer(app_id: int, *, salary: float, start_date: str, currency: str = "GBP",
                expires_on: str = "", letter: str = "", actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO offers(application_id,salary,currency,start_date,status,letter,
                   expires_on,created)
               VALUES (?,?,?,?,'Draft',?,?,datetime('now'))""",
            (app_id, salary, currency, start_date, letter, expires_on or None))
        oid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    set_stage(app_id, "Offer", actor=actor)
    log_event("offer", oid, actor=actor, to_state="Draft", salary=salary)
    return oid


def set_offer_status(offer_id: int, status: str, *, actor: str = "system", reason: str = "") -> dict:
    """Advance an offer. Acceptance converts the candidate into an employee."""
    o = offer(offer_id)
    if not o or status not in OFFER_STATUSES:
        return {"ok": False, "error": "Unknown offer or status."}
    was = o["status"]
    stamp = {"Sent": "sent_at", "Accepted": "signed_at"}.get(status)
    with db.cursor() as conn:
        conn.execute(f"""UPDATE offers SET status=?{', ' + stamp + "=datetime('now')" if stamp else ''},
                             approved_by=CASE WHEN ?='Approved' THEN ? ELSE approved_by END,
                             declined_reason=CASE WHEN ?='Declined' THEN ? ELSE declined_reason END
                         WHERE id=?""",
                     (status, status, actor, status, reason or None, offer_id))
    log_event("offer", offer_id, actor=actor, from_state=was, to_state=status)

    if status == "Accepted":
        return hire(offer_id, actor=actor)
    if status == "Declined":
        set_stage(o["application_id"], "Rejected", actor=actor)
        with db.cursor() as conn:
            conn.execute("UPDATE applications SET rejection_reason=? WHERE id=?",
                         (reason or "Offer declined", o["application_id"]))
    return {"ok": True, "status": status}


# --- hire: candidate → employee (the people graph, plan §A3/§4.7) -----------

def hire(offer_id: int, *, actor: str = "system") -> dict:
    """Convert an accepted offer into an employee record, in one transaction.

    Carries the candidate's identity and extracted skills across, links the two
    records so history survives, marks the requisition seat filled, and starts
    the onboarding checklist.
    """
    o = offer(offer_id)
    if not o:
        return {"ok": False, "error": "No such offer."}
    existing = db.one("SELECT id FROM employees WHERE candidate_id=?", (o["candidate_id"],))
    if existing:
        return {"ok": True, "employee_id": existing["id"], "note": "Already hired."}

    cand = candidate(o["candidate_id"]) or {}
    next_code = (db.scalar("SELECT MAX(CAST(SUBSTR(code,5) AS INTEGER)) FROM employees WHERE code LIKE 'EMP-%'") or 1000) + 1
    manager_id = db.scalar("SELECT hiring_manager_id FROM job_openings WHERE id=?", (o["job_id"],))

    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO employees(code,first_name,last_name,email,dept_id,designation,
                   manager_id,branch,status,date_of_joining,base_salary,candidate_id,
                   employment_type,probation_end)
               VALUES (?,?,?,?,?,?,?,?,'Probation',?,?,?,'Permanent',date(?, '+6 months'))""",
            (f"EMP-{next_code}", cand.get("first_name"), cand.get("last_name"), cand.get("email"),
             o["dept_id"], o["job_title"], manager_id, cand.get("location"),
             o["start_date"], o["salary"], o["candidate_id"], o["start_date"]))
        eid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]

        # carry the extracted skills over to the employee record
        conn.execute("""INSERT INTO employee_skills(employee_id,skill,level,years,source)
                        SELECT ?, skill, level, years, 'cv-extraction'
                        FROM candidate_skills WHERE candidate_id=?""", (eid, o["candidate_id"]))
        # standard leave allocation
        for lt, days in (("Annual Leave", 25), ("Sick Leave", 10), ("Casual Leave", 6)):
            conn.execute("""INSERT INTO leave_balances(employee_id,leave_type,allocated,used)
                            VALUES (?,?,?,0)""", (eid, lt, days))
        conn.execute("UPDATE candidates SET status='Hired' WHERE id=?", (o["candidate_id"],))
        conn.execute("UPDATE job_openings SET filled=filled+1 WHERE id=?", (o["job_id"],))
        conn.execute("""UPDATE job_openings SET status='Filled'
                        WHERE id=? AND filled>=headcount""", (o["job_id"],))

    set_stage(o["application_id"], "Hired", actor=actor)
    log_event("employee", eid, actor=actor, to_state="Hired",
              candidate_id=o["candidate_id"], offer_id=offer_id, job_id=o["job_id"])

    import people
    n_tasks = people.start_onboarding(eid, actor=actor)
    return {"ok": True, "employee_id": eid, "onboarding_tasks": n_tasks}


# --- ranking (explainable, bias-audited) -----------------------------------

# Withheld from the model by construction, and recorded on the run so the
# exclusion is auditable rather than merely claimed.
RANKING_EXCLUDED = ("first_name", "last_name", "email", "phone", "gender",
                    "linkedin_url", "location")


def rankings_for_job(job_id: int):
    run = db.one("SELECT * FROM ranking_runs WHERE job_id=? ORDER BY id DESC LIMIT 1", (job_id,))
    if not run:
        return None, []
    scores = db.rows("""SELECT rs.*, c.first_name, c.last_name, c.id candidate_id,
                               c.current_title, a.stage
                        FROM ranking_scores rs
                        JOIN applications a ON a.id=rs.application_id
                        JOIN candidates c ON c.id=a.candidate_id
                        WHERE rs.ranking_run_id=? ORDER BY rs.score DESC""", (run["id"],))
    return run, scores


def start_ranking_run(job_id: int, *, model: str, prompt_version: int, n: int) -> int:
    import json as _json
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO ranking_runs(job_id,model,prompt_version,excluded_json,candidates,
                   status,created)
               VALUES (?,?,?,?,?,'pending',datetime('now'))""",
            (job_id, model, prompt_version, _json.dumps(list(RANKING_EXCLUDED)), n))
        return cur.execute("SELECT last_insert_rowid()").fetchone()[0]


def save_ranking(run_id: int, scored: list[dict], *, error: str = ""):
    with db.cursor() as conn:
        if error:
            conn.execute("UPDATE ranking_runs SET status='error', error=? WHERE id=?", (error, run_id))
            return
        for s in scored:
            conn.execute("""INSERT INTO ranking_scores
                            (ranking_run_id,application_id,score,rationale,strengths,gaps)
                            VALUES (?,?,?,?,?,?)""",
                         (run_id, s.get("application_id"), s.get("score"), s.get("rationale"),
                          s.get("strengths"), s.get("gaps")))
        conn.execute("UPDATE ranking_runs SET status='ok' WHERE id=?", (run_id,))


def ranking_input(job_id: int) -> list[dict]:
    """Anonymised candidate summaries for the ranker — identity fields removed."""
    apps = db.rows("""SELECT a.id application_id, c.id candidate_id, c.current_title,
                             c.current_employer, c.years_experience, c.headline
                      FROM applications a JOIN candidates c ON c.id=a.candidate_id
                      WHERE a.job_id=? AND a.status='Active'
                      ORDER BY a.id""", (job_id,))
    out = []
    for a in apps:
        skills = db.rows("""SELECT skill, level, years FROM candidate_skills
                            WHERE candidate_id=? ORDER BY years DESC LIMIT 14""", (a["candidate_id"],))
        exp = db.rows("""SELECT title, employer, start_date, end_date FROM candidate_experience
                         WHERE candidate_id=? ORDER BY sort_order LIMIT 6""", (a["candidate_id"],))
        out.append({"application_id": a["application_id"], "current_title": a["current_title"],
                    "current_employer": a["current_employer"], "headline": a["headline"],
                    "years_experience": a["years_experience"],
                    "skills": [{"skill": s["skill"], "level": s["level"], "years": s["years"]} for s in skills],
                    "experience": [dict(x) for x in exp]})
    return out


# --- talent analytics -------------------------------------------------------

def funnel(job_id: int | None = None):
    clause, params = ("", ()) if not job_id else ("WHERE job_id=?", (job_id,))
    counts = {r["stage"]: r["n"] for r in
              db.rows(f"SELECT stage, COUNT(*) n FROM applications {clause} GROUP BY stage", params)}
    return [(s, counts.get(s, 0)) for s in STAGES]


def source_effectiveness():
    return db.rows("""SELECT c.source,
                             COUNT(a.id) applications,
                             SUM(CASE WHEN a.stage NOT IN ('Applied','Rejected') THEN 1 ELSE 0 END) progressed,
                             SUM(CASE WHEN a.stage='Hired' THEN 1 ELSE 0 END) hires
                      FROM candidates c JOIN applications a ON a.candidate_id=c.id
                      GROUP BY c.source ORDER BY applications DESC""")


def time_in_stage():
    return db.rows("""SELECT stage, COUNT(*) n,
                             AVG(julianday('now') - julianday(stage_entered_on)) avg_days
                      FROM applications WHERE status='Active' AND stage_entered_on IS NOT NULL
                      GROUP BY stage""")


def interviewer_load():
    return db.rows("""SELECT e.id, e.first_name||' '||e.last_name interviewer, d.name dept,
                             COUNT(i.id) interviews,
                             SUM(CASE WHEN i.status='Scheduled' THEN 1 ELSE 0 END) upcoming,
                             AVG(CASE WHEN i.recommendation IS NOT NULL THEN 1.0 ELSE NULL END) responded
                      FROM interviews i JOIN employees e ON e.id=i.interviewer_id
                      LEFT JOIN departments d ON d.id=e.dept_id
                      GROUP BY e.id ORDER BY interviews DESC LIMIT 15""")


def offer_stats():
    total = db.scalar("SELECT COUNT(*) FROM offers") or 0
    accepted = db.scalar("SELECT COUNT(*) FROM offers WHERE status='Accepted'") or 0
    declined = db.scalar("SELECT COUNT(*) FROM offers WHERE status='Declined'") or 0
    pending = db.scalar("SELECT COUNT(*) FROM offers WHERE status IN ('Draft','Pending approval','Approved','Sent')") or 0
    decided = accepted + declined
    return {"total": total, "accepted": accepted, "declined": declined, "pending": pending,
            "acceptance_rate": round(100 * accepted / decided) if decided else 0}


def time_to_fill():
    """Days from requisition opening to the hire, per filled seat."""
    return db.rows("""SELECT j.title, j.code,
                             julianday(a.stage_entered_on) - julianday(j.opened_on) days
                      FROM applications a JOIN job_openings j ON j.id=a.job_id
                      WHERE a.stage='Hired' AND j.opened_on IS NOT NULL
                        AND a.stage_entered_on IS NOT NULL
                      ORDER BY days""")
