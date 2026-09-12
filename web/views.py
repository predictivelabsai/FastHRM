"""Center-pane renderers for FastHRM."""
from __future__ import annotations

from datetime import timedelta

from fasthtml.common import (
    Div, H1, H3, P, Span, Small, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button, Select, Option, Label, NotStr, Strong,
)

import db
from web.i18n import t
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
                         ORDER BY lr.from_date LIMIT 8""")
    pend_tbl = Table(Thead(Tr(Th("Employee"), Th("Type"), Th("Dates"), Th("Days"), Th("Reason"))),
                     Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(_pill(r["leave_type"])),
                                Td(f"{r['from_date']} → {r['to_date']}", style="white-space:nowrap;"),
                                Td(str(r["days"]), cls="num"), Td(r["reason"]))
                             for r in pending] or [Tr(Td("No pending requests 🎉", colspan="5"))]), cls="tbl")
    leave_tbl = Table(Thead(Tr(Th("On leave today"), Th("Department"))),
                      Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "—"))
                              for r in on_leave] or [Tr(Td("Nobody on leave today.", colspan="2"))]), cls="tbl")

    return (
        _title("HR Dashboard", "People, time and pay at a glance — fully synthetic demo data."),
        Div(kpi_card("Headcount", k["headcount"], f"{k['depts']} departments"),
            kpi_card("Present today", k["present_today"], f"{k['on_leave_today']} on leave"),
            kpi_card("Attendance (30d)", f"{k['attendance_rate']}%", tone="warn" if k["attendance_rate"] < 85 else ""),
            kpi_card("Pending leave", k["pending_leave"], "awaiting approval", tone="danger" if k["pending_leave"] else ""),
            cls="kpi-grid"),
        Div(Div(Div(H3("Headcount by department"), cls="card-header"), *funnel, cls="card"),
            Div(Div(H3("On leave today"), cls="card-header"), leave_tbl, cls="card"), cls="grid-2"),
        Div(Div(H3("Pending leave requests"), cls="card-header"), pend_tbl, cls="card"),
    )


# ---------- employees -------------------------------------------------------

def employees_list(dept="All", q=""):
    depts = db.rows("SELECT name FROM departments ORDER BY name")
    seg = Div(*[A(s, href=f"/employees?dept={s}", cls="" + ("active" if dept == s else ""))
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
    tbl = Table(Thead(Tr(Th("Employee"), Th("Designation"), Th("Department"), Th("Branch"), Th("Status"), Th("Joined"))),
                Tbody(*[Tr(
                    Td(A(_name(e), href=f"/employees/{e['id']}")),
                    Td(e["designation"] or "—"), Td(e["dept"] or "—"), Td(e["branch"] or "—"),
                    Td(_pill(e["status"])), Td(e["date_of_joining"] or "—", style="color:var(--text-mute);"))
                    for e in emps] or [Tr(Td("No employees found.", colspan="6"))]), cls="tbl")
    search = Form(Input(type="search", name="q", value=q, placeholder="Search employees…"),
                  Input(type="hidden", name="dept", value=dept), cls="toolbar", method="get", action="/employees")
    return _title("Employees", f"{len(emps)} shown"), seg, search, Div(tbl, cls="card")


def employee_detail(eid):
    e = db.employee(eid)
    if not e:
        return _title("Employee not found"), P("No such employee.")
    bal = db.leave_balance(eid)
    att = db.recent_attendance(eid, 20)
    pays = db.payslips_for(eid)

    head = Div(Span(_initials(e["first_name"], e["last_name"]), cls="avatar"),
               Div(H1(_name(e), style="margin:0;"),
                   P(f"{e['designation']} · {e['dept']} · {e['branch']}", cls="sub")), cls="emp-head")
    info = Div(Div(H3("Details"), cls="card-header"),
               Div(Span("Code", cls="k"), Span(e["code"]),
                   Span("Email", cls="k"), Span(e["email"]),
                   Span("Status", cls="k"), _pill(e["status"]),
                   Span("Manager", cls="k"), Span(e["manager"] or "—"),
                   Span("Joined", cls="k"), Span(e["date_of_joining"] or "—"),
                   Span("Base salary", cls="k"), Span(money(e["base_salary"]) + "/yr"),
                   cls="kv"), cls="card")
    bal_card = Div(Div(H3("Leave balance"), cls="card-header"),
                   Div(*[Div(Div(b["leave_type"], cls="lt"), Div(f"{b['remaining']:.1f}", cls="rem"),
                             Div(f"of {b['allocated']:.0f} days", cls="of"), cls="bal")
                         for b in bal if b["allocated"]], cls="bal-grid"), cls="card")
    strip = Div(*[Span(ATT_LETTER[a["status"]], cls=f"att-cell {ATT_CLASS[a['status']]}",
                       title=f"{a['att_date']} {a['status']}") for a in reversed(att)], cls="att-strip")
    att_card = Div(Div(H3("Recent attendance"), cls="card-header"), strip,
                   P("P present · W WFH · L leave · ½ half-day · A absent",
                     style="color:var(--text-mute);font-size:11px;margin-top:8px;"), cls="card")
    pay_tbl = Table(Thead(Tr(Th("Period"), Th("Gross", cls="num"), Th("Deductions", cls="num"), Th("Net", cls="num"), Th(""))),
                    Tbody(*[Tr(Td(p["period"]), Td(money(p["gross"]), cls="num"),
                               Td(money(p["tax"] + p["pension"] + p["other_ded"]), cls="num"),
                               Td(Strong(money(p["net"])), cls="num"),
                               Td(A("Payslip", href=f"/payroll/{p['id']}", cls="btn sm")))
                            for p in pays] or [Tr(Td("No payslips yet.", colspan="5"))]), cls="tbl")
    return (head, A("← All employees", href="/employees", cls="btn"),
            Div(Div(info, Div(Div(H3("Payslips"), cls="card-header"), pay_tbl, cls="card")),
                Div(bal_card, att_card), cls="detail-grid", style="margin-top:14px;"))


def departments_list():
    deps = db.rows("""SELECT d.name, COUNT(e.id) n,
                      (SELECT m.first_name||' '||m.last_name FROM employees m
                       WHERE m.dept_id=d.id AND m.manager_id IS NULL LIMIT 1) lead,
                      COALESCE(SUM(e.base_salary),0) payroll
                      FROM departments d LEFT JOIN employees e ON e.dept_id=d.id
                      GROUP BY d.id ORDER BY n DESC""")
    tbl = Table(Thead(Tr(Th("Department"), Th("Head"), Th("Headcount", cls="num"), Th("Annual payroll", cls="num"))),
                Tbody(*[Tr(Td(Strong(d["name"])), Td(d["lead"] or "—"), Td(str(d["n"]), cls="num"),
                           Td(money(d["payroll"]), cls="num")) for d in deps]
                or [Tr(Td("No departments.", colspan="4"))]), cls="tbl")
    return _title("Departments", f"{len(deps)} departments"), Div(tbl, cls="card")


# ---------- leave -----------------------------------------------------------

def _apply_form():
    emps = db.employees_min()
    return Div(Div(H3("Apply for leave"), cls="card-header"),
               Form(
                   Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in emps],
                          name="employee_id", cls="hr-inp"),
                   Select(*[Option(t, value=t) for t in db.LEAVE_TYPES], name="leave_type", cls="hr-inp"),
                   Input(type="date", name="from_date", cls="hr-inp", required=True),
                   Input(type="date", name="to_date", cls="hr-inp", required=True),
                   Input(name="reason", placeholder="Reason", cls="hr-inp", style="flex:1;min-width:140px;"),
                   Button("Submit", cls="btn primary", type="submit"),
                   **{"hx-post": "/leave/apply", "hx-target": "#leave-main", "hx-swap": "innerHTML"},
                   cls="inline-form", style="flex-wrap:wrap;gap:8px;"),
               cls="card")


def leave_main(status="Pending"):
    seg = Div(*[A(s, href=f"/leave?status={s}", cls="" + ("active" if status == s else ""))
                for s in ["Pending", "All"] + db.LEAVE_STATUSES], cls="seg")
    clause, params = ("", ()) if status == "All" else ("WHERE lr.status=?", (status,))
    reqs = db.rows(f"""SELECT lr.*, e.first_name,e.last_name, d.name dept FROM leave_requests lr
                       JOIN employees e ON e.id=lr.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY (lr.status!='Pending'), lr.from_date DESC LIMIT 200""", params)
    rows_ = []
    for r in reqs:
        if r["status"] == "Pending":
            act = Div(Button("✓ Approve", cls="btn sm primary",
                             **{"hx-post": f"/leave/{r['id']}/approve", "hx-target": "#leave-main", "hx-swap": "innerHTML"}),
                      Button("✕", cls="btn sm", title="Reject",
                             **{"hx-post": f"/leave/{r['id']}/reject", "hx-target": "#leave-main", "hx-swap": "innerHTML"}),
                      style="display:flex;gap:4px;")
        else:
            act = Span("—", style="color:var(--text-mute);")
        rows_.append(Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "—"),
                        Td(_pill(r["leave_type"])),
                        Td(f"{r['from_date']} → {r['to_date']}", style="white-space:nowrap;"),
                        Td(str(r["days"]), cls="num"), Td(_pill(r["status"])), Td(act)))
    tbl = Table(Thead(Tr(Th("Employee"), Th("Dept"), Th("Type"), Th("Dates"), Th("Days", cls="num"), Th("Status"), Th("Action"))),
                Tbody(*rows_ or [Tr(Td("No requests.", colspan="7"))]), cls="tbl")
    return Div(_apply_form(), seg, Div(tbl, cls="card"))


def leave_list(status="Pending"):
    return _title("Leave requests"), Div(leave_main(status), id="leave-main")


# ---------- attendance ------------------------------------------------------

def attendance_view():
    today = db.TODAY.isoformat()
    reg = db.rows("""SELECT e.first_name,e.last_name,d.name dept,a.status,a.hours FROM attendance a
                     JOIN employees e ON e.id=a.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                     WHERE a.att_date=? ORDER BY a.status, e.first_name""", (today,))
    counts = {}
    for r in reg:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    kpis = Div(*[kpi_card(s, counts.get(s, 0)) for s in db.ATTEND_STATUSES[:4]], cls="kpi-grid")
    tbl = Table(Thead(Tr(Th("Employee"), Th("Department"), Th("Status"), Th("Hours", cls="num"))),
                Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "—"),
                           Td(_pill(r["status"])), Td(f"{r['hours']:.1f}" if r["hours"] else "—", cls="num"))
                        for r in reg] or [Tr(Td("No attendance records today.", colspan="4"))]), cls="tbl")
    return _title("Attendance", f"Today — {today}"), kpis, Div(Div(H3("Today's register"), cls="card-header"), tbl, cls="card")


# ---------- shifts and time clocks -----------------------------------------

def _week_start(value=None):
    try:
        day = db.date.fromisoformat(value) if value else db.TODAY
    except (TypeError, ValueError):
        day = db.TODAY
    return day - timedelta(days=day.weekday())


def shifts_roster(week=""):
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
                             Form(Button("Cancel", type="submit", cls="btn sm"), method="post",
                                  action=f"/shifts/{s['id']}/cancel") if s["status"] in ("Scheduled", "Missed") else None,
                             cls="note") for s in shifts] or [Span("—", cls="sub")]))
        rows_.append(Tr(Td(Strong(_name(emp))), *cells))
    table = Table(Thead(Tr(Th("Employee"), *[Th(f"{d:%a}<br>{d:%d %b}", cls="num") for d in days])),
                  Tbody(*rows_ or [Tr(Td("No shifts this week.", colspan="8"))]), cls="tbl")
    types = db.shift_types()
    emps = db.employees_min()
    form = Form(Select(*[Option(_name(e), value=str(e["id"])) for e in emps], name="employee_id", required=True, cls="hr-inp"),
                Select(*[Option(t["name"], value=str(t["id"])) for t in types], name="shift_type_id", required=True, cls="hr-inp"),
                Input(type="date", name="shift_date", value=db.TODAY.isoformat(), required=True, cls="hr-inp"),
                Input(name="location_label", placeholder="Location (e.g. Tallinn HQ)", cls="hr-inp"),
                Button("Create shift", type="submit", cls="btn primary"), method="post", action="/shifts/new")
    prev_week, next_week = (start - timedelta(days=7)).isoformat(), (start + timedelta(days=7)).isoformat()
    return (_title("Shifts & roster", f"Week of {start.isoformat()} — {end.isoformat()}",
                   A("← Previous", href=f"/shifts?week={prev_week}", cls="btn"),
                   A("Next →", href=f"/shifts?week={next_week}", cls="btn")),
            Div(Div(H3("Weekly roster"), cls="card-header"), table, cls="card"),
            Div(Div(H3("New shift"), P("Add a scheduled shift to the roster.", cls="sub"), cls="card-header"), form, cls="card"))


def time_clocks():
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
        return {"In": "Punched in", "Break Start": "On break", "Break End": "Punched in",
                "Out": "Punched out"}.get(kind, "Not clocked")

    board = Table(Thead(Tr(Th("Employee"), Th("State"), Th("Last punch"), Th("Source"))),
                  Tbody(*[Tr(Td(_name(e)), Td(_pill(state_for(e["id"]))),
                           Td(latest[e["id"]]["punched_at"] if e["id"] in latest else "—"),
                           Td(latest[e["id"]]["source"] if e["id"] in latest else "—")) for e in employees]
                  or [Tr(Td("No employees.", colspan="4"))]), cls="tbl")
    selector = Select(*[Option(_name(e), value=str(e["id"])) for e in employees], name="employee_id", required=True, cls="hr-inp")
    widget = Div(Form(selector, Input(type="hidden", name="source", value="Web"), Button("Clock in", type="submit", cls="btn primary"),
                      method="post", action="/timeclock/in"),
                 Form(Select(*[Option(_name(e), value=str(e["id"])) for e in employees], name="employee_id", required=True, cls="hr-inp"),
                      Button("Clock out", type="submit", cls="btn"), method="post", action="/timeclock/out"), cls="actions")
    recent = Table(Thead(Tr(Th("Employee"), Th("Type"), Th("When"), Th("Site"))),
                   Tbody(*[Tr(Td(_name(p)), Td(_pill(p["punch_type"])), Td(p["punched_at"]),
                              Td("On site" if p["on_site"] else ("Off site" if p["on_site"] == 0 else "—"))) for p in punches[:20]] or
                          [Tr(Td("No punches today.", colspan="4"))]), cls="tbl")
    gaps = db.auto_attendance_gap_report((db.TODAY - timedelta(days=7)).isoformat(), today)
    gap_list = [Tr(Td(_name(g)), Td(g["shift_date"]), Td(g["shift_name"])) for g in gaps]
    return (_title("Time clocks", f"Today's board — {today}"),
            Div(Div(H3("Clock now"), widget, cls="card-header"), P("Select an employee for this admin view."), cls="card"),
            Div(Div(H3("Today's clock board"), cls="card-header"), board, cls="card"),
            Div(Div(H3("Recent punches"), cls="card-header"), recent, cls="card"),
            Div(Div(H3("Auto-attendance gaps"), P("Scheduled shifts with no clock-in.", cls="sub"), cls="card-header"),
                Table(Thead(Tr(Th("Employee"), Th("Date"), Th("Shift"))), Tbody(*gap_list or [Tr(Td("No gaps found.", colspan="3"))]), cls="tbl"), cls="card"))


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
    return Div(Div(H3("New pay run"), P("Select a completed pay period and active employees.", cls="sub")),
               Form(Select(*[Option(p, value=p) for p in periods], name="period", required=True, cls="hr-inp"),
                    Div(*[Label(Input(type="checkbox", name="employee_ids", value=str(e["id"])),
                                f" {e['first_name']} {e['last_name']}", style="display:block;padding:3px 0;")
                         for e in emps], style="max-height:180px;overflow:auto;margin:10px 0;"),
                    Button("Create draft", type="submit", cls="btn primary"),
                    method="post", action="/payroll/runs/new"), cls="card")


def payroll_list(period="latest"):
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
        tbl = Table(Thead(Tr(Th("Employee"), Th("Department"), Th("Gross", cls="num"),
                             Th("Net", cls="num"), Th("Status"), Th(""))),
                    Tbody(*[Tr(Td(f"{p['first_name']} {p['last_name']}"), Td(p["dept"] or "—"),
                               Td(money(p["gross"]), cls="num"), Td(Strong(money(p["net"])), cls="num"),
                               Td(_pill(p["status"])), Td(A("View", href=f"/payroll/{p['id']}", cls="btn sm")))
                            for p in pays] or [Tr(Td("No payslips for this period.", colspan="6"))]), cls="tbl")
        return _title("Payroll", f"{period} — legacy payslips"), Div(tbl, cls="card")
    runs = db.pay_runs()
    tbl = Table(Thead(Tr(Th("Period"), Th("Status"), Th("Employees", cls="num"),
                         Th("Gross", cls="num"), Th("Net", cls="num"), Th(""))),
                Tbody(*[Tr(Td(A(r["period"], href=f"/payroll/runs/{r['id']}")),
                           Td(_pill(r["status"])), Td(str(r["headcount"]), cls="num"),
                           Td(money(r["gross_total"]), cls="num"), Td(Strong(money(r["net_total"])), cls="num"),
                           Td(A("Open", href=f"/payroll/runs/{r['id']}", cls="btn sm"),
                              A("TÖR eksport", href=f"/payroll/runs/{r['id']}/export/tor", cls="btn sm"),
                              A("TSD eksport", href=f"/payroll/runs/{r['id']}/export/tsd", cls="btn sm")))
                        for r in runs] or [Tr(Td("No pay runs yet.", colspan="6"))]), cls="tbl")
    return (_title("Pay runs", "Prepare, review, approve and pay monthly payroll.",
                   A("Ekspordi ajalugu", href="/payroll/exports", cls="btn"),
                   A("+ New pay run", href="#new-pay-run", cls="btn primary")),
            Div(tbl, cls="card"), Div(_pay_run_form(), id="new-pay-run"))


def pay_run_detail(rid, saved=False):
    run = db.pay_run(rid)
    if not run:
        return _title("Pay run not found"), P("No such pay run.")
    tbl = Table(Thead(Tr(Th("Employee"), Th("Department"), Th("Gross", cls="num"),
                         Th("Net", cls="num"), Th("Status"), Th(""))),
                Tbody(*[Tr(Td(Div(f"{p['first_name']} {p['last_name']}"),
                              *[Small(f"{line['kind']} · {line['label']}: {money(line['amount'])} · {line['base']}",
                                      style="display:block;color:var(--text-mute);font-size:11px;")
                                 for line in db.payslip_lines(p["id"])
                                 ]),
                           Td(p["dept"] or "—"),
                           Td(money(p["gross"]), cls="num"), Td(Strong(money(p["net"])), cls="num"),
                           Td(_pill(p["status"])), Td(A("Payslip", href=f"/payroll/{p['id']}", cls="btn sm")))
                        for p in run["payslips"]] or [Tr(Td("No payslips in this run.", colspan="6"))]), cls="tbl")
    next_status = db.PAY_RUN_TRANSITIONS.get(run["status"])
    advance = (Form(Button(f"Move to {next_status}", type="submit", cls="btn primary"),
                     method="post", action=f"/payroll/runs/{rid}/advance") if next_status else None)
    reprepare = (Form(Button("Re-prepare", type="submit", cls="btn"),
                      method="post", action=f"/payroll/runs/{rid}/reprepare")
                 if run["status"] == "Draft" else None)
    employer_cost_total = round(sum(float(line["amount"] or 0)
                                    for p in run["payslips"]
                                    for line in db.payslip_lines(p["id"])
                                    if (line["base"] or "").startswith("Employer cost")), 2)
    totals = Div(kpi_card("Gross total", money(sum(p["gross"] for p in run["payslips"]))),
                 kpi_card("Net total", money(sum(p["net"] for p in run["payslips"]))),
                 kpi_card("Employer costs", money(employer_cost_total)),
                 kpi_card("Employees", str(len(run["payslips"]))), cls="kpi-grid")
    offsets = db.rows("""SELECT a.id, a.reason, COALESCE(a.approved_amount,a.requested_amount) amount,
                                e.first_name||' '||e.last_name employee
                         FROM employee_advances a JOIN employees e ON e.id=a.employee_id
                         JOIN payslips p ON p.employee_id=a.employee_id AND p.run_id=?
                         WHERE a.status='Approved' AND a.offset_run_id IS NULL
                         ORDER BY e.first_name""", (rid,)) if run["status"] == "Draft" else []
    offset_card = Div(Div(H3("Approved advances to offset"),
                          P("Available only while this run is Draft.", style="color:var(--text-mute);font-size:12px;"),
                          cls="card-header"),
                      Table(Thead(Tr(Th("Employee"), Th("Reason"), Th("Amount", cls="num"), Th(""))),
                            Tbody(*[Tr(Td(a["employee"]), Td(a["reason"]), Td(money(a["amount"]), cls="num"),
                                       Td(Form(Button("Offset", type="submit", cls="btn sm primary"), method="post",
                                               action=f"/payroll/runs/{rid}/offset?advance_id={a['id']}"))) for a in offsets]
                                  or [Tr(Td("No approved advances are ready to offset.", colspan="4"))]), cls="tbl"), cls="card")
    actions = [A("← Pay runs", href="/payroll", cls="btn"),
               A("TÖR eksport", href=f"/payroll/runs/{rid}/export/tor", cls="btn"),
               A("TSD eksport", href=f"/payroll/runs/{rid}/export/tsd", cls="btn")]
    if reprepare:
        actions.append(reprepare)
    return (_title(f"Pay run · {run['period']}",
                   f"{len(run['payslips'])} employees · {money(sum(p['net'] for p in run['payslips']))} net",
                   *actions, advance),
            P("Pay run re-prepared and saved.", cls="flag") if saved else None,
            totals,
            Div(Div(H3("Payslips"), _pill(run["status"]), cls="card-header"), tbl, cls="card"),
            offset_card)


def statutory_exports_page():
    exports = db.rows("SELECT * FROM statutory_exports ORDER BY created_at DESC,id DESC")
    table = Table(Thead(Tr(Th("Tüüp"), Th("Periood"), Th("Fail"), Th("Read", cls="num"),
                         Th("Loodud"), Th(""))),
                  Tbody(*[Tr(Td(e["kind"]), Td(e["period"]), Td(e["file_name"]),
                           Td(str(e["row_count"]), cls="num"), Td(e["created_at"] or "—"),
                           Td(A("Lae alla", href=f"/payroll/exports/{e['id']}", cls="btn sm")))
                        for e in exports] or [Tr(Td("Ekspordi ajalugu on tühi.", colspan="6"))]), cls="tbl")
    return (_title("Ekspordi ajalugu", "TÖR-i ja TSD ekspordid."), Div(table, cls="card"))


def payslip_detail(pid):
    p = db.one("""SELECT p.*, e.first_name,e.last_name,e.designation,e.code,d.name dept FROM payslips p
                  JOIN employees e ON e.id=p.employee_id LEFT JOIN departments d ON d.id=e.dept_id WHERE p.id=?""", (pid,))
    if not p:
        return _title("Payslip not found"), P("No such payslip.")
    lines = db.payslip_lines(pid)
    if lines:
        earnings = [line for line in lines if line["kind"] == "Earning"]
        employer_costs = [line for line in lines
                          if line["kind"] == "Deduction"
                          and (line["base"] or "").startswith("Employer cost")]
        deductions = [line for line in lines
                      if line["kind"] == "Deduction" and line not in employer_costs]
        line_rows = [Tr(Td(Strong("Earnings")), Td(""))]
        line_rows += [Tr(Td(line["label"]), Td(money(line["amount"]), cls="num")) for line in earnings]
        line_rows += [Tr(Td(Strong("Deductions")), Td(""))]
        line_rows += [Tr(Td(line["label"]), Td("− " + money(line["amount"]), cls="num",
                                             style="color:var(--danger);")) for line in deductions]
        if employer_costs:
            line_rows += [Tr(Td(Strong(f"{t('et')['payroll_employer_costs']} / "
                                      f"{t('en')['payroll_employer_costs']}")), Td(""))]
            line_rows += [Tr(Td(line["label"]), Td(money(line["amount"]), cls="num"))
                          for line in employer_costs]
        line_rows += [Tr(Td(Strong("Net pay")), Td(Strong(money(p["net"])), cls="num"))]
    else:
        legacy = [("Gross pay", p["gross"], False), ("Income tax", p["tax"], True),
                  ("Pension", p["pension"], True), ("Other deductions", p["other_ded"], True),
                  ("Net pay", p["net"], False)]
        line_rows = [Tr(Td(Strong(label) if label in ("Gross pay", "Net pay") else label),
                        Td(Strong(money(amt)) if label == "Net pay" else
                           (("− " if neg else "") + money(amt)), cls="num",
                           style="color:var(--danger);" if neg else ""))
                     for label, amt, neg in legacy]
    body = Table(Tbody(*line_rows), cls="tbl")
    return (_title(f"Payslip — {p['first_name']} {p['last_name']}", f"{p['period']} · {p['designation']} · {p['dept']}",
                   A("← Payroll", href="/payroll", cls="btn")),
            Div(Div(Div(H3(f"{p['period']} payslip"), _pill(p["status"]), cls="card-header"), body, cls="card",
                    style="max-width:520px;")))


# ---------- expenses and travel --------------------------------------------

def _employee_select(name="employee_id"):
    return Select(*[Option(_name(e), value=str(e["id"])) for e in db.employees_min()],
                  name=name, required=True, cls="hr-inp")


def expenses_page():
    summary = db.expenses_summary()
    cats = db.expense_categories()
    claims = db.open_expenses()
    advances = db.open_advances()
    claim_rows = []
    for c in claims:
        actions = []
        if c["status"] == "Submitted":
            actions = [Form(Button("Approve", type="submit", cls="btn sm primary"), method="post", action=f"/expenses/{c['id']}/decide?decision=Approved") ,
                        Form(Button("Reject", type="submit", cls="btn sm"), method="post",
                             action=f"/expenses/{c['id']}/decide?decision=Rejected")]
        elif c["status"] == "Approved":
            actions = [Form(Button("Reimburse", type="submit", cls="btn sm primary"), method="post", action=f"/expenses/{c['id']}/reimburse")]
        claim_rows.append(Tr(Td(f"{c['first_name']} {c['last_name']}"), Td(c["category"]),
                             Td(c["claim_date"]), Td(c["description"]), Td(money(c["amount"]), cls="num"),
                             Td(_pill(c["status"])), Td(*actions, cls="actions")))
    claim_form = Form(_employee_select(),
                      Select(*[Option(cat["name"], value=str(cat["id"])) for cat in cats], name="category_id", required=True, cls="hr-inp"),
                      Input(type="date", name="claim_date", value=db.TODAY.isoformat(), required=True, cls="hr-inp"),
                      Input(type="number", name="amount", min="0", step="0.01", placeholder="Amount", required=True, cls="hr-inp"),
                      Input(name="description", placeholder="What was this for?", required=True, cls="hr-inp"),
                      Input(type="number", name="tax_rate", min="0", max="1", step="0.01", value="0.22", title="Tax rate", cls="hr-inp"),
                      Button("Save claim", type="submit", cls="btn primary"), method="post", action="/expenses/new")
    adv_rows = [Tr(Td(f"{a['first_name']} {a['last_name']}"), Td(a["reason"]),
                   Td(money(a["requested_amount"])), Td(_pill(a["status"])),
                   Td(Form(Button("Approve", type="submit", cls="btn sm primary"), method="post", action=f"/expenses/advance/{a['id']}/decide?decision=Approved"))) for a in advances]
    advance_form = Form(_employee_select(), Input(type="number", name="requested_amount", min="0", step="0.01", placeholder="Amount", required=True, cls="hr-inp"),
                        Input(name="reason", placeholder="Reason", required=True, cls="hr-inp"),
                        Button("Request advance", type="submit", cls="btn primary"), method="post", action="/expenses/advance/new")
    return (_title("Expenses & advances", "Claims, approvals and employee advances.", A("Travel →", href="/travel", cls="btn")),
            Div(kpi_card("Pending total", money(summary["pending_total"])),
                kpi_card("Approved this month", money(summary["approved_this_month"])),
                kpi_card("Advances outstanding", money(summary["advances_outstanding"])), cls="kpi-grid"),
            Div(Div(H3("Expense claims"), cls="card-header"),
                Table(Thead(Tr(Th("Employee"), Th("Category"), Th("Date"), Th("Description"), Th("Amount", cls="num"), Th("Status"), Th(""))),
                      Tbody(*claim_rows or [Tr(Td("No open claims.", colspan="7"))]), cls="tbl"), cls="card"),
            Div(Div(H3("New claim"), cls="card-header"), claim_form, cls="card"),
            Div(Div(H3("Employee advances"), cls="card-header"),
                Table(Thead(Tr(Th("Employee"), Th("Reason"), Th("Amount"), Th("Status"), Th(""))),
                      Tbody(*adv_rows or [Tr(Td("No open advances.", colspan="5"))]), cls="tbl"), advance_form, cls="card"))


def travel_page():
    requests = db.open_travel()
    rows_ = []
    for t in requests:
        actions = []
        if t["status"] == "Submitted":
            for label, decision in (("Approve", "Approved"), ("Reject", "Rejected"), ("Return", "Returned")):
                actions.append(Form(Button(label, type="submit", cls="btn sm"), method="post", action=f"/travel/{t['id']}/decide?decision={decision}"))
        elif t["status"] == "Returned":
            actions.append(Form(Button("Resubmit", type="submit", cls="btn sm primary"), method="post", action=f"/travel/{t['id']}/decide?decision=Resubmit"))
        rows_.append(Tr(Td(f"{t['first_name']} {t['last_name']}"), Td(t["destination"]),
                        Td(f"{t['from_date']} → {t['to_date']}"), Td(t["purpose"]),
                        Td(money(t["estimated_cost"])), Td(_pill(t["status"])), Td(*actions)))
    form = Form(_employee_select(), Input(name="destination", placeholder="Destination", required=True, cls="hr-inp"),
                Input(name="purpose", placeholder="Purpose", required=True, cls="hr-inp"),
                Input(type="date", name="from_date", required=True, cls="hr-inp"), Input(type="date", name="to_date", required=True, cls="hr-inp"),
                Input(type="number", name="estimated_cost", min="0", step="0.01", placeholder="Estimated cost", required=True, cls="hr-inp"),
                Input(type="number", name="advance_requested", min="0", step="0.01", value="0", placeholder="Advance", cls="hr-inp"),
                Button("Submit request", type="submit", cls="btn primary"), method="post", action="/travel/new")
    return (_title("Travel requests", "Plan and approve employee travel.", A("← Expenses", href="/expenses", cls="btn")),
            Div(Div(H3("Travel requests"), cls="card-header"),
                Table(Thead(Tr(Th("Employee"), Th("Destination"), Th("Dates"), Th("Purpose"), Th("Estimate"), Th("Status"), Th(""))),
                      Tbody(*rows_ or [Tr(Td("No travel requests.", colspan="7"))]), cls="tbl"), cls="card"),
            Div(Div(H3("New travel request"), cls="card-header"), form, cls="card"))
