"""Lifecycle renderers — onboarding, internal changes, separations, cases, org chart."""
from __future__ import annotations

import json

from fasthtml.common import (
    Div, H3, H4, P, Span, A, Ul, Li, Table, Thead, Tbody, Tr, Th, Td, Form, Input,
    Button, Select, Option, Textarea, Small, Strong, Label, NotStr,
)

import db
import people
from web.layout import kpi_card, money
from web.views import _pill, _title


def _kpis():
    k = people.lifecycle_kpis()
    return Div(kpi_card("Onboarding", k["onboarding"], f"{k['overdue_tasks']} overdue tasks",
                        tone="warn" if k["overdue_tasks"] else ""),
               kpi_card("Pending changes", k["pending_changes"], "awaiting approval",
                        tone="danger" if k["pending_changes"] else ""),
               kpi_card("Separations", k["separations"], "in progress"),
               kpi_card("Open cases", k["open_cases"], f"{k['alumni']} alumni",
                        tone="warn" if k["open_cases"] else ""),
               cls="kpi-grid")


# ---------- onboarding ------------------------------------------------------

def onboarding_page():
    board = people.onboarding_board()
    rows = []
    for b in board:
        pct = round(100 * (b["done"] or 0) / b["total"]) if b["total"] else 0
        rows.append(Tr(
            Td(A(b["name"], href=f"/lifecycle/onboarding/{b['id']}"),
               Div(b["designation"] or "", style="font-size:11.5px;color:var(--text-mute);")),
            Td(b["dept"] or "—"),
            Td(b["date_of_joining"] or "—", style="white-space:nowrap;color:var(--text-mute);"),
            Td(f"{b['done']} / {b['total']}", cls="num"),
            Td(Div(NotStr(f'<i style="width:{max(2, pct)}%"></i>'),
                   cls="bar" + (" warn" if b["overdue"] else ""))),
            Td(Span(str(b["overdue"]), cls="pill rejected") if b["overdue"]
               else Span("—", style="color:var(--text-mute);")),
            Td(_pill(b["status"]))))
    tbl = Table(Thead(Tr(Th("New hire"), Th("Department"), Th("Start date"), Th("Tasks", cls="num"),
                         Th("Progress"), Th("Overdue"), Th("Status"))),
                Tbody(*rows or [Tr(Td("Nobody is onboarding right now.", colspan="7"))]), cls="tbl")
    return (_title("Onboarding", "Checklists started automatically when an offer is accepted"),
            _kpis(), Div(Div(H3("In progress"), cls="card-header"), tbl, cls="card"))


def onboarding_detail(employee_id: int):
    e = db.employee(employee_id)
    if not e:
        return _title("Employee not found"), P("No such employee.")
    return (_title(f"Onboarding — {e['first_name']} {e['last_name']}",
                   f"{e['designation'] or ''} · started {e['date_of_joining'] or '—'}".strip(" ·"),
                   A("← Onboarding", href="/lifecycle/onboarding", cls="btn")),
            Div(checklist(employee_id), id="onb-body"))


def checklist(employee_id: int):
    tasks = people.onboarding_tasks(employee_id)
    done = sum(1 for t in tasks if t["status"] == "Done")
    items = []
    for t in tasks:
        late = t["status"] == "Open" and (t["due_date"] or "9999") < db.TODAY.isoformat()
        items.append(Div(
            Button("✓" if t["status"] == "Done" else "○",
                   cls="btn sm" + (" primary" if t["status"] == "Done" else ""),
                   title="Toggle",
                   **{"hx-post": f"/lifecycle/onboarding/task/{t['id']}"
                                 f"?status={'Open' if t['status'] == 'Done' else 'Done'}",
                      "hx-target": "#onb-body", "hx-swap": "innerHTML"}),
            Span(t["title"], cls="lbl"),
            _pill(t["owner_role"] or "HR"),
            Span(("due " + (t["due_date"] or "—")) if t["status"] != "Done"
                 else ("done " + (t["completed_on"] or "")),
                 cls="due" + (" late" if late else "")),
            cls="check" + (" done" if t["status"] == "Done" else "")))
    pct = round(100 * done / len(tasks)) if tasks else 0
    return Div(Div(Div(H3(f"Checklist — {done} of {len(tasks)} complete"),
                       Span(f"{pct}%", cls="pill ok" if pct == 100 else "pill"), cls="card-header"),
                   Div(NotStr(f'<i style="width:{max(2, pct)}%"></i>'), cls="bar",
                       style="margin-bottom:12px;"),
                   *items or [P("No checklist for this employee.", style="color:var(--text-mute);")],
                   cls="card"))


# ---------- internal changes ------------------------------------------------

def changes_page(status="All"):
    cs = people.changes(status)
    seg = Div(*[A(s, href=f"/lifecycle/changes?status={s}", cls="active" if status == s else "")
                for s in ["All", "Pending", "Applied", "Rejected"]], cls="seg")

    rows = []
    for c in cs:
        try:
            to_vals = json.loads(c["to_json"] or "{}")
            from_vals = json.loads(c["from_json"] or "{}")
        except json.JSONDecodeError:
            to_vals, from_vals = {}, {}
        delta = ", ".join(f"{k}: {from_vals.get(k) or '—'} → {v}" for k, v in to_vals.items())
        actions = (Div(Button("✓ Approve", cls="btn sm primary",
                              **{"hx-post": f"/lifecycle/changes/{c['id']}/approve",
                                 "hx-target": "#changes", "hx-swap": "innerHTML"}),
                       Button("✕", cls="btn sm", title="Reject",
                              **{"hx-post": f"/lifecycle/changes/{c['id']}/reject",
                                 "hx-target": "#changes", "hx-swap": "innerHTML"}),
                       style="display:flex;gap:4px;")
                   if c["status"] == "Pending" else Span("—", style="color:var(--text-mute);"))
        rows.append(Tr(Td(A(c["employee"], href=f"/employees/{c['employee_id']}")),
                       Td(c["dept"] or "—"), Td(_pill(c["change_type"])),
                       Td(c["effective_date"] or "—", style="white-space:nowrap;"),
                       Td(Small(delta or "—")), Td(_pill(c["status"])), Td(actions)))
    tbl = Table(Thead(Tr(Th("Employee"), Th("Dept"), Th("Change"), Th("Effective"),
                         Th("From → to"), Th("Status"), Th("Action"))),
                Tbody(*rows or [Tr(Td("No changes recorded.", colspan="7"))]), cls="tbl")
    return (_title("Internal changes",
                   "Promotions, transfers and role changes — approved, effective-dated and audited"),
            _kpis(), _change_form(), seg, Div(Div(tbl, cls="card"), id="changes"))


def changes_table(status="All"):
    return changes_page(status)[4].children[0]


def _change_form():
    emps = db.employees_min()
    depts = db.rows("SELECT id, name FROM departments ORDER BY name")
    return Div(Div(H3("Propose a change"), cls="card-header"),
               Form(Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="employee_id", cls="hr-inp"),
                    Select(*[Option(t, value=t) for t in people.CHANGE_TYPES],
                           name="change_type", cls="hr-inp"),
                    Input(type="date", name="effective_date", cls="hr-inp", required=True),
                    Input(name="designation", placeholder="New job title", cls="hr-inp",
                          style="min-width:150px;"),
                    Select(Option("— keep department —", value="0"),
                           *[Option(d["name"], value=str(d["id"])) for d in depts],
                           name="dept_id", cls="hr-inp"),
                    Input(name="base_salary", type="number", step="any",
                          placeholder="New salary", cls="hr-inp", style="width:130px;"),
                    Button("Propose", cls="btn primary", type="submit"),
                    method="post", action="/lifecycle/changes",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")


# ---------- separations -----------------------------------------------------

def separations_page(status="All"):
    seps = people.separations(status)
    seg = Div(*[A(s, href=f"/lifecycle/separations?status={s}", cls="active" if status == s else "")
                for s in ["All", "Open", "In progress", "Complete"]], cls="seg")
    tbl = Table(Thead(Tr(Th("Employee"), Th("Dept"), Th("Type"), Th("Notice"), Th("Last day"),
                         Th("Reason"), Th("Status"))),
                Tbody(*[Tr(Td(A(s["employee"], href=f"/lifecycle/separations/{s['id']}")),
                           Td(s["dept"] or "—"), Td(_pill(s["kind"])),
                           Td(s["notice_date"] or "—", style="white-space:nowrap;"),
                           Td(s["last_day"] or "—", style="white-space:nowrap;"),
                           Td(Small(s["reason"] or "—")), Td(_pill(s["status"])))
                        for s in seps] or [Tr(Td("No separations recorded.", colspan="7"))]),
                cls="tbl")
    emps = db.employees_min()
    form = Div(Div(H3("Record a leaver"), cls="card-header"),
               Form(Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="employee_id", cls="hr-inp"),
                    Select(*[Option(k, value=k) for k in people.SEPARATION_KINDS],
                           name="kind", cls="hr-inp"),
                    Input(type="date", name="notice_date", cls="hr-inp", required=True),
                    Input(type="date", name="last_day", cls="hr-inp", required=True),
                    Input(name="reason", placeholder="Reason", cls="hr-inp", style="flex:1;"),
                    Button("Start", cls="btn primary", type="submit"),
                    method="post", action="/lifecycle/separations",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")
    return (_title("Separations", "Notice, handover, exit interview and alumni status"),
            _kpis(), form, seg, Div(tbl, cls="card"))


def separation_detail(sep_id: int):
    s = people.separation(sep_id)
    if not s:
        return _title("Separation not found"), P("No such record.")
    info = Div(Div(H3("Leaver"), _pill(s["status"]), cls="card-header"),
               Div(Span("Employee", cls="k"), Span(s["employee"]),
                   Span("Role", cls="k"), Span(s["designation"] or "—"),
                   Span("Department", cls="k"), Span(s["dept"] or "—"),
                   Span("Type", cls="k"), _pill(s["kind"]),
                   Span("Notice given", cls="k"), Span(s["notice_date"] or "—"),
                   Span("Last day", cls="k"), Span(s["last_day"] or "—"),
                   Span("Reason", cls="k"), Span(s["reason"] or "—"),
                   Span("Alumni", cls="k"), Span(s["alumni_status"] or "—"),
                   cls="kv"), cls="card")
    exit_form = Div(Div(H3("Exit interview"), cls="card-header"),
                    Form(Textarea(s["exit_interview"] or "", name="notes", cls="prompt-box",
                                  style="min-height:150px;",
                                  placeholder="What worked, what didn't, would they return?"),
                         Div(Select(Option("— sentiment —", value=""),
                                    *[Option(x, value=x) for x in
                                      ("Positive", "Mixed", "Negative")],
                                    name="sentiment", cls="hr-inp",
                                    selected=s["exit_sentiment"]),
                             Button("Save", cls="btn primary", type="submit"),
                             style="display:flex;gap:8px;margin-top:10px;"),
                         method="post", action=f"/lifecycle/separations/{sep_id}/exit"),
                    cls="card")
    return (_title(f"Separation — {s['employee']}", f"{s['kind']} · last day {s['last_day'] or '—'}",
                   A("← Separations", href="/lifecycle/separations", cls="btn")),
            Div(Div(Div(exit_checklist(sep_id), id="sep-body"), exit_form), Div(info),
                cls="detail-grid"))


def exit_checklist(sep_id: int):
    s = people.separation(sep_id)
    try:
        items = json.loads((s or {}).get("checklist_json") or "[]")
    except json.JSONDecodeError:
        items = []
    done = sum(1 for i in items if i.get("done"))
    pct = round(100 * done / len(items)) if items else 0
    return Div(Div(Div(H3(f"Offboarding — {done} of {len(items)}"),
                       Span(f"{pct}%", cls="pill ok" if pct == 100 else "pill"), cls="card-header"),
                   Div(NotStr(f'<i style="width:{max(2, pct)}%"></i>'), cls="bar",
                       style="margin-bottom:12px;"),
                   *[Div(Button("✓" if it.get("done") else "○",
                                cls="btn sm" + (" primary" if it.get("done") else ""),
                                **{"hx-post": f"/lifecycle/separations/{sep_id}/task/{idx}",
                                   "hx-target": "#sep-body", "hx-swap": "innerHTML"}),
                         Span(it.get("title", ""), cls="lbl"),
                         cls="check" + (" done" if it.get("done") else ""))
                     for idx, it in enumerate(items)]
                   or [P("No checklist.", style="color:var(--text-mute);")],
                   cls="card"))


def alumni_page():
    al = people.alumni()
    tbl = Table(Thead(Tr(Th("Name"), Th("Last role"), Th("Department"), Th("Left"),
                         Th("Reason"), Th("Rehire"))),
                Tbody(*[Tr(Td(A(f"{a['first_name']} {a['last_name']}", href=f"/employees/{a['id']}")),
                           Td(a["designation"] or "—"), Td(a["dept"] or "—"),
                           Td(a["last_day"] or a["termination_date"] or "—",
                              style="white-space:nowrap;"),
                           Td(_pill(a["kind"] or "—")),
                           Td(_pill(a["alumni_status"] or "Eligible")))
                        for a in al] or [Tr(Td("No alumni yet.", colspan="6"))]), cls="tbl")
    return (_title("Alumni", "Former colleagues — the cheapest source of a good hire"),
            Div(Div(H3(f"{len(al)} alumni"), cls="card-header"), tbl, cls="card"))


# ---------- cases -----------------------------------------------------------

def cases_page(status="All"):
    cs = people.cases(status)
    seg = Div(*[A(s, href=f"/lifecycle/cases?status={s}", cls="active" if status == s else "")
                for s in ["All"] + people.CASE_STATUSES], cls="seg")
    rows = []
    for c in cs:
        actions = Div(*[Button(s, cls="btn sm" + (" primary" if s == "Resolved" else ""),
                               **{"hx-post": f"/lifecycle/cases/{c['id']}/status?status={s}",
                                  "hx-target": "#cases", "hx-swap": "innerHTML"})
                        for s in ("Investigating", "Resolved") if s != c["status"]],
                      style="display:flex;gap:4px;") if c["status"] in ("Open", "Investigating") \
            else Span("—", style="color:var(--text-mute);")
        rows.append(Tr(Td(A(c["employee"] or "— confidential —",
                            href=f"/employees/{c['employee_id']}") if c["employee_id"]
                          else Span("— confidential —", style="color:var(--text-mute);")),
                       Td(_pill(c["kind"])),
                       Td(Span(c["severity"],
                               cls="pill " + {"Critical": "rejected", "High": "pending"}.get(
                                   c["severity"], ""))),
                       Td(Small(c["summary"])),
                       Td(_pill(c["visibility"])), Td(_pill(c["status"])), Td(actions)))
    tbl = Table(Thead(Tr(Th("Employee"), Th("Type"), Th("Severity"), Th("Summary"),
                         Th("Visibility"), Th("Status"), Th("Action"))),
                Tbody(*rows or [Tr(Td("No cases open.", colspan="7"))]), cls="tbl")
    emps = db.employees_min()
    form = Div(Div(H3("Open a case"), cls="card-header"),
               Form(Select(Option("— confidential / unnamed —", value="0"),
                           *[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="employee_id", cls="hr-inp"),
                    Select(*[Option(k, value=k) for k in people.CASE_KINDS],
                           name="kind", cls="hr-inp"),
                    Select(*[Option(s, value=s, selected=(s == "Normal"))
                             for s in people.CASE_SEVERITIES], name="severity", cls="hr-inp"),
                    Select(*[Option(v, value=v) for v in
                             ("HR only", "HR and manager", "Restricted")],
                           name="visibility", cls="hr-inp"),
                    Input(name="summary", placeholder="Summary", cls="hr-inp", required=True,
                          style="flex:1;min-width:200px;"),
                    Button("Open", cls="btn primary", type="submit"),
                    method="post", action="/lifecycle/cases",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")
    return (_title("Employee relations",
                   "Grievances, wellbeing and conduct — restricted visibility, full audit trail"),
            _kpis(), form, seg, Div(Div(tbl, cls="card"), id="cases"))


def cases_table(status="All"):
    return cases_page(status)[4].children[0]


# ---------- org chart & scenarios -------------------------------------------

def org_page(dept_id: int = 0, delta: int = 0):
    tree = people.org_tree()
    depts = db.rows("SELECT id, name FROM departments ORDER BY name")
    scenario = people.headcount_scenario(dept_id or None, delta)

    def render(nodes):
        return Ul(*[Li(Div(Span(n["name"], cls="n"),
                           Span(f"· {n['designation'] or '—'}", cls="r"),
                           Span(str(n["team_size"]), cls="sz") if n["team_size"] else None,
                           cls="node"),
                       render(n["reports"]) if n["reports"] else None)
                    for n in nodes])

    scen_form = Form(
        Select(Option("Whole company", value="0"),
               *[Option(d["name"], value=str(d["id"]), selected=(dept_id == d["id"]))
                 for d in depts], name="dept_id", cls="hr-inp"),
        Input(type="number", name="delta", value=str(delta), cls="hr-inp", style="width:110px;",
              placeholder="+/- heads"),
        Button("Model it", cls="btn primary", type="submit"),
        method="get", action="/lifecycle/org", cls="inline-form", style="gap:8px;")

    scen = Div(Div(H3("Headcount scenario"), cls="card-header"), scen_form,
               Div(Span("Scope", cls="k"), Span(scenario["scope"]),
                   Span("Current headcount", cls="k"), Span(str(scenario["headcount"])),
                   Span("Average salary", cls="k"), Span(money(scenario["avg_salary"])),
                   Span("Change", cls="k"),
                   Span(f"{scenario['delta']:+d} people" if scenario["delta"] else "no change"),
                   Span("New headcount", cls="k"), Span(Strong(str(scenario["new_headcount"]))),
                   Span("Annual cost change", cls="k"),
                   Span(("+" if scenario["cost_change"] >= 0 else "− ")
                        + money(abs(scenario["cost_change"])),
                        style="color:var(--danger);" if scenario["cost_change"] > 0 else "color:var(--ok);"),
                   Span("New annual cost", cls="k"), Span(Strong(money(scenario["new_cost"]))),
                   cls="kv", style="margin-top:14px;"), cls="card")

    return (_title("Org chart", "Reporting lines, team sizes and what-if headcount planning"),
            Div(Div(Div(Div(H3("Reporting structure"), cls="card-header"),
                        Div(render(tree), cls="org"), cls="card")),
                Div(scen), cls="detail-grid"))
