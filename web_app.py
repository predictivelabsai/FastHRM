"""FastHRM — an open-source HR system built with FastHTML.

A server-side, HTMX-driven port of the core of Frappe HR (HRMS), scoped to three
pillars: people (employee directory + departments), time (leave + attendance),
and pay (payslips) — plus an AI assistant grounded in the live (synthetic) data.

Run:
    python web_app.py            # http://localhost:5010

Login: admin@fasthr.example / FastHR2026$  (override via .env)
"""
from __future__ import annotations

import os
import json
import secrets
import uuid
import logging
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

from fasthtml.common import (
    fast_app, serve, Div, H1, P, A, Form, Input, Button, NotStr,
    RedirectResponse, Script, Style, Link, Title,
)
from starlette.responses import StreamingResponse, Response
from starlette.responses import JSONResponse

import db
import talent
import people
import integrations
import version
from web.layout import page, LAYOUT_CSS
from web import views, ai, ats, cv_extract, ranking, performance, lifecycle, settings
from web.landing import landing_page
from web.seo import register_seo_routes
from web.developer import developer_page
from web import account_auth, google_auth
from web.api import api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("fasthr")

VALID_EMAIL = os.getenv("FASTHR_ADMIN_EMAIL", "admin@fasthr.example")
VALID_PASSWORD = os.getenv("FASTHR_ADMIN_PASSWORD", "FastHR2026$")
ENV_LABEL = os.getenv("FASTHR_ENV_LABEL", "FastHRM")
SECRET = os.getenv("FASTHR_SECRET", secrets.token_hex(32))
PORT = int(os.getenv("FASTHR_PORT", "5010"))

app, rt = fast_app(live=False, pico=False, secret_key=SECRET, hdrs=[Style(LAYOUT_CSS)])
app.mount("/api", api)


@rt("/swagger.json", methods=["GET"])
def swagger_schema():
    return JSONResponse(api.openapi())


@rt("/developers", methods=["GET"])
def developers():
    return developer_page()


account_auth.register_fasthtml_routes(rt, app_name="FastHRM", session_key="user", success_path="/")


def _user(session):
    return session.get("user")


def _thread(session):
    if "thread" not in session:
        session["thread"] = uuid.uuid4().hex
    return session["thread"]


def _guard(session, active, builder):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    content = builder() if callable(builder) else builder
    if not isinstance(content, tuple):
        content = (content,)
    return page(active, ENV_LABEL, _user(session), _thread(session), *content)


def _login_card(error="", email=""):
    return Title("FastHRM — Sign in"), Style(LAYOUT_CSS), Div(
        Form(H1("FastHRM"), P("Sign in to your HR workspace"),
             Input(name="email", type="email", placeholder="Email", value=email, required=True),
             Input(name="password", type="password", placeholder="Password", required=True),
             P(error, cls="error") if error else None,
             Button("Sign in", cls="btn primary", type="submit"),
             P(NotStr("Demo: <code>admin@fasthr.example</code> / <code>FastHR2026$</code>"), cls="hint"),
             method="post", action="/login", cls="login-card"), cls="login-wrap")


@rt("/login")
def get(session):
    if _user(session):
        return RedirectResponse("/", status_code=303)
    return _login_card()


@rt("/login")
def post(session, email: str = "", password: str = ""):
    if email.strip().lower() == VALID_EMAIL.lower() and password == VALID_PASSWORD:
        session["user"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    return _login_card("Invalid email or password.", email)



@rt("/auth/google")
def google_start(session, request):
    if not google_auth.enabled():
        return RedirectResponse("/login?error=Google+sign-in+is+not+configured", status_code=303)
    state = google_auth.new_state()
    session["google_oauth_state"] = state
    return RedirectResponse(google_auth.authorize_url(request, state), status_code=303)


@rt("/auth/google/callback")
def google_callback(session, request, code: str = "", state: str = "", error: str = ""):
    if error or not code or state != session.pop("google_oauth_state", None):
        return RedirectResponse("/login?error=Google+sign-in+failed", status_code=303)
    identity = google_auth.exchange(request, code)
    if not identity:
        return RedirectResponse("/login?error=Google+account+is+not+authorised", status_code=303)
    account_auth.accounts.link_google(identity["email"], identity["name"])
    session["user"] = identity["email"]
    return RedirectResponse("/", status_code=303)


@rt("/logout")
def get(session):
    session.pop("user", None)
    return RedirectResponse("/login", status_code=303)


@rt("/")
def get(session):
    if not _user(session):
        return landing_page()
    return _guard(session, "dashboard", views.dashboard)


@rt("/employees")
def get(session, dept: str = "All", q: str = ""):
    return _guard(session, "employees", lambda: views.employees_list(dept, q))


@rt("/employees/{eid}")
def get(session, eid: int):
    return _guard(session, "employees", lambda: views.employee_detail(eid))


@rt("/departments")
def get(session):
    return _guard(session, "departments", views.departments_list)


@rt("/leave")
def get(session, status: str = "Pending"):
    return _guard(session, "leave", lambda: views.leave_list(status))


def _lfrag(session, status="Pending"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    return views.leave_main(status)


@rt("/leave/apply")
def post(session, employee_id: int = 0, leave_type: str = "", from_date: str = "", to_date: str = "", reason: str = ""):
    if employee_id and from_date and to_date:
        db.apply_leave(employee_id, leave_type, from_date, to_date, reason)
    return _lfrag(session, "Pending")


@rt("/leave/{req_id}/approve")
def post(session, req_id: int):
    db.set_leave_status(req_id, "Approved")
    return _lfrag(session, "Pending")


@rt("/leave/{req_id}/reject")
def post(session, req_id: int):
    db.set_leave_status(req_id, "Rejected")
    return _lfrag(session, "Pending")


@rt("/attendance")
def get(session):
    return _guard(session, "attendance", views.attendance_view)


# ---------- talent / ATS ----------------------------------------------------

@rt("/talent/jobs")
def get(session, status: str = "All"):
    return _guard(session, "jobs", lambda: ats.jobs_list(status))


@rt("/talent/jobs/{job_id}")
def get(session, job_id: int, stage: str = "All"):
    return _guard(session, "jobs", lambda: ats.job_detail(job_id, stage))


@rt("/talent/candidates")
def get(session, q: str = "", status: str = "All"):
    return _guard(session, "candidates", lambda: ats.candidates_list(q, status))


@rt("/talent/candidates/{cid}")
def get(session, cid: int):
    return _guard(session, "candidates", lambda: ats.candidate_detail(cid))


@rt("/talent/applications/{app_id}/stage")
def post(session, app_id: int, stage: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    a = db.one("SELECT job_id FROM applications WHERE id=?", (app_id,))
    if not a:
        return Response("No such application", status_code=404)
    talent.set_stage(app_id, stage, actor=_user(session))
    return ats.job_main(a["job_id"])


@rt("/talent/candidates/{cid}/apply")
def post(session, cid: int, job_id: int = 0):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    if job_id:
        talent.apply_to_job(cid, job_id, actor=_user(session))
        return P("Added to the requisition. Reload to see it listed.", cls="flag",
                 style="border-left-color:var(--accent);background:var(--accent-light);color:var(--accent-hover);")
    return P("Pick a requisition first.", cls="flag")


@rt("/talent/upload")
async def post(session, request):
    """Accept a CV, store it, and kick off extraction on a background thread."""
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    form = await request.form()
    upload = form.get("cv")
    if upload is None or not getattr(upload, "filename", ""):
        return P("Choose a CV file to upload.", cls="flag")
    if not cv_extract.supported(upload.filename):
        return P(f"{upload.filename} is not a supported format — use PDF, DOCX, TXT or MD.", cls="flag")

    data = await upload.read()
    if not data:
        return P("That file is empty.", cls="flag")

    job_id = int(form.get("job_id") or 0) or None
    res = cv_extract.ingest_cv(file_name=upload.filename, data=data, job_id=job_id,
                               source=form.get("source") or "Direct", actor=_user(session))
    cv_extract.run_extraction_async(res["run_id"], res["candidate_id"], res["document_id"])
    return ats.extraction_status(res["candidate_id"])


@rt("/talent/candidates/{cid}/extraction")
def get(session, cid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    return ats.extraction_status(cid)


@rt("/talent/prompts")
def get(session, key: str = "", saved: str = ""):
    return _guard(session, "prompts", lambda: ats.prompts_page(key or cv_extract.PROMPT_KEY, saved))


@rt("/talent/prompts")
def post(session, key: str = "", content: str = "", restore: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    key = key or cv_extract.PROMPT_KEY
    body = cv_extract.DEFAULT_EXTRACTION_PROMPT if restore else (content or "").strip()
    if not body:
        return RedirectResponse(f"/talent/prompts?key={key}", status_code=303)
    version = talent.save_prompt(key, body, title="CV extraction", updated_by=_user(session))
    note = f"Saved as v{version}{' (restored the built-in default)' if restore else ''} — it takes effect on the next upload."
    return RedirectResponse(f"/talent/prompts?key={key}&saved={quote(note)}", status_code=303)


@rt("/talent/prompts/{key}/{version}/activate")
def post(session, key: str, version: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    talent.activate_prompt(key, version)
    return ats.prompt_versions_fragment(key)


# ---------- interviews, offers, ranking, analytics --------------------------

@rt("/talent/applications/{app_id}/interview")
def post(session, app_id: int, kind: str = "Screen", interviewer_id: int = 0,
         scheduled_at: str = "", mode: str = "Video"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    talent.schedule_interview(app_id, interviewer_id=interviewer_id or None, kind=kind,
                              scheduled_at=scheduled_at.replace("T", " "), mode=mode,
                              actor=_user(session))
    return ats.interviews_panel(app_id)


@rt("/talent/interviews/{interview_id}")
def get(session, interview_id: int):
    return _guard(session, "candidates", lambda: ats.scorecard_page(interview_id))


@rt("/talent/interviews/{interview_id}")
async def post(session, interview_id: int, request):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    scores, comments = {}, {}
    for key, val in form.items():
        if key.startswith("score_") and val:
            try:
                scores[int(key[6:])] = float(val)
            except ValueError:
                continue
        elif key.startswith("comment_") and val:
            comments[int(key[8:])] = val
    talent.record_scorecard(interview_id, scores, comment_by=comments,
                            recommendation=form.get("recommendation", ""),
                            notes=form.get("notes", ""), actor=_user(session))
    iv = db.one("SELECT application_id FROM interviews WHERE id=?", (interview_id,))
    cand = db.one("SELECT candidate_id FROM applications WHERE id=?",
                  (iv["application_id"],)) if iv else None
    return RedirectResponse(f"/talent/candidates/{cand['candidate_id']}" if cand
                            else "/talent/candidates", status_code=303)


@rt("/talent/jobs/{job_id}/calibration")
def get(session, job_id: int):
    return _guard(session, "jobs", lambda: ats.calibration_page(job_id))


@rt("/talent/jobs/{job_id}/rank")
def post(session, job_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    ranking.rank_job(job_id, actor=_user(session))
    return ats.ranking_panel(job_id)


@rt("/talent/applications/{app_id}/offer")
def post(session, app_id: int, salary: float = 0, start_date: str = "", expires_on: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    oid = talent.draft_offer(app_id, salary=salary, start_date=start_date,
                             expires_on=expires_on, actor=_user(session))
    letter = ranking.draft_letter(oid)
    with db.cursor() as conn:
        conn.execute("UPDATE offers SET letter=? WHERE id=?", (letter, oid))
    return RedirectResponse(f"/talent/offers/{oid}", status_code=303)


@rt("/talent/offers")
def get(session, status: str = "All"):
    return _guard(session, "offers", lambda: ats.offers_page(status))


@rt("/talent/offers/{offer_id}")
def get(session, offer_id: int):
    return _guard(session, "offers", lambda: ats.offer_detail(offer_id))


@rt("/talent/offers/{offer_id}/status")
def post(session, offer_id: int, status: str = "", reason: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    talent.set_offer_status(offer_id, status, actor=_user(session), reason=reason)
    return ats.offers_table()


@rt("/talent/analytics")
def get(session):
    return _guard(session, "talent-analytics", ats.analytics_page)


# ---------- performance -----------------------------------------------------

@rt("/performance/goals")
def get(session, period: str = "All", status: str = "All", owner_type: str = "All"):
    return _guard(session, "goals", lambda: performance.goals_page(period, status, owner_type))


@rt("/performance/goals")
def post(session, title: str = "", owner_type: str = "employee", owner: str = "0",
         parent_goal_id: int = 0, metric: str = "", target: float = 0, period: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    owner_id = None
    if owner and owner[0] in "ed" and owner[1:].isdigit():
        owner_id = int(owner[1:])
        owner_type = "employee" if owner[0] == "e" else "department"
    elif owner_type == "company":
        owner_id = None
    if title.strip():
        people.create_goal(title=title.strip(), owner_type=owner_type, owner_id=owner_id,
                           parent_goal_id=parent_goal_id or None, metric=metric, target=target,
                           period=period, actor=_user(session))
    return RedirectResponse(f"/performance/goals?period={quote(period)}", status_code=303)


@rt("/performance/goals/{goal_id}")
def get(session, goal_id: int):
    return _guard(session, "goals", lambda: performance.goal_detail(goal_id))


@rt("/performance/goals/{goal_id}/checkin")
def post(session, goal_id: int, value: float = 0, status: str = "", note: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.checkin(goal_id, value=value, status=status, note=note, actor=_user(session))
    return performance.goal_body(goal_id)


@rt("/performance/alignment")
def get(session, period: str = "All"):
    return _guard(session, "goals", lambda: performance.alignment_page(period))


@rt("/performance/feedback")
def get(session, kind: str = "All"):
    return _guard(session, "feedback", lambda: performance.feedback_page(kind))


@rt("/performance/feedback")
def post(session, to_employee_id: int = 0, from_employee_id: int = 0, kind: str = "Praise",
         competency_id: int = 0, visibility: str = "Team", body: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    if to_employee_id and body.strip():
        people.give_feedback(from_employee_id=from_employee_id or None,
                             to_employee_id=to_employee_id, body=body.strip(), kind=kind,
                             competency_id=competency_id or None, visibility=visibility,
                             actor=_user(session))
    return performance.feed_list()


@rt("/performance/reviews")
def get(session):
    return _guard(session, "reviews", performance.reviews_page)


@rt("/performance/reviews")
def post(session, name: str = "", period_start: str = "", period_end: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if name.strip():
        people.create_cycle(name=name.strip(), period_start=period_start,
                            period_end=period_end, actor=_user(session))
    return RedirectResponse("/performance/reviews", status_code=303)


@rt("/performance/reviews/{cycle_id}")
def get(session, cycle_id: int, status: str = "All"):
    return _guard(session, "reviews", lambda: performance.cycle_detail(cycle_id, status))


@rt("/performance/reviews/{cycle_id}/status")
def post(session, cycle_id: int, status: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.set_cycle_status(cycle_id, status, actor=_user(session))
    return performance.cycles_fragment()


@rt("/performance/reviews/{cycle_id}/{review_id}")
def get(session, cycle_id: int, review_id: int):
    return _guard(session, "reviews", lambda: performance.review_form(cycle_id, review_id))


@rt("/performance/reviews/{cycle_id}/{review_id}")
async def post(session, cycle_id: int, review_id: int, request):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    ratings = {k[5:]: v for k, v in form.items() if k.startswith("comp_") and v}
    scores = [float(v) for v in ratings.values() if str(v).replace(".", "").isdigit()]
    people.submit_review(review_id, overall=sum(scores) / len(scores) if scores else 0,
                         narrative=form.get("narrative", ""), ratings=ratings,
                         actor=_user(session))
    return RedirectResponse(f"/performance/reviews/{cycle_id}", status_code=303)


@rt("/performance/signals")
def get(session, dept: str = "All"):
    return _guard(session, "signals", lambda: performance.signals_page(dept))


# ---------- lifecycle -------------------------------------------------------

@rt("/lifecycle/onboarding")
def get(session):
    return _guard(session, "onboarding", lifecycle.onboarding_page)


@rt("/lifecycle/onboarding/{employee_id}")
def get(session, employee_id: int):
    return _guard(session, "onboarding", lambda: lifecycle.onboarding_detail(employee_id))


@rt("/lifecycle/onboarding/task/{task_id}")
def post(session, task_id: int, status: str = "Done"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    eid = people.set_task_status(task_id, status, actor=_user(session))
    return lifecycle.checklist(eid) if eid else Response("Not found", status_code=404)


@rt("/lifecycle/changes")
def get(session, status: str = "All"):
    return _guard(session, "changes", lambda: lifecycle.changes_page(status))


@rt("/lifecycle/changes")
def post(session, employee_id: int = 0, change_type: str = "Role change",
         effective_date: str = "", designation: str = "", dept_id: int = 0,
         base_salary: float = 0):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    to_values = {}
    if designation.strip():
        to_values["designation"] = designation.strip()
    if dept_id:
        to_values["dept_id"] = dept_id
    if base_salary:
        to_values["base_salary"] = base_salary
    if employee_id and to_values:
        people.propose_change(employee_id, change_type=change_type,
                              effective_date=effective_date, to_values=to_values,
                              actor=_user(session))
    return RedirectResponse("/lifecycle/changes", status_code=303)


@rt("/lifecycle/changes/{change_id}/approve")
def post(session, change_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.apply_change(change_id, actor=_user(session))
    return lifecycle.changes_table()


@rt("/lifecycle/changes/{change_id}/reject")
def post(session, change_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.reject_change(change_id, actor=_user(session))
    return lifecycle.changes_table()


@rt("/lifecycle/separations")
def get(session, status: str = "All"):
    return _guard(session, "separations", lambda: lifecycle.separations_page(status))


@rt("/lifecycle/separations")
def post(session, employee_id: int = 0, kind: str = "Resignation", notice_date: str = "",
         last_day: str = "", reason: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if employee_id:
        people.start_separation(employee_id, kind=kind, notice_date=notice_date,
                                last_day=last_day, reason=reason, actor=_user(session))
    return RedirectResponse("/lifecycle/separations", status_code=303)


@rt("/lifecycle/separations/{sep_id}")
def get(session, sep_id: int):
    return _guard(session, "separations", lambda: lifecycle.separation_detail(sep_id))


@rt("/lifecycle/separations/{sep_id}/task/{index}")
def post(session, sep_id: int, index: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.toggle_exit_task(sep_id, index, actor=_user(session))
    return lifecycle.exit_checklist(sep_id)


@rt("/lifecycle/separations/{sep_id}/exit")
def post(session, sep_id: int, notes: str = "", sentiment: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    people.record_exit_interview(sep_id, notes=notes, sentiment=sentiment, actor=_user(session))
    return RedirectResponse(f"/lifecycle/separations/{sep_id}", status_code=303)


@rt("/lifecycle/alumni")
def get(session):
    return _guard(session, "separations", lifecycle.alumni_page)


@rt("/lifecycle/cases")
def get(session, status: str = "All"):
    return _guard(session, "cases", lambda: lifecycle.cases_page(status))


@rt("/lifecycle/cases")
def post(session, employee_id: int = 0, kind: str = "Other", severity: str = "Normal",
         visibility: str = "HR only", summary: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if summary.strip():
        people.open_case(employee_id=employee_id or None, kind=kind, summary=summary.strip(),
                         severity=severity, visibility=visibility, actor=_user(session))
    return RedirectResponse("/lifecycle/cases", status_code=303)


@rt("/lifecycle/cases/{case_id}/status")
def post(session, case_id: int, status: str = "", resolution: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.set_case_status(case_id, status, resolution=resolution, actor=_user(session))
    return lifecycle.cases_table()


@rt("/lifecycle/org")
def get(session, dept_id: int = 0, delta: int = 0):
    return _guard(session, "org", lambda: lifecycle.org_page(dept_id, delta))


# ---------- settings --------------------------------------------------------

@rt("/settings/integrations")
def get(session, saved: str = ""):
    return _guard(session, "integrations", lambda: settings.integrations_page(saved))


@rt("/settings/integrations/{provider}")
def get(session, provider: str, note: str = ""):
    return _guard(session, "integrations", lambda: settings.integration_detail(provider, note))


@rt("/settings/integrations/{provider}")
def post(session, provider: str, api_key: str = "", api_secret: str = "",
         account_ref: str = "", auto_sync: str = "", test: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    integrations.save(provider, api_key=api_key.strip(), api_secret=api_secret.strip(),
                      account_ref=account_ref.strip(), auto_sync=bool(auto_sync),
                      actor=_user(session))
    note = "Credentials saved."
    if test:
        note = integrations.test_connection(provider, actor=_user(session))["note"]
    return RedirectResponse(f"/settings/integrations/{provider}?note={quote(note)}",
                            status_code=303)


@rt("/settings/integrations/{provider}/test")
def post(session, provider: str):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    integrations.test_connection(provider, actor=_user(session))
    return settings.integrations_grid()


@rt("/settings/integrations/{provider}/sync")
def post(session, provider: str):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    integrations.sync(provider, actor=_user(session))
    return settings.integrations_grid()


@rt("/settings/integrations/{provider}/disconnect")
def post(session, provider: str):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    integrations.disconnect(provider, actor=_user(session))
    return RedirectResponse(f"/settings/integrations/{provider}"
                            f"?note={quote('Disconnected. Stored credentials were erased.')}",
                            status_code=303)


@rt("/settings/roles")
def get(session, saved: str = ""):
    return _guard(session, "roles", lambda: settings.roles_page(saved))


@rt("/settings/roles")
def post(session, account_email: str = "", role: str = "employee", scope: str = "all",
         employee_id: int = 0):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if account_email.strip():
        with db.cursor() as conn:
            conn.execute("""INSERT INTO account_roles(account_email,role,scope,employee_id,created)
                            VALUES (?,?,?,?,datetime('now'))""",
                         (account_email.strip().lower(), role, scope, employee_id or None))
    return RedirectResponse(f"/settings/roles?saved={quote('Role assigned.')}", status_code=303)


@rt("/settings/roles/{role_id}/delete")
def post(session, role_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    with db.cursor() as conn:
        conn.execute("DELETE FROM account_roles WHERE id=?", (role_id,))
    return settings.roles_table()


@rt("/payroll")
def get(session, period: str = "latest"):
    return _guard(session, "payroll", lambda: views.payroll_list(period))


@rt("/payroll/{pid}")
def get(session, pid: int):
    return _guard(session, "payroll", lambda: views.payslip_detail(pid))


@rt("/ai")
def get(session):
    body = (views._title("AI Assistant", "Chat lives in the right rail. Ask in plain English or use slash-commands."),
            Div(NotStr(
                "<div class='card'><h3>What you can ask</h3><ul style='line-height:1.8;'>"
                "<li>“Who's on leave today?”</li><li>“Which department is biggest?”</li>"
                "<li>“How many leave requests are pending approval?”</li>"
                "<li>“What's the latest payroll total?”</li></ul>"
                "<p style='color:var(--text-mute)'>Slash-commands (no API key): "
                "<code>/headcount</code> <code>/leave</code> <code>/today</code> <code>/payroll</code></p></div>")))
    return _guard(session, "ai", body)


@rt("/healthz")
def healthz():
    """Unauthenticated build probe — confirms which version a deploy is running."""
    return JSONResponse({"status": "ok", "product": "FastHRM", **version.info(),
                         "migrations": db.scalar(
                             "SELECT COUNT(*) FROM schema_migrations") or 0})


@rt("/about")
def get(session):
    v = version.info()
    stamped = bool(v["commit"])
    rows = [("Version", f"v{v['version']}"),
            ("Commit", v["commit"] + (" (uncommitted changes)" if v["dirty"] else "")
             if v["commit"] else "unknown"),
            ("Branch", v["branch"] or "unknown"),
            ("Built", v["build_date"] or "unknown"),
            ("Environment", ENV_LABEL),
            ("Model provider", f"{os.getenv('MODEL_PROVIDER', 'xai')} · "
                               f"{os.getenv('MODEL_NAME', 'grok-4-1-fast-reasoning')}"),
            ("Database", db.DB_PATH),
            ("Migrations applied", str(db.scalar("SELECT COUNT(*) FROM schema_migrations") or 0))]
    applied = db.rows("SELECT * FROM schema_migrations ORDER BY version")
    body = (
        views._title("About this build", "What is running, and where it came from"),
        Div(NotStr("<div class='card'><div class='card-header'><h3>Build</h3></div>"
                   "<div class='kv'>"
                   + "".join(f"<span class='k'>{k}</span><span>{v_}</span>" for k, v_ in rows)
                   + "</div></div>")),
        None if stamped else Div(NotStr(
            "<p class='flag'>No build stamp and no git metadata available, so the exact "
            "commit cannot be confirmed. Deployed images should set "
            "<code>FASTHR_COMMIT</code> and <code>FASTHR_BUILD_DATE</code>.</p>")),
        Div(NotStr("<div class='card'><div class='card-header'><h3>Schema history</h3></div>"
                   "<table class='tbl'><thead><tr><th>Migration</th><th>Applied</th></tr></thead>"
                   "<tbody>"
                   + "".join(f"<tr><td>{m['version']}</td><td>{m['applied_at']}</td></tr>"
                             for m in applied)
                   + "</tbody></table></div>")),
        Div(NotStr("<p style='color:var(--text-mute);font-size:12.5px;'>"
                   "<code>/healthz</code> returns the same build details as JSON, without "
                   "requiring a login — use it to confirm what a deployment is running.</p>")),
    )
    return _guard(session, "about", tuple(b for b in body if b is not None))


@rt("/guide")
def get(session):
    body = (views._title("User Guide", "How to drive FastHRM"), Div(NotStr("""
<div class='card'><h3>Dashboard</h3><p>Headcount, attendance, on-leave-today and pending leave, with headcount by department.</p></div>
<div class='card'><h3>Employees & Departments</h3><p>Searchable directory filtered by department; each employee shows
leave balance, recent attendance, and payslips. Departments lists headcount, head and annual payroll.</p></div>
<div class='card'><h3>Leave & Attendance</h3><p>Leave requests by status, and today's attendance register with a per-status breakdown.</p></div>
<div class='card'><h3>Payroll</h3><p>Payslips per pay period with a full deductions breakdown on each payslip.</p></div>
<div class='card'><h3>AI Assistant</h3><p>The right rail chats over a live HR snapshot. Set <code>MODEL_PROVIDER</code> + a key in
<code>.env</code> for free-form chat; slash-commands always work.</p></div>""")))
    return _guard(session, "guide", body)


@rt("/chat/new")
def get(session):
    session["thread"] = uuid.uuid4().hex
    return P("Ask about headcount, leave or attendance — or use /headcount /leave /help.", cls="chat-empty-hint")


@rt("/chat/stream")
async def post(session, message: str = "", thread_id: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    message = (message or "").strip()
    if not message:
        return Response("No message", status_code=400)
    tid = thread_id or _thread(session)

    async def gen():
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "user", message))
        full = []
        async for chunk in ai.stream_chat(message):
            if chunk.startswith("data: "):
                try:
                    tok = json.loads(chunk[6:]).get("token")
                    if tok:
                        full.append(tok)
                except Exception:
                    pass
            yield chunk
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "assistant", "".join(full)))

    return StreamingResponse(gen(), media_type="text/event-stream")


def _ensure_db():
    """Migrate, then seed anything that is still empty.

    Emptiness is judged by row counts, not by whether the file exists: importing
    web.api constructs the SQLite backend, which creates the database before this
    runs, so a file-existence check would skip seeding on a fresh install.
    """
    applied = db.migrate()
    if applied:
        logger.info("Applied migrations: %s", ", ".join(applied))
    if not db.scalar("SELECT COUNT(*) FROM employees"):
        logger.info("No employees found — seeding synthetic HR data…")
        import seed
        seed.build()
    if not db.scalar("SELECT COUNT(*) FROM job_openings"):
        logger.info("No requisitions found — seeding synthetic talent pipeline…")
        import seed_talent
        seed_talent.build()
    if not db.scalar("SELECT COUNT(*) FROM goals"):
        logger.info("No performance data found — seeding goals, feedback and lifecycle…")
        import seed_platform
        seed_platform.build()
    cv_extract.ensure_default_prompt()
    ranking.ensure_prompts()


_ensure_db()


register_seo_routes(app)

if __name__ == "__main__":
    logger.info("FastHRM on http://localhost:%s  (login %s)", PORT, VALID_EMAIL)
    serve(port=PORT, reload=os.getenv("FASTHR_RELOAD", "0") == "1")
