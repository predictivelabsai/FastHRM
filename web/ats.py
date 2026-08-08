"""Centre-pane renderers for the ATS — requisitions, candidates, CV extraction.

Same conventions as web/views.py: functions return FastHTML tuples, HTMX targets
a container id and swaps innerHTML.
"""
from __future__ import annotations

import json

from fasthtml.common import (
    Div, H1, H3, H4, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button,
    Select, Option, Label, Textarea, NotStr, Strong, Small, Details, Summary,
)

import db
import recruitment
import recruiting_ops
import talent
from web.layout import kpi_card, money
from web.views import _pill, _title, _initials
from web import cv_extract, llm

POLL_MS = 2500


def _cand_name(c):
    return talent.display_name(c)


def _dash(v, suffix=""):
    return f"{v}{suffix}" if v not in (None, "", 0) else "—"


# ---------- requisitions ----------------------------------------------------

def jobs_list(status="All"):
    k = talent.ats_kpis()
    js = talent.jobs(status)
    seg = Div(*[A(s, href=f"/talent/jobs?status={s}", cls="active" if status == s else "")
                for s in ["All"] + talent.JOB_STATUSES], cls="seg")
    tbl = Table(
        Thead(Tr(Th("Req"), Th("Role"), Th("Department"), Th("Hiring manager"), Th("Location"),
                 Th("Openings", cls="num"), Th("Applicants", cls="num"), Th("Band", cls="num"), Th("Status"))),
        Tbody(*[Tr(
            Td(Small(j["code"] or "—", style="color:var(--text-mute);")),
            Td(A(Strong(j["title"]), href=f"/talent/jobs/{j['id']}")),
            Td(j["dept"] or "—"), Td(j["hiring_manager"] or "—"),
            Td(f"{j['location'] or '—'} · {j['remote_policy'] or ''}".strip(" ·")),
            Td(f"{j['headcount'] - (j['filled'] or 0)} of {j['headcount']}", cls="num"),
            Td(Strong(str(j["active_applicants"])), Small(f" / {j['total_applicants']}",
                                                          style="color:var(--text-mute);"), cls="num"),
            Td(f"{money(j['comp_min'])}–{money(j['comp_max'])}" if j["comp_min"] else "—", cls="num"),
            Td(_pill(j["status"])))
            for j in js] or [Tr(Td("No requisitions.", colspan="9"))]), cls="tbl")
    return (
        _title("Requisitions", f"{len(js)} shown — synthetic demo pipeline",
               Div(A("Careers site", href="/talent/careers", cls="btn"),
                   A("New job", href="/talent/jobs/new", cls="btn primary"),
                   style="display:flex;gap:6px;")),
        Div(kpi_card("Open reqs", k["open_reqs"], f"{k['open_headcount']} seats to fill"),
            kpi_card("Active applications", k["active_applications"], f"{k['in_process']} past first screen"),
            kpi_card("Candidates", k["candidates"], f"{k['parsed']} CVs parsed"),
            kpi_card("Parsed by AI", k["parsed"], "structured profiles",
                     tone="" if k["parsed"] else "warn"),
            cls="kpi-grid"),
        seg, Div(tbl, cls="card"))


def _stage_bar(job_id, counts, active_stage):
    segs = []
    for s in talent.job_stages(job_id):
        segs.append(A(Div(str(counts.get(s, 0)), cls="n"), Div(s, cls="s"),
                      href=f"/talent/jobs/{job_id}?stage={s}",
                      cls="stage-seg" + (" on" if s == active_stage else "") +
                          (" terminal" if s in talent.TERMINAL_STAGES else "")))
    return Div(*segs, cls="stage-bar")


def job_detail(job_id, stage="All"):
    j = talent.job(job_id)
    if not j:
        return _title("Requisition not found"), P("No such requisition.")

    posting = recruitment.ensure_posting(job_id)
    detail = Div(Div(H3("Requisition"), cls="card-header"),
                 Div(Span("Code", cls="k"), Span(j["code"] or "—"),
                     Span("Department", cls="k"), Span(j["dept"] or "—"),
                     Span("Hiring manager", cls="k"), Span(j["hiring_manager"] or "—"),
                     Span("Location", cls="k"), Span(f"{j['location'] or '—'} · {j['remote_policy'] or ''}".strip(" ·")),
                     Span("Openings", cls="k"), Span(f"{j['headcount'] - (j['filled'] or 0)} of {j['headcount']} remaining"),
                     Span("Band", cls="k"), Span(f"{money(j['comp_min'])}–{money(j['comp_max'])}" if j["comp_min"] else "—"),
                     Span("Opened", cls="k"), Span(j["opened_on"] or "—"),
                     Span("Target", cls="k"), Span(j["target_date"] or "—"),
                     Span("Requirements", cls="k"), Span(j["requirements"] or "—"),
                     cls="kv"), cls="card")

    return (_title(j["title"], f"{j['code']} · {j['dept'] or '—'} · {j['status']}",
                   Div(_pill(posting["publication_status"]),
                       A("Public page", href=f"/jobs/{posting['slug']}", target="_blank", cls="btn")
                       if posting["publication_status"] == "Published" else None,
                       A("Preview", href=f"/talent/jobs/{job_id}/preview", target="_blank", cls="btn"),
                       A("Edit job", href=f"/talent/jobs/{job_id}/edit", cls="btn primary"),
                       A("Calibration", href=f"/talent/jobs/{job_id}/calibration", cls="btn"),
                       A("← Requisitions", href="/talent/jobs", cls="btn"),
                       style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;")),
            Div(job_main(job_id, stage), id="job-main"),
            Div(ranking_panel(job_id), id="rank-panel"),
            detail)


def job_main(job_id, stage="All"):
    """The HTMX-swappable half of the requisition page: stage bar + applications."""
    j = talent.job(job_id)
    if not j:
        return P("No such requisition.")
    return Div(_stage_bar(job_id, talent.pipeline_counts(job_id), stage),
               Div(A("All", href=f"/talent/jobs/{job_id}", cls="active" if stage == "All" else ""),
                   *[A(s, href=f"/talent/jobs/{job_id}?stage={s}", cls="active" if stage == s else "")
                     for s in talent.job_stages(job_id)], cls="seg"),
               Div(_applications_table(job_id, stage), cls="card"),
               upload_card(default_job=job_id))


def _applications_table(job_id, stage):
    apps = talent.applications_for_job(job_id, stage)
    stages = talent.job_stages(job_id)
    rows = []
    for a in apps:
        idx = stages.index(a["stage"]) + 1 if a["stage"] in stages else len(stages)
        actions = []
        if a["stage"] not in talent.TERMINAL_STAGES and idx < len(stages):
            actions = [Button(f"→ {stages[idx]}", cls="btn sm primary",
                              **{"hx-post": f"/talent/applications/{a['id']}/stage?stage={stages[idx]}",
                                 "hx-target": "#job-main", "hx-swap": "innerHTML"}),
                       Button("✕", cls="btn sm", title="Reject",
                              **{"hx-post": f"/talent/applications/{a['id']}/stage?stage=Rejected",
                                 "hx-target": "#job-main", "hx-swap": "innerHTML"})]
        rows.append(Tr(
            Td(A(f"{a['first_name']} {a['last_name']}".strip() or "Unnamed",
                 href=f"/talent/candidates/{a['candidate_id']}")),
            Td(a["current_title"] or "—"), Td(a["current_employer"] or "—"),
            Td(_dash(a["years_experience"], " yrs"), cls="num"),
            Td(_pill(a["stage"])),
            Td(f"{a['rating']:.1f}" if a["rating"] else "—", cls="num"),
            Td(a["applied_on"] or "—", style="color:var(--text-mute);white-space:nowrap;"),
            Td(Div(*actions, style="display:flex;gap:4px;") if actions else Span("—", style="color:var(--text-mute);"))))
    return Table(Thead(Tr(Th("Candidate"), Th("Current title"), Th("Employer"), Th("Exp", cls="num"),
                          Th("Stage"), Th("Rating", cls="num"), Th("Applied"), Th("Move"))),
                 Tbody(*rows or [Tr(Td("No applications at this stage.", colspan="8"))]), cls="tbl")


# ---------- CV upload -------------------------------------------------------

def upload_card(default_job: int | None = None):
    jobs = talent.jobs_min()
    warn = None
    if not llm.available():
        warn = P(llm.unavailable_reason(), cls="flag")
    return Div(
        Div(H3("Add a candidate from a CV"),
            Small(f"{llm.provider()} · {llm.model_name()}", style="color:var(--text-mute);"),
            cls="card-header"),
        warn,
        Form(
            Div(Div("Drop a CV here, or choose a file", cls="big"),
                Div("PDF, DOCX, TXT or MD — parsed into a structured profile by the AI", cls="small"),
                Input(type="file", name="cv", accept=".pdf,.docx,.txt,.md", required=True,
                      style="margin-top:12px;"),
                cls="drop-zone"),
            Div(Select(Option("No requisition — add to talent pool", value="0"),
                       *[Option(f"{j['title']} ({j['code']})", value=str(j["id"]),
                                selected=(default_job == j["id"])) for j in jobs],
                       name="job_id", cls="hr-inp", style="flex:1;min-width:220px;"),
                Select(*[Option(s, value=s) for s in talent.SOURCES], name="source", cls="hr-inp"),
                Button("Upload & parse", cls="btn primary", type="submit"),
                cls="inline-form", style="margin-top:12px;flex-wrap:wrap;gap:8px;"),
            enctype="multipart/form-data",
            **{"hx-post": "/talent/upload", "hx-target": "#upload-result", "hx-swap": "innerHTML",
               "hx-encoding": "multipart/form-data", "hx-disabled-elt": "find button"}),
        Div(id="upload-result", style="margin-top:12px;"),
        cls="card")


def extraction_status(cid: int, *, poll: bool = True):
    """Polled fragment: extraction progress for one candidate."""
    run = cv_extract.latest_run(cid)
    c = talent.candidate(cid)
    if not run or not c:
        return Div("No extraction run found.", id=f"xrun-{cid}")

    link = A("Open profile →", href=f"/talent/candidates/{cid}", cls="btn sm")
    if run["status"] == "pending":
        body = Div(Div(Span(cls="dot"), Span(f"Parsing {run['model']}… this usually takes 5–15 seconds."),
                       cls="thinking-indicator"),
                   id=f"xrun-{cid}",
                   **({"hx-get": f"/talent/candidates/{cid}/extraction",
                       "hx-trigger": f"every {POLL_MS}ms", "hx-swap": "outerHTML"} if poll else {}))
        return body
    if run["status"] == "error":
        return Div(P(f"Extraction failed: {run['error']}", cls="flag"), link, id=f"xrun-{cid}")

    prof = talent.candidate_profile(cid)
    return Div(
        P(Strong("✓ Parsed. "),
          f"{_cand_name(c)} — {c['current_title'] or 'role not stated'} at "
          f"{c['current_employer'] or 'employer not stated'}. "
          f"{len(prof['skills'])} skills, {len(prof['experience'])} roles, "
          f"{len(prof['education'])} qualifications in {run['latency_ms'] or 0} ms.",
          style="margin:0 0 8px;"),
        link, id=f"xrun-{cid}")


# ---------- candidates ------------------------------------------------------

def candidates_list(q="", status="All", *, location="", tag="", skill=""):
    cs = recruiting_ops.search_candidates(q, status=status, location=location, tag=tag, skill=skill)
    seg = Div(*[A(s, href=f"/talent/candidates?status={s}", cls="active" if status == s else "")
                for s in ["All", "Active", "Hired", "Archived"]], cls="seg")
    search = Form(Input(type="search", name="q", value=q,
                        placeholder="Search profile, CV, custom field or email…"),
                  Input(name="location", value=location, placeholder="Location"),
                  Input(name="tag", value=tag, placeholder="Tag"),
                  Input(name="skill", value=skill, placeholder="Skill"),
                  Input(type="hidden", name="status", value=status),
                  cls="toolbar", method="get", action="/talent/candidates")
    rows = []
    for c in cs:
        parsed = c["extraction_status"]
        badge = _pill(parsed) if parsed else Span("—", style="color:var(--text-mute);")
        rows.append(Tr(
            Td(A(_cand_name(c), href=f"/talent/candidates/{c['id']}")),
            Td(c["current_title"] or "—"), Td(c["current_employer"] or "—"),
            Td(_dash(c["years_experience"], " yrs"), cls="num"),
            Td(c["location"] or "—"),
            Td(str(c["n_skills"]) if c["n_skills"] else "—", cls="num"),
            Td(c["latest_job"] or "—"),
            Td(_pill(c["latest_stage"]) if c["latest_stage"] else Span("—", style="color:var(--text-mute);")),
            Td(_pill(c["source"] or "Direct")), Td(badge)))
    tbl = Table(Thead(Tr(Th("Candidate"), Th("Current title"), Th("Employer"), Th("Exp", cls="num"),
                         Th("Location"), Th("Skills", cls="num"), Th("Applied to"), Th("Stage"),
                         Th("Source"), Th("CV parse"))),
                Tbody(*rows or [Tr(Td("No candidates yet — upload a CV below.", colspan="10"))]), cls="tbl")
    return (_title("Candidates", f"{len(cs)} shown"), seg, search,
            Div(tbl, cls="card"), upload_card())


def candidate_detail(cid: int):
    p = talent.candidate_profile(cid)
    c = p["candidate"]
    if not c:
        return _title("Candidate not found"), P("No such candidate.")

    head = Div(Span(_initials(c["first_name"] or "?", c["last_name"] or ""), cls="avatar"),
               Div(H1(_cand_name(c), style="margin:0;"),
                   P(c["headline"] or "Profile not yet parsed", cls="sub")), cls="emp-head")

    info = Div(Div(H3("Details"), cls="card-header"),
               Div(Span("Email", cls="k"), Span(c["email"] or "—"),
                   Span("Phone", cls="k"), Span(c["phone"] or "—"),
                   Span("Location", cls="k"), Span(c["location"] or "—"),
                   Span("Current role", cls="k"), Span(c["current_title"] or "—"),
                   Span("Employer", cls="k"), Span(c["current_employer"] or "—"),
                   Span("Experience", cls="k"), Span(_dash(c["years_experience"], " years")),
                   Span("LinkedIn", cls="k"),
                   Span(A(c["linkedin_url"], href=f"https://{c['linkedin_url'].lstrip('https://')}",
                          target="_blank", rel="noopener") if c["linkedin_url"] else "—"),
                   Span("Source", cls="k"), _pill(c["source"] or "Direct"),
                   Span("Referred by", cls="k"), Span(c["referrer"] or "—"),
                   Span("Consent", cls="k"),
                   Span(c["consent_at"] or "not recorded",
                        style="" if c["consent_at"] else "color:var(--warn);"),
                   Span("Status", cls="k"), _pill(c["status"]),
                   cls="kv"), cls="card")

    skills = Div(Div(H3("Skills"), Small(f"{len(p['skills'])} extracted", style="color:var(--text-mute);"),
                     cls="card-header"),
                 Div(*[Span(s["skill"],
                            Span(f"{s['years']:.0f}y" if s["years"] else (s["level"] or ""), cls="yrs"),
                            cls="chip" + (" expert" if (s["level"] or "") == "Expert" else ""),
                            title=s["evidence"] or "")
                       for s in p["skills"]] or [P("No skills extracted yet.", style="color:var(--text-mute);")],
                     cls="chips"), cls="card")

    exp_items = [Div(Div(x["title"] or "—", cls="role"),
                     Div(x["employer"] or "—", Span(f" · {x['location']}" if x["location"] else "",
                                                    style="color:var(--text-mute);"), cls="org"),
                     Div(f"{x['start_date'] or '?'} → {x['end_date'] or 'present'}", cls="when"),
                     Div(x["summary"], cls="what") if x["summary"] else None,
                     cls="tl-item") for x in p["experience"]]
    exp = Div(Div(H3("Experience"), cls="card-header"),
              Div(*exp_items, cls="timeline") if exp_items
              else P("No experience extracted yet.", style="color:var(--text-mute);"), cls="card")

    edu = Div(Div(H3("Education"), cls="card-header"),
              Table(Tbody(*[Tr(Td(Strong(e["institution"] or "—")),
                               Td(f"{e['qualification'] or ''} {e['field'] or ''}".strip() or "—"),
                               Td(e["end_year"] or "—", cls="num"))
                            for e in p["education"]] or [Tr(Td("None extracted.", colspan="3"))]),
                    cls="tbl"), cls="card")

    apps = Div(Div(H3("Applications"), cls="card-header"),
               Table(Thead(Tr(Th("Requisition"), Th("Stage"), Th("Status"), Th("Applied"))),
                     Tbody(*[Tr(Td(A(a["job_title"], href=f"/talent/jobs/{a['job_id']}")),
                                 Td(_pill(a["stage"])), Td(_pill(a["status"])),
                                 Td(a["applied_on"] or "—"))
                             for a in p["applications"]] or [Tr(Td("Not applied to any requisition.", colspan="4"))]),
                     cls="tbl"), cls="card")

    docs = Div(Div(H3("Documents & extraction"), cls="card-header"),
               Table(Thead(Tr(Th("File"), Th("Kind"), Th("Size", cls="num"), Th("Uploaded"))),
                     Tbody(*[Tr(Td(A(d["file_name"], href=f"/talent/documents/{d['id']}")), Td(_pill(d["kind"])),
                                Td(f"{(d['bytes'] or 0) / 1024:.0f} kB", cls="num"),
                                Td(d["uploaded_on"] or "—", style="color:var(--text-mute);"))
                             for d in p["documents"]] or [Tr(Td("No documents.", colspan="4"))]), cls="tbl"),
               *( [Details(Summary(f"Extraction runs ({len(p['runs'])})",
                                   style="cursor:pointer;font-size:13px;margin-top:10px;"),
                           Table(Thead(Tr(Th("Model"), Th("Prompt"), Th("Status"), Th("Latency", cls="num"), Th("When"))),
                                 Tbody(*[Tr(Td(Small(r["model"] or "—")),
                                            Td(f"v{r['prompt_version']}"), Td(_pill(r["status"])),
                                            Td(f"{r['latency_ms'] or 0} ms", cls="num"),
                                            Td(Small(r["created"] or "—", style="color:var(--text-mute);")))
                                         for r in p["runs"]]), cls="tbl"),
                           *([P(f"Last error: {p['runs'][0]['error']}", cls="flag")]
                             if p["runs"] and p["runs"][0]["error"] else []))]
                  if p["runs"] else []),
               cls="card")

    reparse = Form(
        Select(*[Option(f"{j['title']} ({j['code']})", value=str(j["id"]))
                 for j in talent.jobs_min()] or [Option("No open requisitions", value="0")],
               name="job_id", cls="hr-inp"),
        Button("Apply to requisition", cls="btn", type="submit"),
        **{"hx-post": f"/talent/candidates/{cid}/apply", "hx-target": "#cand-actions", "hx-swap": "innerHTML"},
        cls="inline-form", style="gap:8px;flex-wrap:wrap;")

    live_app = next((a for a in p["applications"] if a["status"] == "Active"), None)
    iv_panel = Div(interviews_panel(live_app["id"]), id="iv-panel") if live_app else None
    offer_panel = _offer_panel(live_app, c) if live_app else None

    return (head,
            Div(A("← Candidates", href="/talent/candidates", cls="btn"),
                style="margin-bottom:12px;"),
            Div(Div(id="cand-actions"), reparse, cls="card"),
            Div(Div(info, skills, exp, iv_panel, offer_panel),
                Div(edu, apps, docs), cls="detail-grid"))


def _offer_panel(app, cand):
    """Draft or show the offer for the candidate's live application."""
    existing = talent.offer_for_application(app["id"])
    if existing:
        return Div(Div(H3("Offer"), _pill(existing["status"]), cls="card-header"),
                   Div(Span("Salary", cls="k"), Span(Strong(money(existing["salary"]))),
                       Span("Start date", cls="k"), Span(existing["start_date"] or "—"),
                       Span("Expires", cls="k"), Span(existing["expires_on"] or "—"),
                       cls="kv"),
                   Div(A("Open offer →", href=f"/talent/offers/{existing['id']}", cls="btn sm"),
                       style="margin-top:10px;"), cls="card")
    if app["stage"] not in ("Interview", "Offer"):
        return None
    return Div(Div(H3("Make an offer"), cls="card-header"),
               P("Drafting an offer moves the application to the Offer stage. Accepting one "
                 "creates the employee record and starts onboarding.",
                 style="color:var(--text-mute);font-size:12.5px;margin:0 0 10px;"),
               Form(Input(name="salary", type="number", step="any", placeholder="Salary",
                          cls="hr-inp", required=True, style="width:140px;"),
                    Input(type="date", name="start_date", cls="hr-inp", required=True),
                    Input(type="date", name="expires_on", cls="hr-inp"),
                    Button("Draft offer", cls="btn primary", type="submit"),
                    method="post", action=f"/talent/applications/{app['id']}/offer",
                    cls="inline-form", style="flex-wrap:wrap;gap:8px;"), cls="card")


# ---------- prompt manager --------------------------------------------------

def prompts_page(key: str = cv_extract.PROMPT_KEY, saved: str = ""):
    cv_extract.ensure_default_prompt()
    active = talent.active_prompt(key)

    banner = P(saved, cls="flag", style="border-left-color:var(--accent);background:var(--accent-light);"
                                        "color:var(--accent-hover);") if saved else None

    editor = Form(
        Textarea(active["content"] if active else cv_extract.DEFAULT_EXTRACTION_PROMPT,
                 name="content", cls="prompt-box", spellcheck="true"),
        Div(Button("Save as new version", cls="btn primary", type="submit"),
            Button("Restore the built-in default", cls="btn", type="submit",
                   name="restore", value="1"),
            style="display:flex;gap:8px;margin-top:10px;"),
        method="post", action=f"/talent/prompts?key={key}")

    return (
        _title("AI Prompts", "The wording the model follows when it reads a CV. Business-editable."),
        banner,
        Div(Div(Div(H3("CV extraction guidance"),
                    Small(f"active: v{active['version'] if active else 0} · {llm.model_name()}",
                          style="color:var(--text-mute);"), cls="card-header"),
                P("Plain English only. Describe what to capture and how to interpret it — "
                  "the output format is fixed in code below and cannot be changed from here, "
                  "so an edit can never break the parser.",
                  style="color:var(--text-mute);font-size:12.5px;margin:0 0 10px;"),
                editor, cls="card"),
            Div(Div(Div(H3("Versions"), cls="card-header"),
                    Div(prompt_versions_fragment(key), id="prompt-versions"), cls="card"),
                Div(Div(H3("Output contract"), Small("code-side, read-only",
                                                     style="color:var(--text-mute);"), cls="card-header"),
                    Div(cv_extract.OUTPUT_FORMAT, cls="contract-box"), cls="card")),
            cls="detail-grid", style="--x:1;grid-template-columns:1fr 420px;"))


# ---------- interviews ------------------------------------------------------

def interviews_panel(app_id: int):
    ivs = talent.interviews_for(app_id)
    emps = db.employees_min()
    rows = []
    for iv in ivs:
        rows.append(Tr(
            Td(_pill(iv["kind"] or "—")),
            Td(iv["interviewer"] or "— unassigned —"),
            Td(iv["scheduled_at"] or "—", style="white-space:nowrap;"),
            Td(_pill(iv["mode"] or "—")),
            Td(f"{iv['avg_score']:.1f}" if iv["avg_score"] else "—", cls="num"),
            Td(_pill(iv["recommendation"]) if iv["recommendation"]
               else Span("—", style="color:var(--text-mute);")),
            Td(_pill(iv["status"])),
            Td(A("Scorecard", href=f"/talent/interviews/{iv['id']}", cls="btn sm")
               if iv["status"] != "Completed" else
               A("View", href=f"/talent/interviews/{iv['id']}", cls="btn sm"))))
    tbl = Table(Thead(Tr(Th("Stage"), Th("Interviewer"), Th("When"), Th("Mode"),
                         Th("Score", cls="num"), Th("Recommendation"), Th("Status"), Th(""))),
                Tbody(*rows or [Tr(Td("No interviews scheduled.", colspan="8"))]), cls="tbl")
    form = Form(
        Select(*[Option(k, value=k) for k in talent.INTERVIEW_KINDS], name="kind", cls="hr-inp"),
        Select(Option("— interviewer —", value="0"),
               *[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in emps],
               name="interviewer_id", cls="hr-inp"),
        Input(type="datetime-local", name="scheduled_at", cls="hr-inp", required=True),
        Select(*[Option(m, value=m) for m in talent.INTERVIEW_MODES], name="mode", cls="hr-inp"),
        Button("Schedule", cls="btn primary", type="submit"),
        **{"hx-post": f"/talent/applications/{app_id}/interview", "hx-target": "#iv-panel",
           "hx-swap": "innerHTML"},
        cls="inline-form", style="flex-wrap:wrap;gap:8px;margin-bottom:12px;")
    return Div(Div(Div(H3("Interviews"), cls="card-header"), form, tbl, cls="card"))


def scorecard_page(interview_id: int):
    iv = db.one("""SELECT i.*, a.candidate_id, a.job_id, c.first_name, c.last_name,
                          j.title job_title, e.first_name||' '||e.last_name interviewer
                   FROM interviews i JOIN applications a ON a.id=i.application_id
                   JOIN candidates c ON c.id=a.candidate_id
                   JOIN job_openings j ON j.id=a.job_id
                   LEFT JOIN employees e ON e.id=i.interviewer_id WHERE i.id=?""", (interview_id,))
    if not iv:
        return _title("Interview not found"), P("No such interview.")
    comps = talent.competencies()
    existing = {s["competency_id"]: s for s in
                db.rows("SELECT * FROM scorecards WHERE interview_id=?", (interview_id,))}

    fields = []
    for c in comps:
        cur = existing.get(c["id"]) or {}
        fields.append(Div(
            Div(Strong(c["name"]),
                Small(f" · {c['category'] or ''}", style="color:var(--text-mute);"),
                Div(c["description"] or "", style="font-size:12px;color:var(--text-mute);")),
            Div(Select(Option("—", value=""),
                       *[Option(f"{i} — {lbl}", value=str(i),
                                selected=(cur.get("score") == i))
                         for i, lbl in ((5, "Outstanding"), (4, "Strong"), (3, "Solid"),
                                        (2, "Mixed"), (1, "Weak"))],
                       name=f"score_{c['id']}", cls="hr-inp", style="width:170px;"),
                Input(name=f"comment_{c['id']}", value=cur.get("comment") or "",
                      placeholder="Evidence", cls="hr-inp", style="flex:1;min-width:180px;"),
                style="display:flex;gap:8px;flex:1;"),
            style="display:flex;gap:14px;align-items:flex-start;justify-content:space-between;"
                  "padding:10px 0;border-bottom:1px solid var(--border);"))

    return (_title(f"Scorecard — {iv['first_name']} {iv['last_name']}",
                   f"{iv['kind']} interview for {iv['job_title']} · {iv['interviewer'] or 'unassigned'}",
                   A("← Candidate", href=f"/talent/candidates/{iv['candidate_id']}", cls="btn")),
            Div(Div(H3("Competencies"), _pill(iv["status"]), cls="card-header"),
                Form(*fields,
                     Div(Label("Overall recommendation",
                               style="font-size:13px;font-weight:600;margin-right:10px;"),
                         Select(*[Option(r, value=r, selected=(iv["recommendation"] == r))
                                  for r in talent.RECOMMENDATIONS],
                                name="recommendation", cls="hr-inp"),
                         style="margin-top:14px;display:flex;align-items:center;"),
                     Div(Label("Notes", style="font-size:13px;font-weight:600;"),
                         Textarea(iv["notes"] or "", name="notes", cls="prompt-box",
                                  style="min-height:130px;margin-top:6px;",
                                  placeholder="What they said, what you probed, what you concluded."),
                         style="margin-top:12px;"),
                     Button("Save scorecard", cls="btn primary", type="submit",
                            style="margin-top:12px;"),
                     method="post", action=f"/talent/interviews/{interview_id}"),
                cls="card"))


def calibration_page(job_id: int):
    j = talent.job(job_id)
    if not j:
        return _title("Requisition not found"), P("No such requisition.")
    comps, by_cand = talent.calibration(job_id)

    def cell(v):
        if v is None:
            return Td("—", cls="num", style="color:var(--text-mute);")
        bg = ("var(--accent-light)" if v >= 4 else "var(--warn-light)" if v >= 3
              else "var(--danger-light)")
        fg = ("var(--accent-hover)" if v >= 4 else "#92400e" if v >= 3 else "#9f1239")
        return Td(Span(f"{v:.1f}", cls="heat", style=f"background:{bg};color:{fg};"), cls="num")

    tbl = Table(Thead(Tr(Th("Candidate"), *[Th(c, cls="num") for c in comps],
                         Th("Mean", cls="num"), Th("Stage"))),
                Tbody(*[Tr(Td(A(name, href=f"/talent/candidates/{d['candidate_id']}")),
                           *[cell(d["scores"].get(c)) for c in comps],
                           Td(Strong(f"{d['mean']:.2f}"), cls="num"),
                           Td(_pill(d["stage"])))
                        for name, d in by_cand.items()]
                      or [Tr(Td("No completed scorecards yet.", colspan=str(len(comps) + 3)))]),
                cls="tbl")
    return (_title(f"Calibration — {j['title']}",
                   "Every completed scorecard side by side, so scores can be compared fairly",
                   A("← Requisition", href=f"/talent/jobs/{job_id}", cls="btn")),
            Div(Div(H3("Scores by competency"), cls="card-header"), tbl, cls="card"))


# ---------- offers ----------------------------------------------------------

def offers_page(status="All"):
    os_ = talent.all_offers(status)
    stats = talent.offer_stats()
    seg = Div(*[A(s, href=f"/talent/offers?status={s}", cls="active" if status == s else "")
                for s in ["All"] + talent.OFFER_STATUSES], cls="seg")
    return (_title("Offers", "Approval, e-sign handoff, and automatic conversion to an employee"),
            Div(kpi_card("Acceptance rate", f"{stats['acceptance_rate']}%",
                         f"{stats['accepted']} accepted / {stats['declined']} declined"),
                kpi_card("In flight", stats["pending"], "drafted, approved or sent"),
                kpi_card("Accepted", stats["accepted"], "converted to employees"),
                kpi_card("Total offers", stats["total"]),
                cls="kpi-grid"),
            seg, Div(offers_table(status), id="offers"))


def offers_table(status="All"):
    os_ = talent.all_offers(status)
    rows = []
    for o in os_:
        acts = []
        nxt = {"Draft": "Pending approval", "Pending approval": "Approved",
               "Approved": "Sent", "Sent": "Accepted"}.get(o["status"])
        if nxt:
            acts.append(Button(f"→ {nxt}", cls="btn sm primary",
                               **{"hx-post": f"/talent/offers/{o['id']}/status?status={nxt}",
                                  "hx-target": "#offers", "hx-swap": "innerHTML"}))
        if o["status"] in ("Sent", "Approved"):
            acts.append(Button("Declined", cls="btn sm",
                               **{"hx-post": f"/talent/offers/{o['id']}/status?status=Declined",
                                  "hx-target": "#offers", "hx-swap": "innerHTML"}))
        rows.append(Tr(
            Td(A(f"{o['first_name']} {o['last_name']}",
                 href=f"/talent/candidates/{o['candidate_id']}")),
            Td(o["job_title"]), Td(money(o["salary"]), cls="num"),
            Td(o["start_date"] or "—", style="white-space:nowrap;"),
            Td(o["expires_on"] or "—", style="white-space:nowrap;color:var(--text-mute);"),
            Td(_pill(o["status"])),
            Td(A("Letter", href=f"/talent/offers/{o['id']}", cls="btn sm")),
            Td(Div(*acts, style="display:flex;gap:4px;") if acts
               else Span("—", style="color:var(--text-mute);"))))
    return Div(Div(Table(Thead(Tr(Th("Candidate"), Th("Role"), Th("Salary", cls="num"),
                                  Th("Start"), Th("Expires"), Th("Status"), Th(""), Th("Move"))),
                         Tbody(*rows or [Tr(Td("No offers.", colspan="8"))]), cls="tbl"),
                   cls="card"))


def offer_detail(offer_id: int):
    o = talent.offer(offer_id)
    if not o:
        return _title("Offer not found"), P("No such offer.")
    emp = db.one("SELECT id FROM employees WHERE candidate_id=?", (o["candidate_id"],))
    info = Div(Div(H3("Offer"), _pill(o["status"]), cls="card-header"),
               Div(Span("Candidate", cls="k"),
                   Span(A(f"{o['first_name']} {o['last_name']}",
                          href=f"/talent/candidates/{o['candidate_id']}")),
                   Span("Role", cls="k"), Span(o["job_title"]),
                   Span("Department", cls="k"), Span(o["dept"] or "—"),
                   Span("Salary", cls="k"), Span(Strong(money(o["salary"]))),
                   Span("Start date", cls="k"), Span(o["start_date"] or "—"),
                   Span("Expires", cls="k"), Span(o["expires_on"] or "—"),
                   Span("Approved by", cls="k"), Span(o["approved_by"] or "—"),
                   Span("Sent", cls="k"), Span(o["sent_at"] or "—"),
                   Span("Signed", cls="k"), Span(o["signed_at"] or "—"),
                   *([Span("Employee record", cls="k"),
                      Span(A("View employee →", href=f"/employees/{emp['id']}"))] if emp else []),
                   cls="kv"), cls="card")
    letter = Div(Div(H3("Offer letter"),
                     Small("generated from the requisition and candidate record",
                           style="color:var(--text-mute);"), cls="card-header"),
                 Div(NotStr((o["letter"] or "No letter drafted yet.").replace("\n", "<br>")),
                     style="font-size:13.5px;line-height:1.65;"), cls="card")
    return (_title(f"Offer — {o['first_name']} {o['last_name']}",
                   f"{o['job_code']} · {o['job_title']}",
                   A("← Offers", href="/talent/offers", cls="btn")),
            Div(Div(letter), Div(info), cls="detail-grid"))


# ---------- ranking ---------------------------------------------------------

def ranking_panel(job_id: int):
    run, scores = talent.rankings_for_job(job_id)
    head = Div(H3("AI shortlist ranking"),
               Button("Rank candidates", cls="btn sm primary",
                      **{"hx-post": f"/talent/jobs/{job_id}/rank", "hx-target": "#rank-panel",
                         "hx-swap": "innerHTML"}), cls="card-header")
    if not run:
        return Div(Div(head,
                       P("No ranking run yet. Ranking compares each candidate's experience and "
                         "skills against the requisition, and stores its reasoning so a score can "
                         "always be challenged.", style="color:var(--text-mute);font-size:12.5px;"),
                       cls="card"))
    if run["status"] == "error":
        return Div(Div(head, P(f"Last run failed: {run['error']}", cls="flag"), cls="card"))

    excluded = ", ".join(json.loads(run["excluded_json"] or "[]"))
    tbl = Table(Thead(Tr(Th("#", cls="num"), Th("Candidate"), Th("Current title"),
                         Th("Score", cls="num"), Th("Why"), Th("Stage"))),
                Tbody(*[Tr(Td(str(i), cls="num"),
                           Td(A(f"{s['first_name']} {s['last_name']}",
                                href=f"/talent/candidates/{s['candidate_id']}")),
                           Td(s["current_title"] or "—"),
                           Td(Strong(f"{s['score']:.1f}"), cls="num score-cell"),
                           Td(Div(s["rationale"] or "—", style="font-size:12.5px;"),
                              Div(f"Strengths: {s['strengths']}", cls="factors") if s["strengths"] else None,
                              Div(f"Gaps: {s['gaps']}", cls="factors") if s["gaps"] else None),
                           Td(_pill(s["stage"])))
                        for i, s in enumerate(scores, 1)]
                      or [Tr(Td("Run produced no scores.", colspan="6"))]), cls="tbl")
    return Div(Div(head,
                   P(f"Ranked {run['candidates']} candidates with {run['model']} on "
                     f"{(run['created'] or '')[:16]}. Withheld from the model: {excluded}.",
                     style="color:var(--text-mute);font-size:12px;margin:0 0 10px;"),
                   tbl, cls="card"))


# ---------- talent analytics ------------------------------------------------

def analytics_page():
    k = talent.ats_kpis()
    stats = talent.offer_stats()
    fun = talent.funnel()
    mx = max((n for _, n in fun), default=1) or 1
    src = talent.source_effectiveness()
    tis = {r["stage"]: r for r in talent.time_in_stage()}
    load = talent.interviewer_load()
    ttf = talent.time_to_fill()
    avg_ttf = (sum(r["days"] for r in ttf) / len(ttf)) if ttf else 0

    funnel_card = Div(Div(H3("Pipeline funnel"), cls="card-header"),
                      *[Div(Div(s, style="color:var(--text-dim);"),
                            Div(Div(cls="funnel-bar", style=f"width:{max(2, 100 * n / mx):.0f}%;")),
                            Div(str(n), cls="v"), cls="funnel-row") for s, n in fun], cls="card")

    src_card = Div(Div(H3("Source effectiveness"), cls="card-header"),
                   Table(Thead(Tr(Th("Source"), Th("Applications", cls="num"),
                                  Th("Progressed", cls="num"), Th("Hires", cls="num"),
                                  Th("Conversion", cls="num"))),
                         Tbody(*[Tr(Td(_pill(s["source"] or "—")),
                                    Td(str(s["applications"]), cls="num"),
                                    Td(str(s["progressed"] or 0), cls="num"),
                                    Td(str(s["hires"] or 0), cls="num"),
                                    Td(f"{100 * (s['progressed'] or 0) / s['applications']:.0f}%"
                                       if s["applications"] else "—", cls="num"))
                                 for s in src]), cls="tbl"), cls="card")

    stage_card = Div(Div(H3("Average days in stage"), cls="card-header"),
                     Table(Thead(Tr(Th("Stage"), Th("Waiting", cls="num"), Th("Avg days", cls="num"))),
                           Tbody(*[Tr(Td(_pill(s)),
                                      Td(str((tis.get(s) or {}).get("n", 0)), cls="num"),
                                      Td(f"{(tis.get(s) or {}).get('avg_days') or 0:.0f}", cls="num"))
                                   for s in talent.OPEN_STAGES]), cls="tbl"), cls="card")

    load_card = Div(Div(H3("Interviewer load"), cls="card-header"),
                    Table(Thead(Tr(Th("Interviewer"), Th("Dept"), Th("Interviews", cls="num"),
                                   Th("Upcoming", cls="num"))),
                          Tbody(*[Tr(Td(l["interviewer"]), Td(l["dept"] or "—"),
                                     Td(str(l["interviews"]), cls="num"),
                                     Td(str(l["upcoming"] or 0), cls="num"))
                                  for l in load] or [Tr(Td("No interviews recorded.", colspan="4"))]),
                          cls="tbl"), cls="card")

    return (_title("Talent analytics", "Funnel, sources, speed and interviewer load"),
            Div(kpi_card("Time to fill", f"{avg_ttf:.0f}d" if ttf else "—",
                         f"across {len(ttf)} hires"),
                kpi_card("Offer acceptance", f"{stats['acceptance_rate']}%",
                         f"{stats['accepted']} of {stats['accepted'] + stats['declined']} decided"),
                kpi_card("Active applications", k["active_applications"],
                         f"{k['in_process']} past first screen"),
                kpi_card("CVs parsed", k["parsed"], f"of {k['candidates']} candidates"),
                cls="kpi-grid"),
            Div(funnel_card, stage_card, cls="grid-2"),
            src_card, load_card)


def prompt_versions_fragment(key: str):
    """Version history table — rendered standalone so the activate button can
    swap it without re-rendering the editor (and losing an unsaved edit)."""
    return Table(
        Thead(Tr(Th("Version"), Th("Updated"), Th("By"), Th("Active"), Th(""))),
        Tbody(*[Tr(Td(Strong(f"v{v['version']}")),
                   Td(Small(v["updated"] or "—", style="color:var(--text-mute);")),
                   Td(v["updated_by"] or "—"),
                   Td(_pill("Active") if v["is_active"] else Span("—", style="color:var(--text-mute);")),
                   Td(Button("Activate", cls="btn sm",
                             **{"hx-post": f"/talent/prompts/{key}/{v['version']}/activate",
                                "hx-target": "#prompt-versions", "hx-swap": "innerHTML"})
                      if not v["is_active"] else Span("—", style="color:var(--text-mute);")))
                for v in talent.prompt_versions(key)]), cls="tbl")
