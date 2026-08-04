"""Performance and lifecycle data layer — goals, feedback, reviews, onboarding,
internal changes, separations and employee-relations cases.

Same conventions as db.py and talent.py: raw SQL, no ORM. Every state change
writes to lifecycle_events via talent.log_event, so one audit spine covers
hiring and employment alike.
"""
from __future__ import annotations

import json

import db
from talent import log_event

# --- vocabularies -----------------------------------------------------------

GOAL_STATUSES = ["On track", "At risk", "Behind", "Complete", "Cancelled"]
GOAL_OWNERS = ["company", "department", "employee"]
FEEDBACK_KINDS = ["Praise", "Constructive", "Peer review", "Manager note"]
VISIBILITIES = ["Public", "Team", "Private", "Manager only"]
REVIEW_KINDS = ["Self", "Manager", "Peer", "Skip-level"]
REVIEW_STATUSES = ["Not started", "In progress", "Submitted", "Calibrated"]
CYCLE_STATUSES = ["Draft", "Open", "Calibration", "Closed"]
CHANGE_TYPES = ["Promotion", "Transfer", "Role change", "Salary change", "Manager change"]
SEPARATION_KINDS = ["Resignation", "Termination", "End of contract", "Retirement"]
CASE_KINDS = ["Grievance", "Wellbeing", "Conduct", "Pay query", "Other"]
CASE_SEVERITIES = ["Low", "Normal", "High", "Critical"]
CASE_STATUSES = ["Open", "Investigating", "Resolved", "Closed"]
TASK_OWNERS = ["HR", "Manager", "IT", "New hire"]

DEFAULT_ONBOARDING = [
    ("Send contract and right-to-work documents", "HR", 0),
    ("Collect signed contract", "HR", 3),
    ("Create accounts and email", "IT", 1),
    ("Order laptop and equipment", "IT", 1),
    ("Assign a buddy", "Manager", 2),
    ("Book first-week 1:1", "Manager", 2),
    ("Share team handbook and goals", "Manager", 5),
    ("Complete compliance training", "New hire", 10),
    ("Set 30-day objectives", "Manager", 14),
    ("30-day check-in", "HR", 30),
]


# --- goals ------------------------------------------------------------------

def goals(*, owner_type: str = "All", owner_id: int | None = None, period: str = "All",
          status: str = "All"):
    where, params = [], []
    if owner_type != "All":
        where.append("g.owner_type=?")
        params.append(owner_type)
    if owner_id:
        where.append("g.owner_id=?")
        params.append(owner_id)
    if period != "All":
        where.append("g.period=?")
        params.append(period)
    if status != "All":
        where.append("g.status=?")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return db.rows(f"""SELECT g.*,
                              CASE g.owner_type
                                WHEN 'employee' THEN (SELECT e.first_name||' '||e.last_name
                                                      FROM employees e WHERE e.id=g.owner_id)
                                WHEN 'department' THEN (SELECT d.name FROM departments d WHERE d.id=g.owner_id)
                                ELSE 'Company' END owner_name,
                              (SELECT COUNT(*) FROM goals c WHERE c.parent_goal_id=g.id) n_children,
                              (SELECT p.title FROM goals p WHERE p.id=g.parent_goal_id) parent_title
                       FROM goals g {clause}
                       ORDER BY g.owner_type='company' DESC, g.owner_type='department' DESC,
                                g.status='Complete', g.title""", tuple(params))


def goal(goal_id: int):
    return db.one("""SELECT g.*, (SELECT p.title FROM goals p WHERE p.id=g.parent_goal_id) parent_title
                     FROM goals g WHERE g.id=?""", (goal_id,))


def goal_tree(period: str | None = None):
    """Company → department → individual, as a nested structure for the alignment view."""
    rows_ = goals(period=period or "All")
    by_parent: dict[int | None, list[dict]] = {}
    for g in rows_:
        by_parent.setdefault(g["parent_goal_id"], []).append(g)

    def build(parent_id):
        out = []
        for g in by_parent.get(parent_id, []):
            node = dict(g)
            node["children"] = build(g["id"])
            out.append(node)
        return out

    return build(None)


def goal_periods():
    return [r["period"] for r in
            db.rows("SELECT DISTINCT period FROM goals WHERE period IS NOT NULL ORDER BY period DESC")]


def create_goal(*, title: str, owner_type: str = "employee", owner_id: int | None = None,
                parent_goal_id: int | None = None, metric: str = "", target: float = 0,
                current: float = 0, unit: str = "", period: str = "", due_date: str = "",
                actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO goals(owner_type,owner_id,parent_goal_id,title,metric,target,current,
                   unit,period,status,due_date,created)
               VALUES (?,?,?,?,?,?,?,?,?,'On track',?,datetime('now'))""",
            (owner_type if owner_type in GOAL_OWNERS else "employee", owner_id, parent_goal_id,
             title, metric, target, current, unit, period, due_date or None))
        gid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("goal", gid, actor=actor, to_state="On track", title=title)
    return gid


def checkin(goal_id: int, *, value: float, status: str = "", note: str = "",
            actor: str = "system") -> bool:
    g = goal(goal_id)
    if not g:
        return False
    new_status = status if status in GOAL_STATUSES else g["status"]
    if g["target"] and value >= g["target"]:
        new_status = "Complete"
    with db.cursor() as conn:
        conn.execute("INSERT INTO goal_checkins(goal_id,value,status,note,created_by,created) "
                     "VALUES (?,?,?,?,?,datetime('now'))", (goal_id, value, new_status, note, actor))
        conn.execute("UPDATE goals SET current=?, status=? WHERE id=?", (value, new_status, goal_id))
    log_event("goal", goal_id, actor=actor, from_state=g["status"], to_state=new_status, value=value)
    return True


def checkins(goal_id: int, limit: int = 12):
    return db.rows("SELECT * FROM goal_checkins WHERE goal_id=? ORDER BY id DESC LIMIT ?",
                   (goal_id, limit))


def goal_progress(g: dict) -> int:
    if not g.get("target"):
        return 100 if g.get("status") == "Complete" else 0
    return max(0, min(100, round(100 * (g.get("current") or 0) / g["target"])))


# --- feedback ---------------------------------------------------------------

def feedback_feed(*, to_employee_id: int | None = None, kind: str = "All", limit: int = 60):
    where, params = [], []
    if to_employee_id:
        where.append("f.to_employee_id=?")
        params.append(to_employee_id)
    if kind != "All":
        where.append("f.kind=?")
        params.append(kind)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    return db.rows(f"""SELECT f.*, fe.first_name||' '||fe.last_name from_name,
                              te.first_name||' '||te.last_name to_name,
                              te.id to_id, c.name competency
                       FROM feedback f
                       LEFT JOIN employees fe ON fe.id=f.from_employee_id
                       JOIN employees te ON te.id=f.to_employee_id
                       LEFT JOIN competencies c ON c.id=f.competency_id
                       {clause} ORDER BY f.id DESC LIMIT ?""", tuple(params))


def give_feedback(*, from_employee_id: int | None, to_employee_id: int, body: str,
                  kind: str = "Praise", competency_id: int | None = None,
                  visibility: str = "Team", actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO feedback(from_employee_id,to_employee_id,kind,competency_id,body,
                   visibility,created)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (from_employee_id, to_employee_id, kind if kind in FEEDBACK_KINDS else "Praise",
             competency_id, body, visibility if visibility in VISIBILITIES else "Team"))
        fid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("feedback", fid, actor=actor, to_state=kind, to_employee_id=to_employee_id)
    return fid


def feedback_stats(employee_id: int) -> dict:
    got = db.scalar("SELECT COUNT(*) FROM feedback WHERE to_employee_id=?", (employee_id,)) or 0
    gave = db.scalar("SELECT COUNT(*) FROM feedback WHERE from_employee_id=?", (employee_id,)) or 0
    praise = db.scalar("SELECT COUNT(*) FROM feedback WHERE to_employee_id=? AND kind='Praise'",
                       (employee_id,)) or 0
    return {"received": got, "given": gave, "praise": praise}


# --- review cycles ----------------------------------------------------------

def cycles():
    return db.rows("""SELECT rc.*,
                             (SELECT COUNT(*) FROM reviews r WHERE r.cycle_id=rc.id) n_reviews,
                             (SELECT COUNT(*) FROM reviews r WHERE r.cycle_id=rc.id
                              AND r.status IN ('Submitted','Calibrated')) n_done
                      FROM review_cycles rc ORDER BY rc.period_end DESC""")


def cycle(cycle_id: int):
    return db.one("SELECT * FROM review_cycles WHERE id=?", (cycle_id,))


def reviews_in(cycle_id: int, status: str = "All"):
    clause, params = ("", [cycle_id]) if status == "All" else ("AND r.status=?", [cycle_id, status])
    return db.rows(f"""SELECT r.*, e.first_name||' '||e.last_name employee,
                              d.name dept, rv.first_name||' '||rv.last_name reviewer
                       FROM reviews r JOIN employees e ON e.id=r.employee_id
                       LEFT JOIN departments d ON d.id=e.dept_id
                       LEFT JOIN employees rv ON rv.id=r.reviewer_id
                       WHERE r.cycle_id=? {clause}
                       ORDER BY r.status='Submitted', e.first_name""", tuple(params))


def create_cycle(*, name: str, period_start: str, period_end: str, actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute("""INSERT INTO review_cycles(name,period_start,period_end,status,created)
                              VALUES (?,?,?,'Draft',datetime('now'))""",
                           (name, period_start, period_end))
        cid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("review_cycle", cid, actor=actor, to_state="Draft", name=name)
    return cid


def open_cycle(cycle_id: int, *, actor: str = "system") -> int:
    """Generate a self review and a manager review for every active employee."""
    c = cycle(cycle_id)
    if not c:
        return 0
    emps = db.rows("SELECT id, manager_id FROM employees WHERE status!='Inactive' AND alumni=0")
    made = 0
    with db.cursor() as conn:
        for e in emps:
            for kind, reviewer in (("Self", e["id"]), ("Manager", e["manager_id"])):
                if kind == "Manager" and not reviewer:
                    continue
                dupe = conn.execute("""SELECT 1 FROM reviews WHERE cycle_id=? AND employee_id=?
                                       AND kind=?""", (cycle_id, e["id"], kind)).fetchone()
                if dupe:
                    continue
                conn.execute("""INSERT INTO reviews(cycle_id,employee_id,reviewer_id,kind,status)
                                VALUES (?,?,?,?,'Not started')""",
                             (cycle_id, e["id"], reviewer, kind))
                made += 1
        conn.execute("UPDATE review_cycles SET status='Open' WHERE id=?", (cycle_id,))
    log_event("review_cycle", cycle_id, actor=actor, from_state=c["status"], to_state="Open",
              reviews_created=made)
    return made


def set_cycle_status(cycle_id: int, status: str, *, actor: str = "system") -> bool:
    c = cycle(cycle_id)
    if not c or status not in CYCLE_STATUSES:
        return False
    if status == "Open" and c["status"] == "Draft":
        open_cycle(cycle_id, actor=actor)
        return True
    with db.cursor() as conn:
        conn.execute("UPDATE review_cycles SET status=? WHERE id=?", (status, cycle_id))
    log_event("review_cycle", cycle_id, actor=actor, from_state=c["status"], to_state=status)
    return True


def submit_review(review_id: int, *, overall: float, narrative: str, ratings: dict | None = None,
                  actor: str = "system") -> bool:
    r = db.one("SELECT * FROM reviews WHERE id=?", (review_id,))
    if not r:
        return False
    with db.cursor() as conn:
        conn.execute("""UPDATE reviews SET status='Submitted', overall=?, narrative=?,
                            ratings_json=?, submitted_on=date('now') WHERE id=?""",
                     (overall, narrative, json.dumps(ratings) if ratings else None, review_id))
    log_event("review", review_id, actor=actor, from_state=r["status"], to_state="Submitted")
    return True


def calibration_grid(cycle_id: int):
    """Submitted manager ratings by department — the calibration session view."""
    return db.rows("""SELECT d.name dept, COUNT(r.id) n, AVG(r.overall) avg_score,
                             MIN(r.overall) lo, MAX(r.overall) hi
                      FROM reviews r JOIN employees e ON e.id=r.employee_id
                      LEFT JOIN departments d ON d.id=e.dept_id
                      WHERE r.cycle_id=? AND r.kind='Manager' AND r.overall IS NOT NULL
                      GROUP BY d.id ORDER BY avg_score DESC""", (cycle_id,))


def rating_distribution(cycle_id: int):
    return db.rows("""SELECT CAST(ROUND(overall) AS INTEGER) band, COUNT(*) n
                      FROM reviews WHERE cycle_id=? AND kind='Manager' AND overall IS NOT NULL
                      GROUP BY band ORDER BY band""", (cycle_id,))


# --- onboarding -------------------------------------------------------------

def start_onboarding(employee_id: int, *, template_id: int | None = None,
                     actor: str = "system") -> int:
    """Create the checklist for a new hire. Idempotent per employee."""
    if db.scalar("SELECT COUNT(*) FROM onboarding_tasks WHERE employee_id=?", (employee_id,)):
        return 0
    tmpl = (db.one("SELECT * FROM onboarding_templates WHERE id=?", (template_id,))
            if template_id else db.one("SELECT * FROM onboarding_templates ORDER BY id LIMIT 1"))
    tasks = DEFAULT_ONBOARDING
    if tmpl and tmpl["tasks_json"]:
        try:
            parsed = json.loads(tmpl["tasks_json"])
            tasks = [(t["title"], t.get("owner_role", "HR"), t.get("offset_days", 0)) for t in parsed]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    start = db.scalar("SELECT date_of_joining FROM employees WHERE id=?", (employee_id,))
    with db.cursor() as conn:
        for i, (title, owner, offset) in enumerate(tasks):
            conn.execute("""INSERT INTO onboarding_tasks
                            (employee_id,template_id,title,owner_role,due_date,status,sort_order)
                            VALUES (?,?,?,?,date(?, ?),'Open',?)""",
                         (employee_id, tmpl["id"] if tmpl else None, title, owner,
                          start or "now", f"+{offset} days", i))
    log_event("onboarding", employee_id, actor=actor, to_state="Started", tasks=len(tasks))
    return len(tasks)


def onboarding_tasks(employee_id: int):
    return db.rows("""SELECT * FROM onboarding_tasks WHERE employee_id=?
                      ORDER BY status='Done', sort_order""", (employee_id,))


def onboarding_board():
    """Everyone with an open checklist, most recently joined first."""
    return db.rows("""SELECT e.id, e.first_name||' '||e.last_name name, e.designation,
                             d.name dept, e.date_of_joining, e.status,
                             COUNT(t.id) total,
                             SUM(CASE WHEN t.status='Done' THEN 1 ELSE 0 END) done,
                             SUM(CASE WHEN t.status='Open' AND t.due_date < date('now')
                                      THEN 1 ELSE 0 END) overdue
                      FROM employees e JOIN onboarding_tasks t ON t.employee_id=e.id
                      LEFT JOIN departments d ON d.id=e.dept_id
                      GROUP BY e.id ORDER BY e.date_of_joining DESC""")


def set_task_status(task_id: int, status: str, *, actor: str = "system") -> int | None:
    t = db.one("SELECT * FROM onboarding_tasks WHERE id=?", (task_id,))
    if not t or status not in ("Open", "Done", "Blocked", "N/A"):
        return None
    with db.cursor() as conn:
        conn.execute("""UPDATE onboarding_tasks SET status=?,
                            completed_on=CASE WHEN ?='Done' THEN date('now') ELSE NULL END
                        WHERE id=?""", (status, status, task_id))
    log_event("onboarding_task", task_id, actor=actor, from_state=t["status"], to_state=status)
    return t["employee_id"]


# --- internal changes -------------------------------------------------------

def changes(status: str = "All"):
    clause, params = ("", ()) if status == "All" else ("WHERE ec.status=?", (status,))
    return db.rows(f"""SELECT ec.*, e.first_name||' '||e.last_name employee, d.name dept
                       FROM employee_changes ec JOIN employees e ON e.id=ec.employee_id
                       LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY ec.status!='Pending', ec.effective_date DESC""", params)


def changes_for(employee_id: int):
    return db.rows("""SELECT * FROM employee_changes WHERE employee_id=?
                      ORDER BY effective_date DESC""", (employee_id,))


def propose_change(employee_id: int, *, change_type: str, effective_date: str,
                   to_values: dict, note: str = "", actor: str = "system") -> int:
    """Record a proposed change with its before-state, for approval."""
    emp = db.one("SELECT * FROM employees WHERE id=?", (employee_id,))
    if not emp:
        return 0
    from_values = {k: emp.get(k) for k in to_values}
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO employee_changes(employee_id,change_type,effective_date,from_json,
                   to_json,status,note,created)
               VALUES (?,?,?,?,?,'Pending',?,datetime('now'))""",
            (employee_id, change_type if change_type in CHANGE_TYPES else "Role change",
             effective_date, json.dumps(from_values), json.dumps(to_values), note))
        cid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("""INSERT INTO approvals(entity_type,entity_id,approver,sequence,decision,created)
                        VALUES ('employee_change',?,'hrbp',1,'Pending',datetime('now'))""", (cid,))
    log_event("employee_change", cid, actor=actor, to_state="Pending", change_type=change_type)
    return cid


_CHANGEABLE = {"designation", "dept_id", "manager_id", "base_salary", "branch", "status",
               "employment_type"}


def apply_change(change_id: int, *, actor: str = "system") -> dict:
    """Approve and write the change onto the employee record."""
    c = db.one("SELECT * FROM employee_changes WHERE id=?", (change_id,))
    if not c:
        return {"ok": False, "error": "No such change."}
    if c["status"] == "Applied":
        return {"ok": True, "note": "Already applied."}
    try:
        to_values = json.loads(c["to_json"] or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": "Stored change payload is unreadable."}
    fields = {k: v for k, v in to_values.items() if k in _CHANGEABLE}
    if not fields:
        return {"ok": False, "error": "Nothing changeable in this record."}
    sets = ", ".join(f"{k}=?" for k in fields)
    with db.cursor() as conn:
        conn.execute(f"UPDATE employees SET {sets} WHERE id=?", (*fields.values(), c["employee_id"]))
        conn.execute("""UPDATE employee_changes SET status='Applied', approved_by=? WHERE id=?""",
                     (actor, change_id))
        conn.execute("""UPDATE approvals SET decision='Approved', approver=?,
                            decided_at=datetime('now')
                        WHERE entity_type='employee_change' AND entity_id=?""", (actor, change_id))
    log_event("employee_change", change_id, actor=actor, from_state=c["status"], to_state="Applied",
              **{k: str(v) for k, v in fields.items()})
    log_event("employee", c["employee_id"], actor=actor, to_state=c["change_type"])
    return {"ok": True, "fields": list(fields)}


def reject_change(change_id: int, *, actor: str = "system", note: str = "") -> bool:
    c = db.one("SELECT * FROM employee_changes WHERE id=?", (change_id,))
    if not c:
        return False
    with db.cursor() as conn:
        conn.execute("UPDATE employee_changes SET status='Rejected', note=? WHERE id=?",
                     (note or c["note"], change_id))
        conn.execute("""UPDATE approvals SET decision='Rejected', approver=?,
                            decided_at=datetime('now')
                        WHERE entity_type='employee_change' AND entity_id=?""", (actor, change_id))
    log_event("employee_change", change_id, actor=actor, from_state=c["status"], to_state="Rejected")
    return True


# --- separations ------------------------------------------------------------

EXIT_CHECKLIST = ["Knowledge transfer plan agreed", "Handover documented", "Laptop returned",
                  "Building pass returned", "Accounts revoked", "Final payslip raised",
                  "Exit interview held"]


def separations(status: str = "All"):
    clause, params = ("", ()) if status == "All" else ("WHERE s.status=?", (status,))
    return db.rows(f"""SELECT s.*, e.first_name||' '||e.last_name employee, e.designation,
                              d.name dept
                       FROM separations s JOIN employees e ON e.id=s.employee_id
                       LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY s.status='Complete', s.last_day DESC""", params)


def separation(sep_id: int):
    return db.one("""SELECT s.*, e.first_name||' '||e.last_name employee, e.designation,
                            e.email, d.name dept
                     FROM separations s JOIN employees e ON e.id=s.employee_id
                     LEFT JOIN departments d ON d.id=e.dept_id WHERE s.id=?""", (sep_id,))


def separation_for(employee_id: int):
    return db.one("SELECT * FROM separations WHERE employee_id=? ORDER BY id DESC LIMIT 1",
                  (employee_id,))


def start_separation(employee_id: int, *, kind: str, notice_date: str, last_day: str,
                     reason: str = "", actor: str = "system") -> int:
    checklist = [{"title": t, "done": False} for t in EXIT_CHECKLIST]
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO separations(employee_id,kind,notice_date,last_day,reason,status,
                   checklist_json,created)
               VALUES (?,?,?,?,?,'Open',?,datetime('now'))""",
            (employee_id, kind if kind in SEPARATION_KINDS else "Resignation", notice_date,
             last_day, reason, json.dumps(checklist)))
        sid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("separation", sid, actor=actor, to_state="Open", employee_id=employee_id, kind=kind)
    return sid


def toggle_exit_task(sep_id: int, index: int, *, actor: str = "system") -> bool:
    s = db.one("SELECT * FROM separations WHERE id=?", (sep_id,))
    if not s:
        return False
    try:
        items = json.loads(s["checklist_json"] or "[]")
        items[index]["done"] = not items[index].get("done")
    except (json.JSONDecodeError, IndexError, TypeError):
        return False
    status = "Complete" if all(i.get("done") for i in items) else "In progress"
    with db.cursor() as conn:
        conn.execute("UPDATE separations SET checklist_json=?, status=? WHERE id=?",
                     (json.dumps(items), status, sep_id))
    if status == "Complete" and s["status"] != "Complete":
        complete_separation(sep_id, actor=actor)
    return True


def complete_separation(sep_id: int, *, actor: str = "system") -> bool:
    """Mark the employee as departed and eligible for rehire (alumni)."""
    s = db.one("SELECT * FROM separations WHERE id=?", (sep_id,))
    if not s:
        return False
    with db.cursor() as conn:
        conn.execute("UPDATE separations SET status='Complete' WHERE id=?", (sep_id,))
        conn.execute("""UPDATE employees SET status='Inactive', termination_date=?, alumni=1
                        WHERE id=?""", (s["last_day"], s["employee_id"]))
    log_event("separation", sep_id, actor=actor, from_state=s["status"], to_state="Complete")
    log_event("employee", s["employee_id"], actor=actor, to_state="Alumni")
    return True


def record_exit_interview(sep_id: int, *, notes: str, sentiment: str = "",
                          actor: str = "system") -> bool:
    with db.cursor() as conn:
        conn.execute("UPDATE separations SET exit_interview=?, exit_sentiment=? WHERE id=?",
                     (notes, sentiment or None, sep_id))
    log_event("separation", sep_id, actor=actor, to_state="Exit interview recorded")
    return True


def alumni():
    return db.rows("""SELECT e.*, d.name dept, s.last_day, s.kind, s.alumni_status
                      FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                      LEFT JOIN separations s ON s.employee_id=e.id
                      WHERE e.alumni=1 ORDER BY s.last_day DESC""")


# --- employee-relations cases ----------------------------------------------

def cases(status: str = "All"):
    clause, params = ("", ()) if status == "All" else ("WHERE c.status=?", (status,))
    return db.rows(f"""SELECT c.*, e.first_name||' '||e.last_name employee, d.name dept
                       FROM cases c LEFT JOIN employees e ON e.id=c.employee_id
                       LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY c.status IN ('Resolved','Closed'),
                                CASE c.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                                                WHEN 'Normal' THEN 2 ELSE 3 END,
                                c.created DESC""", params)


def open_case(*, employee_id: int | None, kind: str, summary: str, severity: str = "Normal",
              visibility: str = "HR only", actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO cases(employee_id,kind,severity,visibility,status,summary,opened_by,created)
               VALUES (?,?,?,?,'Open',?,?,datetime('now'))""",
            (employee_id, kind if kind in CASE_KINDS else "Other",
             severity if severity in CASE_SEVERITIES else "Normal", visibility, summary, actor))
        cid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event("case", cid, actor=actor, to_state="Open", kind=kind, severity=severity)
    return cid


def set_case_status(case_id: int, status: str, *, resolution: str = "", actor: str = "system") -> bool:
    c = db.one("SELECT * FROM cases WHERE id=?", (case_id,))
    if not c or status not in CASE_STATUSES:
        return False
    with db.cursor() as conn:
        conn.execute("""UPDATE cases SET status=?, resolution=COALESCE(NULLIF(?,''), resolution),
                            closed_at=CASE WHEN ? IN ('Resolved','Closed')
                                           THEN datetime('now') ELSE NULL END
                        WHERE id=?""", (status, resolution, status, case_id))
    log_event("case", case_id, actor=actor, from_state=c["status"], to_state=status)
    return True


# --- org chart & scenarios --------------------------------------------------

def org_tree():
    """The reports_to tree, rooted at everyone without a manager."""
    emps = db.rows("""SELECT e.id, e.first_name||' '||e.last_name name, e.designation,
                             e.manager_id, e.base_salary, d.name dept
                      FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                      WHERE e.status!='Inactive' ORDER BY e.first_name""")
    by_mgr: dict[int | None, list[dict]] = {}
    for e in emps:
        by_mgr.setdefault(e["manager_id"], []).append(e)

    def build(mid, depth=0):
        out = []
        for e in by_mgr.get(mid, []):
            node = dict(e)
            node["depth"] = depth
            node["reports"] = build(e["id"], depth + 1)
            node["team_size"] = len(node["reports"]) + sum(r["team_size"] for r in node["reports"])
            out.append(node)
        return out

    return build(None)


def headcount_scenario(dept_id: int | None = None, delta: int = 0) -> dict:
    """What-if: add or remove N people from a department at its average salary."""
    if dept_id:
        n = db.scalar("SELECT COUNT(*) FROM employees WHERE dept_id=? AND status!='Inactive'",
                      (dept_id,)) or 0
        avg = db.scalar("SELECT AVG(base_salary) FROM employees WHERE dept_id=? AND status!='Inactive'",
                        (dept_id,)) or 0
        name = db.scalar("SELECT name FROM departments WHERE id=?", (dept_id,)) or "—"
    else:
        n = db.scalar("SELECT COUNT(*) FROM employees WHERE status!='Inactive'") or 0
        avg = db.scalar("SELECT AVG(base_salary) FROM employees WHERE status!='Inactive'") or 0
        name = "Whole company"
    return {"scope": name, "headcount": n, "avg_salary": avg, "delta": delta,
            "new_headcount": max(0, n + delta), "cost_change": avg * delta,
            "new_cost": avg * max(0, n + delta)}


# --- performance signals (explainable, privacy-aware) -----------------------

def attrition_signals(dept: str | None = None, limit: int = 12):
    """Advisory flags with their contributing factors — never an unexplained score.

    Uses only data the employer already holds for HR purposes: goal progress,
    recent attendance, feedback recency and tenure. Every factor is returned
    alongside the score, so the reason is always visible with the flag.
    """
    clause, params = ("", []) if not dept else ("AND d.name=?", [dept])
    emps = db.rows(f"""SELECT e.id, e.first_name||' '||e.last_name name, e.designation,
                              d.name dept, e.date_of_joining, e.status,
                              (SELECT COUNT(*) FROM attendance a WHERE a.employee_id=e.id
                               AND a.status='Absent') absences,
                              (SELECT COUNT(*) FROM attendance a WHERE a.employee_id=e.id) att_days,
                              (SELECT COUNT(*) FROM feedback f WHERE f.to_employee_id=e.id) n_feedback,
                              (SELECT AVG(CASE WHEN g.target>0 THEN 100.0*g.current/g.target ELSE NULL END)
                               FROM goals g WHERE g.owner_type='employee' AND g.owner_id=e.id) goal_pct,
                              (SELECT COUNT(*) FROM goals g WHERE g.owner_type='employee'
                               AND g.owner_id=e.id AND g.status IN ('At risk','Behind')) goals_slipping
                       FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                       WHERE e.status!='Inactive' AND e.alumni=0 {clause}""", tuple(params))
    out = []
    for e in emps:
        factors, score = [], 0
        if e["att_days"] and e["absences"] / e["att_days"] > 0.08:
            pct = round(100 * e["absences"] / e["att_days"])
            factors.append(f"absence rate {pct}% over the recorded period")
            score += 2
        if e["goal_pct"] is not None and e["goal_pct"] < 40:
            factors.append(f"goal progress averaging {e['goal_pct']:.0f}%")
            score += 2
        if e["goals_slipping"]:
            factors.append(f"{e['goals_slipping']} goal(s) at risk or behind")
            score += 1
        if not e["n_feedback"]:
            factors.append("no feedback received at all")
            score += 1
        if e["date_of_joining"] and e["date_of_joining"] < "2022-01-01":
            factors.append("more than four years in the same role")
            score += 1
        if score >= 3:
            out.append({**e, "score": score, "factors": factors,
                        "band": "High" if score >= 5 else "Moderate"})
    return sorted(out, key=lambda r: -r["score"])[:limit]


def promotion_readiness(limit: int = 10):
    """The inverse signal: consistent goal delivery plus positive feedback."""
    rows_ = db.rows("""SELECT e.id, e.first_name||' '||e.last_name name, e.designation, d.name dept,
                              (SELECT AVG(CASE WHEN g.target>0 THEN 100.0*g.current/g.target ELSE NULL END)
                               FROM goals g WHERE g.owner_type='employee' AND g.owner_id=e.id) goal_pct,
                              (SELECT COUNT(*) FROM goals g WHERE g.owner_type='employee'
                               AND g.owner_id=e.id AND g.status='Complete') goals_done,
                              (SELECT COUNT(*) FROM feedback f WHERE f.to_employee_id=e.id
                               AND f.kind='Praise') praise,
                              (SELECT AVG(r.overall) FROM reviews r WHERE r.employee_id=e.id
                               AND r.kind='Manager' AND r.overall IS NOT NULL) review_avg
                       FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                       WHERE e.status='Active' AND e.alumni=0""")
    out = []
    for e in rows_:
        factors, score = [], 0.0
        if (e["goal_pct"] or 0) >= 80:
            factors.append(f"goal progress averaging {e['goal_pct']:.0f}%")
            score += 2
        if e["goals_done"]:
            factors.append(f"{e['goals_done']} goal(s) completed")
            score += 1
        if (e["praise"] or 0) >= 2:
            factors.append(f"{e['praise']} pieces of praise from colleagues")
            score += 1.5
        if (e["review_avg"] or 0) >= 4:
            factors.append(f"manager review average {e['review_avg']:.1f}/5")
            score += 2
        if score >= 3:
            out.append({**e, "score": score, "factors": factors})
    return sorted(out, key=lambda r: -r["score"])[:limit]


def team_health(manager_id: int | None = None):
    clause, params = ("", []) if not manager_id else ("WHERE e.manager_id=?", [manager_id])
    return db.rows(f"""SELECT e.id, e.first_name||' '||e.last_name name, e.designation,
                              (SELECT COUNT(*) FROM goals g WHERE g.owner_type='employee'
                               AND g.owner_id=e.id) goals,
                              (SELECT AVG(CASE WHEN g.target>0 THEN 100.0*g.current/g.target ELSE NULL END)
                               FROM goals g WHERE g.owner_type='employee' AND g.owner_id=e.id) goal_pct,
                              (SELECT COUNT(*) FROM feedback f WHERE f.to_employee_id=e.id) feedback,
                              (SELECT COUNT(*) FROM leave_requests l WHERE l.employee_id=e.id
                               AND l.status='Pending') pending_leave
                       FROM employees e {clause} ORDER BY e.first_name""", tuple(params))


# --- module KPIs ------------------------------------------------------------

def performance_kpis() -> dict:
    return {
        "goals": db.scalar("SELECT COUNT(*) FROM goals WHERE status NOT IN ('Complete','Cancelled')") or 0,
        "at_risk": db.scalar("SELECT COUNT(*) FROM goals WHERE status IN ('At risk','Behind')") or 0,
        "feedback_30d": db.scalar("""SELECT COUNT(*) FROM feedback
                                     WHERE created >= datetime('now','-30 days')""") or 0,
        "open_cycles": db.scalar("SELECT COUNT(*) FROM review_cycles WHERE status IN ('Open','Calibration')") or 0,
        "reviews_due": db.scalar("""SELECT COUNT(*) FROM reviews r
                                    JOIN review_cycles c ON c.id=r.cycle_id
                                    WHERE c.status='Open' AND r.status!='Submitted'""") or 0,
    }


def lifecycle_kpis() -> dict:
    return {
        "onboarding": db.scalar("""SELECT COUNT(DISTINCT employee_id) FROM onboarding_tasks
                                   WHERE status='Open'""") or 0,
        "overdue_tasks": db.scalar("""SELECT COUNT(*) FROM onboarding_tasks
                                      WHERE status='Open' AND due_date < date('now')""") or 0,
        "pending_changes": db.scalar("SELECT COUNT(*) FROM employee_changes WHERE status='Pending'") or 0,
        "separations": db.scalar("SELECT COUNT(*) FROM separations WHERE status!='Complete'") or 0,
        "open_cases": db.scalar("SELECT COUNT(*) FROM cases WHERE status IN ('Open','Investigating')") or 0,
        "alumni": db.scalar("SELECT COUNT(*) FROM employees WHERE alumni=1") or 0,
    }
