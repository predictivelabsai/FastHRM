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

from dotenv import load_dotenv
load_dotenv()

from fasthtml.common import (
    fast_app, serve, Div, H1, P, A, Form, Input, Button, NotStr,
    RedirectResponse, Script, Style, Link, Title,
)
from starlette.responses import StreamingResponse, Response

import db
from web.layout import page, LAYOUT_CSS
from web import views, ai

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("fasthr")

VALID_EMAIL = os.getenv("FASTHR_ADMIN_EMAIL", "admin@fasthr.example")
VALID_PASSWORD = os.getenv("FASTHR_ADMIN_PASSWORD", "FastHR2026$")
ENV_LABEL = os.getenv("FASTHR_ENV_LABEL", "FastHR")
SECRET = os.getenv("FASTHR_SECRET", secrets.token_hex(32))
PORT = int(os.getenv("FASTHR_PORT", "5010"))

app, rt = fast_app(live=False, pico=False, secret_key=SECRET, hdrs=[Style(LAYOUT_CSS)])


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


@rt("/logout")
def get(session):
    session.pop("user", None)
    return RedirectResponse("/login", status_code=303)


@rt("/")
def get(session):
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


@rt("/attendance")
def get(session):
    return _guard(session, "attendance", views.attendance_view)


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
    if not db.db_exists():
        logger.info("No database found — seeding synthetic HR data…")
        import seed
        seed.build()


_ensure_db()

if __name__ == "__main__":
    logger.info("FastHR on http://localhost:%s  (login %s)", PORT, VALID_EMAIL)
    serve(port=PORT, reload=os.getenv("FASTHR_RELOAD", "0") == "1")
