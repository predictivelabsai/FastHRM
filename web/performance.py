"""Performance renderers — goals/OKRs, continuous feedback, review cycles."""
from __future__ import annotations

from fasthtml.common import (
    Div, H3, H4, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button,
    Select, Option, Textarea, Small, Strong, Label,
)

import db
import people
import talent
from web.layout import kpi_card
from web.views import _pill, _title

TONE = {"On track": "", "Complete": "ok", "At risk": "warn", "Behind": "danger",
        "Cancelled": "cancelled"}


def _bar(pct, status=""):
    cls = "bar" + (" danger" if status == "Behind" else " warn" if status == "At risk" else "")
    return Div(Span(style=f"width:{max(2, min(100, pct))}%;display:block;height:100%;"), cls=cls)


def _progress(g):
    pct = people.goal_progress(g)
    cls = "bar" + (" danger" if g["status"] == "Behind" else
                   " warn" if g["status"] == "At risk" else "")
    return Div(Div(style=f"width:{max(2, min(100, pct))}%", cls=""), cls=cls)


def _goal_bar(g):
    pct = people.goal_progress(g)
    tone = ("danger" if g["status"] == "Behind" else "warn" if g["status"] == "At risk" else "")
    inner = f'<i style="width:{max(2, min(100, pct))}%"></i>'
    from fasthtml.common import NotStr
    return Div(NotStr(inner), cls=f"bar {tone}".strip())


# ---------- goals -----------------------------------------------------------

def goals_page(period="All", status="All", owner_type="All"):
    k = people.performance_kpis()
    periods = people.goal_periods()
    gs = people.goals(period=period, status=status, owner_type=owner_type)

    seg = Div(A("All periods", href="/performance/goals", cls="active" if period == "All" else ""),
              *[A(p, href=f"/performance/goals?period={p}", cls="active" if period == p else "")
                for p in periods], cls="seg")
    seg2 = Div(*[A(s, href=f"/performance/goals?period={period}&status={s}",
                   cls="active" if status == s else "")
                 for s in ["All"] + people.GOAL_STATUSES], cls="seg")

    rows = []
    for g in gs:
        pct = people.goal_progress(g)
        rows.append(Div(
            Div(Div(A(g["title"], href=f"/performance/goals/{g['id']}"), cls="t"),
                Div(f"{g['owner_name'] or '—'} · {g['metric'] or 'no metric'}"
                    + (f" · {g['period']}" if g["period"] else ""), cls="m")),
            _goal_bar(g),
            Div(f"{pct}%", cls="score-cell", style="text-align:right;"),
            Div(_pill(g["status"], TONE.get(g["status"], "")), style="text-align:right;"),
            cls="goal-row"))

    return (_title("Goals & OKRs", f"{len(gs)} shown — cascading company → team → individual"),
            Div(kpi_card("Active goals", k["goals"], f"{k['at_risk']} at risk or behind",
                         tone="warn" if k["at_risk"] else ""),
                kpi_card("Feedback (30d)", k["feedback_30d"], "pieces exchanged"),
                kpi_card("Open review cycles", k["open_cycles"], f"{k['reviews_due']} reviews due",
                         tone="danger" if k["reviews_due"] else ""),
                kpi_card("Alignment", sum(1 for g in gs if g["parent_goal_id"]),
                         "goals linked to a parent"),
                cls="kpi-grid"),
            seg, seg2,
            Div(_new_goal_form(), cls="card"),
            Div(Div(H3("Goals"), A("Alignment tree →", href="/performance/alignment",
                                   cls="btn sm"), cls="card-header"),
                Div(*rows) if rows else P("No goals match.", style="color:var(--text-mute);"),
                cls="card"))


def _new_goal_form():
    emps = db.employees_min()
    depts = db.rows("SELECT id, name FROM departments ORDER BY name")
    parents = db.rows("""SELECT id, title FROM goals WHERE owner_type IN ('company','department')
                         ORDER BY owner_type, title""")
    return Div(
        Div(H3("Add a goal"), cls="card-header"),
        Form(
            Input(name="title", placeholder="Goal title", cls="hr-inp", required=True,
                  style="flex:2;min-width:200px;"),
            Select(Option("Company", value="company"), Option("Department", value="department"),
                   Option("Employee", value="employee", selected=True),
                   name="owner_type", cls="hr-inp"),
            Select(Option("— owner —", value="0"),
                   *[Option(f"👤 {e['first_name']} {e['last_name']}", value=f"e{e['id']}")
                     for e in emps],
                   *[Option(f"🏢 {d['name']}", value=f"d{d['id']}") for d in depts],
                   name="owner", cls="hr-inp"),
            Select(Option("— no parent —", value="0"),
                   *[Option(p["title"][:40], value=str(p["id"])) for p in parents],
                   name="parent_goal_id", cls="hr-inp"),
            Input(name="metric", placeholder="Metric", cls="hr-inp", style="min-width:130px;"),
            Input(name="target", type="number", step="any", placeholder="Target", cls="hr-inp",
                  style="width:100px;"),
            Input(name="period", placeholder="2026-Q3", cls="hr-inp", value="2026-Q3",
                  style="width:110px;"),
            Button("Add goal", cls="btn primary", type="submit"),
            method="post", action="/performance/goals",
            cls="inline-form", style="flex-wrap:wrap;gap:8px;"))


def goal_detail(goal_id: int):
    g = people.goal(goal_id)
    if not g:
        return _title("Goal not found"), P("No such goal.")
    pct = people.goal_progress(g)
    history = people.checkins(goal_id)
    children = people.goals()
    kids = [c for c in children if c["parent_goal_id"] == goal_id]

    info = Div(Div(H3("Goal"), _pill(g["status"], TONE.get(g["status"], "")), cls="card-header"),
               Div(Span("Owner", cls="k"), Span(g.get("owner_name") or g["owner_type"]),
                   Span("Metric", cls="k"), Span(g["metric"] or "—"),
                   Span("Target", cls="k"), Span(f"{g['target'] or 0:g} {g['unit'] or ''}".strip()),
                   Span("Current", cls="k"), Span(f"{g['current'] or 0:g}"),
                   Span("Period", cls="k"), Span(g["period"] or "—"),
                   Span("Due", cls="k"), Span(g["due_date"] or "—"),
                   Span("Parent goal", cls="k"), Span(g["parent_title"] or "— top level"),
                   cls="kv"),
               Div(_goal_bar(g), style="margin-top:12px;"),
               P(f"{pct}% of target", style="color:var(--text-mute);font-size:12px;margin:6px 0 0;"),
               cls="card")

    form = Div(Div(H3("Check in"), cls="card-header"),
               Form(Input(name="value", type="number", step="any", placeholder="Current value",
                          cls="hr-inp", required=True, style="width:140px;"),
                    Select(*[Option(s, value=s, selected=(s == g["status"]))
                             for s in people.GOAL_STATUSES], name="status", cls="hr-inp"),
                    Input(name="note", placeholder="What changed?", cls="hr-inp", style="flex:1;"),
                    Button("Save check-in", cls="btn primary", type="submit"),
                    **{"hx-post": f"/performance/goals/{goal_id}/checkin",
                       "hx-target": "#goal-body", "hx-swap": "innerHTML"},
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")

    hist = Div(Div(H3("Check-in history"), cls="card-header"),
               Table(Thead(Tr(Th("When"), Th("Value", cls="num"), Th("Status"), Th("Note"), Th("By"))),
                     Tbody(*[Tr(Td(Small(h["created"], style="color:var(--text-mute);")),
                                 Td(f"{h['value']:g}" if h["value"] is not None else "—", cls="num"),
                                 Td(_pill(h["status"] or "—", TONE.get(h["status"], ""))),
                                 Td(h["note"] or "—"), Td(Small(h["created_by"] or "—")))
                             for h in history] or [Tr(Td("No check-ins yet.", colspan="5"))]),
                     cls="tbl"), cls="card")

    kid_card = Div(Div(H3(f"Contributing goals ({len(kids)})"), cls="card-header"),
                   Div(*[Div(Div(Div(A(c["title"], href=f"/performance/goals/{c['id']}"), cls="t"),
                                 Div(c["owner_name"] or "—", cls="m")),
                             _goal_bar(c),
                             Div(f"{people.goal_progress(c)}%", cls="score-cell",
                                 style="text-align:right;"),
                             Div(_pill(c["status"], TONE.get(c["status"], "")),
                                 style="text-align:right;"),
                             cls="goal-row") for c in kids]
                       or [P("None linked to this goal.", style="color:var(--text-mute);")]),
                   cls="card") if kids else None

    return (_title(g["title"], f"{g.get('owner_name') or ''} · {g['period'] or ''}".strip(" ·"),
                   A("← Goals", href="/performance/goals", cls="btn")),
            Div(Div(form, hist, kid_card), Div(info), cls="detail-grid", id="goal-body"))


def goal_body(goal_id: int):
    """HTMX-swappable inner half after a check-in."""
    return goal_detail(goal_id)[1].children


def alignment_page(period="All"):
    tree = people.goal_tree(period if period != "All" else None)
    periods = people.goal_periods()
    seg = Div(A("All", href="/performance/alignment", cls="active" if period == "All" else ""),
              *[A(p, href=f"/performance/alignment?period={p}", cls="active" if period == p else "")
                for p in periods], cls="seg")

    def render(nodes, depth=0):
        out = []
        for n in nodes:
            out.append(Div(
                Div(Div(Div(A(n["title"], href=f"/performance/goals/{n['id']}"), cls="t"),
                        Div(f"{n['owner_name'] or '—'} · {n['metric'] or 'no metric'}", cls="m")),
                    _goal_bar(n),
                    Div(f"{people.goal_progress(n)}%", cls="score-cell", style="text-align:right;"),
                    Div(_pill(n["status"], TONE.get(n["status"], "")), style="text-align:right;"),
                    cls="goal-row"),
                Div(*render(n["children"], depth + 1), cls="kid") if n["children"] else None))
        return out

    return (_title("Goal alignment",
                   "How individual goals ladder up to team and company objectives"),
            seg,
            Div(Div(H3("Cascade"), A("← Goal list", href="/performance/goals", cls="btn sm"),
                    cls="card-header"),
                Div(*render(tree), cls="goal-tree") if tree
                else P("No goals yet.", style="color:var(--text-mute);"), cls="card"))


# ---------- feedback --------------------------------------------------------

def feedback_page(kind="All"):
    items = people.feedback_feed(kind=kind)
    seg = Div(*[A(k, href=f"/performance/feedback?kind={k}", cls="active" if kind == k else "")
                for k in ["All"] + people.FEEDBACK_KINDS], cls="seg")
    emps = db.employees_min()
    comps = talent.competencies()

    form = Div(Div(H3("Give feedback"), cls="card-header"),
               Form(Select(Option("— from —", value="0"),
                           *[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="from_employee_id", cls="hr-inp"),
                    Select(*[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"]))
                             for e in emps], name="to_employee_id", cls="hr-inp"),
                    Select(*[Option(k, value=k) for k in people.FEEDBACK_KINDS],
                           name="kind", cls="hr-inp"),
                    Select(Option("— competency —", value="0"),
                           *[Option(c["name"], value=str(c["id"])) for c in comps],
                           name="competency_id", cls="hr-inp"),
                    Select(*[Option(v, value=v) for v in people.VISIBILITIES],
                           name="visibility", cls="hr-inp"),
                    Input(name="body", placeholder="What did they do well, or differently?",
                          cls="hr-inp", required=True, style="flex:1;min-width:220px;"),
                    Button("Post", cls="btn primary", type="submit"),
                    **{"hx-post": "/performance/feedback", "hx-target": "#feed",
                       "hx-swap": "innerHTML"},
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")

    return (_title("Feedback", f"{len(items)} entries — praise, coaching and peer review"),
            form, seg, Div(feed_list(kind), id="feed"))


def feed_list(kind="All"):
    items = people.feedback_feed(kind=kind)
    return Div(Div(H3("Recent feedback"), cls="card-header"),
               *[Div(Div(f"{i['from_name'] or 'Anonymous'} → ",
                         A(i["to_name"], href=f"/employees/{i['to_id']}"),
                         Span(f" · {i['created'][:16]}", style="color:var(--text-mute);"),
                         cls="who"),
                     Div(i["body"], cls="body"),
                     Div(_pill(i["kind"]),
                         _pill(i["competency"]) if i["competency"] else None,
                         _pill(i["visibility"]),
                         style="margin-top:6px;display:flex;gap:5px;flex-wrap:wrap;"),
                     cls="feed-item")
                 for i in items] or [P("No feedback yet.", style="color:var(--text-mute);")],
               cls="card")


# ---------- review cycles ---------------------------------------------------

def reviews_page():
    cs = people.cycles()
    k = people.performance_kpis()
    tbl = Table(Thead(Tr(Th("Cycle"), Th("Period"), Th("Reviews", cls="num"),
                         Th("Submitted", cls="num"), Th("Progress"), Th("Status"), Th(""))),
                Tbody(*[Tr(Td(A(Strong(c["name"]), href=f"/performance/reviews/{c['id']}")),
                           Td(f"{c['period_start']} → {c['period_end']}",
                              style="white-space:nowrap;color:var(--text-mute);"),
                           Td(str(c["n_reviews"]), cls="num"),
                           Td(str(c["n_done"]), cls="num"),
                           Td(_bar(round(100 * c["n_done"] / c["n_reviews"]) if c["n_reviews"] else 0)),
                           Td(_pill(c["status"])),
                           Td(Button("Open cycle", cls="btn sm primary",
                                     **{"hx-post": f"/performance/reviews/{c['id']}/status?status=Open",
                                        "hx-target": "#cycles", "hx-swap": "innerHTML"})
                              if c["status"] == "Draft" else
                              Button("Calibrate", cls="btn sm",
                                     **{"hx-post": f"/performance/reviews/{c['id']}/status?status=Calibration",
                                        "hx-target": "#cycles", "hx-swap": "innerHTML"})
                              if c["status"] == "Open" else Span("—", style="color:var(--text-mute);")))
                        for c in cs] or [Tr(Td("No cycles yet.", colspan="7"))]), cls="tbl")

    form = Div(Div(H3("New review cycle"), cls="card-header"),
               Form(Input(name="name", placeholder="e.g. 2026 H2 review", cls="hr-inp",
                          required=True, style="flex:1;min-width:180px;"),
                    Input(type="date", name="period_start", cls="hr-inp", required=True),
                    Input(type="date", name="period_end", cls="hr-inp", required=True),
                    Button("Create", cls="btn primary", type="submit"),
                    method="post", action="/performance/reviews",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")

    return (_title("Review cycles", "Self, manager and skip-level reviews with calibration"),
            Div(kpi_card("Open cycles", k["open_cycles"]),
                kpi_card("Reviews due", k["reviews_due"], "not yet submitted",
                         tone="danger" if k["reviews_due"] else ""),
                kpi_card("Active goals", k["goals"]),
                kpi_card("Feedback (30d)", k["feedback_30d"]),
                cls="kpi-grid"),
            form, Div(Div(Div(H3("Cycles"), cls="card-header"), tbl, cls="card"), id="cycles"))


def cycles_fragment():
    return reviews_page()[3].children[0]


def cycle_detail(cycle_id: int, status="All"):
    c = people.cycle(cycle_id)
    if not c:
        return _title("Cycle not found"), P("No such review cycle.")
    rs = people.reviews_in(cycle_id, status)
    grid = people.calibration_grid(cycle_id)
    dist = people.rating_distribution(cycle_id)

    seg = Div(*[A(s, href=f"/performance/reviews/{cycle_id}?status={s}",
                  cls="active" if status == s else "")
                for s in ["All"] + people.REVIEW_STATUSES], cls="seg")

    tbl = Table(Thead(Tr(Th("Employee"), Th("Department"), Th("Kind"), Th("Reviewer"),
                         Th("Overall", cls="num"), Th("Status"), Th(""))),
                Tbody(*[Tr(Td(r["employee"]), Td(r["dept"] or "—"), Td(_pill(r["kind"])),
                           Td(r["reviewer"] or "—"),
                           Td(f"{r['overall']:.1f}" if r["overall"] else "—", cls="num"),
                           Td(_pill(r["status"])),
                           Td(A("Complete", href=f"/performance/reviews/{cycle_id}/{r['id']}",
                                cls="btn sm") if r["status"] != "Submitted"
                              else Span("—", style="color:var(--text-mute);")))
                        for r in rs] or [Tr(Td("No reviews.", colspan="7"))]), cls="tbl")

    cal = Div(Div(H3("Calibration by department"), cls="card-header"),
              Table(Thead(Tr(Th("Department"), Th("Reviews", cls="num"), Th("Average", cls="num"),
                             Th("Range", cls="num"))),
                    Tbody(*[Tr(Td(g["dept"] or "—"), Td(str(g["n"]), cls="num"),
                               Td(Strong(f"{g['avg_score']:.2f}"), cls="num"),
                               Td(f"{g['lo']:.1f} – {g['hi']:.1f}", cls="num"))
                            for g in grid] or [Tr(Td("Nothing submitted yet.", colspan="4"))]),
                    cls="tbl"), cls="card")

    mx = max((d["n"] for d in dist), default=1) or 1
    distro = Div(Div(H3("Rating distribution"), cls="card-header"),
                 *[Div(Div(f"{d['band']} ★", style="color:var(--text-dim);"),
                       Div(Div(cls="funnel-bar", style=f"width:{max(2, 100 * d['n'] / mx):.0f}%;")),
                       Div(str(d["n"]), cls="v"), cls="funnel-row") for d in dist]
                 or [P("Nothing submitted yet.", style="color:var(--text-mute);")], cls="card")

    return (_title(c["name"], f"{c['period_start']} → {c['period_end']} · {c['status']}",
                   A("← Cycles", href="/performance/reviews", cls="btn")),
            seg,
            Div(Div(Div(H3(f"Reviews ({len(rs)})"), cls="card-header"), tbl, cls="card"),
                Div(cal, distro), cls="detail-grid"))


def review_form(cycle_id: int, review_id: int):
    r = db.one("""SELECT r.*, e.first_name||' '||e.last_name employee, e.designation,
                         rv.first_name||' '||rv.last_name reviewer
                  FROM reviews r JOIN employees e ON e.id=r.employee_id
                  LEFT JOIN employees rv ON rv.id=r.reviewer_id WHERE r.id=?""", (review_id,))
    if not r:
        return _title("Review not found"), P("No such review.")
    comps = talent.competencies()
    return (_title(f"{r['kind']} review — {r['employee']}", r["designation"] or "",
                   A("← Cycle", href=f"/performance/reviews/{cycle_id}", cls="btn")),
            Div(Div(H3("Ratings"), cls="card-header"),
                Form(
                    *[Div(Label(c["name"], style="font-size:13px;font-weight:600;"),
                          Small(f" — {c['description'] or c['category']}",
                                style="color:var(--text-mute);"),
                          Select(*[Option(f"{i} — {lbl}", value=str(i)) for i, lbl in
                                   ((5, "Outstanding"), (4, "Exceeds"), (3, "Meets"),
                                    (2, "Developing"), (1, "Below"))],
                                 name=f"comp_{c['id']}", cls="hr-inp",
                                 style="margin-left:10px;width:190px;"),
                          style="margin-bottom:10px;display:flex;align-items:center;"
                                "justify-content:space-between;gap:10px;")
                      for c in comps],
                    Div(Label("Overall summary", style="font-size:13px;font-weight:600;"),
                        Textarea(name="narrative", cls="prompt-box",
                                 style="min-height:150px;margin-top:6px;",
                                 placeholder="What went well, what to work on next."),
                        style="margin-top:14px;"),
                    Button("Submit review", cls="btn primary", type="submit",
                           style="margin-top:12px;"),
                    method="post", action=f"/performance/reviews/{cycle_id}/{review_id}"),
                cls="card"))


# ---------- signals ---------------------------------------------------------

def signals_page(dept="All"):
    depts = db.rows("SELECT name FROM departments ORDER BY name")
    seg = Div(A("All", href="/performance/signals", cls="active" if dept == "All" else ""),
              *[A(d["name"], href=f"/performance/signals?dept={d['name']}",
                  cls="active" if dept == d["name"] else "") for d in depts], cls="seg")
    risk = people.attrition_signals(None if dept == "All" else dept)
    ready = people.promotion_readiness()

    risk_card = Div(
        Div(H3("Attrition signals"),
            Small("advisory only", style="color:var(--text-mute);"), cls="card-header"),
        P("Flags are raised from goal progress, attendance, feedback recency and tenure. "
          "Every flag lists the factors behind it — there are no unexplained scores, and "
          "nothing here should be acted on without a conversation.",
          style="color:var(--text-mute);font-size:12.5px;margin:0 0 12px;"),
        Table(Thead(Tr(Th("Employee"), Th("Department"), Th("Signal"), Th("Why"))),
              Tbody(*[Tr(Td(A(r["name"], href=f"/employees/{r['id']}"),
                            Div(r["designation"] or "", style="font-size:11.5px;color:var(--text-mute);")),
                         Td(r["dept"] or "—"),
                         Td(Span(r["band"], cls="pill " + ("rejected" if r["band"] == "High" else "pending"))),
                         Td(Div(*[Div("• " + f, style="font-size:12px;color:var(--text-dim);")
                                  for f in r["factors"]])))
                      for r in risk] or [Tr(Td("No signals raised — good news.", colspan="4"))]),
              cls="tbl"), cls="card")

    ready_card = Div(
        Div(H3("Promotion readiness"), cls="card-header"),
        Table(Thead(Tr(Th("Employee"), Th("Department"), Th("Score", cls="num"), Th("Why"))),
              Tbody(*[Tr(Td(A(r["name"], href=f"/employees/{r['id']}")),
                         Td(r["dept"] or "—"),
                         Td(Strong(f"{r['score']:.1f}"), cls="num score-cell"),
                         Td(Div(*[Div("• " + f, style="font-size:12px;color:var(--text-dim);")
                                  for f in r["factors"]])))
                      for r in ready] or [Tr(Td("Not enough data yet.", colspan="4"))]),
              cls="tbl"), cls="card")

    return (_title("Performance signals",
                   "Explainable, advisory indicators — every score shows its working"),
            seg, risk_card, ready_card)
