"""Synthetic data for the performance and lifecycle modules, plus competencies.

Safe to re-run: it clears only the tables it owns. Requires seed.py (employees)
and seed_talent.py (requisitions and candidates) to have run first.

    python seed_platform.py
"""
from __future__ import annotations

import json
import random
from datetime import timedelta

import db
import people
import talent
from web import cv_extract, ranking

RNG = random.Random(20260611)
TODAY = db.TODAY

COMPETENCIES = [
    ("Technical depth", "Technical", "Command of the craft their role requires."),
    ("Problem solving", "Technical", "Breaks ambiguous problems into tractable pieces."),
    ("Delivery", "Delivery", "Ships work of the right size, on a predictable rhythm."),
    ("Ownership", "Delivery", "Takes responsibility for outcomes, not just tasks."),
    ("Communication", "Collaboration", "Writes and speaks clearly to the right audience."),
    ("Collaboration", "Collaboration", "Makes the people around them more effective."),
    ("Leadership", "Leadership", "Sets direction and grows others."),
    ("Customer focus", "Delivery", "Keeps the customer's problem in view."),
]

COMPANY_GOALS = [
    ("Grow annual recurring revenue to £12m", "ARR", 12_000_000, 8_400_000, "£"),
    ("Reach 95% customer retention", "Retention", 95, 91, "%"),
    ("Cut time-to-hire below 30 days", "Days to hire", 30, 41, "days"),
]
DEPT_GOAL_TEMPLATES = {
    "Engineering": [("Ship the platform migration", "Milestones", 8),
                    ("Hold p95 latency under 200ms", "ms", 200)],
    "Sales": [("Close £4m of new business", "£", 4_000_000),
              ("Build £12m of qualified pipeline", "£", 12_000_000)],
    "Marketing": [("Generate 2,400 qualified leads", "Leads", 2400)],
    "Customer Success": [("Lift NPS to 45", "NPS", 45)],
    "Finance": [("Close the books within 5 days", "Days", 5)],
    "People & Culture": [("Fill 12 open roles", "Hires", 12),
                         ("Complete 100% of review cycle", "%", 100)],
    "Operations": [("Reduce supplier spend by 8%", "%", 8)],
    "Product": [("Launch 4 major features", "Features", 4)],
}
IND_GOALS = [
    "Own the {area} workstream end to end", "Improve {area} by a measurable margin",
    "Mentor a colleague through {area}", "Document and hand over {area}",
    "Reduce time spent on {area}", "Raise quality of {area} reporting",
]
AREAS = ["onboarding", "reporting", "the release process", "customer escalations",
         "the data pipeline", "forecast accuracy", "our documentation", "incident response"]

PRAISE = [
    "Stepped in on the {a} escalation at short notice and steadied it — the customer noticed.",
    "The {a} write-up was the clearest thing I've read this quarter.",
    "Quietly unblocked three people this week on {a}. Not glamorous, very valuable.",
    "Ran the {a} session so well that the follow-up actions wrote themselves.",
    "Caught a problem in {a} before it reached the customer.",
]
CONSTRUCTIVE = [
    "The {a} work landed well, but the update came late — flag slippage sooner.",
    "Strong analysis on {a}; the recommendation was buried on page four.",
    "Great instincts on {a}. Try bringing others in earlier rather than finishing alone.",
    "Consider handing {a} over — you're the only person who knows how it works.",
]
EXIT_NOTES = [
    ("Leaving for a step up in scope that we couldn't offer right now. No complaints about "
     "the team — I'd come back if the right role opened.", "Positive"),
    ("Workload became unsustainable after two people left and weren't replaced. Raised it "
     "twice; nothing changed.", "Negative"),
    ("Relocating for family reasons. Genuinely sorry to go — the last project was the best "
     "work I've done.", "Positive"),
    ("Wanted a clearer path to management. The conversations kept being deferred.", "Mixed"),
]
CASES = [
    ("Pay query", "Overtime for the March on-call rota appears not to have been paid.", "Normal"),
    ("Wellbeing", "Requesting a phased return after extended sick leave.", "High"),
    ("Grievance", "Reports being consistently talked over in team meetings.", "High"),
    ("Conduct", "Repeated late arrival without notice; manager has raised it informally.", "Normal"),
    ("Other", "Asking about the flexible working policy for a compressed week.", "Low"),
]


def _d(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def _fwd(days):
    return (TODAY + timedelta(days=days)).isoformat()


def build():
    db.migrate()
    cv_extract.ensure_default_prompt()
    ranking.ensure_prompts()

    with db.cursor() as conn:
        for t in ("scorecards", "interviews", "offers", "ranking_scores", "ranking_runs",
                  "goal_checkins", "goals", "feedback", "reviews", "review_cycles",
                  "onboarding_tasks", "onboarding_templates", "employee_changes",
                  "separations", "cases", "employee_skills", "competencies", "approvals"):
            conn.execute(f"DELETE FROM {t}")
        conn.executemany("INSERT INTO competencies(name,category,description) VALUES (?,?,?)",
                         COMPETENCIES)
        conn.execute("""INSERT INTO onboarding_templates(name,role_filter,tasks_json,created)
                        VALUES ('Standard new joiner','',?,datetime('now'))""",
                     (json.dumps([{"title": t, "owner_role": o, "offset_days": d}
                                  for t, o, d in people.DEFAULT_ONBOARDING]),))

    emps = db.rows("""SELECT e.id, e.dept_id, e.manager_id, e.designation, d.name dept
                      FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                      WHERE e.status!='Inactive'""")
    depts = db.rows("SELECT id, name FROM departments")
    comps = talent.competencies()

    # --- interviews and scorecards for candidates past the screen -----------
    advanced = db.rows("""SELECT a.id, a.job_id, a.stage, j.dept_id
                          FROM applications a JOIN job_openings j ON j.id=a.job_id
                          WHERE a.stage IN ('Interview','Offer','Hired')""")
    n_iv = n_sc = 0
    for app in advanced:
        panel = [e for e in emps if e["dept_id"] == app["dept_id"]] or emps
        for kind in RNG.sample(talent.INTERVIEW_KINDS[:4], RNG.randint(1, 3)):
            interviewer = RNG.choice(panel)
            iid = talent.schedule_interview(
                app["id"], interviewer_id=interviewer["id"], kind=kind,
                scheduled_at=_d(RNG.randint(2, 30)) + f" {RNG.randint(9, 16)}:00",
                mode=RNG.choice(talent.INTERVIEW_MODES), actor="seed")
            n_iv += 1
            if RNG.random() < 0.82:
                base = RNG.uniform(2.4, 4.6)
                scores = {c["id"]: round(max(1, min(5, base + RNG.uniform(-0.9, 0.9))))
                          for c in RNG.sample(comps, RNG.randint(3, 5))}
                rec = ("Strong hire" if base > 4.2 else "Hire" if base > 3.4
                       else "No decision" if base > 2.9 else "No hire")
                talent.record_scorecard(iid, scores, recommendation=rec,
                                        notes=f"Probed {RNG.choice(AREAS)}; evidence was "
                                              f"{'convincing' if base > 3.5 else 'thin in places'}.",
                                        actor="seed")
                n_sc += len(scores)

    # --- offers for candidates at Offer / Hired -----------------------------
    n_off = 0
    for app in db.rows("""SELECT a.id, a.stage, j.comp_min, j.comp_max FROM applications a
                          JOIN job_openings j ON j.id=a.job_id
                          WHERE a.stage IN ('Offer','Hired')"""):
        salary = round(RNG.uniform(app["comp_min"] or 50000, app["comp_max"] or 90000), -2)
        oid = talent.draft_offer(app["id"], salary=salary, start_date=_fwd(RNG.randint(20, 70)),
                                 expires_on=_fwd(RNG.randint(5, 14)), actor="seed")
        with db.cursor() as conn:
            conn.execute("UPDATE offers SET letter=? WHERE id=?",
                         (ranking._template_letter(talent.offer(oid)), oid))
        status = "Accepted" if app["stage"] == "Hired" else RNG.choice(
            ["Draft", "Pending approval", "Approved", "Sent", "Sent", "Declined"])
        if status != "Draft":
            with db.cursor() as conn:
                conn.execute("""UPDATE offers SET status=?,
                                    sent_at=CASE WHEN ? IN ('Sent','Accepted','Declined')
                                                 THEN datetime('now') ELSE NULL END,
                                    approved_by=CASE WHEN ?!='Draft' THEN 'seed' ELSE NULL END
                                WHERE id=?""", (status, status, status, oid))
        n_off += 1

    # --- goals: company → department → individual ---------------------------
    company_ids = []
    for title, metric, target, current, unit in COMPANY_GOALS:
        gid = people.create_goal(title=title, owner_type="company", metric=metric, target=target,
                                 current=current, unit=unit, period="2026-Q3",
                                 due_date=_fwd(80), actor="seed")
        company_ids.append(gid)

    dept_ids = []
    for d in depts:
        for title, metric, target in DEPT_GOAL_TEMPLATES.get(d["name"], []):
            gid = people.create_goal(title=title, owner_type="department", owner_id=d["id"],
                                     parent_goal_id=RNG.choice(company_ids), metric=metric,
                                     target=target, current=round(target * RNG.uniform(.2, .95)),
                                     period="2026-Q3", due_date=_fwd(RNG.randint(30, 90)),
                                     actor="seed")
            dept_ids.append((gid, d["id"]))

    n_goals = 0
    for e in emps:
        if RNG.random() > 0.72:
            continue
        parent = next((g for g, did in dept_ids if did == e["dept_id"]), None)
        for _ in range(RNG.randint(1, 2)):
            target = RNG.choice([100, 10, 5, 20, 12])
            current = round(target * RNG.uniform(0.05, 1.0))
            gid = people.create_goal(
                title=RNG.choice(IND_GOALS).format(area=RNG.choice(AREAS)),
                owner_type="employee", owner_id=e["id"], parent_goal_id=parent,
                metric="Progress", target=target, current=current, unit="%",
                period="2026-Q3", due_date=_fwd(RNG.randint(15, 85)), actor="seed")
            pct = 100 * current / target
            status = ("Complete" if pct >= 100 else "On track" if pct > 55
                      else "At risk" if pct > 30 else "Behind")
            with db.cursor() as conn:
                conn.execute("UPDATE goals SET status=? WHERE id=?", (status, gid))
                for k in range(RNG.randint(1, 3)):
                    conn.execute("""INSERT INTO goal_checkins(goal_id,value,status,note,created_by,created)
                                    VALUES (?,?,?,?,'seed',?)""",
                                 (gid, round(current * (k + 1) / 3, 1), status,
                                  f"Progress on {RNG.choice(AREAS)}.", _d(RNG.randint(3, 60))))
            n_goals += 1

    # --- feedback -----------------------------------------------------------
    n_fb = 0
    for _ in range(90):
        giver, receiver = RNG.sample(emps, 2)
        praise = RNG.random() < 0.68
        body = RNG.choice(PRAISE if praise else CONSTRUCTIVE).format(a=RNG.choice(AREAS))
        with db.cursor() as conn:
            conn.execute("""INSERT INTO feedback(from_employee_id,to_employee_id,kind,
                                competency_id,body,visibility,created)
                            VALUES (?,?,?,?,?,?,?)""",
                         (giver["id"], receiver["id"],
                          "Praise" if praise else RNG.choice(["Constructive", "Peer review"]),
                          RNG.choice(comps)["id"], body,
                          RNG.choices(["Public", "Team", "Private"], weights=[35, 50, 15])[0],
                          _d(RNG.randint(1, 75))))
        n_fb += 1

    # --- a review cycle, part-completed --------------------------------------
    cid = people.create_cycle(name="2026 H1 review", period_start="2026-01-01",
                              period_end="2026-06-30", actor="seed")
    people.open_cycle(cid, actor="seed")
    n_rev = 0
    for r in db.rows("SELECT id, kind FROM reviews WHERE cycle_id=?", (cid,)):
        if RNG.random() < 0.55:
            overall = round(RNG.gauss(3.5, 0.7), 1)
            overall = max(1.0, min(5.0, overall))
            people.submit_review(r["id"], overall=overall,
                                 narrative=f"Delivered consistently on {RNG.choice(AREAS)}. "
                                           f"Next: {RNG.choice(AREAS)}.",
                                 ratings={c["name"]: max(1, min(5, round(overall + RNG.uniform(-.8, .8))))
                                          for c in RNG.sample(comps, 4)}, actor="seed")
            n_rev += 1

    # --- onboarding for the newest joiners ----------------------------------
    n_onb = 0
    for e in db.rows("""SELECT id FROM employees WHERE date_of_joining >= ?
                        ORDER BY date_of_joining DESC LIMIT 6""", (_d(120),)):
        if people.start_onboarding(e["id"], actor="seed"):
            n_onb += 1
            for t in people.onboarding_tasks(e["id"]):
                if RNG.random() < 0.55:
                    people.set_task_status(t["id"], "Done", actor="seed")

    # --- internal changes ---------------------------------------------------
    n_chg = 0
    for e in RNG.sample(emps, min(7, len(emps))):
        ctype = RNG.choice(people.CHANGE_TYPES)
        to_vals = {}
        if ctype in ("Promotion", "Role change"):
            to_vals["designation"] = "Senior " + (e["designation"] or "Specialist")
        if ctype == "Salary change" or ctype == "Promotion":
            cur = db.scalar("SELECT base_salary FROM employees WHERE id=?", (e["id"],)) or 50000
            to_vals["base_salary"] = round(cur * RNG.uniform(1.05, 1.18), -2)
        if ctype == "Transfer":
            to_vals["dept_id"] = RNG.choice(depts)["id"]
        if not to_vals:
            to_vals["designation"] = e["designation"] or "Specialist"
        chg = people.propose_change(e["id"], change_type=ctype, effective_date=_fwd(RNG.randint(5, 60)),
                                    to_values=to_vals, note="Proposed during the quarterly review.",
                                    actor="seed")
        n_chg += 1
        if RNG.random() < 0.45:
            people.apply_change(chg, actor="seed")

    # --- separations and alumni ---------------------------------------------
    n_sep = 0
    for e in RNG.sample(emps, min(4, len(emps))):
        notes, sentiment = RNG.choice(EXIT_NOTES)
        sid = people.start_separation(e["id"], kind=RNG.choice(people.SEPARATION_KINDS),
                                      notice_date=_d(RNG.randint(10, 40)),
                                      last_day=_fwd(RNG.randint(-10, 30)),
                                      reason=RNG.choice(["New role elsewhere", "Relocation",
                                                         "End of fixed term", "Personal reasons"]),
                                      actor="seed")
        people.record_exit_interview(sid, notes=notes, sentiment=sentiment, actor="seed")
        n_sep += 1
        if RNG.random() < 0.5:
            for idx in range(len(people.EXIT_CHECKLIST)):
                people.toggle_exit_task(sid, idx, actor="seed")

    # --- employee-relations cases -------------------------------------------
    for kind, summary, severity in CASES:
        emp = RNG.choice(emps)
        cid2 = people.open_case(employee_id=emp["id"] if RNG.random() < 0.8 else None,
                                kind=kind, summary=summary, severity=severity,
                                visibility=RNG.choice(["HR only", "HR and manager"]), actor="seed")
        if RNG.random() < 0.4:
            people.set_case_status(cid2, "Investigating", actor="seed")

    # --- employee skills for internal mobility ------------------------------
    skills_pool = ["Python", "SQL", "Stakeholder management", "Forecasting", "Figma",
                   "Salesforce", "Coaching", "Data analysis", "Project delivery", "Copywriting",
                   "Employment law", "Negotiation", "Kubernetes", "Accounting"]
    with db.cursor() as conn:
        for e in emps:
            for s in RNG.sample(skills_pool, RNG.randint(2, 5)):
                conn.execute("""INSERT INTO employee_skills(employee_id,skill,level,years,source)
                                VALUES (?,?,?,?,'manual')""",
                             (e["id"], s, RNG.choice(["Intermediate", "Advanced", "Expert"]),
                              round(RNG.uniform(1, 9), 1)))

    print(f"FastHRM platform seeded → {db.DB_PATH}")
    print(f"  {len(COMPETENCIES)} competencies · {n_iv} interviews · {n_sc} scorecard entries · {n_off} offers")
    print(f"  {len(COMPANY_GOALS)} company + {len(dept_ids)} team + {n_goals} individual goals · {n_fb} feedback")
    print(f"  {n_rev} reviews submitted · {n_onb} onboarding checklists · {n_chg} changes · {n_sep} separations")


if __name__ == "__main__":
    build()
