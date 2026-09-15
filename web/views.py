"""Center-pane renderers for FastHR."""
from __future__ import annotations

from datetime import timedelta

from fasthtml.common import (
    Div, H1, H3, P, Span, Small, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button, Select, Option, Label, NotStr, Strong,
    Script,
)

import db
from web.i18n import current_lang, t, t_app
from web.layout import kpi_card, money

ATT_CLASS = {"Present": "att-present", "Work From Home": "att-wfh", "On Leave": "att-leave",
             "Half Day": "att-half", "Absent": "att-absent"}
ATT_LETTER = {"Present": "P", "Work From Home": "W", "On Leave": "L", "Half Day": "½", "Absent": "A"}


def _pill(text, kind=""):
    return Span(text, cls="pill " + (kind or str(text)).lower().replace(" ", "").replace("/", ""))


def _title(title, sub="", *actions):
    return Div(Div(H1(title), P(sub, cls="sub") if sub else None),
               Div(*actions) if actions else None, cls="page-title")


def _initials(f, l):
    return ((f or "?")[0] + (l or "")[:1]).upper()


def _name(e):
    return f"{e.get('first_name','')} {e.get('last_name','')}".strip()


# ---------- dashboard -------------------------------------------------------

def dashboard():
    lang = current_lang()
    k = db.kpis()
    by_dept = db.headcount_by_dept()
    mx = max((d["n"] for d in by_dept), default=1) or 1
    funnel = [Div(Div(d["dept"], style="color:var(--text-dim);"),
                  Div(Div(cls="funnel-bar", style=f"width:{max(2,100*d['n']/mx):.0f}%;")),
                  Div(str(d["n"]), cls="v"), cls="funnel-row") for d in by_dept]

    on_leave = db.rows("""SELECT e.first_name,e.last_name,d.name dept, a.status FROM attendance a
                          JOIN employees e ON e.id=a.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                          WHERE a.att_date=? AND a.status='On Leave'""", (db.TODAY.isoformat(),))
    pending = db.rows("""SELECT lr.*, e.first_name,e.last_name FROM leave_requests lr
                         JOIN employees e ON e.id=lr.employee_id WHERE lr.status='Pending'
                         ORDER BY lr.from_date LIMIT 5""")
    pend_tbl = Table(Thead(Tr(Th(t_app(lang, "table_employee")), Th(t_app(lang, "table_type")),
                              Th(t_app(lang, "table_dates")), Th(t_app(lang, "table_days")),
                              Th(t_app(lang, "table_reason")))),
                     Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(_pill(r["leave_type"])),
                                Td(f"{r['from_date']} → {r['to_date']}", style="white-space:nowrap;"),
                                Td(str(r["days"]), cls="num"), Td(r["reason"]))
                              for r in pending] or [Tr(Td(t_app(lang, "empty_pending_leave"), colspan="5"))]), cls="tbl")
    leave_tbl = Table(Thead(Tr(Th(t_app(lang, "on_leave_today")), Th(t_app(lang, "table_department")))),
                      Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"),
                                 Td(r["dept"] or t_app(lang, "app_missing_value")))
                               for r in on_leave] or
                           [Tr(Td(t_app(lang, "empty_on_leave"), colspan="2"))]), cls="tbl")

    pending_action = A(t_app(lang, "dashboard_review_pending").format(n=k["pending_leave"]),
                       href="/leave", cls="btn primary") if k["pending_leave"] else None
    title = _title(t_app(lang, "dashboard_title"), t_app(lang, "dashboard_subtitle"))
    pending_header = Div(H3(t_app(lang, "pending_leave_requests")), cls="card-header")
    if pending_action:
        title = _title(t_app(lang, "dashboard_title"), t_app(lang, "dashboard_subtitle"), pending_action)
        pending_header = Div(H3(t_app(lang, "pending_leave_requests")),
                             A(t_app(lang, "dashboard_view_all_pending").format(n=k["pending_leave"]),
                               href="/leave", cls="btn sm"), cls="card-header")
    return (
        title,
        Div(kpi_card(t_app(lang, "kpi_headcount"), k["headcount"],
                     f"{k['depts']} {t_app(lang, 'kpi_departments')}", href="/employees"),
            kpi_card(t_app(lang, "kpi_present_today"), k["present_today"],
                     f"{k['on_leave_today']} {t_app(lang, 'kpi_on_leave')}", href="/attendance"),
            kpi_card(t_app(lang, "kpi_attendance"), f"{k['attendance_rate']}%",
                     tone="warn" if k["attendance_rate"] < 85 else "", href="/attendance"),
            kpi_card(t_app(lang, "kpi_pending_leave"), k["pending_leave"],
                     t_app(lang, "kpi_awaiting_approval"), tone="danger" if k["pending_leave"] else "", href="/leave"),
            cls="kpi-grid"),
        Div(Div(Div(H3(t_app(lang, "headcount_by_department")),
                    A(t_app(lang, "dashboard_view_employees"), href="/employees", cls="btn sm"), cls="card-header"),
                *funnel, cls="card"),
            Div(Div(H3(t_app(lang, "on_leave_today")),
                    A(t_app(lang, "dashboard_view_leave"), href="/leave", cls="btn sm"), cls="card-header"),
                leave_tbl, cls="card"), cls="grid-2"),
        Div(pending_header, pend_tbl, cls="card"),
    )


# ---------- employees -------------------------------------------------------

def employees_list(dept="All", q=""):
    lang = current_lang()
    depts = db.rows("SELECT name FROM departments ORDER BY name")
    seg = Div(*[A(t_app(lang, "employees_all") if s == "All" else s,
                  href=f"/employees?dept={s}", cls="" + ("active" if dept == s else ""))
                for s in ["All"] + [d["name"] for d in depts]], cls="seg")
    where, params = [], []
    if dept != "All":
        where.append("d.name=?")
        params.append(dept)
    if q:
        where.append("(e.first_name LIKE ? OR e.last_name LIKE ? OR e.email LIKE ? OR e.designation LIKE ?)")
        params += [f"%{q}%"] * 4
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    emps = db.rows(f"""SELECT e.*, d.name dept FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY e.first_name LIMIT 300""", tuple(params))
    tbl = Table(Thead(Tr(Th(t_app(lang, "table_employee")), Th(t_app(lang, "employees_job_title")),
                        Th(t_app(lang, "table_department")), Th(t_app(lang, "employees_branch")),
                        Th(t_app(lang, "employees_status")), Th(t_app(lang, "employees_start_date")))),
                Tbody(*[Tr(
                    Td(A(_name(e), href=f"/employees/{e['id']}")),
                    Td(e["designation"] or t_app(lang, "app_missing_value")),
                    Td(e["dept"] or t_app(lang, "app_missing_value")),
                    Td(e["branch"] or t_app(lang, "app_missing_value")),
                    Td(_pill(e["status"])),
                    Td(e["date_of_joining"] or t_app(lang, "app_missing_value"), style="color:var(--text-mute);"))
                    for e in emps] or [Tr(Td(t_app(lang, "employees_empty"), colspan="6"))]), cls="tbl")
    search = Form(Input(type="search", name="q", value=q,
                        placeholder=t_app(lang, "employees_search_placeholder")),
                  Input(type="hidden", name="dept", value=dept), cls="toolbar", method="get", action="/employees")
    return _title(t_app(lang, "employees_title"),
                  f"{len(emps)} {t_app(lang, 'employees_shown')}"), seg, search, Div(tbl, cls="card")


def employee_detail(eid):
    e = db.employee(eid)
    if not e:
        return _title("Töötajat ei leitud"), P("Sellist töötajat pole.")
    bal = db.leave_balance(eid)
    att = db.recent_attendance(eid, 20)
    pays = db.payslips_for(eid)

    head = Div(Span(_initials(e["first_name"], e["last_name"]), cls="avatar"),
               Div(H1(_name(e), style="margin:0;"),
                   P(f"{e['designation']} · {e['dept']} · {e['branch']}", cls="sub")), cls="emp-head")
    info = Div(Div(H3("Andmed"), cls="card-header"),
               Div(Span("Kood", cls="k"), Span(e["code"]),
                   Span("E-post", cls="k"), Span(e["email"]),
                   Span("Staatus", cls="k"), _pill(e["status"]),
                   Span("Juht", cls="k"), Span(e["manager"] or "Puudub"),
                   Span("Tööle asumine", cls="k"), Span(e["date_of_joining"] or "Puudub"),
                   Span("Põhitöötasu", cls="k"), Span(money(e["base_salary"]) + "/aastas"),
                   cls="kv"), cls="card")
    bal_card = Div(Div(H3("Puhkusejääk"), cls="card-header"),
                   Div(*[Div(Div(b["leave_type"], cls="lt"), Div(f"{b['remaining']:.1f}", cls="rem"),
                             Div(f"{b['allocated']:.0f} päevast", cls="of"), cls="bal")
                         for b in bal if b["allocated"]], cls="bal-grid"), cls="card")
    strip = Div(*[Span(ATT_LETTER[a["status"]], cls=f"att-cell {ATT_CLASS[a['status']]}",
                       title=f"{a['att_date']} {a['status']}") for a in reversed(att)], cls="att-strip")
    att_card = Div(Div(H3("Viimane kohalolek"), cls="card-header"), strip,
                   P("P kohal · W kaugtöö · L puhkusel · ½ poolik päev · A puudub",
                     style="color:var(--text-mute);font-size:11px;margin-top:8px;"), cls="card")
    pay_tbl = Table(Thead(Tr(Th("Periood"), Th("Bruto", cls="num"), Th("Mahaarvamised", cls="num"), Th("Netosumma", cls="num"), Th(""))),
                    Tbody(*[Tr(Td(p["period"]), Td(money(p["gross"]), cls="num"),
                               Td(money(p["tax"] + p["pension"] + p["other_ded"]), cls="num"),
                               Td(Strong(money(p["net"])), cls="num"),
                               Td(A("Palgaleht", href=f"/payroll/{p['id']}", cls="btn sm")))
                            for p in pays] or [Tr(Td("Palgalehti pole.", colspan="5"))]), cls="tbl")
    return (head, A("← Kõik töötajad", href="/employees", cls="btn"),
            Div(Div(info, Div(Div(H3("Palgalehed"), cls="card-header"), pay_tbl, cls="card")),
                Div(bal_card, att_card), cls="detail-grid", style="margin-top:14px;"))


def departments_list():
    lang = current_lang()
    deps = db.rows("""SELECT d.name, COUNT(e.id) n,
                      (SELECT m.first_name||' '||m.last_name FROM employees m
                       WHERE m.dept_id=d.id AND m.manager_id IS NULL LIMIT 1) lead,
                      COALESCE(SUM(e.base_salary),0) payroll
                      FROM departments d LEFT JOIN employees e ON e.dept_id=d.id
                      GROUP BY d.id ORDER BY n DESC""")
    tbl = Table(Thead(Tr(Th(t_app(lang, "table_department")), Th(t_app(lang, "departments_lead")),
                        Th(t_app(lang, "departments_employees"), cls="num"),
                        Th(t_app(lang, "departments_payroll"), cls="num"))),
                Tbody(*[Tr(Td(Strong(d["name"])), Td(d["lead"] or t_app(lang, "app_missing_value")), Td(str(d["n"]), cls="num"),
                           Td(money(d["payroll"]), cls="num")) for d in deps]
                or [Tr(Td(t_app(lang, "departments_empty"), colspan="4"))]), cls="tbl")
    return _title(t_app(lang, "departments_title"),
                  f"{len(deps)} {t_app(lang, 'departments_shown')}"), Div(tbl, cls="card")


# ---------- leave -----------------------------------------------------------

def _apply_form():
    lang = current_lang()
    emps = db.employees_min()
    return Div(Div(H3(t_app(lang, "leave_form_title")), cls="card-header"),
               Form(
                   Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in emps],
                          name="employee_id", cls="hr-inp", aria_label=t_app(lang, "leave_employee")),
                   Select(*[Option(t, value=t) for t in db.LEAVE_TYPES], name="leave_type", cls="hr-inp",
                          aria_label=t_app(lang, "leave_type")),
                   Input(type="date", name="from_date", cls="hr-inp", required=True,
                         aria_label=t_app(lang, "leave_start_date")),
                   Input(type="date", name="to_date", cls="hr-inp", required=True,
                         aria_label=t_app(lang, "leave_end_date")),
                   Input(name="reason", placeholder=t_app(lang, "leave_reason_placeholder"), cls="hr-inp",
                         style="flex:1;min-width:140px;"),
                   Button(t_app(lang, "leave_submit"), cls="btn primary", type="submit"),
                   **{"hx-post": "/leave/apply", "hx-target": "#leave-main", "hx-swap": "innerHTML"},
                   cls="inline-form", style="flex-wrap:wrap;gap:8px;"),
               cls="card")


def leave_main(status="Pending"):
    lang = current_lang()
    seg = Div(*[A(s, href=f"/leave?status={s}", cls="" + ("active" if status == s else ""))
                for s in ["Pending", "All"] + [st for st in db.LEAVE_STATUSES if st != "Pending"]], cls="seg")
    clause, params = ("", ()) if status == "All" else ("WHERE lr.status=?", (status,))
    reqs = db.rows(f"""SELECT lr.*, e.first_name,e.last_name, d.name dept FROM leave_requests lr
                       JOIN employees e ON e.id=lr.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY (lr.status!='Pending'), lr.from_date DESC LIMIT 200""", params)
    rows_ = []
    for r in reqs:
        if r["status"] == "Pending":
            act = Div(Button(t_app(lang, "leave_approve"), cls="btn sm primary",
                             **{"hx-post": f"/leave/{r['id']}/approve", "hx-target": "#leave-main", "hx-swap": "innerHTML"}),
                      Button(t_app(lang, "leave_reject"), cls="btn sm", title=t_app(lang, "leave_reject"),
                             **{"hx-post": f"/leave/{r['id']}/reject", "hx-target": "#leave-main", "hx-swap": "innerHTML"}),
                      style="display:flex;gap:4px;")
        else:
            act = Span(t_app(lang, "app_missing_value"), style="color:var(--text-mute);")
        rows_.append(Tr(Td(f"{r['first_name']} {r['last_name']}"),
                        Td(r["dept"] or t_app(lang, "app_missing_value")),
                        Td(_pill(r["leave_type"])),
                        Td(f"{r['from_date']} → {r['to_date']}", style="white-space:nowrap;"),
                        Td(str(r["days"]), cls="num"), Td(_pill(r["status"])), Td(act)))
    tbl = Table(Thead(Tr(Th(t_app(lang, "leave_employee")), Th(t_app(lang, "leave_department")),
                       Th(t_app(lang, "leave_type")), Th(t_app(lang, "leave_dates")),
                       Th(t_app(lang, "leave_days"), cls="num"), Th(t_app(lang, "leave_status")),
                       Th(t_app(lang, "leave_action")))),
                Tbody(*rows_ or [Tr(Td(t_app(lang, "leave_empty"), colspan="7"))]), cls="tbl")
    return Div(_apply_form(), seg, Div(tbl, cls="card"))


def leave_list(status="Pending"):
    lang = current_lang()
    return _title(t_app(lang, "leave_title")), Div(leave_main(status), id="leave-main")


# ---------- attendance ------------------------------------------------------

def attendance_view():
    lang = current_lang()
    today = db.TODAY.isoformat()
    reg = db.rows("""SELECT e.first_name,e.last_name,d.name dept,a.status,a.hours FROM attendance a
                     JOIN employees e ON e.id=a.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                     WHERE a.att_date=? ORDER BY a.status, e.first_name""", (today,))
    counts = {}
    for r in reg:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    kpis = Div(*[kpi_card(s, counts.get(s, 0)) for s in db.ATTEND_STATUSES[:4]], cls="kpi-grid")
    tbl = Table(Thead(Tr(Th(t_app(lang, "table_employee")), Th(t_app(lang, "table_department")),
                       Th(t_app(lang, "attendance_status")), Th(t_app(lang, "attendance_hours"), cls="num"))),
                Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "Puudub"),
                           Td(_pill(r["status"])), Td(f"{r['hours']:.1f}" if r["hours"] else "Puudub", cls="num"))
                        for r in reg] or [Tr(Td(t_app(lang, "attendance_empty"), colspan="4"))]), cls="tbl")
    return (_title(t_app(lang, "attendance_title"), t_app(lang, "attendance_subtitle").format(today=today)),
            kpis, Div(Div(H3(t_app(lang, "attendance_today_register")), cls="card-header"), tbl, cls="card"))


# ---------- shifts and time clocks -----------------------------------------

def _week_start(value=None):
    try:
        day = db.date.fromisoformat(value) if value else db.TODAY
    except (TypeError, ValueError):
        day = db.TODAY
    return day - timedelta(days=day.weekday())


def shifts_roster(week=""):
    lang = current_lang()
    start = _week_start(week)
    days = [start + timedelta(days=i) for i in range(7)]
    end = days[-1]
    assignments = db.roster(start.isoformat(), end.isoformat())
    by_day = {}
    for item in assignments:
        by_day.setdefault((item["employee_id"], item["shift_date"]), []).append(item)
    employees = db.rows("""SELECT DISTINCT e.id,e.first_name,e.last_name FROM employees e
                           JOIN shift_assignments s ON s.employee_id=e.id
                           WHERE s.shift_date BETWEEN ? AND ? ORDER BY e.first_name,e.last_name""",
                        (start.isoformat(), end.isoformat()))
    rows_ = []
    for emp in employees:
        cells = []
        for day in days:
            shifts = by_day.get((emp["id"], day.isoformat()), [])
            cells.append(Td(*[Div(A(f"{s['shift_name']} {s['start_time']}–{s['end_time']}",
                                  href=f"/shifts?week={start.isoformat()}",
                                  style=f"border-left:3px solid {s['color'] or 'var(--accent)'};"),
                             _pill(s["status"]),
                             Form(Button(t_app(lang, "shifts_cancel"), type="submit", cls="btn sm"), method="post",
                                  action=f"/shifts/{s['id']}/cancel") if s["status"] in ("Scheduled", "Missed") else None,
                             cls="note") for s in shifts] or [Span(t_app(lang, "app_missing_value"), cls="sub")]))
        rows_.append(Tr(Td(Strong(_name(emp))), *cells))
    table = Table(Thead(Tr(Th(t_app(lang, "table_employee")), *[Th(f"{d:%a}<br>{d:%d %b}", cls="num") for d in days])),
                  Tbody(*rows_ or [Tr(Td(t_app(lang, "shifts_missing"), colspan="8"))]), cls="tbl")
    types = db.shift_types()
    emps = db.employees_min()
    form = Form(Select(*[Option(_name(e), value=str(e["id"])) for e in emps], name="employee_id", required=True, cls="hr-inp", aria_label=t_app(lang, "table_employee")),
                Select(*[Option(t["name"], value=str(t["id"])) for t in types], name="shift_type_id", required=True, cls="hr-inp", aria_label=t_app(lang, "shifts_type")),
                Input(type="date", name="shift_date", value=db.TODAY.isoformat(), required=True, cls="hr-inp", aria_label=t_app(lang, "shifts_date")),
                Input(name="location_label", placeholder=t_app(lang, "shifts_location_placeholder"), cls="hr-inp"),
                Button(t_app(lang, "shifts_create"), type="submit", cls="btn primary"), method="post", action="/shifts/new")
    prev_week, next_week = (start - timedelta(days=7)).isoformat(), (start + timedelta(days=7)).isoformat()
    return (_title(t_app(lang, "shifts_title"), t_app(lang, "shifts_week").format(start=start.isoformat(), end=end.isoformat()),
                   A(t_app(lang, "shifts_previous"), href=f"/shifts?week={prev_week}", cls="btn"),
                   A(t_app(lang, "shifts_next"), href=f"/shifts?week={next_week}", cls="btn")),
            Div(Div(H3(t_app(lang, "shifts_week_schedule")), cls="card-header"), table, cls="card"),
            Div(Div(H3(t_app(lang, "shifts_new_title")), P(t_app(lang, "shifts_new_subtitle"), cls="sub"), cls="card-header"), form, cls="card"))


def time_clocks():
    lang = current_lang()
    today = db.TODAY.isoformat()
    employees = db.employees_min()
    punches = db.rows("""SELECT p.*, e.first_name,e.last_name FROM clock_punches p
                         JOIN employees e ON e.id=p.employee_id
                         WHERE substr(p.punched_at,1,10)=? ORDER BY p.punched_at DESC""", (today,))
    latest = {}
    for punch in sorted(punches, key=lambda p: p["punched_at"]):
        latest[punch["employee_id"]] = punch
    def state_for(eid):
        kind = latest.get(eid, {}).get("punch_type")
        return {"In": t_app(lang, "timeclock_state_started"),
                "Break Start": t_app(lang, "timeclock_state_break"),
                "Break End": t_app(lang, "timeclock_state_started"),
                "Out": t_app(lang, "timeclock_state_ended")}.get(kind, t_app(lang, "timeclock_state_missing"))

    board = Table(Thead(Tr(Th(t_app(lang, "table_employee")), Th(t_app(lang, "timeclock_state")),
                           Th(t_app(lang, "timeclock_last_entry")), Th(t_app(lang, "timeclock_source")))),
                  Tbody(*[Tr(Td(_name(e)), Td(_pill(state_for(e["id"]))),
                           Td(latest[e["id"]]["punched_at"] if e["id"] in latest else t_app(lang, "app_missing_value")),
                           Td(latest[e["id"]]["source"] if e["id"] in latest else t_app(lang, "app_missing_value"))) for e in employees]
                  or [Tr(Td(t_app(lang, "timeclock_no_employees"), colspan="4"))]), cls="tbl")
    selector = Select(*[Option(_name(e), value=str(e["id"])) for e in employees], name="employee_id", required=True, cls="hr-inp")
    widget = Div(Form(selector, Input(type="hidden", name="source", value="Web"), Button(t_app(lang, "timeclock_start"), type="submit", cls="btn primary"),
                      method="post", action="/timeclock/in"),
                 Form(Select(*[Option(_name(e), value=str(e["id"])) for e in employees], name="employee_id", required=True, cls="hr-inp"),
                      Button(t_app(lang, "timeclock_end"), type="submit", cls="btn"), method="post", action="/timeclock/out"), cls="actions")
    recent = Table(Thead(Tr(Th(t_app(lang, "table_employee")), Th(t_app(lang, "timeclock_type")),
                           Th(t_app(lang, "timeclock_time")), Th(t_app(lang, "timeclock_location")))),
                   Tbody(*[Tr(Td(_name(p)), Td(_pill(p["punch_type"])), Td(p["punched_at"]),
                              Td(t_app(lang, "timeclock_on_site") if p["on_site"] else (t_app(lang, "timeclock_off_site") if p["on_site"] == 0 else t_app(lang, "app_missing_value")))) for p in punches[:20]] or
                          [Tr(Td(t_app(lang, "timeclock_no_entries"), colspan="4"))]), cls="tbl")
    gaps = db.auto_attendance_gap_report((db.TODAY - timedelta(days=7)).isoformat(), today)
    gap_list = [Tr(Td(_name(g)), Td(g["shift_date"]), Td(g["shift_name"])) for g in gaps]
    return (_title(t_app(lang, "timeclock_title"), t_app(lang, "timeclock_subtitle").format(today=today)),
            Div(Div(H3(t_app(lang, "timeclock_mark")), widget, cls="card-header"), P(t_app(lang, "timeclock_mark_help")), cls="card"),
            Div(Div(H3(t_app(lang, "timeclock_today_overview")), cls="card-header"), board, cls="card"),
            Div(Div(H3(t_app(lang, "timeclock_recent")), cls="card-header"), recent, cls="card"),
            Div(Div(H3(t_app(lang, "timeclock_missing_entries")), P(t_app(lang, "timeclock_missing_help"), cls="sub"), cls="card-header"),
                Table(Thead(Tr(Th(t_app(lang, "table_employee")), Th(t_app(lang, "table_dates")), Th(t_app(lang, "timeclock_shift")))),
                      Tbody(*gap_list or [Tr(Td(t_app(lang, "timeclock_no_gaps"), colspan="3"))]), cls="tbl"), cls="card"))


# ---------- payroll ---------------------------------------------------------

def _pay_run_form():
    emps = db.rows("SELECT id,first_name,last_name,designation FROM employees WHERE status='Active' ORDER BY first_name,last_name")
    periods = []
    y, m = db.TODAY.year, db.TODAY.month
    for _ in range(6):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        periods.append(f"{y:04d}-{m:02d}")
    rows = [Label(Input(type="checkbox", name="employee_ids", value=str(e["id"]), cls="pr-emp"),
                  f" {e['first_name']} {e['last_name']}",
                  **{"data-name": f"{e['first_name']} {e['last_name']}".lower()},
                  style="display:block;padding:3px 0;")
            for e in emps]
    return Div(Div(H3("Uus palgaperiood"), P("Vali lõppenud periood ja aktiivsed töötajad.", cls="sub")),
               Form(Select(*[Option(p, value=p) for p in periods], name="period", required=True, cls="hr-inp"),
                    Input(type="search", placeholder="Otsi töötajaid…", cls="hr-inp",
                          style="margin-top:8px;", oninput="prFilter(this.value)"),
                    Label(Input(type="checkbox", onchange="prToggle(this.checked)"),
                          " Vali kõik", style="display:block;padding:6px 0;font-weight:600;"),
                    Div(*rows or [P("Aktiivseid töötajaid pole.", cls="sub")], id="pr-emps",
                        style="max-height:180px;overflow:auto;margin:10px 0;"),
                    Button("Loo mustand", type="submit", cls="btn primary"),
                    method="post", action="/payroll/runs/new"),
               Script("function prToggle(on){document.querySelectorAll('#pr-emps .pr-emp').forEach(c=>c.checked=on);}"
                      "function prFilter(q){q=q.toLowerCase();document.querySelectorAll('#pr-emps label').forEach("
                      "l=>{l.style.display=(!q||(l.dataset.name||'').includes(q))?'block':'none';});}"),
               cls="card")


def pay_run_new():
    lang = current_lang()
    return (_title(t_app(lang, "pay_new_title"), t_app(lang, "pay_new_subtitle"),
                   A(t_app(lang, "pay_back_periods"), href="/payroll", cls="btn")),
            _pay_run_form())


def payroll_list(period="latest"):
    lang = current_lang()
    c = lambda key: t_app(lang, key)
    if period != "latest":
        run = db.one("SELECT id FROM pay_runs WHERE period=?", (period,))
        if run:
            return pay_run_detail(run["id"])
        # Preserve links/bookmarks for pre-Phase-1 legacy payslips that have
        # no pay_run relationship yet.
        pays = db.rows("""SELECT p.*, e.first_name,e.last_name,d.name dept
                          FROM payslips p JOIN employees e ON e.id=p.employee_id
                          LEFT JOIN departments d ON d.id=e.dept_id
                          WHERE p.period=? ORDER BY p.net DESC""", (period,))
        tbl = Table(Thead(Tr(Th(c("pay_employee")), Th(c("pay_department")), Th(c("pay_gross"), cls="num"),
                             Th(c("pay_net"), cls="num"), Th(c("pay_status")), Th(""))),
                    Tbody(*[Tr(Td(f"{p['first_name']} {p['last_name']}"), Td(p["dept"] or c("pay_missing")),
                               Td(money(p["gross"]), cls="num"), Td(Strong(money(p["net"])), cls="num"),
                               Td(_pill(p["status"])), Td(A(c("pay_payslip"), href=f"/payroll/{p['id']}", cls="btn sm")))
                            for p in pays] or [Tr(Td(c("pay_no_period_payslips"), colspan="6"))]), cls="tbl")
        return _title(c("payroll"), f"{period} · {c('pay_old_payslips')}"), Div(tbl, cls="card")
    runs = db.pay_runs()
    tbl = Table(Thead(Tr(Th(c("pay_period")), Th(c("pay_status")), Th(c("pay_headcount"), cls="num"),
                         Th(c("pay_gross"), cls="num"), Th(c("pay_net"), cls="num"), Th(""))),
                Tbody(*[Tr(Td(A(r["period"], href=f"/payroll/runs/{r['id']}")),
                           Td(_pill(r["status"])), Td(str(r["headcount"]), cls="num"),
                           Td(money(r["gross_total"]), cls="num"), Td(Strong(money(r["net_total"])), cls="num"),
                           Td(A(c("pay_open"), href=f"/payroll/runs/{r['id']}", cls="btn sm"),
                              A(c("pay_tor_export"), href=f"/payroll/runs/{r['id']}/export/tor", cls="btn sm"),
                              A(c("pay_tsd_export"), href=f"/payroll/runs/{r['id']}/export/tsd", cls="btn sm")))
                        for r in runs] or [Tr(Td(c("pay_no_periods"), colspan="6"))]), cls="tbl")
    return (_title(c("pay_periods"), c("pay_subtitle"),
                   A(c("pay_export_history"), href="/payroll/exports", cls="btn"),
                   A(c("pay_new_run"), href="/payroll/runs/new", cls="btn primary")),
            Div(tbl, cls="card"))


def pay_run_detail(rid, saved=False):
    lang = current_lang()
    c = lambda key: t_app(lang, key)
    run = db.pay_run(rid)
    if not run:
        return _title(c("pay_run_not_found")), P(c("pay_run_missing"))
    tbl = Table(Thead(Tr(Th(c("pay_employee")), Th(c("pay_department")), Th(c("pay_gross"), cls="num"),
                         Th(c("pay_net"), cls="num"), Th(c("pay_status")), Th(""))),
                Tbody(*[Tr(Td(Div(f"{p['first_name']} {p['last_name']}"),
                              *[Small(f"{line['kind']} · {line['label']}: {money(line['amount'])} · {line['base']}",
                                      style="display:block;color:var(--text-mute);font-size:11px;")
                                 for line in db.payslip_lines(p["id"])
                                 ]),
                           Td(p["dept"] or c("pay_missing")),
                           Td(money(p["gross"]), cls="num"), Td(Strong(money(p["net"])), cls="num"),
                           Td(_pill(p["status"])), Td(A(c("pay_payslip"), href=f"/payroll/{p['id']}", cls="btn sm")))
                        for p in run["payslips"]] or [Tr(Td(c("pay_no_payslips"), colspan="6"))]), cls="tbl")
    next_status = db.PAY_RUN_TRANSITIONS.get(run["status"])
    advance = (Form(Button(c("pay_move_to").format(status=next_status), type="submit", cls="btn primary"),
                     method="post", action=f"/payroll/runs/{rid}/advance") if next_status else None)
    reprepare = (Form(Button(c("pay_reprepare"), type="submit", cls="btn"),
                      method="post", action=f"/payroll/runs/{rid}/reprepare")
                 if run["status"] == "Draft" else None)
    employer_cost_total = round(sum(float(line["amount"] or 0)
                                    for p in run["payslips"]
                                    for line in db.payslip_lines(p["id"])
                                    if (line["base"] or "").startswith("Employer cost")), 2)
    totals = Div(kpi_card(c("pay_gross_total"), money(sum(p["gross"] for p in run["payslips"]))),
                 kpi_card(c("pay_net_total"), money(sum(p["net"] for p in run["payslips"]))),
                 kpi_card(c("pay_employer_costs"), money(employer_cost_total)),
                 kpi_card(c("pay_headcount"), str(len(run["payslips"]))), cls="kpi-grid")
    offsets = db.rows("""SELECT a.id, a.reason, COALESCE(a.approved_amount,a.requested_amount) amount,
                                e.first_name||' '||e.last_name employee
                         FROM employee_advances a JOIN employees e ON e.id=a.employee_id
                         JOIN payslips p ON p.employee_id=a.employee_id AND p.run_id=?
                         WHERE a.status='Approved' AND a.offset_run_id IS NULL
                         ORDER BY e.first_name""", (rid,)) if run["status"] == "Draft" else []
    offset_card = Div(Div(H3(c("pay_offset_title")),
                          P(c("pay_offset_help"), style="color:var(--text-mute);font-size:12px;"),
                          cls="card-header"),
                      Table(Thead(Tr(Th(c("pay_employee")), Th(c("expenses_reason")), Th(c("expenses_amount"), cls="num"), Th(""))),
                            Tbody(*[Tr(Td(a["employee"]), Td(a["reason"]), Td(money(a["amount"]), cls="num"),
                                       Td(Form(Button(c("pay_offset"), type="submit", cls="btn sm primary"), method="post",
                                               action=f"/payroll/runs/{rid}/offset?advance_id={a['id']}"))) for a in offsets]
                                  or [Tr(Td(c("pay_no_offsets"), colspan="4"))]), cls="tbl"), cls="card")
    actions = [A(c("pay_back_periods"), href="/payroll", cls="btn"),
               A(c("pay_tor_export"), href=f"/payroll/runs/{rid}/export/tor", cls="btn"),
               A(c("pay_tsd_export"), href=f"/payroll/runs/{rid}/export/tsd", cls="btn")]
    if reprepare:
        actions.append(reprepare)
    return (_title(c("pay_run_title").format(period=run["period"]),
                   c("pay_run_subtitle").format(count=len(run["payslips"]), net=money(sum(p["net"] for p in run["payslips"]))),
                   *actions, advance),
            P(c("pay_saved"), cls="flag") if saved else None,
            totals,
            Div(Div(H3(c("pay_payslips")), _pill(run["status"]), cls="card-header"), tbl, cls="card"),
            offset_card)


def statutory_exports_page():
    lang = current_lang()
    c = lambda key: t_app(lang, key)
    exports = db.rows("SELECT * FROM statutory_exports ORDER BY created_at DESC,id DESC")
    table = Table(Thead(Tr(Th(c("pay_export_type")), Th(c("pay_period")), Th(c("pay_file")), Th(c("pay_rows"), cls="num"),
                         Th(c("pay_created")), Th(""))),
                  Tbody(*[Tr(Td(e["kind"]), Td(e["period"]), Td(e["file_name"]),
                           Td(str(e["row_count"]), cls="num"), Td(e["created_at"] or c("pay_missing")),
                           Td(A(c("pay_download"), href=f"/payroll/exports/{e['id']}", cls="btn sm")))
                        for e in exports] or [Tr(Td(c("pay_exports_empty"), colspan="6"))]), cls="tbl")
    return (_title(c("pay_export_history"), c("pay_exports_subtitle")), Div(table, cls="card"))


def payslip_detail(pid):
    lang = current_lang()
    c = lambda key: t_app(lang, key)
    p = db.one("""SELECT p.*, e.first_name,e.last_name,e.designation,e.code,d.name dept FROM payslips p
                  JOIN employees e ON e.id=p.employee_id LEFT JOIN departments d ON d.id=e.dept_id WHERE p.id=?""", (pid,))
    if not p:
        return _title(c("pay_payslip_not_found")), P(c("pay_no_such_payslip"))
    lines = db.payslip_lines(pid)
    if lines:
        earnings = [line for line in lines if line["kind"] == "Earning"]
        employer_costs = [line for line in lines
                          if line["kind"] == "Deduction"
                          and (line["base"] or "").startswith("Employer cost")]
        deductions = [line for line in lines
                      if line["kind"] == "Deduction" and line not in employer_costs]
        line_rows = [Tr(Td(Strong(c("pay_earnings"))), Td(""))]
        line_rows += [Tr(Td(line["label"]), Td(money(line["amount"]), cls="num")) for line in earnings]
        line_rows += [Tr(Td(Strong(c("pay_deductions"))), Td(""))]
        line_rows += [Tr(Td(line["label"]), Td("− " + money(line["amount"]), cls="num",
                                             style="color:var(--danger);")) for line in deductions]
        if employer_costs:
            line_rows += [Tr(Td(Strong(t(lang)["payroll_employer_costs"])), Td(""))]
            line_rows += [Tr(Td(line["label"]), Td(money(line["amount"]), cls="num"))
                          for line in employer_costs]
        line_rows += [Tr(Td(Strong(c("pay_net"))), Td(Strong(money(p["net"])), cls="num"))]
    else:
        legacy = [(c("pay_gross_pay"), p["gross"], False), (c("pay_income_tax"), p["tax"], True),
                  (c("pay_pension"), p["pension"], True), (c("pay_other_deductions"), p["other_ded"], True),
                  (c("pay_net"), p["net"], False)]
        line_rows = [Tr(Td(Strong(label) if label in (c("pay_gross_pay"), c("pay_net")) else label),
                        Td(Strong(money(amt)) if label == c("pay_net") else
                           (("− " if neg else "") + money(amt)), cls="num",
                           style="color:var(--danger);" if neg else ""))
                     for label, amt, neg in legacy]
    body = Table(Tbody(*line_rows), cls="tbl")
    return (_title(c("pay_payslip_title").format(name=f"{p['first_name']} {p['last_name']}"), f"{p['period']} · {p['designation']} · {p['dept']}",
                   A(c("pay_payroll_back"), href="/payroll", cls="btn")),
            Div(Div(Div(H3(c("pay_payslip_heading").format(period=p["period"])), _pill(p["status"]), cls="card-header"), body, cls="card",
                    style="max-width:520px;")))


# ---------- expenses and travel --------------------------------------------

def _employee_select(name="employee_id"):
    return Select(*[Option(_name(e), value=str(e["id"])) for e in db.employees_min()],
                  name=name, required=True, cls="hr-inp", aria_label="Töötaja")


def expenses_page():
    lang = current_lang()
    c = lambda key: t_app(lang, key)
    summary = db.expenses_summary()
    cats = db.expense_categories()
    claims = db.open_expenses()
    advances = db.open_advances()
    claim_rows = []
    for c in claims:
        actions = []
        if c["status"] == "Submitted":
            actions = [Form(Button(c("expenses_approve"), type="submit", cls="btn sm primary"), method="post", action=f"/expenses/{c['id']}/decide?decision=Approved") ,
                        Form(Button(c("expenses_reject"), type="submit", cls="btn sm"), method="post",
                             action=f"/expenses/{c['id']}/decide?decision=Rejected")]
        elif c["status"] == "Approved":
            actions = [Form(Button(c("expenses_reimburse"), type="submit", cls="btn sm primary"), method="post", action=f"/expenses/{c['id']}/reimburse")]
        claim_rows.append(Tr(Td(f"{c['first_name']} {c['last_name']}"), Td(c["category"]),
                             Td(c["claim_date"]), Td(c["description"]), Td(money(c["amount"]), cls="num"),
                             Td(_pill(c["status"])), Td(*actions, cls="actions")))
    claim_form = Form(_employee_select(),
                      Select(*[Option(cat["name"], value=str(cat["id"])) for cat in cats], name="category_id", required=True, cls="hr-inp", aria_label=c("expenses_category")),
                      Input(type="date", name="claim_date", value=db.TODAY.isoformat(), required=True, cls="hr-inp", aria_label=c("expenses_date")),
                      Input(type="number", name="amount", min="0", step="0.01", placeholder=c("expenses_amount"), required=True, cls="hr-inp"),
                      Input(name="description", placeholder=c("expenses_description"), required=True, cls="hr-inp"),
                      Input(type="number", name="tax_rate", min="0", max="1", step="0.01", value="0.22", title=c("expenses_tax_rate"), cls="hr-inp"),
                      Button(c("expenses_save_claim"), type="submit", cls="btn primary"), method="post", action="/expenses/new")
    adv_rows = [Tr(Td(f"{a['first_name']} {a['last_name']}"), Td(a["reason"]),
                   Td(money(a["requested_amount"])), Td(_pill(a["status"])),
                   Td(Form(Button(c("expenses_approve"), type="submit", cls="btn sm primary"), method="post", action=f"/expenses/advance/{a['id']}/decide?decision=Approved"))) for a in advances]
    advance_form = Form(_employee_select(), Input(type="number", name="requested_amount", min="0", step="0.01", placeholder=c("expenses_amount"), required=True, cls="hr-inp"),
                        Input(name="reason", placeholder=c("expenses_reason"), required=True, cls="hr-inp"),
                        Button(c("expenses_request_advance"), type="submit", cls="btn primary"), method="post", action="/expenses/advance/new")
    return (_title(c("expenses_title"), c("expenses_subtitle"), A(c("expenses_travel"), href="/travel", cls="btn")),
            Div(kpi_card(c("expenses_pending_total"), money(summary["pending_total"])),
                kpi_card(c("expenses_approved_month"), money(summary["approved_this_month"])),
                kpi_card(c("expenses_outstanding"), money(summary["advances_outstanding"])), cls="kpi-grid"),
            Div(Div(H3(c("expenses_claims")), cls="card-header"),
                Table(Thead(Tr(Th(c("expenses_employee")), Th(c("expenses_category")), Th(c("expenses_date")), Th(c("expenses_description_heading")), Th(c("expenses_amount"), cls="num"), Th(c("expenses_status")), Th(""))),
                      Tbody(*claim_rows or [Tr(Td(c("expenses_no_claims"), colspan="7"))]), cls="tbl"), cls="card"),
            Div(Div(H3(c("expenses_new_claim")), cls="card-header"), claim_form, cls="card"),
            Div(Div(H3(c("expenses_advances")), cls="card-header"),
                Table(Thead(Tr(Th(c("pay_employee")), Th(c("expenses_reason")), Th(c("expenses_amount")), Th(c("pay_status")), Th(""))),
                      Tbody(*adv_rows or [Tr(Td(c("expenses_no_advances"), colspan="5"))]), cls="tbl"), advance_form, cls="card"))


def travel_page():
    lang = current_lang()
    c = lambda key: t_app(lang, key)
    requests = db.open_travel()
    rows_ = []
    for t in requests:
        actions = []
        if t["status"] == "Submitted":
            for label, decision in ((c("expenses_approve"), "Approved"), (c("travel_reject"), "Rejected"), (c("travel_return"), "Returned")):
                actions.append(Form(Button(label, type="submit", cls="btn sm"), method="post", action=f"/travel/{t['id']}/decide?decision={decision}"))
        elif t["status"] == "Returned":
            actions.append(Form(Button(c("travel_resubmit"), type="submit", cls="btn sm primary"), method="post", action=f"/travel/{t['id']}/decide?decision=Resubmit"))
        rows_.append(Tr(Td(f"{t['first_name']} {t['last_name']}"), Td(t["destination"]),
                        Td(f"{t['from_date']} → {t['to_date']}"), Td(t["purpose"]),
                        Td(money(t["estimated_cost"])), Td(_pill(t["status"])), Td(*actions)))
    form = Form(_employee_select(), Input(name="destination", placeholder=c("travel_destination"), required=True, cls="hr-inp"),
                Input(name="purpose", placeholder=c("travel_purpose"), required=True, cls="hr-inp"),
                Input(type="date", name="from_date", required=True, cls="hr-inp", aria_label=c("travel_start")),
                Input(type="date", name="to_date", required=True, cls="hr-inp", aria_label=c("travel_end")),
                Input(type="number", name="estimated_cost", min="0", step="0.01", placeholder=c("travel_estimated_cost"), required=True, cls="hr-inp"),
                Input(type="number", name="advance_requested", min="0", step="0.01", value="0", placeholder=c("travel_advance"), cls="hr-inp"),
                Button(c("travel_submit"), type="submit", cls="btn primary"), method="post", action="/travel/new")
    return (_title(c("travel_title"), c("travel_subtitle"), A(c("travel_back_expenses"), href="/expenses", cls="btn")),
            Div(Div(H3(c("travel_title")), cls="card-header"),
                Table(Thead(Tr(Th(c("pay_employee")), Th(c("travel_destination")), Th(c("travel_dates")), Th(c("travel_purpose")), Th(c("travel_estimate")), Th(c("pay_status")), Th(""))),
                      Tbody(*rows_ or [Tr(Td(c("travel_empty"), colspan="7"))]), cls="tbl"), cls="card"),
            Div(Div(H3(c("travel_new")), cls="card-header"), form, cls="card"))
