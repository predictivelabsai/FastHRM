"""FastHR — an open-source HR system built with FastHTML.

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
from web.layout import page, LAYOUT_CSS
from web import views, ai, ats, cv_extract
from web.landing import landing_page
from web.seo import register_seo_routes
from web.developer import developer_page
from web import account_auth, google_auth
from web.api import api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("fasthr")

VALID_EMAIL = os.getenv("FASTHR_ADMIN_EMAIL", "admin@fasthr.example")
VALID_PASSWORD = os.getenv("FASTHR_ADMIN_PASSWORD", "FastHR2026$")
ENV_LABEL = os.getenv("FASTHR_ENV_LABEL", "FastHR")
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
    return Title("FastHR — Sign in"), Style(LAYOUT_CSS), Div(
        Form(H1("FastHR"), P("Sign in to your HR workspace"),
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


@rt("/guide")
def get(session):
    body = (views._title("User Guide", "How to drive FastHR"), Div(NotStr("""
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
    cv_extract.ensure_default_prompt()


_ensure_db()


register_seo_routes(app)

if __name__ == "__main__":
    logger.info("FastHR on http://localhost:%s  (login %s)", PORT, VALID_EMAIL)
    serve(port=PORT, reload=os.getenv("FASTHR_RELOAD", "0") == "1")
