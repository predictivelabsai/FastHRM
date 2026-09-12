"""Center-pane renderers for FastHR."""
from __future__ import annotations

from datetime import timedelta

from fasthtml.common import (
    Div, H1, H3, P, Span, Small, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button, Select, Option, Label, NotStr, Strong,
    Script,
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
    pend_tbl = Table(Thead(Tr(Th("Töötaja"), Th("Liik"), Th("Kuupäevad"), Th("Päevad"), Th("Põhjus"))),
                     Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(_pill(r["leave_type"])),
                                Td(f"{r['from_date']} → {r['to_date']}", style="white-space:nowrap;"),
                                Td(str(r["days"]), cls="num"), Td(r["reason"]))
                              for r in pending] or [Tr(Td("Ootel taotlusi pole", colspan="5"))]), cls="tbl")
    leave_tbl = Table(Thead(Tr(Th("Täna puhkusel"), Th("Osakond"))),
                      Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "Puudub"))
                               for r in on_leave] or [Tr(Td("Täna pole keegi puhkusel.", colspan="2"))]), cls="tbl")

    return (
        _title("Töölaud", "Töötajad, tööaeg ja palgaarvestus ühel lehel."),
        Div(kpi_card("Töötajaid", k["headcount"], f"{k['depts']} osakonda"),
            kpi_card("Täna tööl", k["present_today"], f"{k['on_leave_today']} puhkusel"),
            kpi_card("Kohalolek (30 päeva)", f"{k['attendance_rate']}%", tone="warn" if k["attendance_rate"] < 85 else ""),
            kpi_card("Ootel puhkused", k["pending_leave"], "ootab kinnitamist", tone="danger" if k["pending_leave"] else ""),
            cls="kpi-grid"),
        Div(Div(Div(H3("Töötajate arv osakondade kaupa"), cls="card-header"), *funnel, cls="card"),
            Div(Div(H3("Täna puhkusel"), cls="card-header"), leave_tbl, cls="card"), cls="grid-2"),
        Div(Div(H3("Ootel puhkuse taotlused"), cls="card-header"), pend_tbl, cls="card"),
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
    tbl = Table(Thead(Tr(Th("Töötaja"), Th("Amet"), Th("Osakond"), Th("Üksus"), Th("Staatus"), Th("Tööle asumine"))),
                Tbody(*[Tr(
                    Td(A(_name(e), href=f"/employees/{e['id']}")),
                    Td(e["designation"] or "Puudub"), Td(e["dept"] or "Puudub"), Td(e["branch"] or "Puudub"),
                    Td(_pill(e["status"])), Td(e["date_of_joining"] or "Puudub", style="color:var(--text-mute);"))
                    for e in emps]), cls="tbl")
    search = Form(Input(type="search", name="q", value=q, placeholder="Otsi töötajaid…"),
                  Input(type="hidden", name="dept", value=dept), cls="toolbar", method="get", action="/employees")
    return _title("Töötajad", f"{len(emps)} kuvatud"), seg, search, Div(tbl, cls="card")


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
                            for p in pays]), cls="tbl")
    return (head, A("← Kõik töötajad", href="/employees", cls="btn"),
            Div(Div(info, Div(Div(H3("Palgalehed"), cls="card-header"), pay_tbl, cls="card")),
                Div(bal_card, att_card), cls="detail-grid", style="margin-top:14px;"))


def departments_list():
    deps = db.rows("""SELECT d.name, COUNT(e.id) n,
                      (SELECT m.first_name||' '||m.last_name FROM employees m
                       WHERE m.dept_id=d.id AND m.manager_id IS NULL LIMIT 1) lead,
                      COALESCE(SUM(e.base_salary),0) payroll
                      FROM departments d LEFT JOIN employees e ON e.dept_id=d.id
                      GROUP BY d.id ORDER BY n DESC""")
    tbl = Table(Thead(Tr(Th("Osakond"), Th("Juht"), Th("Töötajaid", cls="num"), Th("Aastane palgakulu", cls="num"))),
                Tbody(*[Tr(Td(Strong(d["name"])), Td(d["lead"] or "Puudub"), Td(str(d["n"]), cls="num"),
                           Td(money(d["payroll"]), cls="num")) for d in deps]), cls="tbl")
    return _title("Osakonnad", f"{len(deps)} osakonda"), Div(tbl, cls="card")


# ---------- leave -----------------------------------------------------------

def _apply_form():
    emps = db.employees_min()
    return Div(Div(H3("Puhkuse taotlus"), cls="card-header"),
               Form(
                   Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in emps],
                          name="employee_id", cls="hr-inp"),
                   Select(*[Option(t, value=t) for t in db.LEAVE_TYPES], name="leave_type", cls="hr-inp"),
                   Input(type="date", name="from_date", cls="hr-inp", required=True),
                   Input(type="date", name="to_date", cls="hr-inp", required=True),
                   Input(name="reason", placeholder="Põhjus", cls="hr-inp", style="flex:1;min-width:140px;"),
                   Button("Esita", cls="btn primary", type="submit"),
                   **{"hx-post": "/leave/apply", "hx-target": "#leave-main", "hx-swap": "innerHTML"},
                   cls="inline-form", style="flex-wrap:wrap;gap:8px;"),
               cls="card")


def leave_main(status="Pending"):
    seg = Div(*[A(s, href=f"/leave?status={s}", cls="" + ("active" if status == s else ""))
                for s in ["Pending", "All"] + [st for st in db.LEAVE_STATUSES if st != "Pending"]], cls="seg")
    clause, params = ("", ()) if status == "All" else ("WHERE lr.status=?", (status,))
    reqs = db.rows(f"""SELECT lr.*, e.first_name,e.last_name, d.name dept FROM leave_requests lr
                       JOIN employees e ON e.id=lr.employee_id LEFT JOIN departments d ON d.id=e.dept_id
                       {clause} ORDER BY (lr.status!='Pending'), lr.from_date DESC LIMIT 200""", params)
    rows_ = []
    for r in reqs:
        if r["status"] == "Pending":
            act = Div(Button("✓ Approve", cls="btn sm primary",
                             **{"hx-post": f"/leave/{r['id']}/approve", "hx-target": "#leave-main", "hx-swap": "innerHTML"}),
                      Button("✕ Reject", cls="btn sm", title="Reject",
                             **{"hx-post": f"/leave/{r['id']}/reject", "hx-target": "#leave-main", "hx-swap": "innerHTML"}),
                      style="display:flex;gap:4px;")
        else:
            act = Span("Puudub", style="color:var(--text-mute);")
        rows_.append(Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "Puudub"),
                        Td(_pill(r["leave_type"])),
                        Td(f"{r['from_date']} → {r['to_date']}", style="white-space:nowrap;"),
                        Td(str(r["days"]), cls="num"), Td(_pill(r["status"])), Td(act)))
    tbl = Table(Thead(Tr(Th("Töötaja"), Th("Osakond"), Th("Liik"), Th("Kuupäevad"), Th("Päevad", cls="num"), Th("Staatus"), Th("Tegevus"))),
                Tbody(*rows_ or [Tr(Td("Taotlusi pole.", colspan="7"))]), cls="tbl")
    return Div(_apply_form(), seg, Div(tbl, cls="card"))


def leave_list(status="Pending"):
    return _title("Puhkuse taotlused"), Div(leave_main(status), id="leave-main")


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
                Tbody(*[Tr(Td(f"{r['first_name']} {r['last_name']}"), Td(r["dept"] or "Puudub"),
                           Td(_pill(r["status"])), Td(f"{r['hours']:.1f}" if r["hours"] else "Puudub", cls="num"))
                        for r in reg]), cls="tbl")
    return _title("Kohalolek", f"Täna: {today}"), kpis, Div(Div(H3("Tänane register"), cls="card-header"), tbl, cls="card")


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
                             Form(Button("Tühista", type="submit", cls="btn sm"), method="post",
                                  action=f"/shifts/{s['id']}/cancel") if s["status"] in ("Scheduled", "Missed") else None,
                             cls="note") for s in shifts] or [Span("Puudub", cls="sub")]))
        rows_.append(Tr(Td(Strong(_name(emp))), *cells))
    table = Table(Thead(Tr(Th("Töötaja"), *[Th(f"{d:%a}<br>{d:%d %b}", cls="num") for d in days])),
                  Tbody(*rows_ or [Tr(Td("Sel nädalal vahetusi pole.", colspan="8"))]), cls="tbl")
    types = db.shift_types()
    emps = db.employees_min()
    form = Form(Select(*[Option(_name(e), value=str(e["id"])) for e in emps], name="employee_id", required=True, cls="hr-inp"),
                Select(*[Option(t["name"], value=str(t["id"])) for t in types], name="shift_type_id", required=True, cls="hr-inp"),
                Input(type="date", name="shift_date", value=db.TODAY.isoformat(), required=True, cls="hr-inp"),
                Input(name="location_label", placeholder="Asukoht, näiteks Tallinna kontor", cls="hr-inp"),
                Button("Loo vahetus", type="submit", cls="btn primary"), method="post", action="/shifts/new")
    prev_week, next_week = (start - timedelta(days=7)).isoformat(), (start + timedelta(days=7)).isoformat()
    return (_title("Vahetused ja töögraafik", f"Nädal: {start.isoformat()} kuni {end.isoformat()}",
                   A("← Eelmine", href=f"/shifts?week={prev_week}", cls="btn"),
                   A("Järgmine →", href=f"/shifts?week={next_week}", cls="btn")),
            Div(Div(H3("Nädala töögraafik"), cls="card-header"), table, cls="card"),
            Div(Div(H3("Uus vahetus"), P("Lisa graafikusse uus vahetus.", cls="sub"), cls="card-header"), form, cls="card"))


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
        return {"In": "Tööaeg alustatud", "Break Start": "Pausil", "Break End": "Tööaeg alustatud",
                "Out": "Tööaeg lõpetatud"}.get(kind, "Märge puudub")

    board = Table(Thead(Tr(Th("Töötaja"), Th("Olek"), Th("Viimane märge"), Th("Allikas"))),
                  Tbody(*[Tr(Td(_name(e)), Td(_pill(state_for(e["id"]))),
                           Td(latest[e["id"]]["punched_at"] if e["id"] in latest else "Puudub"),
                           Td(latest[e["id"]]["source"] if e["id"] in latest else "Puudub")) for e in employees]), cls="tbl")
    selector = Select(*[Option(_name(e), value=str(e["id"])) for e in employees], name="employee_id", required=True, cls="hr-inp")
    widget = Div(Form(selector, Input(type="hidden", name="source", value="Veeb"), Button("Alusta tööaega", type="submit", cls="btn primary"),
                      method="post", action="/timeclock/in"),
                 Form(Select(*[Option(_name(e), value=str(e["id"])) for e in employees], name="employee_id", required=True, cls="hr-inp"),
                      Button("Lõpeta tööaeg", type="submit", cls="btn"), method="post", action="/timeclock/out"), cls="actions")
    recent = Table(Thead(Tr(Th("Töötaja"), Th("Tüüp"), Th("Aeg"), Th("Asukoht"))),
                   Tbody(*[Tr(Td(_name(p)), Td(_pill(p["punch_type"])), Td(p["punched_at"]),
                              Td("Kohapeal" if p["on_site"] else ("Eemal" if p["on_site"] == 0 else "Puudub"))) for p in punches[:20]] or
                          [Tr(Td("Täna pole tööaja märkmeid.", colspan="4"))]), cls="tbl")
    gaps = db.auto_attendance_gap_report((db.TODAY - timedelta(days=7)).isoformat(), today)
    gap_list = [Tr(Td(_name(g)), Td(g["shift_date"]), Td(g["shift_name"])) for g in gaps]
    return (_title("Tööaja märkimine", f"Tänane ülevaade: {today}"),
            Div(Div(H3("Märgi tööaeg"), widget, cls="card-header"), P("Vali töötaja, kelle tööaega märgid."), cls="card"),
            Div(Div(H3("Tänane tööaja ülevaade"), cls="card-header"), board, cls="card"),
            Div(Div(H3("Viimased märked"), cls="card-header"), recent, cls="card"),
            Div(Div(H3("Puuduvad tööaja märked"), P("Graafikus on vahetus, kuid tööaega pole alustatud.", cls="sub"), cls="card-header"),
                Table(Thead(Tr(Th("Töötaja"), Th("Kuupäev"), Th("Vahetus"))), Tbody(*gap_list or [Tr(Td("Puudumisi ei leitud.", colspan="3"))]), cls="tbl"), cls="card"))


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
    return (_title("Uus palgaperiood", "Vali lõppenud periood ja aktiivsed töötajad.",
                   A("← Palgaperioodid", href="/payroll", cls="btn")),
            _pay_run_form())


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
        tbl = Table(Thead(Tr(Th("Töötaja"), Th("Osakond"), Th("Bruto", cls="num"),
                             Th("Netosumma", cls="num"), Th("Staatus"), Th(""))),
                    Tbody(*[Tr(Td(f"{p['first_name']} {p['last_name']}"), Td(p["dept"] or "Puudub"),
                               Td(money(p["gross"]), cls="num"), Td(Strong(money(p["net"])), cls="num"),
                               Td(_pill(p["status"])), Td(A("Vaata", href=f"/payroll/{p['id']}", cls="btn sm")))
                            for p in pays] or [Tr(Td("Selle perioodi palgalehti pole.", colspan="6"))]), cls="tbl")
        return _title("Palgaarvestus", f"{period} · vanad palgalehed"), Div(tbl, cls="card")
    runs = db.pay_runs()
    tbl = Table(Thead(Tr(Th("Periood"), Th("Staatus"), Th("Töötajaid", cls="num"),
                         Th("Bruto", cls="num"), Th("Netosumma", cls="num"), Th(""))),
                Tbody(*[Tr(Td(A(r["period"], href=f"/payroll/runs/{r['id']}")),
                           Td(_pill(r["status"])), Td(str(r["headcount"]), cls="num"),
                           Td(money(r["gross_total"]), cls="num"), Td(Strong(money(r["net_total"])), cls="num"),
                           Td(A("Ava", href=f"/payroll/runs/{r['id']}", cls="btn sm"),
                              A("TÖR eksport", href=f"/payroll/runs/{r['id']}/export/tor", cls="btn sm"),
                              A("TSD eksport", href=f"/payroll/runs/{r['id']}/export/tsd", cls="btn sm")))
                        for r in runs] or [Tr(Td("Palgaperioode pole veel.", colspan="6"))]), cls="tbl")
    return (_title("Palgaperioodid", "Koosta, kontrolli ja kinnita kuu palgaarvestus.",
                   A("Ekspordi ajalugu", href="/payroll/exports", cls="btn"),
                   A("+ Uus palgaperiood", href="/payroll/runs/new", cls="btn primary")),
            Div(tbl, cls="card"))


def pay_run_detail(rid, saved=False):
    run = db.pay_run(rid)
    if not run:
        return _title("Palgaperioodi ei leitud"), P("Sellist palgaperioodi pole.")
    tbl = Table(Thead(Tr(Th("Töötaja"), Th("Osakond"), Th("Bruto", cls="num"),
                         Th("Netosumma", cls="num"), Th("Staatus"), Th(""))),
                Tbody(*[Tr(Td(Div(f"{p['first_name']} {p['last_name']}"),
                              *[Small(f"{line['kind']} · {line['label']}: {money(line['amount'])} · {line['base']}",
                                      style="display:block;color:var(--text-mute);font-size:11px;")
                                 for line in db.payslip_lines(p["id"])
                                 ]),
                           Td(p["dept"] or "Puudub"),
                           Td(money(p["gross"]), cls="num"), Td(Strong(money(p["net"])), cls="num"),
                           Td(_pill(p["status"])), Td(A("Palgaleht", href=f"/payroll/{p['id']}", cls="btn sm")))
                        for p in run["payslips"]] or [Tr(Td("Selles perioodis palgalehti pole.", colspan="6"))]), cls="tbl")
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
    totals = Div(kpi_card("Bruto kokku", money(sum(p["gross"] for p in run["payslips"]))),
                 kpi_card("Netosumma kokku", money(sum(p["net"] for p in run["payslips"]))),
                 kpi_card("Tööandja kulud", money(employer_cost_total)),
                 kpi_card("Töötajaid", str(len(run["payslips"]))), cls="kpi-grid")
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
    actions = [A("← Palgaperioodid", href="/payroll", cls="btn"),
               A("TÖR eksport", href=f"/payroll/runs/{rid}/export/tor", cls="btn"),
               A("TSD eksport", href=f"/payroll/runs/{rid}/export/tsd", cls="btn")]
    if reprepare:
        actions.append(reprepare)
    return (_title(f"Palgaperiood · {run['period']}",
                   f"{len(run['payslips'])} töötajat · netosumma {money(sum(p['net'] for p in run['payslips']))}",
                   *actions, advance),
            P("Pay run re-prepared and saved.", cls="flag") if saved else None,
            totals,
            Div(Div(H3("Palgalehed"), _pill(run["status"]), cls="card-header"), tbl, cls="card"),
            offset_card)


def statutory_exports_page():
    exports = db.rows("SELECT * FROM statutory_exports ORDER BY created_at DESC,id DESC")
    table = Table(Thead(Tr(Th("Tüüp"), Th("Periood"), Th("Fail"), Th("Read", cls="num"),
                         Th("Loodud"), Th(""))),
                  Tbody(*[Tr(Td(e["kind"]), Td(e["period"]), Td(e["file_name"]),
                           Td(str(e["row_count"]), cls="num"), Td(e["created_at"] or "Puudub"),
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
        line_rows = [Tr(Td(Strong("Tulud")), Td(""))]
        line_rows += [Tr(Td(line["label"]), Td(money(line["amount"]), cls="num")) for line in earnings]
        line_rows += [Tr(Td(Strong("Mahaarvamised")), Td(""))]
        line_rows += [Tr(Td(line["label"]), Td("− " + money(line["amount"]), cls="num",
                                             style="color:var(--danger);")) for line in deductions]
        if employer_costs:
            line_rows += [Tr(Td(Strong(t("et")["payroll_employer_costs"])), Td(""))]
            line_rows += [Tr(Td(line["label"]), Td(money(line["amount"]), cls="num"))
                          for line in employer_costs]
        line_rows += [Tr(Td(Strong("Netosumma")), Td(Strong(money(p["net"])), cls="num"))]
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
    return (_title(f"Palgaleht: {p['first_name']} {p['last_name']}", f"{p['period']} · {p['designation']} · {p['dept']}",
                   A("← Palgaarvestus", href="/payroll", cls="btn")),
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
            actions = [Form(Button("Kinnita", type="submit", cls="btn sm primary"), method="post", action=f"/expenses/{c['id']}/decide?decision=Approved") ,
                        Form(Button("Lükka tagasi", type="submit", cls="btn sm"), method="post",
                             action=f"/expenses/{c['id']}/decide?decision=Rejected")]
        elif c["status"] == "Approved":
            actions = [Form(Button("Hüvita", type="submit", cls="btn sm primary"), method="post", action=f"/expenses/{c['id']}/reimburse")]
        claim_rows.append(Tr(Td(f"{c['first_name']} {c['last_name']}"), Td(c["category"]),
                             Td(c["claim_date"]), Td(c["description"]), Td(money(c["amount"]), cls="num"),
                             Td(_pill(c["status"])), Td(*actions, cls="actions")))
    claim_form = Form(_employee_select(),
                      Select(*[Option(cat["name"], value=str(cat["id"])) for cat in cats], name="category_id", required=True, cls="hr-inp"),
                      Input(type="date", name="claim_date", value=db.TODAY.isoformat(), required=True, cls="hr-inp"),
                      Input(type="number", name="amount", min="0", step="0.01", placeholder="Summa", required=True, cls="hr-inp"),
                      Input(name="description", placeholder="Mille eest kulu tekkis?", required=True, cls="hr-inp"),
                      Input(type="number", name="tax_rate", min="0", max="1", step="0.01", value="0.22", title="Maksumäär", cls="hr-inp"),
                      Button("Salvesta kulunõue", type="submit", cls="btn primary"), method="post", action="/expenses/new")
    adv_rows = [Tr(Td(f"{a['first_name']} {a['last_name']}"), Td(a["reason"]),
                   Td(money(a["requested_amount"])), Td(_pill(a["status"])),
                   Td(Form(Button("Approve", type="submit", cls="btn sm primary"), method="post", action=f"/expenses/advance/{a['id']}/decide?decision=Approved"))) for a in advances]
    advance_form = Form(_employee_select(), Input(type="number", name="requested_amount", min="0", step="0.01", placeholder="Summa", required=True, cls="hr-inp"),
                        Input(name="reason", placeholder="Põhjus", required=True, cls="hr-inp"),
                        Button("Taotle avanssi", type="submit", cls="btn primary"), method="post", action="/expenses/advance/new")
    return (_title("Kulud ja avansid", "Kulunõuded, kinnitused ja töötajatele antud avansid.", A("Lähetused →", href="/travel", cls="btn")),
            Div(kpi_card("Pending total", money(summary["pending_total"])),
                kpi_card("Approved this month", money(summary["approved_this_month"])),
                kpi_card("Advances outstanding", money(summary["advances_outstanding"])), cls="kpi-grid"),
            Div(Div(H3("Expense claims"), cls="card-header"),
                Table(Thead(Tr(Th("Töötaja"), Th("Kategooria"), Th("Kuupäev"), Th("Kirjeldus"), Th("Summa", cls="num"), Th("Staatus"), Th(""))),
                      Tbody(*claim_rows or [Tr(Td("Avatud kulunõudeid pole.", colspan="7"))]), cls="tbl"), cls="card"),
            Div(Div(H3("Uus kulunõue"), cls="card-header"), claim_form, cls="card"),
            Div(Div(H3("Töötajate avansid"), cls="card-header"),
                Table(Thead(Tr(Th("Töötaja"), Th("Põhjus"), Th("Summa"), Th("Staatus"), Th(""))),
                      Tbody(*adv_rows or [Tr(Td("Avatud avansse pole.", colspan="5"))]), cls="tbl"), advance_form, cls="card"))


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
