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
from web.i18n import current_lang, current_path, t_app


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
    lang = current_lang()
    path = current_path()
    links = [("home", "portal_home", "/me"), ("pay", "portal_pay", "/me/pay"),
             ("leave", "portal_leave", "/me/leave"), ("time", "portal_time", "/me/time"),
             ("expenses", "portal_expenses", "/me/expenses"),
             ("onboarding", "portal_onboarding", "/me/onboarding")]
    switcher = Div(A("ET", href=f"{path}?lang=et", cls="active" if lang == "et" else ""),
                   A("EN", href=f"{path}?lang=en", cls="active" if lang == "en" else ""),
                   style="display:flex;gap:8px;font-size:11px;font-weight:700")
    return Html(Head(Title(_copy("portal_title")), Style(PORTAL_CSS)),
                Body(Div(Div(A("FastHR", href="/me", cls="me-brand"),
                             Div(Span(_name(employee), cls="me-muted"), switcher,
                                 A(t_app(lang, "portal_logout"), href="/me/logout"),
                                 style="display:flex;gap:16px;align-items:center"), cls="me-top"),
                         Div(*[A(t_app(lang, label), href=href, cls="active" if active == key else "") for key, label, href in links], cls="me-nav"),
                         Main(*content, cls="me-main"), cls="me-shell")),
                lang=lang)


def login_page(error=""):
    lang = current_lang()
    return (Title(_copy("portal_title")), Style(PORTAL_CSS),
            Main(Div(A("FastHR", href="/", cls="me-brand"), H1(t_app(lang, "portal_login_title")),
                     P(t_app(lang, "portal_login_intro")),
                     P(error, cls="me-error") if error else None,
                     Form(Label(t_app(lang, "portal_work_email")), Input(type="email", name="email", required=True, autocomplete="email", aria_label=t_app(lang, "portal_work_email")),
                          Label(t_app(lang, "portal_password")), Input(type="password", name="password", required=True, autocomplete="current-password", aria_label=t_app(lang, "portal_password")),
                          Button(t_app(lang, "portal_sign_in"), type="submit", cls="me-btn lime"), method="post", action="/me/login", cls="me-form"),
                     P(A(t_app(lang, "portal_admin_sign_in"), href="/login"), cls="me-muted"), cls="me-card me-login"), cls="me-shell"))


def _card(title, body, cls="me-half"):
    return Div(H2(title), body, cls=f"me-card {cls}")


def _status(value):
    return Span(value or _copy("portal_missing"), cls="me-pill")


def _count_text(count, singular, plural):
    noun = singular if count == 1 else plural
    return f"{count} {noun}"


def _num(count, et_single, et_plural, en_single, en_plural):
    lang = current_lang()
    if lang == "et":
        return f"{count} {et_single if count == 1 else et_plural}"
    return f"{count} {en_single if count == 1 else en_plural}"


def _copy(key, **values):
    return t_app(current_lang(), key).format(**values)


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
    clock = Form(Button(_copy("portal_clock_out" if open_punch else "portal_clock_in"), type="submit", cls="me-btn lime"), method="post", action="/me/time/clock-out" if open_punch else "/me/time/clock-in")
    shift = P(f"{upcoming[0]['shift_date']} · {upcoming[0]['shift_name']} · {upcoming[0]['start_time']}–{upcoming[0]['end_time']}" if upcoming else _copy("portal_no_upcoming_shifts"), cls="me-muted")
    active_goals = sum(g['status'] not in ('Complete', 'Cancelled') for g in goals)
    return _shell("home", employee, Div(Div(H1(_copy("portal_hello", name=employee['first_name'])), P(f"{employee.get('designation') or _copy('portal_employee')} · {employee.get('dept') or ''}")), clock, cls="me-title"),
                  Div(_card(_copy("portal_next_shift"), shift, "me-wide"), _card(_copy("portal_today"), P(_copy("portal_clocked_in" if open_punch else "portal_not_clocked_in"), cls="me-stat"), "me-third"),
                      _card(_copy("portal_leave_card"), Ul(*[Li(Span(b["leave_type"]), Strong(f"{b['remaining']:g} {_copy('portal_days')}")) for b in balances[:4]] or [Li(_copy("portal_no_leave_balances"))], cls="me-list"), "me-third"),
                      _card(_copy("portal_latest_payslip"), P(f"{slips[0]['period']} · {slips[0]['net']:,.2f} EUR" if slips else _copy("portal_no_payslips"), cls="me-stat"), "me-third"),
                      _card(_copy("portal_open_expenses"), P(f"{_num(len(claims), 'kulutaotlus', 'kulutaotlust', 'expense claim', 'expense claims')} {_copy('portal_waiting_action')}", cls="me-stat"), "me-third"),
                      _card(_copy("portal_travel_requests"), P(f"{_num(len(travel), 'taotlus', 'taotlust', 'request', 'requests')} {_copy('portal_in_progress')}", cls="me-stat"), "me-third"),
                      _card(_copy("portal_onboarding_card"), P(f"{sum(t['status'] == 'Done' for t in tasks)} / {len(tasks)} {_copy('portal_tasks_done')}", cls="me-stat"), "me-third"),
                      _card(_copy("portal_active_goals"), P(_num(active_goals, 'eesmärk', 'eesmärki', 'active goal', 'active goals'), cls="me-stat"), "me-third"), cls="me-grid"))


def pay_page(employee):
    slips = db.payslips_for(employee["id"])
    body = Table(Tr(Th(_copy("portal_period")), Th(_copy("portal_status")), Th(_copy("portal_net_amount")), Th("")), *[Tr(Td(p["period"]), Td(_status(p["status"])), Td(f"{p['net']:,.2f} EUR"), Td(A(_copy("portal_view"), href=f"/me/pay/{p['id']}", cls="me-btn"))) for p in slips] or [Tr(Td(_copy("portal_no_payslips_period"), colspan="4"))], cls="me-table")
    latest = slips[0] if slips else None
    latest_lines = Table(Tr(Th(_copy("portal_line")), Th(_copy("portal_amount"))),
                         *[Tr(Td(f"{line['kind']} · {line['label']}"),
                              Td(f"{line['amount']:,.2f} EUR"))
                           for line in db.payslip_lines(latest["id"])]
                         if latest else [Tr(Td(_copy("portal_no_payslip_lines"), colspan="2"))],
                         cls="me-table")
    active = [row for row in benefits.active_enrolments(db.TODAY)
              if row["employee_id"] == employee["id"]]
    benefit_body = Table(Tr(Th(_copy("portal_benefit")), Th(_copy("portal_employer_cost"))),
                         *[Tr(Td(row["name"]), Td(f"{row['employer_contribution']:,.2f} EUR"))
                            for row in active] or [Tr(Td(_copy("portal_no_active_benefits"), colspan="2"))],
                         cls="me-table")
    return _shell("pay", employee, Div(H1(_copy("portal_pay_title")), P(_copy("portal_pay_subtitle"), cls="me-muted"), cls="me-title"),
                  _card(_copy("portal_payslips"), body, "me-full"), _card(_copy("portal_latest_payslip_breakdown"), latest_lines, "me-full"),
                  _card(_copy("portal_my_benefits"), benefit_body, "me-full"))


def payslip_page(employee, pid):
    p = db.one("SELECT * FROM payslips WHERE id=? AND employee_id=?", (pid, employee["id"]))
    if not p:
        return _shell("pay", employee, H1(_copy("portal_payslip_not_found")), P(_copy("portal_payslip_unavailable")))
    lines = db.payslip_lines(pid)
    body = Table(Tr(Th(_copy("portal_line")), Th(_copy("portal_amount"))), *[Tr(Td(line["label"]), Td(f"{line['amount']:,.2f} EUR")) for line in lines], Tr(Td(Strong(_copy("portal_net"))), Td(Strong(f"{p['net']:,.2f} EUR"))), cls="me-table")
    return _shell("pay", employee, Div(H1(f"{_copy('portal_payslips')} · {p['period']}"), A(_copy("portal_back_pay"), href="/me/pay", cls="me-btn"), cls="me-title"), _card(_copy("portal_payslip_breakdown"), body, "me-half"))


def leave_page(employee):
    eid = employee["id"]
    balances = db.leave_balance(eid)
    requests = db.rows("SELECT * FROM leave_requests WHERE employee_id=? ORDER BY applied_on DESC, id DESC", (eid,))
    body = Table(Tr(Th(_copy("portal_leave_type")), Th(_copy("portal_balance"))), *[Tr(Td(b["leave_type"]), Td(f"{b['remaining']:g} {_copy('portal_days')}")) for b in balances], cls="me-table")
    reqs = Table(Tr(Th(_copy("portal_dates")), Th(_copy("portal_type")), Th(_copy("portal_status"))), *[Tr(Td(f"{r['from_date']} → {r['to_date']}"), Td(r["leave_type"]), Td(_status(r["status"]))) for r in requests] or [Tr(Td(_copy("portal_no_requests"), colspan="3"))], cls="me-table")
    form = Form(Select(*[Option(t, value=t) for t in db.LEAVE_TYPES], name="leave_type"), Input(type="date", name="from_date", required=True), Input(type="date", name="to_date", required=True), Input(name="reason", placeholder=_copy("portal_reason")), Button(_copy("portal_apply_leave"), type="submit", cls="me-btn lime"), method="post", action="/me/leave/apply", cls="me-form")
    return _shell("leave", employee, Div(H1(_copy("portal_leave_title")), P(_copy("portal_leave_subtitle"), cls="me-muted"), cls="me-title"), _card(_copy("portal_balances"), body, "me-half"), _card(_copy("portal_new_request"), form, "me-half"), _card(_copy("portal_my_requests"), reqs, "me-full"))


def time_page(employee):
    eid = employee["id"]
    shifts = db.roster(db.TODAY.isoformat(), (db.TODAY + timedelta(days=30)).isoformat(), eid)
    punches = db.punches_for(eid, (db.TODAY - timedelta(days=30)).isoformat(), db.TODAY.isoformat())
    rows = Table(Tr(Th(_copy("portal_shift")), Th(_copy("portal_date")), Th(_copy("portal_status"))), *[Tr(Td(f"{s['shift_name']} · {s['start_time']}–{s['end_time']}"), Td(s["shift_date"]), Td(_status(s["status"]))) for s in shifts] or [Tr(Td(_copy("portal_no_scheduled_shifts"), colspan="3"))], cls="me-table")
    punch_rows = Table(Tr(Th(_copy("portal_time")), Th(_copy("portal_kind")), Th(_copy("portal_source"))), *[Tr(Td(p["punched_at"]), Td(p["punch_type"]), Td(p["source"])) for p in punches] or [Tr(Td(_copy("portal_no_time_entries"), colspan="3"))], cls="me-table")
    open_punch = db.one("SELECT id FROM clock_punches WHERE employee_id=? AND punch_type='In' AND NOT EXISTS (SELECT 1 FROM clock_punches o WHERE o.employee_id=clock_punches.employee_id AND o.punch_type='Out' AND o.punched_at>clock_punches.punched_at) ORDER BY punched_at DESC LIMIT 1", (eid,))
    action = Form(Button(_copy("portal_clock_out" if open_punch else "portal_clock_in"), type="submit", cls="me-btn lime"), method="post", action="/me/time/clock-out" if open_punch else "/me/time/clock-in")
    return _shell("time", employee, Div(H1(_copy("portal_time_title")), action, cls="me-title"), _card(_copy("portal_future_shifts"), rows, "me-full"), _card(_copy("portal_time_history"), punch_rows, "me-full"))


def expenses_page(employee):
    eid = employee["id"]
    claims = db.rows("SELECT c.*, cat.name category FROM expense_claims c JOIN expense_categories cat ON cat.id=c.category_id WHERE c.employee_id=? ORDER BY c.claim_date DESC", (eid,))
    advances = db.rows("SELECT * FROM employee_advances WHERE employee_id=? ORDER BY requested_at DESC", (eid,))
    travel = db.rows("SELECT * FROM travel_requests WHERE employee_id=? ORDER BY from_date DESC", (eid,))
    cats = db.expense_categories()
    claim_table = Table(Tr(Th(_copy("portal_claim_date")), Th(_copy("portal_category")), Th(_copy("portal_total")), Th(_copy("portal_status"))), *[Tr(Td(c["claim_date"]), Td(c["category"]), Td(f"{c['amount']:,.2f} {c['currency']}"), Td(_status(c["status"]))) for c in claims] or [Tr(Td(_copy("portal_no_claims"), colspan="4"))], cls="me-table")
    travel_table = Table(Tr(Th(_copy("portal_trip")), Th(_copy("portal_dates")), Th(_copy("portal_status"))), *[Tr(Td(f"{t['destination']} · {t['purpose']}"), Td(f"{t['from_date']} → {t['to_date']}"), Td(_status(t["status"]))) for t in travel] or [Tr(Td(_copy("portal_no_travel"), colspan="3"))], cls="me-table")
    form = Form(Select(*[Option(c["name"], value=str(c["id"])) for c in cats], name="category_id"), Input(type="date", name="claim_date", value=db.TODAY.isoformat()), Input(type="number", name="amount", min="0", step="0.01", required=True), Input(name="description", placeholder=_copy("portal_description_placeholder"), required=True), Button(_copy("portal_submit_claim"), type="submit", cls="me-btn lime"), method="post", action="/me/expenses/claim", cls="me-form")
    travel_form = Form(Input(name="destination", placeholder=_copy("portal_destination"), required=True), Input(name="purpose", placeholder=_copy("portal_purpose"), required=True), Input(type="date", name="from_date", required=True), Input(type="date", name="to_date", required=True), Input(type="number", name="estimated_cost", min="0", step="0.01", required=True), Button(_copy("portal_request_travel"), type="submit", cls="me-btn lime"), method="post", action="/me/expenses/travel", cls="me-form")
    return _shell("expenses", employee, Div(H1(_copy("portal_expenses_title")), P(_copy("portal_expenses_subtitle"), cls="me-muted"), cls="me-title"), _card(_copy("portal_my_claims"), claim_table, "me-full"), _card(_copy("portal_new_claim"), form, "me-half"), _card(_copy("portal_travel_request"), travel_form, "me-half"), _card(_copy("portal_my_travel"), travel_table, "me-full"), _card(_copy("portal_advances"), P(f"{len(advances)} {_copy('portal_registered')}", cls="me-stat"), "me-half"))


def onboarding_page(employee):
    tasks = people.onboarding_tasks(employee["id"])
    goals = people.goals(owner_type="employee", owner_id=employee["id"], status="All")
    task_list = Ul(*[Li(Span(t["title"]), _status(t["status"])) for t in tasks] or [Li(_copy("portal_no_onboarding_tasks"))], cls="me-list")
    goal_list = Ul(*[Li(Span(g["title"]), _status(g["status"])) for g in goals] or [Li(_copy("portal_no_active_goals"))], cls="me-list")
    plans = learning.plans_for(employee["id"])
    certifications = learning.list_for(employee["id"])
    learning_list = Ul(*[Li(Span(p["course_name"]), Span(f"{p['progress']}% · {p['status']}", cls="me-pill")) for p in plans] or [Li(_copy("portal_no_development_plans"))], cls="me-list")
    cert_list = Ul(*[Li(Span(c["name"]), Span(c["expires_on"] or _copy("portal_missing"), cls="me-pill")) for c in certifications] or [Li(_copy("portal_no_certifications"))], cls="me-list")
    return _shell("onboarding", employee, Div(H1(_copy("portal_onboarding_title")), P(_copy("portal_development_intro"), cls="me-muted"), cls="me-title"), _card(_copy("portal_onboarding_tasks"), task_list, "me-half"), _card(_copy("portal_goals"), goal_list, "me-half"), _card(_copy("portal_development_plan"), learning_list, "me-half"), _card(_copy("portal_certifications"), cert_list, "me-half"))
