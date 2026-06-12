"""Center-pane renderers for FastHR."""
from __future__ import annotations

from fasthtml.common import (
    Div, H1, H3, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button, Select, Option, NotStr, Strong,
)

import db
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
                    for e in emps]), cls="tbl")
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
                            for p in pays]), cls="tbl")
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
                           Td(money(d["payroll"]), cls="num")) for d in deps]), cls="tbl")
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
                        for r in reg]), cls="tbl")
    return _title("Attendance", f"Today — {today}"), kpis, Div(Div(H3("Today's register"), cls="card-header"), tbl, cls="card")


# ---------- payroll ---------------------------------------------------------

def payroll_list(period="latest"):
    periods = [r["period"] for r in db.rows("SELECT DISTINCT period FROM payslips ORDER BY period DESC")]
    if period == "latest" and periods:
        period = periods[0]
    seg = Div(*[A(p, href=f"/payroll?period={p}", cls="" + ("active" if period == p else "")) for p in periods], cls="seg")
    pays = db.rows("""SELECT p.*, e.first_name,e.last_name,d.name dept FROM payslips p
                      JOIN employees e ON e.id=p.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                      WHERE p.period=? ORDER BY p.net DESC""", (period,))
    total = sum(p["net"] for p in pays)
    tbl = Table(Thead(Tr(Th("Employee"), Th("Dept"), Th("Gross", cls="num"), Th("Tax", cls="num"),
                         Th("Net", cls="num"), Th("Status"), Th(""))),
                Tbody(*[Tr(Td(f"{p['first_name']} {p['last_name']}"), Td(p["dept"] or "—"),
                           Td(money(p["gross"]), cls="num"), Td(money(p["tax"]), cls="num"),
                           Td(Strong(money(p["net"])), cls="num"), Td(_pill(p["status"])),
                           Td(A("View", href=f"/payroll/{p['id']}", cls="btn sm")))
                        for p in pays]), cls="tbl")
    return (_title("Payroll", f"{period} — {len(pays)} payslips · {money(total)} net"), seg,
            Div(tbl, cls="card"))


def payslip_detail(pid):
    p = db.one("""SELECT p.*, e.first_name,e.last_name,e.designation,e.code,d.name dept FROM payslips p
                  JOIN employees e ON e.id=p.employee_id LEFT JOIN departments d ON d.id=e.dept_id WHERE p.id=?""", (pid,))
    if not p:
        return _title("Payslip not found"), P("No such payslip.")
    rows_ = [("Gross pay", p["gross"], False), ("Income tax", -p["tax"], True),
             ("Pension (5%)", -p["pension"], True), ("Other deductions", -p["other_ded"], True),
             ("Net pay", p["net"], False)]
    body = Table(Tbody(*[Tr(Td(Strong(label) if label in ("Gross pay", "Net pay") else label),
                            Td(Strong(money(abs(amt)) if not neg else "− " + money(abs(amt)))
                               if label == "Net pay" else (("− " if neg else "") + money(abs(amt))),
                               cls="num", style="color:var(--danger);" if neg else ""))
                         for label, amt, neg in rows_]), cls="tbl")
    return (_title(f"Payslip — {p['first_name']} {p['last_name']}", f"{p['period']} · {p['designation']} · {p['dept']}",
                   A("← Payroll", href="/payroll", cls="btn")),
            Div(Div(Div(H3(f"{p['period']} payslip"), _pill(p["status"]), cls="card-header"), body, cls="card",
                    style="max-width:520px;")))
