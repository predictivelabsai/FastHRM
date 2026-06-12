"""openhr — FastHTML app. Server-rendered HTML, HTMX for interactivity.

Run locally::

    openhr serve            # via CLI
    python -m openhr        # equivalent

or, programmatically:

    from openhr.app import app
    import uvicorn; uvicorn.run(app, host="127.0.0.1", port=5060)
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from fasthtml.common import (
    H1, H2, H3, H4, A, Button, Div, Form, Input, Label, Li, Option, P, Redirect, Script, Select,
    Span, Style, Table, Tbody, Td, Textarea, Th, Thead, Title, Titled, Tr, Ul, fast_app, serve,
)
from sqlalchemy.orm import Session

from . import repo
from .db import (
    Base, Department, Employee, EmployeeStatus, ExpenseStatus, LeaveKind, LeaveStatus,
    OnboardingTaskState, create_all, get_engine,
)

CSS = """
:root {
    --bg:#f5f7fa; --card:#ffffff; --text:#1a202c; --muted:#6c7989;
    --border:#dde3ea; --accent:#2f6be0; --accent-dark:#224a9d;
    --ok:#16a34a; --warn:#d97706; --err:#dc2626;
}
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       margin:0; background:var(--bg); color:var(--text); font-size:14px; line-height:1.45; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header.topbar { background:#0e1626; color:#fff; padding:12px 24px; display:flex; align-items:center; gap:24px; }
header.topbar h1 { margin:0; font-size:18px; letter-spacing:.02em; }
header.topbar nav { display:flex; gap:16px; }
header.topbar nav a { color:#b8c1d1; font-size:13px; }
header.topbar nav a.active, header.topbar nav a:hover { color:#fff; }
main { max-width:1180px; margin:0 auto; padding:24px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px; margin-bottom:20px; }
.card h2, .card h3 { margin-top:0; }
.grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; }
.kpi { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 18px; }
.kpi .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }
.kpi .value { font-size:24px; font-weight:600; margin-top:4px; }
table { width:100%; border-collapse:collapse; }
th { background:#eef2f7; text-align:left; padding:8px 10px; font-weight:600; font-size:12.5px; color:#4a5568; }
td { padding:8px 10px; border-top:1px solid var(--border); vertical-align:top; font-size:13px; }
tr:hover td { background:#f8fafc; }
.btn { display:inline-block; background:var(--accent); color:#fff; padding:7px 14px; border:0;
       border-radius:6px; cursor:pointer; font-size:13px; text-decoration:none; }
.btn:hover { background:var(--accent-dark); }
.btn.ghost { background:transparent; color:var(--muted); border:1px solid var(--border); }
.btn.ok { background:var(--ok); }
.btn.err { background:var(--err); }
.btn.sm { padding:4px 10px; font-size:12px; }
form.inline { display:inline; }
label { display:block; font-weight:600; font-size:12px; margin-top:10px; }
input, select, textarea { width:100%; padding:7px 9px; border:1px solid var(--border); border-radius:6px; font-family:inherit; font-size:13px; }
textarea { min-height:80px; }
.chip { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; background:#eef2f7; color:#4a5568; }
.chip.ok { background:#dcfce7; color:#166534; }
.chip.warn { background:#fef3c7; color:#92400e; }
.chip.err { background:#fee2e2; color:#991b1b; }
.chip.info { background:#dbeafe; color:#1e40af; }
.org-tree, .org-tree ul { list-style:none; padding-left:18px; margin:6px 0; border-left:2px solid var(--border); }
.org-tree li { padding:4px 0; }
.flex { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
.backend-chip { color:var(--muted); font-size:11px; }
"""

app, rt = fast_app(live=False, hdrs=(
    Style(CSS),
    Script(src="https://unpkg.com/htmx.org@1.9.12"),
))


def db() -> Session:
    return Session(get_engine())


def layout(title: str, *content, active: str = ""):
    def nav_link(name: str, href: str):
        cls = "active" if active == name else ""
        return A(name, href=href, cls=cls)
    return (
        Title(f"{title} — OpenHR"),
        Div(
            H1("OpenHR"),
            Div(
                nav_link("Dashboard", "/"),
                nav_link("Employees", "/employees"),
                nav_link("Org chart", "/org"),
                nav_link("Leave", "/leave"),
                nav_link("Attendance", "/attendance"),
                nav_link("Payroll", "/payroll"),
                nav_link("Expenses", "/expenses"),
                nav_link("Onboarding", "/onboarding"),
                cls="", style="display:flex;gap:16px;",
            ),
            cls="topbar",
        ),
        Div(*content, style="max-width:1180px; margin:0 auto; padding:24px;"),
    )


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------

@rt("/")
def dashboard():
    with db() as s:
        emps = repo.list_employees(s)
        active = [e for e in emps if e.status == EmployeeStatus.ACTIVE]
        on_leave = [e for e in emps if e.status == EmployeeStatus.ON_LEAVE]
        pending_leave = repo.list_leave_requests(s, status=LeaveStatus.PENDING)
        submitted_expenses = repo.list_expenses(s, status=ExpenseStatus.SUBMITTED)
        today = date.today()
        today_att = s.scalars(sa.select(sa.func.count()).select_from(sa.text(
            "attendance_records WHERE work_date = :d"
        )).params(d=today)).first()

    kpis = Div(
        Div(Div("Active employees", cls="label"), Div(str(len(active)), cls="value"), cls="kpi"),
        Div(Div("On leave today", cls="label"), Div(str(len(on_leave)), cls="value"), cls="kpi"),
        Div(Div("Pending leave requests", cls="label"), Div(str(len(pending_leave)), cls="value"), cls="kpi"),
        Div(Div("Expenses awaiting approval", cls="label"), Div(str(len(submitted_expenses)), cls="value"), cls="kpi"),
        Div(Div("Checked in today", cls="label"), Div(str(today_att or 0), cls="value"), cls="kpi"),
        cls="grid",
    )

    def row(items):
        return Tr(*[Td(x) for x in items])

    recent_leave = pending_leave[:8]
    leave_tbl = Table(
        Thead(Tr(Th("Employee"), Th("Kind"), Th("From"), Th("To"), Th("Days"), Th(""))),
        Tbody(*[Tr(
            Td(l.employee.full_name),
            Td(Span(l.kind.value, cls="chip info")),
            Td(l.from_date.isoformat()),
            Td(l.to_date.isoformat()),
            Td(f"{float(l.days):.1f}"),
            Td(A("review →", href=f"/leave/{l.id}")),
        ) for l in recent_leave]) if recent_leave else Tbody(Tr(Td("Nothing pending.", colspan="6"))),
    )

    return layout(
        "Dashboard",
        H2("Dashboard"),
        kpis,
        Div(H3("Pending leave approvals"), leave_tbl, cls="card"),
        active="Dashboard",
    )


# ------------------------------------------------------------
# Employees
# ------------------------------------------------------------

@rt("/employees")
def employees(search: str = "", status: str = "", department: str = ""):
    with db() as s:
        status_enum = EmployeeStatus(status) if status else None
        dept_id = int(department) if department else None
        items = repo.list_employees(s, status=status_enum, department_id=dept_id, search=search or None)
        departments = s.scalars(sa.select(Department).order_by(Department.name)).all()

    filter_form = Form(
        Input(name="search", value=search, placeholder="search name…", style="max-width:220px;"),
        Select(
            Option("any status", value="", selected=(not status)),
            *[Option(v.value, value=v.value, selected=(status == v.value)) for v in EmployeeStatus],
            name="status", style="max-width:160px;",
        ),
        Select(
            Option("any department", value="", selected=(not department)),
            *[Option(d.name, value=str(d.id), selected=(department == str(d.id))) for d in departments],
            name="department", style="max-width:200px;",
        ),
        Button("Filter", cls="btn sm"),
        method="get", action="/employees", cls="flex",
    )

    rows = [Tr(
        Td(A(e.full_name, href=f"/employees/{e.id}")),
        Td(e.job_title),
        Td(e.department.name if e.department else "—"),
        Td(e.manager.full_name if e.manager else "—"),
        Td(Span(e.status.value, cls=f"chip {'ok' if e.status == EmployeeStatus.ACTIVE else 'warn'}")),
        Td(e.email, style="font-family:ui-monospace,monospace; font-size:12px;"),
    ) for e in items]

    return layout(
        "Employees",
        H2(f"Employees ({len(items)})"),
        Div(filter_form, cls="card"),
        Div(
            Table(
                Thead(Tr(Th("Name"), Th("Title"), Th("Department"), Th("Manager"), Th("Status"), Th("Email"))),
                Tbody(*rows) if rows else Tbody(Tr(Td("No employees match.", colspan="6"))),
            ),
            cls="card",
        ),
        active="Employees",
    )


@rt("/employees/{emp_id:int}")
def employee_detail(emp_id: int):
    with db() as s:
        e = repo.get_employee(s, emp_id)
        if not e:
            return layout("Not found", H2(f"Employee #{emp_id} not found"))
        bal = repo.leave_balance(s, e)
        recent_leave = repo.list_leave_requests(s, employee_id=emp_id)[:10]
        recent_att = repo.list_attendance(s, emp_id)[:10]
        expenses = repo.list_expenses(s, employee_id=emp_id)[:10]
        payslips = repo.list_payslips(s, employee_id=emp_id)[:6]

    profile = Div(
        H2(e.full_name),
        P(f"{e.job_title} · {e.department.name if e.department else '—'}"),
        P(f"Manager: {e.manager.full_name if e.manager else '—'} · Started: {e.start_date}"),
        P(Span(e.status.value, cls=f"chip {'ok' if e.status == EmployeeStatus.ACTIVE else 'warn'}"),
          f" · Salary {e.currency} {float(e.base_salary_annual):,.0f}/yr",
          style="color:var(--muted);"),
        cls="card",
    )

    balance = Div(
        H3("Leave balance (this year)"),
        Div(
            Div(Div("Annual entitlement", cls="label"), Div(f"{bal['entitlement']}d", cls="value"), cls="kpi"),
            Div(Div("Annual taken", cls="label"), Div(f"{bal['taken_annual']:.1f}d", cls="value"), cls="kpi"),
            Div(Div("Annual remaining", cls="label"), Div(f"{bal['remaining_annual']:.1f}d", cls="value"), cls="kpi"),
            Div(Div("Sick days", cls="label"), Div(f"{bal['taken_sick']:.1f}d", cls="value"), cls="kpi"),
            cls="grid",
        ),
        cls="card",
    )

    def leave_row(lr):
        cls = {"approved": "ok", "rejected": "err", "pending": "warn"}.get(lr.status.value, "info")
        return Tr(
            Td(lr.from_date.isoformat()), Td(lr.to_date.isoformat()),
            Td(Span(lr.kind.value, cls="chip info")),
            Td(f"{float(lr.days):.1f}"),
            Td(Span(lr.status.value, cls=f"chip {cls}")),
        )
    leave_tbl = Table(
        Thead(Tr(Th("From"), Th("To"), Th("Kind"), Th("Days"), Th("Status"))),
        Tbody(*[leave_row(l) for l in recent_leave]) if recent_leave else Tbody(Tr(Td("No leave yet.", colspan="5"))),
    )

    att_tbl = Table(
        Thead(Tr(Th("Date"), Th("Check-in"), Th("Check-out"), Th("Hours"))),
        Tbody(*[Tr(
            Td(a.work_date.isoformat()),
            Td(a.check_in.strftime("%H:%M") if a.check_in else "—"),
            Td(a.check_out.strftime("%H:%M") if a.check_out else "—"),
            Td(f"{float(a.hours_worked):.1f}" if a.hours_worked else "—"),
        ) for a in recent_att]) if recent_att else Tbody(Tr(Td("No attendance yet.", colspan="4"))),
    )

    pay_tbl = Table(
        Thead(Tr(Th("Period"), Th("Gross"), Th("Tax"), Th("Pension"), Th("Net"))),
        Tbody(*[Tr(
            Td(f"{p.period_year}-{p.period_month:02d}"),
            Td(f"{p.currency} {float(p.gross):,.2f}"),
            Td(f"{float(p.tax):,.2f}"),
            Td(f"{float(p.pension):,.2f}"),
            Td(Span(f"{p.currency} {float(p.net):,.2f}", style="font-weight:600;")),
        ) for p in payslips]) if payslips else Tbody(Tr(Td("No payslips yet.", colspan="5"))),
    )

    exp_tbl = Table(
        Thead(Tr(Th("Date"), Th("Category"), Th("Amount"), Th("Status"))),
        Tbody(*[Tr(
            Td(x.claim_date.isoformat()),
            Td(x.category),
            Td(f"{x.currency} {float(x.amount):,.2f}"),
            Td(Span(x.status.value, cls="chip info")),
        ) for x in expenses]) if expenses else Tbody(Tr(Td("No claims.", colspan="4"))),
    )

    return layout(
        e.full_name,
        profile,
        balance,
        Div(H3("Recent leave"), leave_tbl, cls="card"),
        Div(H3("Recent attendance"), att_tbl, cls="card"),
        Div(H3("Payslips"), pay_tbl, cls="card"),
        Div(H3("Expense claims"), exp_tbl, cls="card"),
        active="Employees",
    )


# ------------------------------------------------------------
# Org chart
# ------------------------------------------------------------

@rt("/org")
def org_chart():
    with db() as s:
        tree = repo.org_tree(s)

        def render_node(node_tuple):
            emp, children = node_tuple
            badge = f" ({emp.department.code})" if emp.department else ""
            return Li(A(emp.full_name, href=f"/employees/{emp.id}"),
                      Span(f" — {emp.job_title}{badge}", style="color:var(--muted);"),
                      Ul(*[render_node(c) for c in children], cls="org-tree") if children else "")

        rendered = [render_node(root) for root in tree]

    return layout(
        "Org chart",
        Div(
            H2("Organisation chart"),
            Ul(*rendered, cls="org-tree") if rendered
            else P("No employees yet. Add one under /employees/new.", style="color:var(--muted);"),
            cls="card",
        ),
        active="Org chart",
    )


# ------------------------------------------------------------
# Leave
# ------------------------------------------------------------

@rt("/leave")
def leave_index(status: str = ""):
    with db() as s:
        status_enum = LeaveStatus(status) if status else None
        items = repo.list_leave_requests(s, status=status_enum)

    filter_bar = Div(
        *[A(x, href=f"/leave?status={x}" if x != "all" else "/leave",
            cls="chip info" if status == x or (x == "all" and not status) else "chip")
          for x in ("all", "pending", "approved", "rejected")],
        cls="flex",
    )

    rows = [Tr(
        Td(A(l.employee.full_name, href=f"/employees/{l.employee_id}")),
        Td(Span(l.kind.value, cls="chip info")),
        Td(l.from_date.isoformat()),
        Td(l.to_date.isoformat()),
        Td(f"{float(l.days):.1f}"),
        Td(Span(l.status.value, cls=f"chip {'ok' if l.status == LeaveStatus.APPROVED else 'warn' if l.status == LeaveStatus.PENDING else 'err'}")),
        Td(A("review", href=f"/leave/{l.id}", cls="btn sm ghost") if l.status == LeaveStatus.PENDING else ""),
    ) for l in items]

    return layout(
        "Leave",
        H2(f"Leave requests ({len(items)})"),
        Div(filter_bar, " ",
            A("+ New request", href="/leave/new", cls="btn sm"),
            cls="card flex"),
        Div(
            Table(
                Thead(Tr(Th("Employee"), Th("Kind"), Th("From"), Th("To"), Th("Days"), Th("Status"), Th(""))),
                Tbody(*rows) if rows else Tbody(Tr(Td("No requests match.", colspan="7"))),
            ),
            cls="card",
        ),
        active="Leave",
    )


@rt("/leave/new")
def leave_new_form():
    with db() as s:
        emps = repo.list_employees(s, status=EmployeeStatus.ACTIVE)
    return layout(
        "New leave request",
        Div(
            H2("New leave request"),
            Form(
                Label("Employee"),
                Select(*[Option(e.full_name, value=str(e.id)) for e in emps], name="employee_id"),
                Label("Kind"),
                Select(*[Option(k.value, value=k.value) for k in LeaveKind], name="kind"),
                Label("From"), Input(type="date", name="from_date", value=date.today().isoformat()),
                Label("To"), Input(type="date", name="to_date", value=date.today().isoformat()),
                Label("Reason"), Textarea(name="reason"),
                Div(Button("Submit", cls="btn"), " ", A("Cancel", href="/leave", cls="btn ghost"),
                    style="margin-top:12px;"),
                method="post", action="/leave/new",
            ),
            cls="card",
        ),
        active="Leave",
    )


@rt("/leave/new", methods=["POST"])
def leave_new_post(employee_id: int, kind: str, from_date: str, to_date: str, reason: str = ""):
    with db() as s:
        lr = repo.submit_leave(s, employee_id, LeaveKind(kind),
                               date.fromisoformat(from_date), date.fromisoformat(to_date), reason)
    return Redirect(f"/leave/{lr.id}")


@rt("/leave/{lid:int}")
def leave_detail(lid: int):
    with db() as s:
        lr = s.get(repo.LeaveRequest, lid)
        if not lr:
            return layout("Not found", H2(f"Leave #{lid} not found"))
        employee = lr.employee

    cls = {"approved": "ok", "rejected": "err", "pending": "warn"}.get(lr.status.value, "info")
    approve_form = Form(
        Button("Approve", cls="btn ok", name="approve", value="1"),
        Input(type="hidden", name="approver_id", value=str(employee.manager_id or employee.id)),
        method="post", action=f"/leave/{lid}/decide", cls="inline",
    ) if lr.status == LeaveStatus.PENDING else ""
    reject_form = Form(
        Button("Reject", cls="btn err", name="approve", value="0"),
        Input(type="hidden", name="approver_id", value=str(employee.manager_id or employee.id)),
        method="post", action=f"/leave/{lid}/decide", cls="inline",
    ) if lr.status == LeaveStatus.PENDING else ""

    return layout(
        "Leave detail",
        Div(
            A("← back", href="/leave"),
            H2(f"Leave #{lr.id}"),
            P(f"{employee.full_name} · ", Span(lr.kind.value, cls="chip info"), " · ",
              Span(lr.status.value, cls=f"chip {cls}")),
            P(f"From {lr.from_date} to {lr.to_date} · {float(lr.days):.1f} working day(s)"),
            P(f"Reason: {lr.reason or '—'}", style="white-space:pre-wrap;"),
            Div(approve_form, " ", reject_form, cls="flex", style="margin-top:16px;"),
            cls="card",
        ),
        active="Leave",
    )


@rt("/leave/{lid:int}/decide", methods=["POST"])
def leave_decide(lid: int, approver_id: int, approve: str):
    with db() as s:
        repo.decide_leave(s, lid, approver_id, approve == "1")
    return Redirect(f"/leave/{lid}")


# ------------------------------------------------------------
# Attendance
# ------------------------------------------------------------

@rt("/attendance")
def attendance_index():
    with db() as s:
        emps = repo.list_employees(s, status=EmployeeStatus.ACTIVE)
        today = date.today()
        today_records = {}
        for e in emps:
            recs = repo.list_attendance(s, e.id, since=today)
            if recs:
                today_records[e.id] = recs[0]

    rows = []
    for e in emps:
        rec = today_records.get(e.id)
        ci = rec.check_in.strftime("%H:%M") if rec and rec.check_in else "—"
        co = rec.check_out.strftime("%H:%M") if rec and rec.check_out else "—"
        action = ""
        if not rec or not rec.check_in:
            action = Form(Button("Check in", cls="btn sm ok"),
                          method="post", action=f"/attendance/{e.id}/check-in", cls="inline")
        elif not rec.check_out:
            action = Form(Button("Check out", cls="btn sm"),
                          method="post", action=f"/attendance/{e.id}/check-out", cls="inline")
        else:
            action = Span("done", cls="chip ok")
        rows.append(Tr(
            Td(A(e.full_name, href=f"/employees/{e.id}")),
            Td(e.job_title),
            Td(ci), Td(co),
            Td(f"{float(rec.hours_worked):.1f}" if rec and rec.hours_worked else "—"),
            Td(action),
        ))

    return layout(
        "Attendance",
        H2(f"Attendance — {today.isoformat()}"),
        Div(
            Table(
                Thead(Tr(Th("Employee"), Th("Title"), Th("Check-in"), Th("Check-out"), Th("Hours"), Th(""))),
                Tbody(*rows) if rows else Tbody(Tr(Td("No active employees.", colspan="6"))),
            ),
            cls="card",
        ),
        active="Attendance",
    )


@rt("/attendance/{emp_id:int}/check-in", methods=["POST"])
def attendance_check_in(emp_id: int):
    with db() as s:
        repo.check_in(s, emp_id)
    return Redirect("/attendance")


@rt("/attendance/{emp_id:int}/check-out", methods=["POST"])
def attendance_check_out(emp_id: int):
    with db() as s:
        repo.check_out(s, emp_id)
    return Redirect("/attendance")


# ------------------------------------------------------------
# Payroll
# ------------------------------------------------------------

@rt("/payroll")
def payroll_index(year: int = 0, month: int = 0):
    today = date.today()
    y = year or today.year
    m = month or today.month
    with db() as s:
        slips = repo.list_payslips(s, year=y)

    rows = [Tr(
        Td(A(p.employee.full_name, href=f"/employees/{p.employee_id}")),
        Td(f"{p.period_year}-{p.period_month:02d}"),
        Td(f"{p.currency} {float(p.gross):,.2f}"),
        Td(f"{float(p.tax):,.2f}"),
        Td(f"{float(p.pension):,.2f}"),
        Td(Span(f"{p.currency} {float(p.net):,.2f}", style="font-weight:600;")),
        Td(p.paid_at.isoformat() if p.paid_at else "—"),
    ) for p in slips]

    return layout(
        "Payroll",
        H2(f"Payroll {y}"),
        Div(
            Form(
                Input(type="number", name="year", value=str(y), style="max-width:100px;"),
                Input(type="hidden", name="month", value=str(m)),
                Button("Show", cls="btn sm"),
                method="get", action="/payroll", cls="flex",
            ),
            " ",
            Form(
                Input(type="number", name="year", value=str(y), style="max-width:90px;"),
                Input(type="number", name="month", value=str(m), min="1", max="12", style="max-width:70px;"),
                Button("Run payroll for period", cls="btn sm ok"),
                method="post", action="/payroll/run", cls="flex",
                style="margin-top:12px;",
            ),
            cls="card",
        ),
        Div(
            Table(
                Thead(Tr(Th("Employee"), Th("Period"), Th("Gross"), Th("Tax"), Th("Pension"), Th("Net"), Th("Paid"))),
                Tbody(*rows) if rows else Tbody(Tr(Td("No payslips.", colspan="7"))),
            ),
            cls="card",
        ),
        active="Payroll",
    )


@rt("/payroll/run", methods=["POST"])
def payroll_run(year: int, month: int):
    with db() as s:
        for e in repo.list_employees(s, status=EmployeeStatus.ACTIVE):
            existing = s.scalar(sa.select(repo.Payslip).where(
                repo.Payslip.employee_id == e.id,
                repo.Payslip.period_year == year,
                repo.Payslip.period_month == month,
            ))
            if existing:
                continue
            repo.create_payslip(s, e, year, month)
    return Redirect(f"/payroll?year={year}&month={month}")


# ------------------------------------------------------------
# Expenses
# ------------------------------------------------------------

@rt("/expenses")
def expenses_index(status: str = ""):
    with db() as s:
        status_enum = ExpenseStatus(status) if status else None
        items = repo.list_expenses(s, status=status_enum)

    rows = [Tr(
        Td(A(e.employee.full_name, href=f"/employees/{e.employee_id}")),
        Td(e.claim_date.isoformat()),
        Td(e.category),
        Td(f"{e.currency} {float(e.amount):,.2f}"),
        Td(Span(e.status.value, cls="chip info")),
        Td(A("review", href=f"/expenses/{e.id}", cls="btn sm ghost") if e.status == ExpenseStatus.SUBMITTED else ""),
    ) for e in items]

    filter_bar = Div(
        *[A(x, href=f"/expenses?status={x}" if x != "all" else "/expenses",
            cls="chip info" if status == x or (x == "all" and not status) else "chip")
          for x in ("all", "draft", "submitted", "approved", "reimbursed", "rejected")],
        cls="flex",
    )

    return layout(
        "Expenses",
        H2(f"Expense claims ({len(items)})"),
        Div(filter_bar, " ", A("+ New claim", href="/expenses/new", cls="btn sm"), cls="card flex"),
        Div(
            Table(
                Thead(Tr(Th("Employee"), Th("Date"), Th("Category"), Th("Amount"), Th("Status"), Th(""))),
                Tbody(*rows) if rows else Tbody(Tr(Td("No claims.", colspan="6"))),
            ),
            cls="card",
        ),
        active="Expenses",
    )


@rt("/expenses/new")
def expenses_new_form():
    with db() as s:
        emps = repo.list_employees(s, status=EmployeeStatus.ACTIVE)
    return layout(
        "New expense",
        Div(
            H2("New expense claim"),
            Form(
                Label("Employee"),
                Select(*[Option(e.full_name, value=str(e.id)) for e in emps], name="employee_id"),
                Label("Claim date"), Input(type="date", name="claim_date", value=date.today().isoformat()),
                Label("Category"),
                Select(*[Option(c, value=c) for c in ("travel", "meals", "accommodation", "supplies",
                                                       "training", "telecoms", "other")],
                       name="category"),
                Label("Amount"), Input(type="number", name="amount", step="0.01", value="0.00"),
                Label("Currency"),
                Select(*[Option(c, value=c) for c in ("EUR", "NOK", "SEK", "DKK", "GBP", "USD")],
                       name="currency"),
                Label("Description"), Textarea(name="description"),
                Label("Receipt URL (optional)"), Input(name="receipt_url"),
                Div(Button("Submit", cls="btn"), " ", A("Cancel", href="/expenses", cls="btn ghost"),
                    style="margin-top:12px;"),
                method="post", action="/expenses/new",
            ),
            cls="card",
        ),
        active="Expenses",
    )


@rt("/expenses/new", methods=["POST"])
def expenses_new_post(employee_id: int, claim_date: str, category: str, amount: str,
                      currency: str, description: str, receipt_url: str = ""):
    with db() as s:
        claim = repo.submit_expense(
            s, employee_id, claim_date=date.fromisoformat(claim_date),
            category=category, amount=Decimal(amount), currency=currency,
            description=description, receipt_url=receipt_url or None,
        )
    return Redirect(f"/expenses/{claim.id}")


@rt("/expenses/{eid:int}")
def expense_detail(eid: int):
    with db() as s:
        claim = s.get(repo.ExpenseClaim, eid)
        if not claim:
            return layout("Not found", H2(f"Expense #{eid} not found"))
        emp = claim.employee

    action = ""
    if claim.status == ExpenseStatus.SUBMITTED:
        action = Div(
            Form(Button("Approve", cls="btn ok"),
                 Input(type="hidden", name="approver_id", value=str(emp.manager_id or emp.id)),
                 Input(type="hidden", name="approve", value="1"),
                 method="post", action=f"/expenses/{eid}/decide", cls="inline"),
            " ",
            Form(Button("Reject", cls="btn err"),
                 Input(type="hidden", name="approver_id", value=str(emp.manager_id or emp.id)),
                 Input(type="hidden", name="approve", value="0"),
                 method="post", action=f"/expenses/{eid}/decide", cls="inline"),
            cls="flex", style="margin-top:16px;",
        )

    return layout(
        "Expense",
        Div(
            A("← back", href="/expenses"),
            H2(f"Expense #{claim.id} — {emp.full_name}"),
            P(f"{claim.claim_date} · {claim.category}"),
            P(f"Amount: {claim.currency} {float(claim.amount):,.2f}"),
            P(f"Description: {claim.description}", style="white-space:pre-wrap;"),
            P(A(claim.receipt_url, href=claim.receipt_url)) if claim.receipt_url else "",
            P(Span(claim.status.value, cls="chip info")),
            action,
            cls="card",
        ),
        active="Expenses",
    )


@rt("/expenses/{eid:int}/decide", methods=["POST"])
def expense_decide(eid: int, approver_id: int, approve: str):
    with db() as s:
        repo.decide_expense(s, eid, approver_id, approve == "1")
    return Redirect(f"/expenses/{eid}")


# ------------------------------------------------------------
# Onboarding
# ------------------------------------------------------------

@rt("/onboarding")
def onboarding_index():
    with db() as s:
        checklists = s.scalars(sa.select(repo.OnboardingChecklist).options(
            sa.orm.joinedload(repo.OnboardingChecklist.employee),
            sa.orm.joinedload(repo.OnboardingChecklist.tasks),
        )).unique().all()

    def progress(c):
        done = sum(1 for t in c.tasks if t.state == OnboardingTaskState.DONE)
        return f"{done}/{len(c.tasks)}"

    rows = [Tr(
        Td(A(c.employee.full_name, href=f"/employees/{c.employee_id}")),
        Td(c.employee.job_title),
        Td(c.started_at.date().isoformat()),
        Td(progress(c)),
        Td(Span("complete", cls="chip ok") if c.completed_at else Span("in progress", cls="chip warn")),
        Td(A("open", href=f"/onboarding/{c.id}", cls="btn sm ghost")),
    ) for c in checklists]

    return layout(
        "Onboarding",
        H2(f"Onboarding ({len(checklists)})"),
        Div(
            Table(
                Thead(Tr(Th("Employee"), Th("Title"), Th("Started"), Th("Tasks"), Th("Status"), Th(""))),
                Tbody(*rows) if rows else Tbody(Tr(Td("No onboarding checklists yet.", colspan="6"))),
            ),
            cls="card",
        ),
        active="Onboarding",
    )


@rt("/onboarding/{cid:int}")
def onboarding_detail(cid: int):
    with db() as s:
        cl = s.get(repo.OnboardingChecklist, cid)
        if not cl:
            return layout("Not found", H2(f"Checklist #{cid} not found"))

    def task_row(t):
        cls = {"done": "ok", "blocked": "err"}.get(t.state.value, "warn")
        complete_btn = Form(
            Button("mark done", cls="btn sm ok"),
            method="post", action=f"/onboarding/task/{t.id}/done", cls="inline",
        ) if t.state != OnboardingTaskState.DONE else ""
        return Tr(
            Td(t.title),
            Td(t.owner or "—"),
            Td(Span(t.state.value, cls=f"chip {cls}")),
            Td(t.completed_at.strftime("%Y-%m-%d") if t.completed_at else ""),
            Td(complete_btn),
        )

    return layout(
        f"Onboarding — {cl.employee.full_name}",
        Div(
            A("← back", href="/onboarding"),
            H2(f"Onboarding — {cl.employee.full_name}"),
            P(f"Started {cl.started_at.date()}"),
            Table(
                Thead(Tr(Th("Task"), Th("Owner"), Th("State"), Th("Completed"), Th(""))),
                Tbody(*[task_row(t) for t in cl.tasks]),
            ),
            cls="card",
        ),
        active="Onboarding",
    )


@rt("/onboarding/task/{tid:int}/done", methods=["POST"])
def onboarding_task_done(tid: int):
    with db() as s:
        task = repo.complete_task(s, tid)
    return Redirect(f"/onboarding/{task.checklist_id}")


# ------------------------------------------------------------
# Health + CLI
# ------------------------------------------------------------

@rt("/healthz")
def health():
    with db() as s:
        n = s.scalar(sa.select(sa.func.count()).select_from(Employee))
    return {"status": "ok", "employees": n, "time": datetime.utcnow().isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5060)
    ap.add_argument("--init-db", action="store_true", help="Create tables if missing and exit")
    ap.add_argument("--seed", action="store_true", help="Insert demo data (requires empty DB) and exit")
    args = ap.parse_args()

    if args.init_db or args.seed:
        create_all()
        if args.seed:
            from .seed import seed_demo
            seed_demo()
        print("Ready.")
        return 0

    create_all()
    print(f"OpenHR serving on http://{args.host}:{args.port}")
    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
