"""Workforce planning administration."""
from __future__ import annotations

import db
from fasthtml.common import *

STATUSES = ("Proposed", "Approved", "Rejected")


def list_budgets(status: str | None = None) -> list[dict]:
    query = """SELECT p.*, d.name department_name
               FROM position_budgets p LEFT JOIN departments d ON d.id=p.department_id"""
    params: tuple = ()
    if status in STATUSES:
        query += " WHERE p.status=?"
        params = (status,)
    return db.rows(query + " ORDER BY p.status, p.name", params)


def save_budget(name: str, department_id: int | None, role_title: str,
                headcount_target: int = 1, annual_salary_budget: float = 0,
                effective_date: str | None = None, notes: str = "",
                budget_id: int | None = None) -> int:
    if not name.strip() or not role_title.strip():
        raise ValueError("Budget name and role title are required")
    headcount_target = max(0, int(headcount_target))
    annual_salary_budget = float(annual_salary_budget)
    values = (name.strip(), department_id or None, role_title.strip(), headcount_target,
              annual_salary_budget, effective_date or None, notes.strip())
    with db.cursor() as conn:
        if budget_id:
            conn.execute("""UPDATE position_budgets SET name=?, department_id=?, role_title=?,
                           headcount_target=?, annual_salary_budget=?, effective_date=?, notes=?
                           WHERE id=?""", values + (budget_id,))
            return budget_id
        return conn.execute("""INSERT INTO position_budgets
            (name, department_id, role_title, headcount_target, annual_salary_budget,
             effective_date, notes) VALUES (?,?,?,?,?,?,?)""", values).lastrowid


def decide_budget(budget_id: int, decision: str) -> bool:
    if decision not in ("Approved", "Rejected"):
        return False
    with db.cursor() as conn:
        return bool(conn.execute("""UPDATE position_budgets SET status=?
                                  WHERE id=? AND status='Proposed'""",
                                 (decision, budget_id)).rowcount)


def scenarios() -> list[dict]:
    return db.rows("SELECT * FROM workforce_scenarios ORDER BY status, name")


def save_scenario(name: str, description: str = "", headcount_delta: int = 0,
                  annual_cost_delta: float = 0, scenario_id: int | None = None) -> int:
    if not name.strip():
        raise ValueError("Scenario name is required")
    values = (name.strip(), description.strip(), int(headcount_delta), float(annual_cost_delta))
    with db.cursor() as conn:
        if scenario_id:
            conn.execute("""UPDATE workforce_scenarios SET name=?, description=?,
                           headcount_delta=?, annual_cost_delta=? WHERE id=?""",
                         values + (scenario_id,))
            return scenario_id
        return conn.execute("""INSERT INTO workforce_scenarios
            (name, description, headcount_delta, annual_cost_delta) VALUES (?,?,?,?)""",
                            values).lastrowid


def decide_scenario(scenario_id: int, decision: str) -> bool:
    if decision not in ("Approved", "Rejected"):
        return False
    with db.cursor() as conn:
        return bool(conn.execute("""UPDATE workforce_scenarios SET status=?
                                  WHERE id=? AND status='Proposed'""",
                                 (decision, scenario_id)).rowcount)


def kpis() -> dict:
    return {
        "budgeted_headcount": db.scalar("SELECT COALESCE(SUM(headcount_target), 0) FROM position_budgets WHERE status='Approved'"),
        "proposed_headcount": db.scalar("SELECT COALESCE(SUM(headcount_target), 0) FROM position_budgets WHERE status='Proposed'"),
        "approved_salary_budget": db.scalar("SELECT COALESCE(SUM(annual_salary_budget), 0) FROM position_budgets WHERE status='Approved'"),
        "scenario_delta": db.scalar("SELECT COALESCE(SUM(headcount_delta), 0) FROM workforce_scenarios WHERE status='Approved'"),
    }


def staff_page(lang: str = "et"):
    et = lang != "en"
    labels = {"title": "Tööjõu planeerimine" if et else "Workforce planning",
              "budget": "Ametikoha eelarve" if et else "Position budget",
              "budgets": "Ametikohad" if et else "Positions",
              "scenarios": "Stsenaariumid" if et else "Scenarios",
              "approve": "Kinnita" if et else "Approve",
              "reject": "Keeldu" if et else "Reject",
              "save": "Salvesta" if et else "Save",
              "proposed": "Kavandatud" if et else "Proposed",
              "approved": "Heaks kiidetud" if et else "Approved",
              "rejected": "Keeldutud" if et else "Rejected"}
    departments = db.rows("SELECT id, name FROM departments ORDER BY name")
    budget_rows = list_budgets()
    scenario_rows = scenarios()
    k = kpis()
    subtitle = (f"{k['budgeted_headcount']} {labels['approved'].lower()} · "
                f"{k['proposed_headcount']} {labels['proposed'].lower()} · "
                f"{k['scenario_delta']} {('ametikohta' if et else 'scenario headcount')}"
                if et else
                f"{k['budgeted_headcount']} approved · {k['proposed_headcount']} proposed · "
                f"{k['scenario_delta']} scenario headcount")
    department_options = [Option(d["name"], value=str(d["id"])) for d in departments]
    budget_form = Form(Input(name="name", placeholder="Nimi / Name", required=True),
                       Select(Option("—", value=""), *department_options, name="department_id"),
                       Input(name="role_title", placeholder="Roll / Role title", required=True),
                       Input(type="number", name="headcount_target", value="1", min="0"),
                       Input(type="number", name="annual_salary_budget", value="0", min="0", step="0.01"),
                       Input(type="date", name="effective_date"),
                       Button(labels["save"], type="submit", cls="btn primary"),
                       method="post", action="/workforce/budgets", cls="inline-form")
    def status_pill(status):
        text = labels[status.lower()]
        return Span(text, cls=f"pill {status.lower()}")
    budget_rows_html = []
    for row in budget_rows:
        actions = (Div(A(labels["approve"], href=f"/workforce/budgets/{row['id']}/approve", cls="btn sm"),
                    A(labels["reject"], href=f"/workforce/budgets/{row['id']}/reject", cls="btn sm"))
                   if row["status"] == "Proposed" else "")
        budget_rows_html.append(Tr(Td(row["name"]), Td(row["department_name"] or "—"),
                                   Td(row["role_title"]), Td(row["headcount_target"]),
                                   Td(f"{row['annual_salary_budget']:,.2f}"),
                                   Td(row["effective_date"] or "—"),
                                   Td(status_pill(row["status"])), Td(actions)))
    headings = (["Nimi", "Osakond", "Roll", "Ametikohad", "Eelarve", "Kehtiv alates", "Staatus", ""]
                if et else ["Name", "Department", "Role title", "Headcount", "Budget", "Effective date", "Status", ""])
    budget_table = Table(Thead(Tr(*[Th(x) for x in headings])),
                         Tbody(*(budget_rows_html or [Tr(Td("Ametikohti pole." if et else "No positions yet.", colspan="8"))]),
                               cls="tbl"))
    scenario_form = Form(Input(name="name", placeholder="Nimi / Name", required=True),
                         Input(name="headcount_delta", type="number", value="0"),
                         Input(name="annual_cost_delta", type="number", value="0", step="0.01"),
                         Input(name="description", placeholder="Märkused / Notes"),
                         Button(labels["save"], type="submit", cls="btn primary"), method="post",
                         action="/workforce/scenarios", cls="inline-form")
    scenario_table = Table(Thead(Tr(Th("Nimi / Name"), Th("Muutus / Headcount"),
        Th("Kulu / Cost"), Th("Staatus / Status"), Th(""))), Tbody(*[
        Tr(Td(row["name"]), Td(row["headcount_delta"]), Td(f"{row['annual_cost_delta']:,.2f}"),
           Td(status_pill(row["status"])),
           Td(A(labels["approve"], href=f"/workforce/scenarios/{row['id']}/approve", cls="btn sm"),
              A(labels["reject"], href=f"/workforce/scenarios/{row['id']}/reject", cls="btn sm"))
           if row["status"] == "Proposed" else "")
        for row in scenario_rows] or [Tr(Td("Stsenaariume pole." if et else "No scenarios yet.", colspan="5"))]), cls="tbl")
    return Div(Div(H1(labels["title"]), P(subtitle, cls="sub"), cls="page-title"),
               Div(Div(H3(labels["budget"]), budget_form, budget_table, cls="card"),
                   Div(H3(labels["scenarios"]), scenario_form, scenario_table, cls="card"),
                   Div(H3(labels["budgets"]), P(f"{k['approved_salary_budget']:,.2f} € · {k['scenario_delta']} {labels['approved'].lower()}"), cls="card")))
