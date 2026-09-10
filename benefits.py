"""Benefits administration and employer contribution calculations."""
from __future__ import annotations

from datetime import date
import sqlite3

import db
from fasthtml.common import A, Button, Div, Form, H1, H3, Input, Option, P, Select, Table, Tbody, Td, Th, Thead, Tr

PLAN_CATEGORIES = ("health", "pension_extra", "sport", "commute", "other")


def list_plans(active_only: bool = False) -> list[dict]:
    where = "WHERE p.active=1" if active_only else ""
    return db.rows(
        """SELECT p.*, d.name AS department,
                  COUNT(CASE WHEN e.ended IS NULL THEN e.id END) AS enrolment_count
             FROM benefit_plans p
             LEFT JOIN departments d ON d.id=p.department_id
             LEFT JOIN benefit_enrolments e ON e.plan_id=p.id
             """ + where + " GROUP BY p.id ORDER BY p.active DESC, p.name", ())


def save_plan(name: str, category: str, employer_contribution: float = 0,
              contribution_frequency: str = "monthly", eligibility: str = "all_active",
              department_id: int | None = None, plan_id: int | None = None,
              active: int = 1) -> int:
    if category not in PLAN_CATEGORIES:
        raise ValueError("Unknown benefit category")
    if eligibility == "department" and not department_id:
        raise ValueError("Department eligibility requires a department")
    with db.cursor() as conn:
        if plan_id:
            conn.execute("""UPDATE benefit_plans SET name=?, category=?,
                           employer_contribution=?, contribution_frequency=?, eligibility=?,
                           department_id=?, active=? WHERE id=?""",
                         (name.strip(), category, float(employer_contribution or 0),
                          contribution_frequency, eligibility, department_id, active, plan_id))
            return plan_id
        return conn.execute("""INSERT INTO benefit_plans
                           (name, category, employer_contribution, contribution_frequency,
                            eligibility, department_id, active)
                           VALUES (?,?,?,?,?,?,?)""",
                           (name.strip(), category, float(employer_contribution or 0),
                            contribution_frequency, eligibility, department_id, active)).lastrowid


def deactivate_plan(plan_id: int) -> bool:
    with db.cursor() as conn:
        return bool(conn.execute("UPDATE benefit_plans SET active=0 WHERE id=?", (plan_id,)).rowcount)


def enrol(plan_id: int, employee_id: int, started: str | date | None = None,
          employee_contribution: float = 0) -> int:
    started_value = started.isoformat() if isinstance(started, date) else started
    with db.cursor() as conn:
        row = conn.execute("""SELECT id FROM benefit_enrolments
                             WHERE plan_id=? AND employee_id=?""", (plan_id, employee_id)).fetchone()
        if row:
            conn.execute("""UPDATE benefit_enrolments SET ended=NULL,
                           started=COALESCE(?, started), employee_contribution=? WHERE id=?""",
                         (started_value, float(employee_contribution or 0), row[0]))
            return row[0]
        return conn.execute("""INSERT INTO benefit_enrolments
                           (plan_id, employee_id, started, employee_contribution)
                           VALUES (?,?,?,?)""",
                           (plan_id, employee_id, started_value,
                            float(employee_contribution or 0))).lastrowid


def unenrol(plan_id: int, employee_id: int, ended: str | date | None = None) -> bool:
    ended_value = (ended or db.TODAY).isoformat() if isinstance(ended or db.TODAY, date) else (ended or db.TODAY.isoformat())
    with db.cursor() as conn:
        return bool(conn.execute("""UPDATE benefit_enrolments SET ended=?
                                  WHERE plan_id=? AND employee_id=? AND ended IS NULL""",
                                 (ended_value, plan_id, employee_id)).rowcount)


def enrolments_for(employee_id: int) -> list[dict]:
    return db.rows("""SELECT e.*, p.name, p.category, p.employer_contribution,
                           p.contribution_frequency, p.eligibility
                    FROM benefit_enrolments e JOIN benefit_plans p ON p.id=e.plan_id
                    WHERE e.employee_id=? ORDER BY e.started DESC, p.name""", (employee_id,))


def _active_enrolments(conn: sqlite3.Connection, period_start: str | date) -> list[dict]:
    start = period_start.isoformat() if isinstance(period_start, date) else str(period_start)
    return [dict(row) for row in conn.execute("""SELECT e.id AS enrolment_id, e.plan_id,
                    e.employee_id, e.started, e.ended, e.employee_contribution,
                    p.name, p.category, p.employer_contribution, p.contribution_frequency,
                    p.eligibility, p.department_id
             FROM benefit_enrolments e
             JOIN benefit_plans p ON p.id=e.plan_id AND p.active=1
             JOIN employees emp ON emp.id=e.employee_id AND emp.status='Active'
             WHERE (e.started IS NULL OR e.started <= ?)
               AND (e.ended IS NULL OR e.ended >= ?)
               AND (p.eligibility='all_active' OR p.department_id=emp.dept_id)
             ORDER BY emp.first_name, emp.last_name, p.name""", (start, start)).fetchall()]


def active_enrolments(period_start: str | date) -> list[dict]:
    with db.cursor() as conn:
        return _active_enrolments(conn, period_start)


def monthly_cost(conn: sqlite3.Connection, employee_id: int, period: str | date) -> list[dict]:
    """Return employer-cost lines for one employee and payroll period."""
    return [{"plan_id": row["plan_id"], "name": row["name"], "category": row["category"],
             "employer_amount": round(float(row["employer_contribution"] or 0), 2)}
            for row in _active_enrolments(conn, period)
            if row["employee_id"] == employee_id]


def staff_page(lang: str = "et"):
    et = lang != "en"
    title = "Soodustused" if et else "Benefits"
    plan_title = "Soodustused" if et else "Benefit plans"
    employees = db.rows("""SELECT e.id, e.first_name, e.last_name, d.name AS department
                           FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                           WHERE e.status='Active' ORDER BY e.first_name, e.last_name""")
    departments = db.rows("SELECT id, name FROM departments ORDER BY name")
    plans = list_plans()
    enrolments = {(row["employee_id"], row["plan_id"]): row
                  for employee in employees for row in enrolments_for(employee["id"])}
    form = Form(
        Input(name="name", placeholder="Soodustus" if et else "Benefit plan", required=True),
        Select(*[Option(category, value=category) for category in PLAN_CATEGORIES], name="category"),
        Input(name="employer_contribution", type="number", min="0", step="0.01",
              placeholder="Tööandja kulu" if et else "Employer contribution", required=True),
        Select(Option("Kuus" if et else "Monthly", value="monthly"),
               Option("Iga palgaarvestuse korral" if et else "Per pay run", value="per_payrun"),
               name="contribution_frequency"),
        Select(Option("Kõik aktiivsed" if et else "All active", value="all_active"),
               Option("Osakond" if et else "Department", value="department"), name="eligibility"),
        Select(Option("Kõik osakonnad" if et else "All departments", value="0"),
               *[Option(d["name"], value=str(d["id"])) for d in departments], name="department_id"),
        Button("Salvesta" if et else "Save", type="submit", cls="btn primary"),
        method="post", action="/benefits/plans", cls="inline-form")
    plan_rows = [Tr(Td(p["name"]), Td(p["category"]), Td(f"{p['employer_contribution']:,.2f} EUR"),
                    Td(str(p["enrolment_count"])),
                    Td(A("Keela" if et else "Deactivate", href=f"/benefits/plans/{p['id']}/deactivate", cls="btn sm")))
                 for p in plans]
    plan_table = Table(Thead(Tr(Th("Nimi" if et else "Name"), Th("Kategooria" if et else "Category"),
                               Th("Tööandja kulu" if et else "Employer contribution"),
                               Th("Registreerunud" if et else "Enrolled"), Th(""))),
                       Tbody(*plan_rows or [Tr(Td("Soodustusi pole." if et else "No benefit plans.", colspan="5"))]), cls="tbl")
    cells = []
    for employee in employees:
        row = [Td(f"{employee['first_name']} {employee['last_name']}")]
        for plan in plans:
            current = enrolments.get((employee["id"], plan["id"]))
            row.append(Td(Form(Input(type="hidden", name="plan_id", value=str(plan["id"])),
                             Input(type="hidden", name="employee_id", value=str(employee["id"])),
                             Input(type="hidden", name="action", value="unenrol" if current and not current["ended"] else "enrol"),
                             Input(type="checkbox", checked=bool(current and not current["ended"]),
                                   onchange="this.form.submit()", aria_label=f"{employee['first_name']} {plan['name']}"),
                             method="post", action="/benefits/enrol")))
        cells.append(Tr(*row))
    enrol_table = Table(Thead(Tr(Th("Töötaja" if et else "Employee"),
                                *[Th(plan["name"]) for plan in plans])),
                        Tbody(*(cells or [Tr(Td("Aktiivseid töötajaid pole." if et else "No active employees.",
                                                  colspan=str(len(plans) + 1))) ])), cls="tbl")
    return (Div(H1(title), P("Tööandjapoolsed soodustused: registreerimine ja kulu" if et else
                         "Eligibility, enrolment and employer contribution tracking", cls="sub"), cls="page-title"),
            Div(Div(H3(plan_title), form, cls="card-header"), plan_table, cls="card"),
            Div(Div(H3("Töötajate registreerimine" if et else "Employee enrolment"), cls="card-header"),
                enrol_table, cls="card"))
