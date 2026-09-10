"""Employee self-service portal renderers and small identity helpers."""
from __future__ import annotations

from datetime import timedelta
import hashlib
import hmac
import secrets

from fasthtml.common import *

import db
import people
import benefits
import learning


PORTAL_CSS = """
.me-shell{min-height:100vh;background:#f7f7f2;color:#17221c;font-family:var(--font-body,sans-serif)}
.me-top{display:flex;justify-content:space-between;align-items:center;padding:18px clamp(18px,5vw,64px);background:#17221c;color:#f7f7f2}
.me-brand{font-weight:800;letter-spacing:.4px}.me-brand i{color:#c7f36b;font-style:normal}.me-top a{color:#f7f7f2;text-decoration:none}
.me-nav{display:flex;gap:18px;flex-wrap:wrap;padding:14px clamp(18px,5vw,64px);background:#fff;border-bottom:1px solid #dfe5dc}
.me-nav a{color:#536058;text-decoration:none;font-size:13px}.me-nav a:hover,.me-nav a.active{color:#17221c;font-weight:700}
.me-main{max-width:1180px;margin:0 auto;padding:42px clamp(18px,5vw,64px) 70px}.me-title{display:flex;justify-content:space-between;gap:20px;align-items:end;margin-bottom:28px}.me-title h1{font-family:var(--font-display,sans-serif);font-size:clamp(30px,5vw,52px);margin:0}.me-title p{color:#68756c;margin:8px 0 0}.me-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.me-card{background:#fff;border:1px solid #dfe5dc;border-radius:14px;padding:20px;box-shadow:0 5px 16px rgba(23,34,28,.04)}.me-card h2,.me-card h3{margin:0 0 14px;font-family:var(--font-display,sans-serif)}.me-wide{grid-column:span 7}.me-half{grid-column:span 5}.me-third{grid-column:span 4}.me-full{grid-column:1/-1}.me-stat{font-size:30px;font-weight:750}.me-muted{color:#68756c;font-size:13px}.me-list{list-style:none;padding:0;margin:0}.me-list li{display:flex;justify-content:space-between;gap:12px;padding:11px 0;border-bottom:1px solid #edf0eb;font-size:13px}.me-list li:last-child{border-bottom:0}.me-pill{display:inline-block;border-radius:999px;padding:4px 9px;background:#edf5d9;color:#42561e;font-size:11px}.me-btn{display:inline-block;border:0;border-radius:999px;padding:10px 15px;background:#17221c;color:#f7f7f2;text-decoration:none;font-weight:700;cursor:pointer}.me-btn.lime{background:#c7f36b;color:#17221c}.me-form{display:grid;gap:10px}.me-form input,.me-form select,.me-form textarea{width:100%;box-sizing:border-box;border:1px solid #ccd6ca;border-radius:8px;padding:10px;font:inherit}.me-table{width:100%;border-collapse:collapse;font-size:13px}.me-table th,.me-table td{text-align:left;padding:10px 6px;border-bottom:1px solid #edf0eb}.me-table th:last-child,.me-table td:last-child{text-align:right}.me-login{max-width:430px;margin:12vh auto;padding:34px 22px}.me-error{color:#a7342d;font-size:13px}.me-empty{color:#68756c;font-size:13px;padding:8px 0}@media(max-width:760px){.me-wide,.me-half,.me-third{grid-column:1/-1}.me-title{display:block}.me-top{align-items:start}.me-nav{gap:12px}}
"""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return "pbkdf2_sha256$240000$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        algorithm, iterations, salt, expected = (encoded or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual.hex(), expected)
    except (TypeError, ValueError):
        return False


def authenticate(email: str, password: str):
    employee = db.one("SELECT * FROM employees WHERE lower(email)=? AND status!='Inactive'", ((email or "").strip().lower(),))
    return employee if employee and verify_password(password or "", employee.get("password_hash")) else None


def _name(employee):
    return f"{employee['first_name']} {employee['last_name']}".strip()


def _shell(active: str, employee, *content):
    links = [("home", "Home", "/me"), ("pay", "Pay", "/me/pay"), ("leave", "Leave", "/me/leave"),
             ("time", "Time", "/me/time"), ("expenses", "Expenses & travel", "/me/expenses"),
             ("onboarding", "Onboarding & goals", "/me/onboarding")]
    return (Title("FastHR · Employee portal"), Style(PORTAL_CSS),
            Div(Div(A("Fast HRM", href="/me", cls="me-brand"),
                    Div(Span(_name(employee), cls="me-muted"), A("Sign out", href="/me/logout"), style="display:flex;gap:16px;align-items:center"), cls="me-top"),
                Div(*[A(label, href=href, cls="active" if active == key else "") for key, label, href in links], cls="me-nav"),
                Main(*content, cls="me-main"), cls="me-shell"))


def login_page(error=""):
    return (Title("FastHR · Employee sign in"), Style(PORTAL_CSS),
            Div(Div(A("Fast HRM", href="/", cls="me-brand"), H1("Employee portal"),
                    P("Sign in to view your pay, time, leave and people tasks."),
                    P(error, cls="me-error") if error else None,
                    Form(Label("Work email"), Input(type="email", name="email", required=True, autocomplete="email"),
                         Label("Password"), Input(type="password", name="password", required=True, autocomplete="current-password"),
                         Button("Sign in", type="submit", cls="me-btn lime"), method="post", action="/me/login", cls="me-form"),
                    P(A("Admin sign in", href="/login"), cls="me-muted"), cls="me-card me-login"), cls="me-shell"))


def _card(title, body, cls="me-half"):
    return Div(H2(title), body, cls=f"me-card {cls}")


def _status(value):
    return Span(value or "—", cls="me-pill")


def dashboard(employee):
    eid = employee["id"]
    upcoming = db.roster(db.TODAY.isoformat(), (db.TODAY + timedelta(days=14)).isoformat(), eid)
    balances = db.leave_balance(eid)
    slips = db.payslips_for(eid)
    claims = db.rows("SELECT c.*, cat.name category FROM expense_claims c JOIN expense_categories cat ON cat.id=c.category_id WHERE c.employee_id=? AND c.status IN ('Draft','Submitted','Approved') ORDER BY c.claim_date DESC LIMIT 5", (eid,))
    travel = db.rows("SELECT * FROM travel_requests WHERE employee_id=? AND status IN ('Submitted','Approved','Returned') ORDER BY from_date DESC LIMIT 5", (eid,))
    tasks = people.onboarding_tasks(eid)
    goals = people.goals(owner_type="employee", owner_id=eid, status="All")
    open_punch = db.one("SELECT id FROM clock_punches WHERE employee_id=? AND punch_type='In' AND NOT EXISTS (SELECT 1 FROM clock_punches o WHERE o.employee_id=clock_punches.employee_id AND o.punch_type='Out' AND o.punched_at>clock_punches.punched_at) ORDER BY punched_at DESC LIMIT 1", (eid,))
    today_assignment = next((s for s in db.roster(db.TODAY.isoformat(), db.TODAY.isoformat(), eid)), None)
    clock = Form(Button("Clock out" if open_punch else "Clock in", type="submit", cls="me-btn lime"), method="post", action="/me/time/clock-out" if open_punch else "/me/time/clock-in")
    shift = P(f"{upcoming[0]['shift_date']} · {upcoming[0]['shift_name']} · {upcoming[0]['start_time']}–{upcoming[0]['end_time']}" if upcoming else "No upcoming shifts.", cls="me-muted")
    return _shell("home", employee, Div(Div(H1(f"Tere, {employee['first_name']}"), P(f"{employee.get('designation') or 'Employee'} · {employee.get('dept') or ''}")), clock, cls="me-title"),
                  Div(_card("Next shift", shift, "me-wide"), _card("Today", P("Punched in" if open_punch else "Not clocked in", cls="me-stat") , "me-third"),
                      _card("Leave", Ul(*[Li(Span(b["leave_type"]), Strong(f"{b['remaining']:g} days")) for b in balances[:4]] or [Li("No balances yet")], cls="me-list"), "me-third"),
                      _card("Latest payslip", P(f"{slips[0]['period']} · {slips[0]['net']:,.2f} EUR" if slips else "No payslips yet", cls="me-stat"), "me-third"),
                      _card("Open expenses", P(f"{len(claims)} claim(s) awaiting action", cls="me-stat"), "me-third"),
                      _card("Travel", P(f"{len(travel)} request(s) in progress", cls="me-stat"), "me-third"),
                      _card("Onboarding", P(f"{sum(t['status'] == 'Done' for t in tasks)} / {len(tasks)} tasks complete", cls="me-stat"), "me-third"),
                      _card("Active goals", P(f"{sum(g['status'] not in ('Complete','Cancelled') for g in goals)} goal(s)", cls="me-stat"), "me-third"), cls="me-grid"))


def pay_page(employee):
    slips = db.payslips_for(employee["id"])
    body = Table(Tr(Th("Period"), Th("Status"), Th("Net"), Th("")), *[Tr(Td(p["period"]), Td(_status(p["status"])), Td(f"{p['net']:,.2f} EUR"), Td(A("View", href=f"/me/pay/{p['id']}", cls="me-btn"))) for p in slips] or [Tr(Td("No payslips yet.", colspan="4"))], cls="me-table")
    latest = slips[0] if slips else None
    latest_lines = Table(Tr(Th("Item / Rida"), Th("Amount")),
                         *[Tr(Td(f"{line['kind']} · {line['label']}"),
                              Td(f"{line['amount']:,.2f} EUR"))
                           for line in db.payslip_lines(latest["id"])]
                         if latest else [Tr(Td("No payslip lines yet. / Palgalehe ridu veel pole.", colspan="2"))],
                         cls="me-table")
    active = [row for row in benefits.active_enrolments(db.TODAY)
              if row["employee_id"] == employee["id"]]
    benefit_body = Table(Tr(Th("Soodustus / Benefit"), Th("Tööandja kulu / Employer contribution")),
                         *[Tr(Td(row["name"]), Td(f"{row['employer_contribution']:,.2f} EUR"))
                           for row in active] or [Tr(Td("Aktiivseid soodustusi pole / No active benefits.", colspan="2"))],
                         cls="me-table")
    return _shell("pay", employee, Div(H1("My pay"), P("Payslips and pay history", cls="me-muted"), cls="me-title"),
                  _card("Payslips", body, "me-full"),
                  _card("Latest payslip breakdown / Viimase palgalehe jaotus", latest_lines, "me-full"),
                  _card("Minu soodustused / My benefits", benefit_body, "me-full"))


def payslip_page(employee, pid):
    p = db.one("SELECT * FROM payslips WHERE id=? AND employee_id=?", (pid, employee["id"]))
    if not p:
        return _shell("pay", employee, H1("Payslip not found"), P("This payslip is not available."))
    lines = db.payslip_lines(pid)
    body = Table(Tr(Th("Item"), Th("Amount")), *[Tr(Td(line["label"]), Td(f"{line['amount']:,.2f} EUR")) for line in lines], Tr(Td(Strong("Net pay")), Td(Strong(f"{p['net']:,.2f} EUR"))), cls="me-table")
    return _shell("pay", employee, Div(H1(f"Payslip · {p['period']}"), A("← My pay", href="/me/pay", cls="me-btn"), cls="me-title"), _card("Pay breakdown", body, "me-half"))


def leave_page(employee):
    eid = employee["id"]
    balances = db.leave_balance(eid)
    requests = db.rows("SELECT * FROM leave_requests WHERE employee_id=? ORDER BY applied_on DESC, id DESC", (eid,))
    body = Table(Tr(Th("Leave type"), Th("Remaining")), *[Tr(Td(b["leave_type"]), Td(f"{b['remaining']:g} days")) for b in balances], cls="me-table")
    reqs = Table(Tr(Th("Dates"), Th("Type"), Th("Status")), *[Tr(Td(f"{r['from_date']} → {r['to_date']}"), Td(r["leave_type"]), Td(_status(r["status"]))) for r in requests] or [Tr(Td("No requests yet.", colspan="3"))], cls="me-table")
    form = Form(Select(*[Option(t, value=t) for t in db.LEAVE_TYPES], name="leave_type"), Input(type="date", name="from_date", required=True), Input(type="date", name="to_date", required=True), Input(name="reason", placeholder="Reason"), Button("Apply for leave", type="submit", cls="me-btn lime"), method="post", action="/me/leave/apply", cls="me-form")
    return _shell("leave", employee, Div(H1("My leave"), P("Balances and requests", cls="me-muted"), cls="me-title"), _card("Balances", body, "me-half"), _card("Apply", form, "me-half"), _card("My requests", reqs, "me-full"))


def time_page(employee):
    eid = employee["id"]
    shifts = db.roster(db.TODAY.isoformat(), (db.TODAY + timedelta(days=30)).isoformat(), eid)
    punches = db.punches_for(eid, (db.TODAY - timedelta(days=30)).isoformat(), db.TODAY.isoformat())
    rows = Table(Tr(Th("Shift"), Th("Date"), Th("Status")), *[Tr(Td(f"{s['shift_name']} · {s['start_time']}–{s['end_time']}"), Td(s["shift_date"]), Td(_status(s["status"]))) for s in shifts] or [Tr(Td("No scheduled shifts.", colspan="3"))], cls="me-table")
    punch_rows = Table(Tr(Th("When"), Th("Type"), Th("Source")), *[Tr(Td(p["punched_at"]), Td(p["punch_type"]), Td(p["source"])) for p in punches] or [Tr(Td("No punches in the last 30 days.", colspan="3"))], cls="me-table")
    open_punch = db.one("SELECT id FROM clock_punches WHERE employee_id=? AND punch_type='In' AND NOT EXISTS (SELECT 1 FROM clock_punches o WHERE o.employee_id=clock_punches.employee_id AND o.punch_type='Out' AND o.punched_at>clock_punches.punched_at) ORDER BY punched_at DESC LIMIT 1", (eid,))
    action = Form(Button("Clock out" if open_punch else "Clock in", type="submit", cls="me-btn lime"), method="post", action="/me/time/clock-out" if open_punch else "/me/time/clock-in")
    return _shell("time", employee, Div(H1("My time"), action, cls="me-title"), _card("Upcoming roster", rows, "me-full"), _card("Punch history", punch_rows, "me-full"))


def expenses_page(employee):
    eid = employee["id"]
    claims = db.rows("SELECT c.*, cat.name category FROM expense_claims c JOIN expense_categories cat ON cat.id=c.category_id WHERE c.employee_id=? ORDER BY c.claim_date DESC", (eid,))
    advances = db.rows("SELECT * FROM employee_advances WHERE employee_id=? ORDER BY requested_at DESC", (eid,))
    travel = db.rows("SELECT * FROM travel_requests WHERE employee_id=? ORDER BY from_date DESC", (eid,))
    cats = db.expense_categories()
    claim_table = Table(Tr(Th("Date"), Th("Category"), Th("Amount"), Th("Status")), *[Tr(Td(c["claim_date"]), Td(c["category"]), Td(f"{c['amount']:,.2f} {c['currency']}"), Td(_status(c["status"]))) for c in claims] or [Tr(Td("No claims yet.", colspan="4"))], cls="me-table")
    travel_table = Table(Tr(Th("Trip"), Th("Dates"), Th("Status")), *[Tr(Td(f"{t['destination']} · {t['purpose']}"), Td(f"{t['from_date']} → {t['to_date']}"), Td(_status(t["status"]))) for t in travel] or [Tr(Td("No travel requests yet.", colspan="3"))], cls="me-table")
    form = Form(Select(*[Option(c["name"], value=str(c["id"])) for c in cats], name="category_id"), Input(type="date", name="claim_date", value=db.TODAY.isoformat()), Input(type="number", name="amount", min="0", step="0.01", required=True), Input(name="description", placeholder="What was this for?", required=True), Button("Submit claim", type="submit", cls="me-btn lime"), method="post", action="/me/expenses/claim", cls="me-form")
    travel_form = Form(Input(name="destination", placeholder="Destination", required=True), Input(name="purpose", placeholder="Purpose", required=True), Input(type="date", name="from_date", required=True), Input(type="date", name="to_date", required=True), Input(type="number", name="estimated_cost", min="0", step="0.01", required=True), Button("Request travel", type="submit", cls="me-btn lime"), method="post", action="/me/expenses/travel", cls="me-form")
    return _shell("expenses", employee, Div(H1("Expenses & travel"), P("Submit and track your requests", cls="me-muted"), cls="me-title"), _card("My claims", claim_table, "me-full"), _card("New claim", form, "me-half"), _card("Travel request", travel_form, "me-half"), _card("My travel", travel_table, "me-full"), _card("Advances", P(f"{len(advances)} advance(s) on record", cls="me-stat"), "me-half"))


def onboarding_page(employee):
    tasks = people.onboarding_tasks(employee["id"])
    goals = people.goals(owner_type="employee", owner_id=employee["id"], status="All")
    task_list = Ul(*[Li(Span(t["title"]), _status(t["status"])) for t in tasks] or [Li("No onboarding tasks yet.")], cls="me-list")
    goal_list = Ul(*[Li(Span(g["title"]), _status(g["status"])) for g in goals] or [Li("No active goals yet.")], cls="me-list")
    plans = learning.plans_for(employee["id"])
    certifications = learning.list_for(employee["id"])
    learning_list = Ul(*[Li(Span(p["course_name"]), Span(f"{p['progress']}% · {p['status']}", cls="me-pill")) for p in plans] or [Li("Arengukava puudub / No learning plans yet.")], cls="me-list")
    cert_list = Ul(*[Li(Span(c["name"]), Span(c["expires_on"] or "—", cls="me-pill")) for c in certifications] or [Li("Sertifikaate pole / No certifications yet.")], cls="me-list")
    return _shell("onboarding", employee, Div(H1("Onboarding & goals"), P("Your progress at FastHRM", cls="me-muted"), cls="me-title"), _card("Onboarding tasks", task_list, "me-half"), _card("Goals", goal_list, "me-half"), _card("Minu arengukava / My learning", learning_list, "me-half"), _card("Sertifikaadid / Certifications", cert_list, "me-half"))
