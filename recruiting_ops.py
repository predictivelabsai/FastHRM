"""Phase 2 recruiter operations: projects, pipelines, collaboration, and talent CRM."""
from __future__ import annotations

import json
import secrets
from datetime import date

import db
import recruitment
import talent


DEFAULT_STAGES = [
    {"name": "Applied", "category": "new", "color": "#64748b"},
    {"name": "Screen", "category": "active", "color": "#0ea5e9"},
    {"name": "Interview", "category": "active", "color": "#8b5cf6"},
    {"name": "Offer", "category": "active", "color": "#f59e0b"},
    {"name": "Hired", "category": "success", "color": "#10b981"},
    {"name": "Rejected", "category": "terminal", "color": "#ef4444"},
]


def ensure_default_template() -> dict:
    row = db.one("SELECT * FROM pipeline_templates WHERE is_default=1 ORDER BY id LIMIT 1")
    if row:
        return row
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO pipeline_templates
               (name,description,stages_json,is_default,created_by,created,updated)
               VALUES ('Standard hiring','Default FastHRM hiring workflow',?,1,'system',datetime('now'),datetime('now'))""",
            (json.dumps(DEFAULT_STAGES),),
        )
    return db.one("SELECT * FROM pipeline_templates WHERE name='Standard hiring'")


def save_pipeline_template(name: str, stages: list[dict], *, description: str = "",
                           actor: str = "system", template_id: int | None = None) -> int:
    clean = []
    seen = set()
    for index, stage in enumerate(stages):
        label = str(stage.get("name") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        clean.append({"name": label, "category": stage.get("category") or "active",
                      "color": stage.get("color") or "#64748b", "sort_order": index})
    if len(clean) < 2:
        raise ValueError("A pipeline requires at least two uniquely named stages.")
    with db.cursor() as conn:
        if template_id:
            conn.execute(
                "UPDATE pipeline_templates SET name=?,description=?,stages_json=?,updated=datetime('now') WHERE id=?",
                (name.strip(), description.strip(), json.dumps(clean), template_id),
            )
            return template_id
        cur = conn.execute(
            """INSERT INTO pipeline_templates(name,description,stages_json,created_by,created,updated)
               VALUES (?,?,?,?,datetime('now'),datetime('now'))""",
            (name.strip(), description.strip(), json.dumps(clean), actor),
        )
        return cur.lastrowid


def pipeline_templates() -> list[dict]:
    ensure_default_template()
    rows = db.rows("SELECT * FROM pipeline_templates ORDER BY is_default DESC,name")
    for row in rows:
        row["stages"] = json.loads(row["stages_json"] or "[]")
    return rows


def ensure_project(job_id: int, *, actor: str = "system") -> dict:
    project = db.one("SELECT * FROM recruitment_projects WHERE job_id=?", (job_id,))
    if project:
        return project
    if not talent.job(job_id):
        raise ValueError("No such requisition.")
    template = ensure_default_template()
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO recruitment_projects
               (job_id,template_id,category,access_json,custom_fields_json,created_by,created,updated)
               VALUES (?,?,'Standard','{}','{}',?,datetime('now'),datetime('now'))""",
            (job_id, template["id"], actor),
        )
        conn.execute("UPDATE job_openings SET stages_json=? WHERE id=?",
                     (json.dumps([s["name"] for s in json.loads(template["stages_json"])]), job_id))
        project_id = cur.lastrowid
    talent.log_event("recruitment_project", project_id, actor=actor, to_state="Created", job_id=job_id)
    return db.one("SELECT * FROM recruitment_projects WHERE id=?", (project_id,))


def project(job_id: int) -> dict:
    row = ensure_project(job_id)
    row["access"] = json.loads(row["access_json"] or "{}")
    row["custom_fields"] = json.loads(row["custom_fields_json"] or "{}")
    row["members"] = db.rows("SELECT * FROM project_members WHERE project_id=? ORDER BY role,account_email", (row["id"],))
    row["stages"] = talent.job_stages(job_id)
    return row


def configure_project(job_id: int, *, category: str = "Standard", continuous: bool = False,
                      confidential: bool = False, template_id: int | None = None,
                      custom_fields: dict | None = None, actor: str = "system") -> dict:
    row = ensure_project(job_id, actor=actor)
    template_id = template_id or row["template_id"]
    template = db.one("SELECT * FROM pipeline_templates WHERE id=?", (template_id,))
    if not template:
        raise ValueError("No such pipeline template.")
    stages = [s["name"] for s in json.loads(template["stages_json"])]
    with db.cursor() as conn:
        conn.execute(
            """UPDATE recruitment_projects SET template_id=?,category=?,continuous=?,confidential=?,
                      custom_fields_json=?,updated=datetime('now') WHERE id=?""",
            (template_id, category.strip() or "Standard", int(continuous), int(confidential),
             json.dumps(custom_fields or {}), row["id"]),
        )
        conn.execute("UPDATE job_openings SET stages_json=? WHERE id=?", (json.dumps(stages), job_id))
    talent.log_event("recruitment_project", row["id"], actor=actor, to_state="Configured")
    return project(job_id)


def clone_project(job_id: int, *, title: str = "", actor: str = "system") -> int:
    posting = recruitment.ensure_posting(job_id, actor=actor)
    values = {key: posting.get(key) for key in (
        "public_title", "summary", "description", "requirements", "benefits", "seo_title",
        "seo_description", "location", "remote_policy", "employment_type", "comp_min",
        "comp_max", "currency", "dept_id", "hiring_manager_id", "headcount", "target_date",
    )}
    values["title"] = title.strip() or f"Copy of {posting['title']}"
    values["public_title"] = values["title"]
    new_id = recruitment.create_job(values, actor=actor)
    source = project(job_id)
    configure_project(new_id, category=source["category"], continuous=bool(source["continuous"]),
                      confidential=bool(source["confidential"]), template_id=source["template_id"],
                      custom_fields=source["custom_fields"], actor=actor)
    for member in source["members"]:
        add_project_member(new_id, member["account_email"], member["role"],
                           can_view_salary=bool(member["can_view_salary"]),
                           can_decide=bool(member["can_decide"]))
    return new_id


def add_project_member(job_id: int, email: str, role: str = "hiring_manager", *,
                       can_view_salary: bool = False, can_decide: bool = False) -> None:
    p = ensure_project(job_id)
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO project_members
               (project_id,account_email,role,can_view_salary,can_decide,created)
               VALUES (?,?,?,?,?,datetime('now'))
               ON CONFLICT(project_id,account_email) DO UPDATE SET
               role=excluded.role,can_view_salary=excluded.can_view_salary,can_decide=excluded.can_decide""",
            (p["id"], email.strip().lower(), role, int(can_view_salary), int(can_decide)),
        )


def can_access_project(job_id: int, email: str, roles: set[str] | None = None,
                       *, decision: bool = False) -> bool:
    if roles and roles.intersection({"admin", "hrbp", "recruiter"}):
        return True
    p = ensure_project(job_id)
    if not p["confidential"] and not decision:
        return True
    member = db.one("SELECT * FROM project_members WHERE project_id=? AND lower(account_email)=?",
                    (p["id"], email.strip().lower()))
    return bool(member and (not decision or member["can_decide"]))


def move_application(app_id: int, stage: str, *, actor: str, drop_reason: str = "",
                     drop_detail: str = "") -> bool:
    app = db.one("SELECT * FROM applications WHERE id=?", (app_id,))
    if not app:
        return False
    changed = talent.set_stage(app_id, stage, actor=actor)
    if changed and stage == "Rejected" and drop_reason:
        with db.cursor() as conn:
            conn.execute(
                """INSERT INTO application_drop_reasons(application_id,reason,detail,actor,created)
                   VALUES (?,?,?,?,datetime('now'))""",
                (app_id, drop_reason, drop_detail.strip(), actor),
            )
            conn.execute("UPDATE applications SET rejection_reason=? WHERE id=?",
                         (drop_reason + (f": {drop_detail}" if drop_detail else ""), app_id))
    return changed


def add_tag(candidate_id: int, name: str, *, color: str = "#64748b", actor: str = "system") -> int:
    label = name.strip()
    if not label:
        raise ValueError("Tag name is required.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO talent_tags(name,color,created_by,created) VALUES (?,?,?,datetime('now'))
               ON CONFLICT(name) DO UPDATE SET color=COALESCE(excluded.color,talent_tags.color)""",
            (label, color, actor),
        )
        tag_id = conn.execute("SELECT id FROM talent_tags WHERE name=?", (label,)).fetchone()[0]
        conn.execute(
            """INSERT OR IGNORE INTO candidate_tags(candidate_id,tag_id,added_by,created)
               VALUES (?,?,?,datetime('now'))""", (candidate_id, tag_id, actor),
        )
    return tag_id


def remove_tag(candidate_id: int, tag_id: int) -> None:
    with db.cursor() as conn:
        conn.execute("DELETE FROM candidate_tags WHERE candidate_id=? AND tag_id=?", (candidate_id, tag_id))


def tags_for(candidate_id: int) -> list[dict]:
    return db.rows(
        """SELECT t.* FROM talent_tags t JOIN candidate_tags ct ON ct.tag_id=t.id
           WHERE ct.candidate_id=? ORDER BY t.name""", (candidate_id,),
    )


def add_comment(candidate_id: int, body: str, *, author: str, application_id: int | None = None,
                rating: float | None = None, visibility: str = "team", pinned: bool = False) -> int:
    if not body.strip():
        raise ValueError("Comment text is required.")
    if visibility not in {"team", "private", "hiring_manager"}:
        raise ValueError("Invalid comment visibility.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO candidate_comments
               (candidate_id,application_id,body,rating,visibility,pinned,author,created,updated)
               VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (candidate_id, application_id, body.strip(), rating, visibility, int(pinned), author),
        )
        comment_id = cur.lastrowid
    talent.log_event("candidate_comment", comment_id, actor=author, to_state="Added", candidate_id=candidate_id)
    return comment_id


def comments_for(candidate_id: int, *, viewer: str = "", include_private: bool = False) -> list[dict]:
    clause, params = "", [candidate_id]
    if not include_private:
        clause = "AND (visibility!='private' OR author=?)"
        params.append(viewer)
    return db.rows(
        f"""SELECT * FROM candidate_comments WHERE candidate_id=? {clause}
            ORDER BY pinned DESC,created DESC""", tuple(params),
    )


def create_task(title: str, *, assignee: str = "", candidate_id: int | None = None,
                application_id: int | None = None, job_id: int | None = None,
                description: str = "", due_at: str | None = None, priority: str = "Normal",
                actor: str = "system") -> int:
    if not title.strip():
        raise ValueError("Task title is required.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO recruiting_tasks
               (title,description,assignee,candidate_id,application_id,job_id,due_at,status,priority,created_by,created)
               VALUES (?,?,?,?,?,?,?,'Open',?,?,datetime('now'))""",
            (title.strip(), description.strip(), assignee.strip().lower(), candidate_id,
             application_id, job_id, due_at, priority, actor),
        )
        return cur.lastrowid


def set_task_status(task_id: int, status: str, *, actor: str = "system") -> bool:
    if status not in {"Open", "In progress", "Done", "Cancelled"}:
        return False
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE recruiting_tasks SET status=?,
               completed_at=CASE WHEN ?='Done' THEN datetime('now') ELSE NULL END WHERE id=?""",
            (status, status, task_id),
        )
    if cur.rowcount:
        talent.log_event("recruiting_task", task_id, actor=actor, to_state=status)
    return bool(cur.rowcount)


def tasks(*, assignee: str = "", candidate_id: int | None = None,
          job_id: int | None = None, status: str = "All") -> list[dict]:
    where, params = [], []
    for clause, value in (("lower(assignee)=?", assignee.lower() if assignee else ""),
                          ("candidate_id=?", candidate_id), ("job_id=?", job_id)):
        if value not in (None, ""):
            where.append(clause); params.append(value)
    if status != "All":
        where.append("status=?"); params.append(status)
    return db.rows("SELECT * FROM recruiting_tasks " + ("WHERE " + " AND ".join(where) if where else "") +
                   " ORDER BY (due_at IS NULL),due_at,priority DESC,id DESC", tuple(params))


def define_candidate_field(key: str, label: str, field_type: str = "text", *,
                           options: list[str] | None = None, required: bool = False) -> int:
    clean_key = "_".join(key.strip().lower().split())
    if not clean_key or not label.strip():
        raise ValueError("Field key and label are required.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO candidate_field_definitions
               (key,label,field_type,options_json,required,created) VALUES (?,?,?,?,?,datetime('now'))
               ON CONFLICT(key) DO UPDATE SET label=excluded.label,field_type=excluded.field_type,
               options_json=excluded.options_json,required=excluded.required""",
            (clean_key, label.strip(), field_type, json.dumps(options or []), int(required)),
        )
        return conn.execute("SELECT id FROM candidate_field_definitions WHERE key=?", (clean_key,)).fetchone()[0]


def set_candidate_field(candidate_id: int, key: str, value: str, *, actor: str) -> None:
    field = db.one("SELECT * FROM candidate_field_definitions WHERE key=?", (key,))
    if not field:
        raise ValueError("No such candidate field.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO candidate_field_values(candidate_id,field_id,value_text,updated_by,updated)
               VALUES (?,?,?,?,datetime('now')) ON CONFLICT(candidate_id,field_id) DO UPDATE SET
               value_text=excluded.value_text,updated_by=excluded.updated_by,updated=excluded.updated""",
            (candidate_id, field["id"], value, actor),
        )


def candidate_fields(candidate_id: int) -> list[dict]:
    return db.rows(
        """SELECT d.*,v.value_text FROM candidate_field_definitions d
           LEFT JOIN candidate_field_values v ON v.field_id=d.id AND v.candidate_id=?
           ORDER BY d.label""", (candidate_id,),
    )


def search_candidates(query: str = "", *, source: str = "", location: str = "",
                      tag: str = "", skill: str = "", job_id: int | None = None,
                      status: str = "All", limit: int = 200) -> list[dict]:
    where, params = [], []
    if query.strip():
        term = f"%{query.strip()}%"
        where.append("""(c.first_name||' '||c.last_name LIKE ? OR c.email LIKE ? OR
                      c.headline LIKE ? OR c.current_title LIKE ? OR c.current_employer LIKE ? OR
                      EXISTS (SELECT 1 FROM candidate_documents d WHERE d.candidate_id=c.id AND d.text_content LIKE ?) OR
                      EXISTS (SELECT 1 FROM candidate_field_values fv WHERE fv.candidate_id=c.id AND fv.value_text LIKE ?))""")
        params.extend([term] * 7)
    for column, value in (("c.source", source), ("c.location", location)):
        if value:
            where.append(f"{column} LIKE ?"); params.append(f"%{value}%")
    if tag:
        where.append("EXISTS (SELECT 1 FROM candidate_tags ct JOIN talent_tags t ON t.id=ct.tag_id WHERE ct.candidate_id=c.id AND t.name=?)")
        params.append(tag)
    if skill:
        where.append("EXISTS (SELECT 1 FROM candidate_skills s WHERE s.candidate_id=c.id AND s.skill LIKE ?)")
        params.append(f"%{skill}%")
    if job_id:
        where.append("EXISTS (SELECT 1 FROM applications a WHERE a.candidate_id=c.id AND a.job_id=?)")
        params.append(job_id)
    if status != "All":
        where.append("c.status=?"); params.append(status)
    sql = """SELECT c.*,
             (SELECT group_concat(t.name, ', ') FROM candidate_tags ct JOIN talent_tags t ON t.id=ct.tag_id WHERE ct.candidate_id=c.id) tags,
             (SELECT group_concat(s.skill, ', ') FROM candidate_skills s WHERE s.candidate_id=c.id) skills,
             (SELECT COUNT(*) FROM applications a WHERE a.candidate_id=c.id) application_count,
             (SELECT COUNT(*) FROM candidate_skills s WHERE s.candidate_id=c.id) n_skills,
             (SELECT r.status FROM extraction_runs r WHERE r.candidate_id=c.id ORDER BY r.id DESC LIMIT 1) extraction_status,
             (SELECT j.title FROM applications a JOIN job_openings j ON j.id=a.job_id
                WHERE a.candidate_id=c.id ORDER BY a.id DESC LIMIT 1) latest_job,
             (SELECT a.stage FROM applications a WHERE a.candidate_id=c.id ORDER BY a.id DESC LIMIT 1) latest_stage
             FROM candidates c"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.created DESC,c.id DESC LIMIT ?"
    params.append(max(1, min(limit, 1000)))
    return db.rows(sql, tuple(params))


def save_view(owner: str, name: str, filters: dict, *, shared: bool = False) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO saved_candidate_views(owner_email,name,filters_json,shared,created)
               VALUES (?,?,?,?,datetime('now')) ON CONFLICT(owner_email,name) DO UPDATE SET
               filters_json=excluded.filters_json,shared=excluded.shared""",
            (owner.lower(), name.strip(), json.dumps(filters), int(shared)),
        )
        return conn.execute("SELECT id FROM saved_candidate_views WHERE owner_email=? AND name=?",
                            (owner.lower(), name.strip())).fetchone()[0]


def save_candidate_pool(name: str, filters: dict, *, owner: str,
                        description: str = "", automatic: bool = True) -> int:
    if not name.strip():
        raise ValueError("Pool name is required.")
    allowed = {"query", "source", "location", "tag", "skill", "job_id", "status"}
    clean_filters = {key: value for key, value in filters.items() if key in allowed and value not in (None, "")}
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO candidate_pools
               (name,description,filters_json,automatic,owner_email,created,updated)
               VALUES (?,?,?,?,?,datetime('now'),datetime('now'))
               ON CONFLICT(name) DO UPDATE SET description=excluded.description,
               filters_json=excluded.filters_json,automatic=excluded.automatic,
               owner_email=excluded.owner_email,updated=excluded.updated""",
            (name.strip(), description.strip(), json.dumps(clean_filters), int(automatic), owner.lower()),
        )
        pool_id = conn.execute("SELECT id FROM candidate_pools WHERE name=?", (name.strip(),)).fetchone()[0]
    refresh_candidate_pool(pool_id)
    return pool_id


def refresh_candidate_pool(pool_id: int) -> dict:
    pool = db.one("SELECT * FROM candidate_pools WHERE id=?", (pool_id,))
    if not pool:
        raise ValueError("Candidate pool not found.")
    filters = json.loads(pool["filters_json"] or "{}")
    matches = search_candidates(**filters, limit=1000)
    candidate_ids = {row["id"] for row in matches}
    with db.cursor() as conn:
        conn.execute("DELETE FROM candidate_pool_members WHERE pool_id=? AND source='rule'", (pool_id,))
        for candidate_id in candidate_ids:
            conn.execute(
                """INSERT INTO candidate_pool_members(pool_id,candidate_id,source,added_at)
                   VALUES (?,?,'rule',datetime('now'))
                   ON CONFLICT(pool_id,candidate_id) DO UPDATE SET source='rule',added_at=excluded.added_at""",
                (pool_id, candidate_id),
            )
    return {"pool_id": pool_id, "members": len(candidate_ids)}


def candidate_pools() -> list[dict]:
    pools = db.rows(
        """SELECT p.*,COUNT(m.candidate_id) member_count FROM candidate_pools p
           LEFT JOIN candidate_pool_members m ON m.pool_id=p.id
           GROUP BY p.id ORDER BY p.name""")
    for pool in pools:
        pool["filters"] = json.loads(pool["filters_json"] or "{}")
    return pools


def send_pool_job_offer(pool_id: int, job_id: int, *, actor: str,
                        subject: str = "A role you may be interested in",
                        body: str = "") -> dict:
    posting = recruitment.posting_for_job(job_id)
    if not posting or posting["publication_status"] != "Published":
        raise ValueError("Targeted offers require a published job.")
    candidate_ids = [row["candidate_id"] for row in db.rows(
        "SELECT candidate_id FROM candidate_pool_members WHERE pool_id=?", (pool_id,))]
    message = body.strip() or (f"We thought you may be interested in {posting['public_title']}: "
                               f"/jobs/{posting['slug']}")
    return run_bulk_action("email", candidate_ids,
                           payload={"subject": subject, "body": message}, actor=actor)


def merge_candidates(survivor_id: int, merged_id: int, *, actor: str) -> dict:
    if survivor_id == merged_id:
        raise ValueError("Choose two different candidates.")
    survivor, merged = talent.candidate(survivor_id), talent.candidate(merged_id)
    if not survivor or not merged:
        raise ValueError("Candidate not found.")
    with db.cursor() as conn:
        snapshot = json.dumps(merged, default=str)
        duplicate_jobs = {r[0] for r in conn.execute(
            "SELECT job_id FROM applications WHERE candidate_id=?", (survivor_id,)).fetchall()}
        for app in conn.execute("SELECT id,job_id FROM applications WHERE candidate_id=?", (merged_id,)).fetchall():
            if app["job_id"] in duplicate_jobs:
                conn.execute("UPDATE candidate_consents SET application_id=NULL WHERE application_id=?", (app["id"],))
                conn.execute("DELETE FROM application_answers WHERE application_id=?", (app["id"],))
                conn.execute("DELETE FROM applications WHERE id=?", (app["id"],))
            else:
                conn.execute("UPDATE applications SET candidate_id=? WHERE id=?", (survivor_id, app["id"]))
        for table in ("candidate_documents", "candidate_skills", "candidate_experience", "candidate_education",
                      "candidate_consents", "candidate_comments", "recruiting_tasks", "reference_requests",
                      "candidate_credentials", "communication_messages", "candidate_requests", "privacy_requests",
                      "survey_invitations", "recruitment_analytics_events", "video_messages"):
            conn.execute(f"UPDATE {table} SET candidate_id=? WHERE candidate_id=?", (survivor_id, merged_id))
        conn.execute(
            """INSERT OR IGNORE INTO candidate_tags(candidate_id,tag_id,added_by,created)
               SELECT ?,tag_id,?,datetime('now') FROM candidate_tags WHERE candidate_id=?""",
            (survivor_id, actor, merged_id),
        )
        conn.execute("DELETE FROM candidate_tags WHERE candidate_id=?", (merged_id,))
        conn.execute(
            """INSERT OR IGNORE INTO candidate_field_values(candidate_id,field_id,value_text,updated_by,updated)
               SELECT ?,field_id,value_text,?,datetime('now') FROM candidate_field_values WHERE candidate_id=?""",
            (survivor_id, actor, merged_id),
        )
        conn.execute("DELETE FROM candidate_field_values WHERE candidate_id=?", (merged_id,))
        conn.execute("UPDATE candidates SET status='Archived',email=NULL,phone=NULL,notes=? WHERE id=?",
                     (f"Merged into candidate {survivor_id}", merged_id))
        cur = conn.execute(
            """INSERT INTO candidate_merge_events(survivor_id,merged_id,snapshot_json,actor,created)
               VALUES (?,?,?,?,datetime('now'))""", (survivor_id, merged_id, snapshot, actor),
        )
    talent.log_event("candidate", survivor_id, actor=actor, to_state="Merged", merged_id=merged_id)
    return {"ok": True, "survivor_id": survivor_id, "merge_event_id": cur.lastrowid}


def run_bulk_action(action_type: str, candidates: list[int], *, payload: dict | None = None,
                    actor: str) -> dict:
    payload = payload or {}
    ids = list(dict.fromkeys(int(cid) for cid in candidates if cid))
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO bulk_actions(action_type,payload_json,requested_by,status,total,created)
               VALUES (?,?,?,'Running',?,datetime('now'))""",
            (action_type, json.dumps(payload), actor, len(ids)),
        )
        bulk_id = cur.lastrowid
        for cid in ids:
            conn.execute("INSERT INTO bulk_action_items(bulk_action_id,candidate_id,status) VALUES (?,?,'Queued')",
                         (bulk_id, cid))
    succeeded, failed = 0, 0
    for item in db.rows("SELECT * FROM bulk_action_items WHERE bulk_action_id=?", (bulk_id,)):
        try:
            cid = item["candidate_id"]
            if action_type == "tag":
                add_tag(cid, payload.get("tag") or "Bulk", actor=actor)
            elif action_type == "task":
                create_task(payload.get("title") or "Follow up", assignee=payload.get("assignee") or actor,
                            candidate_id=cid, due_at=payload.get("due_at"), actor=actor)
            elif action_type == "comment":
                add_comment(cid, payload.get("body") or "Bulk note", author=actor)
            elif action_type == "stage":
                app = db.one("SELECT id FROM applications WHERE candidate_id=? AND job_id=?",
                             (cid, payload.get("job_id")))
                if not app or not move_application(app["id"], payload.get("stage") or "", actor=actor):
                    raise ValueError("Candidate has no matching application or stage.")
            elif action_type == "interview":
                from recruitment_ecosystem import create_scheduling_link
                from recruitment_communications import queue_message
                app = db.one(
                    """SELECT id FROM applications WHERE candidate_id=?
                       AND (? IS NULL OR job_id=?) AND status='Active' ORDER BY id DESC LIMIT 1""",
                    (cid, payload.get("job_id"), payload.get("job_id")),
                )
                if not app:
                    raise ValueError("Candidate has no active application.")
                token = create_scheduling_link(
                    app["id"], payload.get("interviewer_emails") or [],
                    window_start=payload["window_start"], window_end=payload["window_end"],
                    timezone=payload.get("timezone") or "UTC",
                    provider=payload.get("provider") or "fasthr", actor=actor)
                queue_message(
                    cid, channel="email", application_id=app["id"],
                    subject=payload.get("subject") or "Choose an interview time",
                    body=(payload.get("body") or "Choose a convenient interview time:") + f" /schedule/{token}",
                    actor=actor)
            elif action_type in {"email", "sms"}:
                from recruitment_communications import queue_message
                queue_message(cid, channel=action_type, subject=payload.get("subject") or "",
                              body=payload.get("body") or "", actor=actor)
            else:
                raise ValueError("Unsupported bulk action.")
            status, error, succeeded = "Done", None, succeeded + 1
        except Exception as exc:  # each row must be independently auditable
            status, error, failed = "Failed", str(exc), failed + 1
        with db.cursor() as conn:
            conn.execute("UPDATE bulk_action_items SET status=?,error=?,completed_at=datetime('now') WHERE id=?",
                         (status, error, item["id"]))
    with db.cursor() as conn:
        conn.execute(
            """UPDATE bulk_actions SET status=?,succeeded=?,failed=?,completed_at=datetime('now') WHERE id=?""",
            ("Completed" if not failed else "Completed with errors", succeeded, failed, bulk_id),
        )
    return db.one("SELECT * FROM bulk_actions WHERE id=?", (bulk_id,))


def save_scorecard_template(name: str, items: list[dict], *, actor: str) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO scorecard_templates(name,description,created_by,created)
               VALUES (?,?,?,datetime('now')) ON CONFLICT(name) DO UPDATE SET description=excluded.description""",
            (name.strip(), "Configurable interview scorecard", actor),
        )
        template_id = conn.execute("SELECT id FROM scorecard_templates WHERE name=?", (name.strip(),)).fetchone()[0]
        conn.execute("DELETE FROM scorecard_template_items WHERE template_id=?", (template_id,))
        for index, item in enumerate(items):
            conn.execute(
                """INSERT INTO scorecard_template_items
                   (template_id,competency_id,label,description,weight,required,sort_order)
                   VALUES (?,?,?,?,?,?,?)""",
                (template_id, item.get("competency_id"), item["label"], item.get("description", ""),
                 float(item.get("weight", 1)), int(item.get("required", True)), index),
            )
    return template_id


def request_approval(entity_type: str, entity_id: int, approvers: list[str], *, actor: str) -> list[int]:
    ids = []
    with db.cursor() as conn:
        for sequence, email in enumerate(approvers, 1):
            cur = conn.execute(
                """INSERT INTO approvals(entity_type,entity_id,approver,sequence,decision,created)
                   VALUES (?,?,?,?,'Pending',datetime('now'))""",
                (entity_type, entity_id, email.lower(), sequence),
            )
            ids.append(cur.lastrowid)
    talent.log_event(entity_type, entity_id, actor=actor, to_state="Approval requested")
    return ids


def decide_approval(approval_id: int, decision: str, *, actor: str, note: str = "") -> bool:
    if decision not in {"Approved", "Rejected"}:
        return False
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE approvals SET decision=?,note=?,decided_at=datetime('now')
               WHERE id=? AND lower(approver)=? AND decision='Pending'""",
            (decision, note.strip(), approval_id, actor.lower()),
        )
    return bool(cur.rowcount)


def request_reference(candidate_id: int, referee_name: str, referee_email: str, *,
                      application_id: int | None = None, actor: str) -> str:
    token = secrets.token_urlsafe(24)
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO reference_requests
               (candidate_id,application_id,referee_name,referee_email,token,status,requested_by,requested_at)
               VALUES (?,?,?,?,?,'Requested',?,datetime('now'))""",
            (candidate_id, application_id, referee_name.strip(), referee_email.strip().lower(), token, actor),
        )
    return token


def complete_reference(token: str, response: dict) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE reference_requests SET status='Completed',response_json=?,completed_at=datetime('now')
               WHERE token=? AND status='Requested'""", (json.dumps(response), token),
        )
    return bool(cur.rowcount)


def add_credential(candidate_id: int, name: str, *, issuer: str = "", expires_on: str | None = None,
                   credential_number: str = "") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO candidate_credentials
               (candidate_id,name,issuer,credential_number,expires_on,status,created)
               VALUES (?,?,?,?,?,'Unverified',datetime('now'))""",
            (candidate_id, name.strip(), issuer.strip(), credential_number.strip(), expires_on),
        )
        return cur.lastrowid


def refresh_credential_statuses() -> int:
    today = date.today().isoformat()
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE candidate_credentials SET status='Expired'
               WHERE expires_on IS NOT NULL AND expires_on<? AND status!='Expired'""", (today,),
        )
        return cur.rowcount


def create_scorecard_reminders(*, actor: str = "system") -> int:
    interviews = db.rows(
        """SELECT i.id,i.application_id,i.interviewer_id,e.email,j.id job_id,c.id candidate_id
           FROM interviews i JOIN applications a ON a.id=i.application_id
           JOIN candidates c ON c.id=a.candidate_id JOIN job_openings j ON j.id=a.job_id
           LEFT JOIN employees e ON e.id=i.interviewer_id
           WHERE i.status IN ('Scheduled','Completed')
           AND NOT EXISTS (SELECT 1 FROM scorecards s WHERE s.interview_id=i.id)
           AND NOT EXISTS (SELECT 1 FROM recruiting_tasks t
                           WHERE t.application_id=i.application_id
                           AND t.title='Complete scorecard for interview #'||i.id
                           AND t.status IN ('Open','In progress'))"""
    )
    for row in interviews:
        create_task(f"Complete scorecard for interview #{row['id']}", assignee=row.get("email") or actor,
                    candidate_id=row["candidate_id"], application_id=row["application_id"],
                    job_id=row["job_id"], priority="High", actor=actor)
    return len(interviews)


def save_application_form(name: str, fields: list[dict], *, description: str = "",
                          confirmation_subject: str = "Application received",
                          confirmation_body: str = "Thank you for applying, {{first_name}}.",
                          actor: str = "system") -> int:
    if not name.strip() or not fields:
        raise ValueError("Application form name and fields are required.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO application_forms
               (name,description,confirmation_subject,confirmation_body,created_by,created,updated)
               VALUES (?,?,?,?,?,datetime('now'),datetime('now')) ON CONFLICT(name) DO UPDATE SET
               description=excluded.description,confirmation_subject=excluded.confirmation_subject,
               confirmation_body=excluded.confirmation_body,updated=excluded.updated""",
            (name.strip(), description, confirmation_subject, confirmation_body, actor),
        )
        form_id = conn.execute("SELECT id FROM application_forms WHERE name=?", (name.strip(),)).fetchone()[0]
        conn.execute("DELETE FROM application_form_fields WHERE form_id=?", (form_id,))
        for index, field in enumerate(fields):
            key = "_".join(str(field.get("key") or field.get("label") or "").lower().split())
            if not key:
                continue
            conn.execute(
                """INSERT INTO application_form_fields
                   (form_id,field_key,label,field_type,options_json,required,condition_json,sort_order)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (form_id, key, field.get("label") or key.replace("_", " ").title(),
                 field.get("type") or "text", json.dumps(field.get("options") or []),
                 int(field.get("required", False)), json.dumps(field.get("condition") or {}), index),
            )
    return form_id


def attach_application_form(job_id: int, form_id: int) -> None:
    posting = recruitment.ensure_posting(job_id)
    with db.cursor() as conn:
        if not form_id:
            conn.execute("DELETE FROM job_application_forms WHERE job_posting_id=?", (posting["id"],))
            return
        conn.execute(
            """INSERT INTO job_application_forms(job_posting_id,form_id) VALUES (?,?)
               ON CONFLICT(job_posting_id) DO UPDATE SET form_id=excluded.form_id""",
            (posting["id"], form_id),
        )


def application_form(job_id: int) -> dict | None:
    form = db.one(
        """SELECT f.* FROM application_forms f JOIN job_application_forms jf ON jf.form_id=f.id
           JOIN job_postings p ON p.id=jf.job_posting_id WHERE p.job_id=?""", (job_id,),
    )
    if form:
        form["fields"] = db.rows("SELECT * FROM application_form_fields WHERE form_id=? ORDER BY sort_order,id", (form["id"],))
        for field in form["fields"]:
            field["options"] = json.loads(field["options_json"] or "[]")
            field["condition"] = json.loads(field["condition_json"] or "{}")
    return form


def validate_application_form(job_id: int, values: dict) -> tuple[bool, str, list[dict]]:
    form = application_form(job_id)
    if not form:
        return True, "", []
    answers = []
    for field in form["fields"]:
        condition = field["condition"]
        visible = not condition or str(values.get(condition.get("field"), "")) == str(condition.get("equals", ""))
        value = values.get(field["field_key"], "") if visible else ""
        if visible and field["required"] and not str(value).strip():
            return False, f"{field['label']} is required.", []
        if visible and value not in (None, ""):
            answers.append({"field_key": field["field_key"], "label": field["label"],
                            "value_text": str(value)})
    return True, "", answers


def publish_internal_job(job_id: int, audiences: list[str], *, closes_at: str | None = None,
                         actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO internal_job_posts
               (job_id,audience_json,status,published_at,closes_at,created_by,created)
               VALUES (?,?,'Published',datetime('now'),?,?,datetime('now'))""",
            (job_id, json.dumps(audiences), closes_at, actor),
        )
        return cur.lastrowid


def internal_jobs(*, audience: str = "all") -> list[dict]:
    return db.rows(
        """SELECT i.*,j.title,j.location,j.remote_policy FROM internal_job_posts i
           JOIN job_openings j ON j.id=i.job_id WHERE i.status='Published'
           AND (i.closes_at IS NULL OR i.closes_at>=date('now'))
           AND (i.audience_json LIKE ? OR i.audience_json LIKE '%"all"%') ORDER BY i.published_at DESC""",
        (f'%"{audience}"%',),
    )


def hiring_manager_workspace(email: str) -> list[dict]:
    return db.rows(
        """SELECT p.*,j.title,j.code,j.status,
                  (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.id AND a.status='Active') active_candidates,
                  m.can_decide,m.can_view_salary
           FROM project_members m JOIN recruitment_projects p ON p.id=m.project_id
           JOIN job_openings j ON j.id=p.job_id WHERE lower(m.account_email)=?
           ORDER BY j.status='Open' DESC,j.title""", (email.lower(),),
    )
