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
from web.i18n import current_lang, t_app
from web.views import _pill, _title


def _c(key):
    return t_app(current_lang(), key)


def _kpis():
    k = people.lifecycle_kpis()
    return Div(kpi_card(_c("lc_onboarding"), k["onboarding"], _c("lc_kpi_overdue").format(n=k["overdue_tasks"]),
                        tone="warn" if k["overdue_tasks"] else ""),
               kpi_card(_c("lc_kpi_pending"), k["pending_changes"], _c("lc_kpi_awaiting"),
                        tone="danger" if k["pending_changes"] else ""),
               kpi_card(_c("lc_departures"), k["separations"], _c("lc_kpi_in_progress")),
               kpi_card(_c("lc_kpi_cases"), k["open_cases"], _c("lc_kpi_alumni").format(n=k["alumni"]),
                        tone="warn" if k["open_cases"] else ""),
               cls="kpi-grid")


# ---------- onboarding ------------------------------------------------------

def onboarding_page():
    c = _c
    board = people.onboarding_board()
    rows = []
    for b in board:
        pct = round(100 * (b["done"] or 0) / b["total"]) if b["total"] else 0
        rows.append(Tr(
            Td(A(b["name"], href=f"/lifecycle/onboarding/{b['id']}"),
               Div(b["designation"] or "", style="font-size:11.5px;color:var(--text-mute);")),
             Td(b["dept"] or _c("lc_missing")),
             Td(b["date_of_joining"] or _c("lc_missing"), style="white-space:nowrap;color:var(--text-mute);"),
            Td(f"{b['done']} / {b['total']}", cls="num"),
            Td(Div(NotStr(f'<i style="width:{max(2, pct)}%"></i>'),
                   cls="bar" + (" warn" if b["overdue"] else ""))),
            Td(Span(str(b["overdue"]), cls="pill rejected") if b["overdue"]
               else Span(_c("lc_missing"), style="color:var(--text-mute);")),
            Td(_pill(b["status"]))))
    tbl = Table(Thead(Tr(Th(c("lc_new_employee")), Th(c("table_department")), Th(c("lc_start")), Th(c("lc_tasks"), cls="num"),
                         Th(c("lc_progress")), Th(c("lc_overdue")), Th(c("lc_status")))),
                Tbody(*rows or [Tr(Td(c("lc_empty_onboarding"), colspan="7"))]), cls="tbl")
    return (_title(c("lc_onboarding"), c("lc_onboarding_subtitle")),
            _kpis(), Div(Div(H3(c("lc_in_progress")), cls="card-header"), tbl, cls="card"))


def onboarding_detail(employee_id: int):
    c = _c
    e = db.employee(employee_id)
    if not e:
        return _title(c("lc_employee_not_found")), P(c("lc_no_employee"))
    return (_title(f"Sisseelamine — {e['first_name']} {e['last_name']}",
                   f"{e['designation'] or ''} · alustas {e['date_of_joining'] or 'Puudub'}".strip(" ·"),
                   A(c("lc_back_onboarding"), href="/lifecycle/onboarding", cls="btn")),
            Div(checklist(employee_id), id="onb-body"))


def checklist(employee_id: int):
    c = _c
    tasks = people.onboarding_tasks(employee_id)
    done = sum(1 for t in tasks if t["status"] == "Done")
    items = []
    for t in tasks:
        late = t["status"] == "Open" and (t["due_date"] or "9999") < db.TODAY.isoformat()
        items.append(Div(
            Button("✓" if t["status"] == "Done" else "○",
                   cls="btn sm" + (" primary" if t["status"] == "Done" else ""),
                   title=c("lc_toggle"),
                   **{"hx-post": f"/lifecycle/onboarding/task/{t['id']}"
                                 f"?status={'Open' if t['status'] == 'Done' else 'Done'}",
                      "hx-target": "#onb-body", "hx-swap": "innerHTML"}),
            Span(t["title"], cls="lbl"),
            _pill(t["owner_role"] or "HR"),
             Span((c("lc_due") + " " + (t["due_date"] or c("lc_missing"))) if t["status"] != "Done"
                 else (c("lc_done") + " " + (t["completed_on"] or "")),
                 cls="due" + (" late" if late else "")),
            cls="check" + (" done" if t["status"] == "Done" else "")))
    pct = round(100 * done / len(tasks)) if tasks else 0
    return Div(Div(Div(H3(_c("lc_checklist").format(done=done, total=len(tasks))),
                       Span(f"{pct}%", cls="pill ok" if pct == 100 else "pill"), cls="card-header"),
                   Div(NotStr(f'<i style="width:{max(2, pct)}%"></i>'), cls="bar",
                       style="margin-bottom:12px;"),
                   *items or [P(_c("lc_no_checklist"), style="color:var(--text-mute);")],
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
        actions = (Div(Button(_c("lc_approve"), cls="btn sm primary",
                              **{"hx-post": f"/lifecycle/changes/{c['id']}/approve",
                                 "hx-target": "#changes", "hx-swap": "innerHTML"}),
                       Button(_c("lc_reject"), cls="btn sm", title=_c("lc_reject"),
                              **{"hx-post": f"/lifecycle/changes/{c['id']}/reject",
                                 "hx-target": "#changes", "hx-swap": "innerHTML"}),
                       style="display:flex;gap:4px;")
                   if c["status"] == "Pending" else Span("Puudub", style="color:var(--text-mute);"))
        rows.append(Tr(Td(A(c["employee"], href=f"/employees/{c['employee_id']}")),
                       Td(c["dept"] or "Puudub"), Td(_pill(c["change_type"])),
                       Td(c["effective_date"] or "Puudub", style="white-space:nowrap;"),
                       Td(Small(delta or "Puudub")), Td(_pill(c["status"])), Td(actions)))
    tbl = Table(Thead(Tr(Th(_c("table_employee")), Th(_c("table_department")), Th(_c("lc_change")), Th(_c("lc_effective_from")),
                         Th(_c("lc_from_to")), Th(_c("lc_status")), Th(_c("lc_action")))),
                Tbody(*rows or [Tr(Td(_c("lc_empty_changes"), colspan="7"))]), cls="tbl")
    return (_title(_c("lc_changes"), _c("lc_changes_subtitle")),
            _kpis(), _change_form(), seg, Div(Div(tbl, cls="card"), id="changes"))


def changes_table(status="All"):
    return changes_page(status)[4].children[0]


def _change_form():
    emps = db.employees_min()
    depts = db.rows("SELECT id, name FROM departments ORDER BY name")
    return Div(Div(H3(_c("lc_propose")), cls="card-header"),
               Form(Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="employee_id", cls="hr-inp", aria_label="Töötaja"),
                    Select(*[Option(t, value=t) for t in people.CHANGE_TYPES],
                           name="change_type", cls="hr-inp", aria_label="Muudatuse liik"),
                    Input(type="date", name="effective_date", cls="hr-inp", required=True,
                           aria_label=_c("lc_effective_from")),
                     Input(name="designation", placeholder=_c("lc_new_title"), cls="hr-inp",
                          style="min-width:150px;"),
                     Select(Option(_c("lc_keep_department"), value="0"),
                           *[Option(d["name"], value=str(d["id"])) for d in depts],
                           name="dept_id", cls="hr-inp", aria_label="Osakond"),
                    Input(name="base_salary", type="number", step="any",
                           placeholder=_c("lc_new_salary"), cls="hr-inp", style="width:130px;"),
                     Button(_c("lc_propose"), cls="btn primary", type="submit"),
                    method="post", action="/lifecycle/changes",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")


# ---------- separations -----------------------------------------------------

def separations_page(status="All"):
    seps = people.separations(status)
    seg = Div(*[A(s, href=f"/lifecycle/separations?status={s}", cls="active" if status == s else "")
                for s in ["All", "Open", "In progress", "Complete"]], cls="seg")
    tbl = Table(Thead(Tr(Th(_c("table_employee")), Th(_c("table_department")), Th(_c("lc_kind")), Th(_c("lc_notice")), Th(_c("lc_last_day")),
                         Th(_c("lc_reason")), Th(_c("lc_status")))),
                Tbody(*[Tr(Td(A(s["employee"], href=f"/lifecycle/separations/{s['id']}")),
                           Td(s["dept"] or _c("lc_missing")), Td(_pill(s["kind"])),
                           Td(s["notice_date"] or _c("lc_missing"), style="white-space:nowrap;"),
                           Td(s["last_day"] or _c("lc_missing"), style="white-space:nowrap;"),
                           Td(Small(s["reason"] or _c("lc_missing"))), Td(_pill(s["status"])))
                        for s in seps] or [Tr(Td(_c("lc_empty_departures"), colspan="7"))]),
                cls="tbl")
    emps = db.employees_min()
    form = Div(Div(H3(_c("lc_register_departure")), cls="card-header"),
               Form(Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="employee_id", cls="hr-inp", aria_label="Töötaja"),
                    Select(*[Option(k, value=k) for k in people.SEPARATION_KINDS],
                           name="kind", cls="hr-inp", aria_label=_c("lc_separation_kind")),
                    Input(type="date", name="notice_date", cls="hr-inp", required=True,
                          aria_label=_c("lc_notice_date")),
                    Input(type="date", name="last_day", cls="hr-inp", required=True,
                          aria_label=_c("lc_last_workday")),
                     Input(name="reason", placeholder=_c("lc_reason"), cls="hr-inp", style="flex:1;"),
                     Button(_c("lc_departure_start"), cls="btn primary", type="submit"),
                    method="post", action="/lifecycle/separations",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")
    return (_title(_c("lc_departures"), _c("lc_departures_subtitle")),
            _kpis(), form, seg, Div(tbl, cls="card"))


def separation_detail(sep_id: int):
    s = people.separation(sep_id)
    if not s:
        return _title(_c("lc_not_found")), P(_c("lc_no_record"))
    info = Div(Div(H3(_c("lc_departure")), _pill(s["status"]), cls="card-header"),
               Div(Span(_c("table_employee"), cls="k"), Span(s["employee"]),
                   Span("Roll", cls="k"), Span(s["designation"] or "Puudub"),
                   Span(_c("table_department"), cls="k"), Span(s["dept"] or _c("lc_missing")),
                   Span(_c("lc_kind"), cls="k"), _pill(s["kind"]),
                   Span(_c("lc_notified"), cls="k"), Span(s["notice_date"] or _c("lc_missing")),
                   Span(_c("lc_last_day"), cls="k"), Span(s["last_day"] or _c("lc_missing")),
                   Span(_c("lc_reason"), cls="k"), Span(s["reason"] or _c("lc_missing")),
                   Span(_c("lc_alumni"), cls="k"), Span(s["alumni_status"] or _c("lc_missing")),
                   cls="kv"), cls="card")
    exit_form = Div(Div(H3(_c("lc_exit_interview")), cls="card-header"),
                    Form(Textarea(s["exit_interview"] or "", name="notes", cls="prompt-box",
                                  style="min-height:150px;",
                                  placeholder=_c("lc_exit_prompt")),
                         Div(Select(Option("— meelsus —", value=""),
                                    *[Option(x, value=x) for x in
                                      ("Positive", "Mixed", "Negative")],
                                    name="sentiment", cls="hr-inp", aria_label=_c("lc_sentiment"),
                                    selected=s["exit_sentiment"]),
                              Button(_c("lc_save"), cls="btn primary", type="submit"),
                             style="display:flex;gap:8px;margin-top:10px;"),
                         method="post", action=f"/lifecycle/separations/{sep_id}/exit"),
                    cls="card")
    return (_title(f"Lahkumine — {s['employee']}", f"{s['kind']} · viimane päev {s['last_day'] or 'Puudub'}",
                   A("← Lahkumised", href="/lifecycle/separations", cls="btn")),
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
    return Div(Div(Div(H3(f"{_c('lc_departure')} — {done} / {len(items)}"),
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
                    or [P(_c("lc_empty_checklist"), style="color:var(--text-mute);")],
                   cls="card"))


def alumni_page():
    c = _c
    al = people.alumni()
    tbl = Table(Thead(Tr(Th(c("table_name")), Th(c("lc_last_role")), Th(c("table_department")), Th(c("lc_left")),
                         Th(c("lc_reason")), Th(c("lc_rehire")))),
                Tbody(*[Tr(Td(A(f"{a['first_name']} {a['last_name']}", href=f"/employees/{a['id']}")),
                           Td(a["designation"] or c("lc_missing")), Td(a["dept"] or c("lc_missing")),
                           Td(a["last_day"] or a["termination_date"] or c("lc_missing"),
                              style="white-space:nowrap;"),
                           Td(_pill(a["kind"] or "Puudub")),
                           Td(_pill(a["alumni_status"] or "Eligible")))
                        for a in al] or [Tr(Td(c("lc_empty_alumni"), colspan="6"))]), cls="tbl")
    return (_title(_c("lc_alumni"), _c("lc_alumni_subtitle")),
             Div(Div(H3(_c("lc_kpi_alumni").format(n=len(al))), cls="card-header"), tbl, cls="card"))


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
            else Span("Puudub", style="color:var(--text-mute);")
        rows.append(Tr(Td(A(c["employee"] or "— konfidentsiaalne —",
                            href=f"/employees/{c['employee_id']}") if c["employee_id"]
                          else Span("— konfidentsiaalne —", style="color:var(--text-mute);")),
                       Td(_pill(c["kind"])),
                       Td(Span(c["severity"],
                               cls="pill " + {"Critical": "rejected", "High": "pending"}.get(
                                   c["severity"], ""))),
                       Td(Small(c["summary"])),
                       Td(_pill(c["visibility"])), Td(_pill(c["status"])), Td(actions)))
    tbl = Table(Thead(Tr(Th(_c("table_employee")), Th(_c("lc_kind")), Th(_c("lc_severity")), Th(_c("lc_summary")),
                         Th(_c("lc_visibility")), Th(_c("lc_status")), Th(_c("lc_action")))),
                Tbody(*rows or [Tr(Td(_c("lc_open_cases"), colspan="7"))]), cls="tbl")
    emps = db.employees_min()
    form = Div(Div(H3(_c("lc_open_case")), cls="card-header"),
               Form(Select(Option(_c("lc_confidential"), value="0"),
                           *[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="employee_id", cls="hr-inp", aria_label="Töötaja"),
                    Select(*[Option(k, value=k) for k in people.CASE_KINDS],
                           name="kind", cls="hr-inp", aria_label=_c("lc_case_kind")),
                    Select(*[Option(s, value=s, selected=(s == "Normal"))
                             for s in people.CASE_SEVERITIES], name="severity", cls="hr-inp",
                           aria_label=_c("lc_severity")),
                    Select(*[Option(v, value=v) for v in
                             ("HR only", "HR and manager", "Restricted")],
                           name="visibility", cls="hr-inp", aria_label=_c("lc_visibility")),
                    Input(name="summary", placeholder=_c("lc_summary"), cls="hr-inp", required=True,
                          style="flex:1;min-width:200px;"),
                    Button(_c("lc_open"), cls="btn primary", type="submit"),
                    method="post", action="/lifecycle/cases",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")
    return (_title(_c("lc_cases"), _c("lc_cases_subtitle")),
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
        Select(Option("Kogu ettevõte", value="0"),
               *[Option(d["name"], value=str(d["id"]), selected=(dept_id == d["id"]))
                 for d in depts], name="dept_id", cls="hr-inp", aria_label="Osakond"),
        Input(type="number", name="delta", value=str(delta), cls="hr-inp", style="width:110px;",
              placeholder="+/- töötajat", aria_label="Töötajate muutus"),
        Button(_c("lc_model_button"), cls="btn primary", type="submit"),
        method="get", action="/lifecycle/org", cls="inline-form", style="gap:8px;")

    scen = Div(Div(H3("Töötajate stsenaarium"), cls="card-header"), scen_form,
               Div(Span("Ulatus", cls="k"), Span(scenario["scope"]),
                   Span("Hetke töötajate arv", cls="k"), Span(str(scenario["headcount"])),
                   Span("Keskmine palk", cls="k"), Span(money(scenario["avg_salary"])),
                   Span("Muutus", cls="k"),
                   Span(f"{scenario['delta']:+d} inimest" if scenario["delta"] else "muutusteta"),
                   Span("Uus töötajate arv", cls="k"), Span(Strong(str(scenario["new_headcount"]))),
                   Span("Aastase kulu muutus", cls="k"),
                   Span(("+" if scenario["cost_change"] >= 0 else "− ")
                        + money(abs(scenario["cost_change"])),
                        style="color:var(--danger);" if scenario["cost_change"] > 0 else "color:var(--ok);"),
                   Span("Uus aastakulu", cls="k"), Span(Strong(money(scenario["new_cost"]))),
                   cls="kv", style="margin-top:14px;"), cls="card")

    return (_title(_c("lc_org"), _c("lc_org_subtitle")),
            Div(Div(Div(Div(H3("Alluvusstruktuur"), cls="card-header"),
                        Div(render(tree), cls="org"), cls="card")),
                Div(scen), cls="detail-grid"))
