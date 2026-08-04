"""Centre-pane renderers for the ATS — requisitions, candidates, CV extraction.

Same conventions as web/views.py: functions return FastHTML tuples, HTMX targets
a container id and swaps innerHTML.
"""
from __future__ import annotations

from fasthtml.common import (
    Div, H1, H3, H4, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button,
    Select, Option, Label, Textarea, NotStr, Strong, Small, Details, Summary,
)

import db
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
        _title("Requisitions", f"{len(js)} shown — synthetic demo pipeline"),
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
                   A("← Requisitions", href="/talent/jobs", cls="btn")),
            Div(job_main(job_id, stage), id="job-main"),
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

def candidates_list(q="", status="All"):
    cs = talent.candidates(q, status)
    seg = Div(*[A(s, href=f"/talent/candidates?status={s}", cls="active" if status == s else "")
                for s in ["All", "Active", "Hired", "Archived"]], cls="seg")
    search = Form(Input(type="search", name="q", value=q,
                        placeholder="Search name, email, title, employer…"),
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
                     Tbody(*[Tr(Td(d["file_name"]), Td(_pill(d["kind"])),
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

    return (head,
            Div(A("← Candidates", href="/talent/candidates", cls="btn"),
                style="margin-bottom:12px;"),
            Div(Div(id="cand-actions"), reparse, cls="card"),
            Div(Div(info, skills, exp), Div(edu, apps, docs), cls="detail-grid"))


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
