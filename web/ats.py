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
from web.i18n import current_lang, t_app

POLL_MS = 2500


def _c(key: str) -> str:
    return t_app(current_lang(), key)


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
        Thead(Tr(Th(_c("ats_req")), Th(_c("ats_role")), Th(_c("ats_department")), Th(_c("ats_hiring_manager")), Th(_c("ats_location")),
                 Th(_c("ats_openings"), cls="num"), Th(_c("ats_applicants"), cls="num"), Th(_c("ats_band"), cls="num"), Th(_c("ats_status")))),
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
            for j in js] or [Tr(Td(_c("ats_no_requisitions"), colspan="9"))]), cls="tbl")
    return (
        _title(_c("ats_jobs_title"), _c("ats_jobs_subtitle").format(n=len(js)),
               Div(A(_c("ats_careers_site"), href="/talent/careers", cls="btn"),
                   A(_c("ats_new_job"), href="/talent/jobs/new", cls="btn primary"),
                   style="display:flex;gap:6px;")),
        Div(kpi_card(_c("ats_kpi_open_reqs"), k["open_reqs"], _c("ats_kpi_seats").format(n=k["open_headcount"])),
            kpi_card(_c("ats_kpi_active_apps"), k["active_applications"], _c("ats_kpi_past_screen").format(n=k["in_process"])),
            kpi_card(_c("ats_kpi_candidates"), k["candidates"], _c("ats_kpi_cvs_parsed").format(n=k["parsed"])),
            kpi_card(_c("ats_kpi_parsed_ai"), k["parsed"], _c("ats_kpi_structured"),
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
        return _title(_c("ats_requisition_not_found")), P(_c("ats_no_such_requisition"))

    posting = recruitment.ensure_posting(job_id)
    detail = Div(Div(H3(_c("ats_requisition")), cls="card-header"),
                 Div(Span(_c("ats_code"), cls="k"), Span(j["code"] or "—"),
                     Span(_c("ats_department"), cls="k"), Span(j["dept"] or "—"),
                     Span(_c("ats_hiring_manager"), cls="k"), Span(j["hiring_manager"] or "—"),
                     Span(_c("ats_location"), cls="k"), Span(f"{j['location'] or '—'} · {j['remote_policy'] or ''}".strip(" ·")),
                      Span(_c("ats_openings"), cls="k"), Span(_c("ats_openings_remaining").format(n=j["headcount"] - (j["filled"] or 0), total=j["headcount"])),
                     Span(_c("ats_band"), cls="k"), Span(f"{money(j['comp_min'])}–{money(j['comp_max'])}" if j["comp_min"] else "—"),
                     Span(_c("ats_opened"), cls="k"), Span(j["opened_on"] or "—"),
                     Span(_c("ats_target"), cls="k"), Span(j["target_date"] or "—"),
                     Span(_c("ats_requirements"), cls="k"), Span(j["requirements"] or "—"),
                     cls="kv"), cls="card")

    return (_title(j["title"], f"{j['code']} · {j['dept'] or '—'} · {j['status']}",
                   Div(_pill(posting["publication_status"]),
                       A(_c("ats_public_page"), href=f"/jobs/{posting['slug']}", target="_blank", cls="btn")
                       if posting["publication_status"] == "Published" else None,
                       A(_c("ats_preview"), href=f"/talent/jobs/{job_id}/preview", target="_blank", cls="btn"),
                       A(_c("ats_edit_job"), href=f"/talent/jobs/{job_id}/edit", cls="btn primary"),
                       A(_c("ats_calibration"), href=f"/talent/jobs/{job_id}/calibration", cls="btn"),
                       A(_c("ats_back_jobs"), href="/talent/jobs", cls="btn"),
                       style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;")),
            Div(job_main(job_id, stage), id="job-main"),
            Div(ranking_panel(job_id), id="rank-panel"),
            detail)


def job_main(job_id, stage="All"):
    """The HTMX-swappable half of the requisition page: stage bar + applications."""
    j = talent.job(job_id)
    if not j:
        return P(_c("ats_no_such_requisition"))
    return Div(_stage_bar(job_id, talent.pipeline_counts(job_id), stage),
               Div(A(_c("ats_all"), href=f"/talent/jobs/{job_id}", cls="active" if stage == "All" else ""),
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
                       Button(_c("ats_reject"), cls="btn sm", title=_c("ats_reject"),
                              **{"hx-post": f"/talent/applications/{a['id']}/stage?stage=Rejected",
                                 "hx-target": "#job-main", "hx-swap": "innerHTML"})]
        rows.append(Tr(
            Td(A(f"{a['first_name']} {a['last_name']}".strip() or _c("ats_unnamed"),
                 href=f"/talent/candidates/{a['candidate_id']}")),
            Td(a["current_title"] or "—"), Td(a["current_employer"] or "—"),
             Td(_dash(a["years_experience"], _c("ats_years_short")), cls="num"),
            Td(_pill(a["stage"])),
            Td(f"{a['rating']:.1f}" if a["rating"] else "—", cls="num"),
            Td(a["applied_on"] or "—", style="color:var(--text-mute);white-space:nowrap;"),
            Td(Div(*actions, style="display:flex;gap:4px;") if actions else Span("—", style="color:var(--text-mute);"))))
    return Table(Thead(Tr(Th(_c("ats_candidate")), Th(_c("ats_current_title")), Th(_c("ats_employer")), Th(_c("ats_experience_short"), cls="num"),
                          Th(_c("ats_stage")), Th(_c("ats_rating"), cls="num"), Th(_c("ats_applied")), Th(_c("ats_move")))),
                 Tbody(*rows or [Tr(Td(_c("ats_no_applications"), colspan="8"))]), cls="tbl")


# ---------- CV upload -------------------------------------------------------

def upload_card(default_job: int | None = None):
    jobs = talent.jobs_min()
    warn = None
    if not llm.available():
        warn = P(llm.unavailable_reason(), cls="flag")
    return Div(
        Div(H3(_c("ats_add_candidate")),
            Small(f"{llm.provider()} · {llm.model_name()}", style="color:var(--text-mute);"),
            cls="card-header"),
        warn,
        Form(
            Div(Div(_c("ats_drop_cv"), cls="big"),
                Div(_c("ats_cv_help"), cls="small"),
                Input(type="file", name="cv", accept=".pdf,.docx,.txt,.md", required=True,
                      style="margin-top:12px;", aria_label=_c("ats_cv_file")),
                cls="drop-zone"),
            Div(Select(Option(_c("ats_no_requisition_pool"), value="0"),
                       *[Option(f"{j['title']} ({j['code']})", value=str(j["id"]),
                                selected=(default_job == j["id"])) for j in jobs],
                       name="job_id", cls="hr-inp", style="flex:1;min-width:220px;", aria_label=_c("ats_requisition")),
                Select(*[Option(s, value=s) for s in talent.SOURCES], name="source", cls="hr-inp", aria_label=_c("ats_source")),
                Button(_c("ats_upload_parse"), cls="btn primary", type="submit"),
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
        return Div(_c("ats_no_extraction"), id=f"xrun-{cid}")

    link = A(_c("ats_open_profile"), href=f"/talent/candidates/{cid}", cls="btn sm")
    if run["status"] == "pending":
        body = Div(Div(Span(cls="dot"), Span(_c("ats_parsing").format(model=run['model'])),
                       cls="thinking-indicator"),
                   id=f"xrun-{cid}",
                   **({"hx-get": f"/talent/candidates/{cid}/extraction",
                       "hx-trigger": f"every {POLL_MS}ms", "hx-swap": "outerHTML"} if poll else {}))
        return body
    if run["status"] == "error":
        return Div(P(_c("ats_extraction_failed").format(error=run['error']), cls="flag"), link, id=f"xrun-{cid}")

    prof = talent.candidate_profile(cid)
    return Div(
        P(Strong(_c("ats_parsed")),
          f"{_cand_name(c)}. "
          + _c("ats_role_value").format(role=c["current_title"] or _c("ats_not_stated"))
          + _c("ats_employer_value").format(employer=c["current_employer"] or _c("ats_not_stated"))
          + _c("ats_profile_counts").format(skills=len(prof["skills"]), roles=len(prof["experience"]))
          + _c("ats_profile_latency").format(education=len(prof["education"]), ms=run["latency_ms"] or 0),
          style="margin:0 0 8px;"),
        link, id=f"xrun-{cid}")


# ---------- candidates ------------------------------------------------------

def candidates_list(q="", status="All", *, location="", tag="", skill=""):
    cs = recruiting_ops.search_candidates(q, status=status, location=location, tag=tag, skill=skill)
    seg = Div(*[A(s, href=f"/talent/candidates?status={s}", cls="active" if status == s else "")
                for s in ["All", "Active", "Hired", "Archived"]], cls="seg")
    search = Form(Input(type="search", name="q", value=q,
                        placeholder=_c("ats_search_placeholder")),
                  Input(name="location", value=location, placeholder=_c("ats_location")),
                  Input(name="tag", value=tag, placeholder=_c("ats_tag")),
                  Input(name="skill", value=skill, placeholder=_c("ats_skill")),
                  Input(type="hidden", name="status", value=status),
                  cls="toolbar", method="get", action="/talent/candidates")
    rows = []
    for c in cs:
        parsed = c["extraction_status"]
        badge = _pill(parsed) if parsed else Span("—", style="color:var(--text-mute);")
        rows.append(Tr(
            Td(A(_cand_name(c), href=f"/talent/candidates/{c['id']}")),
            Td(c["current_title"] or "—"), Td(c["current_employer"] or "—"),
            Td(_dash(c["years_experience"], _c("ats_years_short")), cls="num"),
            Td(c["location"] or "—"),
            Td(str(c["n_skills"]) if c["n_skills"] else "—", cls="num"),
            Td(c["latest_job"] or "—"),
            Td(_pill(c["latest_stage"]) if c["latest_stage"] else Span("—", style="color:var(--text-mute);")),
            Td(_pill(c["source"] or "Direct")), Td(badge)))
    tbl = Table(Thead(Tr(Th(_c("ats_candidate")), Th(_c("ats_current_title")), Th(_c("ats_employer")), Th(_c("ats_experience_short"), cls="num"),
                         Th(_c("ats_location")), Th(_c("ats_skills"), cls="num"), Th(_c("ats_applied_to")), Th(_c("ats_stage")),
                         Th(_c("ats_source")), Th(_c("ats_cv_parse")))),
                Tbody(*rows or [Tr(Td(_c("ats_no_candidates"), colspan="10"))]), cls="tbl")
    return (_title(_c("ats_candidates_title"), _c("ats_shown").format(n=len(cs))), seg, search,
            Div(tbl, cls="card"), upload_card())


def candidate_detail(cid: int):
    p = talent.candidate_profile(cid)
    c = p["candidate"]
    if not c:
        return _title(_c("ats_candidate_not_found")), P(_c("ats_no_such_candidate"))

    head = Div(Span(_initials(c["first_name"] or "?", c["last_name"] or ""), cls="avatar"),
               Div(H1(_cand_name(c), style="margin:0;"),
                   P(c["headline"] or _c("ats_profile_not_parsed"), cls="sub")), cls="emp-head")

    info = Div(Div(H3(_c("ats_details")), cls="card-header"),
               Div(Span(_c("ats_email"), cls="k"), Span(c["email"] or "—"),
                   Span(_c("ats_phone"), cls="k"), Span(c["phone"] or "—"),
                   Span(_c("ats_location"), cls="k"), Span(c["location"] or "—"),
                   Span(_c("ats_current_role"), cls="k"), Span(c["current_title"] or "—"),
                   Span(_c("ats_employer"), cls="k"), Span(c["current_employer"] or "—"),
                   Span(_c("ats_experience"), cls="k"), Span(_dash(c["years_experience"], " " + _c("ats_years"))),
                   Span(_c("ats_linkedin"), cls="k"),
                   Span(A(c["linkedin_url"], href=f"https://{c['linkedin_url'].lstrip('https://')}",
                          target="_blank", rel="noopener") if c["linkedin_url"] else "—"),
                   Span(_c("ats_source"), cls="k"), _pill(c["source"] or "Direct"),
                   Span(_c("ats_referred_by"), cls="k"), Span(c["referrer"] or "—"),
                   Span(_c("ats_consent"), cls="k"),
                   Span(c["consent_at"] or _c("ats_not_recorded"),
                        style="" if c["consent_at"] else "color:var(--warn);"),
                   Span(_c("ats_status"), cls="k"), _pill(c["status"]),
                   cls="kv"), cls="card")

    skills = Div(Div(H3(_c("ats_skills")), Small(_c("ats_extracted").format(n=len(p['skills'])), style="color:var(--text-mute);"),
                     cls="card-header"),
                 Div(*[Span(s["skill"],
                            Span(f"{s['years']:.0f}y" if s["years"] else (s["level"] or ""), cls="yrs"),
                            cls="chip" + (" expert" if (s["level"] or "") == "Expert" else ""),
                            title=s["evidence"] or "")
                       for s in p["skills"]] or [P(_c("ats_no_skills"), style="color:var(--text-mute);")],
                     cls="chips"), cls="card")

    exp_items = [Div(Div(x["title"] or "—", cls="role"),
                     Div(x["employer"] or "—", Span(f" · {x['location']}" if x["location"] else "",
                                                    style="color:var(--text-mute);"), cls="org"),
                     Div(f"{x['start_date'] or '?'} → {x['end_date'] or 'present'}", cls="when"),
                     Div(x["summary"], cls="what") if x["summary"] else None,
                     cls="tl-item") for x in p["experience"]]
    exp = Div(Div(H3(_c("ats_experience")), cls="card-header"),
              Div(*exp_items, cls="timeline") if exp_items
              else P(_c("ats_no_experience"), style="color:var(--text-mute);"), cls="card")

    edu = Div(Div(H3(_c("ats_education")), cls="card-header"),
              Table(Tbody(*[Tr(Td(Strong(e["institution"] or "—")),
                               Td(f"{e['qualification'] or ''} {e['field'] or ''}".strip() or "—"),
                               Td(e["end_year"] or "—", cls="num"))
                            for e in p["education"]] or [Tr(Td(_c("ats_none_extracted"), colspan="3"))]),
                    cls="tbl"), cls="card")

    apps = Div(Div(H3(_c("ats_applications")), cls="card-header"),
               Table(Thead(Tr(Th(_c("ats_requisition")), Th(_c("ats_stage")), Th(_c("ats_status")), Th(_c("ats_applied")))),
                     Tbody(*[Tr(Td(A(a["job_title"], href=f"/talent/jobs/{a['job_id']}")),
                                 Td(_pill(a["stage"])), Td(_pill(a["status"])),
                                 Td(a["applied_on"] or "—"))
                             for a in p["applications"]] or [Tr(Td(_c("ats_not_applied"), colspan="4"))]),
                     cls="tbl"), cls="card")

    docs = Div(Div(H3(_c("ats_documents_extraction")), cls="card-header"),
               Table(Thead(Tr(Th(_c("ats_file")), Th(_c("ats_kind")), Th(_c("ats_size"), cls="num"), Th(_c("ats_uploaded")))),
                     Tbody(*[Tr(Td(A(d["file_name"], href=f"/talent/documents/{d['id']}")), Td(_pill(d["kind"])),
                                Td(f"{(d['bytes'] or 0) / 1024:.0f} kB", cls="num"),
                                Td(d["uploaded_on"] or "—", style="color:var(--text-mute);"))
                             for d in p["documents"]] or [Tr(Td(_c("ats_no_documents"), colspan="4"))]), cls="tbl"),
               *( [Details(Summary(_c("ats_extraction_runs").format(n=len(p['runs'])),
                                   style="cursor:pointer;font-size:13px;margin-top:10px;"),
                           Table(Thead(Tr(Th(_c("ats_model")), Th(_c("ats_prompt")), Th(_c("ats_status")), Th(_c("ats_latency"), cls="num"), Th(_c("ats_when")))),
                                 Tbody(*[Tr(Td(Small(r["model"] or "—")),
                                            Td(f"v{r['prompt_version']}"), Td(_pill(r["status"])),
                                            Td(f"{r['latency_ms'] or 0} ms", cls="num"),
                                            Td(Small(r["created"] or "—", style="color:var(--text-mute);")))
                                         for r in p["runs"]]), cls="tbl"),
                           *([P(_c("ats_last_error").format(error=p['runs'][0]['error']), cls="flag")]
                             if p["runs"] and p["runs"][0]["error"] else []))]
                  if p["runs"] else []),
               cls="card")

    reparse = Form(
        Select(*[Option(f"{j['title']} ({j['code']})", value=str(j["id"]))
                 for j in talent.jobs_min()] or [Option(_c("ats_no_open_requisitions"), value="0")],
               name="job_id", cls="hr-inp"),
        Button(_c("ats_apply_requisition"), cls="btn", type="submit"),
        **{"hx-post": f"/talent/candidates/{cid}/apply", "hx-target": "#cand-actions", "hx-swap": "innerHTML"},
        cls="inline-form", style="gap:8px;flex-wrap:wrap;")

    live_app = next((a for a in p["applications"] if a["status"] == "Active"), None)
    iv_panel = Div(interviews_panel(live_app["id"]), id="iv-panel") if live_app else None
    offer_panel = _offer_panel(live_app, c) if live_app else None

    return (head,
            Div(A(_c("ats_back_candidates"), href="/talent/candidates", cls="btn"),
                style="margin-bottom:12px;"),
            Div(Div(id="cand-actions"), reparse, cls="card"),
            Div(Div(info, skills, exp, iv_panel, offer_panel),
                Div(edu, apps, docs), cls="detail-grid"))


def _offer_panel(app, cand):
    """Draft or show the offer for the candidate's live application."""
    existing = talent.offer_for_application(app["id"])
    if existing:
        return Div(Div(H3(_c("ats_offer")), _pill(existing["status"]), cls="card-header"),
                   Div(Span(_c("ats_salary"), cls="k"), Span(Strong(money(existing["salary"]))),
                       Span(_c("ats_start_date"), cls="k"), Span(existing["start_date"] or "—"),
                       Span(_c("ats_expires"), cls="k"), Span(existing["expires_on"] or "—"),
                       cls="kv"),
                   Div(A(_c("ats_open_offer"), href=f"/talent/offers/{existing['id']}", cls="btn sm"),
                       style="margin-top:10px;"), cls="card")
    if app["stage"] not in ("Interview", "Offer"):
        return None
    return Div(Div(H3(_c("ats_make_offer")), cls="card-header"),
               P(_c("ats_offer_help"),
                 style="color:var(--text-mute);font-size:12.5px;margin:0 0 10px;"),
               Form(Input(name="salary", type="number", step="any", placeholder=_c("ats_salary"),
                          cls="hr-inp", required=True, style="width:140px;"),
                    Input(type="date", name="start_date", cls="hr-inp", required=True, aria_label=_c("ats_start_date")),
                    Input(type="date", name="expires_on", cls="hr-inp", aria_label=_c("ats_expires")),
                    Button(_c("ats_draft_offer"), cls="btn primary", type="submit"),
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
        Div(Button(_c("ats_save_new_version"), cls="btn primary", type="submit"),
            Button(_c("ats_restore_default"), cls="btn", type="submit",
                   name="restore", value="1"), cls="prompt-actions"),
        method="post", action=f"/talent/prompts?key={key}")

    return (
        _title(_c("ats_prompts_title"), _c("ats_prompts_subtitle")),
        banner,
        Div(Div(Div(H3(_c("ats_cv_guidance")),
                    Small(f"active: v{active['version'] if active else 0} · {llm.model_name()}",
                          style="color:var(--text-mute);"), cls="card-header"),
                P(_c("ats_prompt_help"),
                  style="color:var(--text-mute);font-size:12.5px;margin:0 0 10px;"),
                editor, cls="card"),
            Div(Div(Div(H3(_c("ats_versions")), cls="card-header"),
                    Div(prompt_versions_fragment(key), id="prompt-versions"), cls="card"),
                Div(Div(H3(_c("ats_output_contract")), Small(_c("ats_code_readonly"),
                                                     style="color:var(--text-mute);"), cls="card-header"),
                    Div(cv_extract.OUTPUT_FORMAT, cls="contract-box"), cls="card")),
            cls="prompt-layout"))


# ---------- interviews ------------------------------------------------------

def interviews_panel(app_id: int):
    ivs = talent.interviews_for(app_id)
    emps = db.employees_min()
    rows = []
    for iv in ivs:
        rows.append(Tr(
            Td(_pill(iv["kind"] or "—")),
            Td(iv["interviewer"] or _c("ats_unassigned")),
            Td(iv["scheduled_at"] or "—", style="white-space:nowrap;"),
            Td(_pill(iv["mode"] or "—")),
            Td(f"{iv['avg_score']:.1f}" if iv["avg_score"] else "—", cls="num"),
            Td(_pill(iv["recommendation"]) if iv["recommendation"]
               else Span("—", style="color:var(--text-mute);")),
            Td(_pill(iv["status"])),
            Td(A(_c("ats_scorecard"), href=f"/talent/interviews/{iv['id']}", cls="btn sm")
               if iv["status"] != "Completed" else
               A(_c("ats_view"), href=f"/talent/interviews/{iv['id']}", cls="btn sm"))))
    tbl = Table(Thead(Tr(Th(_c("ats_stage")), Th(_c("ats_interviewer")), Th(_c("ats_when")), Th(_c("ats_mode")),
                         Th(_c("ats_score"), cls="num"), Th(_c("ats_recommendation")), Th(_c("ats_status")), Th(""))),
                Tbody(*rows or [Tr(Td(_c("ats_no_interviews"), colspan="8"))]), cls="tbl")
    form = Form(
        Select(*[Option(k, value=k) for k in talent.INTERVIEW_KINDS], name="kind", cls="hr-inp"),
        Select(Option(_c("ats_interviewer_unassigned"), value="0"),
               *[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in emps],
               name="interviewer_id", cls="hr-inp"),
        Input(type="datetime-local", name="scheduled_at", cls="hr-inp", required=True),
        Select(*[Option(m, value=m) for m in talent.INTERVIEW_MODES], name="mode", cls="hr-inp"),
        Button(_c("ats_schedule"), cls="btn primary", type="submit"),
        **{"hx-post": f"/talent/applications/{app_id}/interview", "hx-target": "#iv-panel",
           "hx-swap": "innerHTML"},
        cls="inline-form", style="flex-wrap:wrap;gap:8px;margin-bottom:12px;")
    return Div(Div(Div(H3(_c("ats_interviews")), cls="card-header"), form, tbl, cls="card"))


def scorecard_page(interview_id: int):
    iv = db.one("""SELECT i.*, a.candidate_id, a.job_id, c.first_name, c.last_name,
                          j.title job_title, e.first_name||' '||e.last_name interviewer
                   FROM interviews i JOIN applications a ON a.id=i.application_id
                   JOIN candidates c ON c.id=a.candidate_id
                   JOIN job_openings j ON j.id=a.job_id
                   LEFT JOIN employees e ON e.id=i.interviewer_id WHERE i.id=?""", (interview_id,))
    if not iv:
        return _title(_c("ats_interview_not_found")), P(_c("ats_no_such_interview"))
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
                         for i, lbl in ((5, _c("ats_outstanding")), (4, _c("ats_strong")),
                                        (3, _c("ats_solid")), (2, _c("ats_mixed")),
                                        (1, _c("ats_weak")))],
                       name=f"score_{c['id']}", cls="hr-inp", style="width:170px;"),
                Input(name=f"comment_{c['id']}", value=cur.get("comment") or "",
                      placeholder=_c("ats_evidence"), cls="hr-inp", style="flex:1;min-width:180px;"),
                style="display:flex;gap:8px;flex:1;"),
            style="display:flex;gap:14px;align-items:flex-start;justify-content:space-between;"
                  "padding:10px 0;border-bottom:1px solid var(--border);"))

    return (_title(_c("ats_scorecard_title").format(name=f"{iv['first_name']} {iv['last_name']}"),
                   _c("ats_interview_context").format(kind=iv["kind"], job=iv["job_title"],
                                                       interviewer=iv["interviewer"] or _c("ats_unassigned")),
                   A(_c("ats_back_candidate"), href=f"/talent/candidates/{iv['candidate_id']}", cls="btn")),
            Div(Div(H3(_c("ats_competencies")), _pill(iv["status"]), cls="card-header"),
                Form(*fields,
                     Div(Label(_c("ats_overall_recommendation"),
                               style="font-size:13px;font-weight:600;margin-right:10px;"),
                         Select(*[Option(r, value=r, selected=(iv["recommendation"] == r))
                                  for r in talent.RECOMMENDATIONS],
                                name="recommendation", cls="hr-inp"),
                         style="margin-top:14px;display:flex;align-items:center;"),
                     Div(Label(_c("ats_notes"), style="font-size:13px;font-weight:600;"),
                         Textarea(iv["notes"] or "", name="notes", cls="prompt-box",
                                  style="min-height:130px;margin-top:6px;",
                                  placeholder=_c("ats_notes_placeholder")),
                         style="margin-top:12px;"),
                     Button(_c("ats_save_scorecard"), cls="btn primary", type="submit",
                            style="margin-top:12px;"),
                     method="post", action=f"/talent/interviews/{interview_id}"),
                cls="card"))


def calibration_page(job_id: int):
    j = talent.job(job_id)
    if not j:
        return _title(_c("ats_requisition_not_found")), P(_c("ats_no_such_requisition"))
    comps, by_cand = talent.calibration(job_id)

    def cell(v):
        if v is None:
            return Td("—", cls="num", style="color:var(--text-mute);")
        bg = ("var(--accent-light)" if v >= 4 else "var(--warn-light)" if v >= 3
              else "var(--danger-light)")
        fg = ("var(--accent-hover)" if v >= 4 else "#92400e" if v >= 3 else "#9f1239")
        return Td(Span(f"{v:.1f}", cls="heat", style=f"background:{bg};color:{fg};"), cls="num")

    tbl = Table(Thead(Tr(Th(_c("ats_candidate")), *[Th(c, cls="num") for c in comps],
                         Th(_c("ats_mean"), cls="num"), Th(_c("ats_stage")))),
                Tbody(*[Tr(Td(A(name, href=f"/talent/candidates/{d['candidate_id']}")),
                           *[cell(d["scores"].get(c)) for c in comps],
                           Td(Strong(f"{d['mean']:.2f}"), cls="num"),
                           Td(_pill(d["stage"])))
                        for name, d in by_cand.items()]
                      or [Tr(Td(_c("ats_no_scorecards"), colspan=str(len(comps) + 3)))]),
                cls="tbl")
    return (_title(_c("ats_calibration_title").format(title=j['title']),
                   _c("ats_calibration_subtitle"),
                   A(_c("ats_back_requisition"), href=f"/talent/jobs/{job_id}", cls="btn")),
            Div(Div(H3(_c("ats_scores_by_competency")), cls="card-header"), tbl, cls="card"))


# ---------- offers ----------------------------------------------------------

def offers_page(status="All"):
    os_ = talent.all_offers(status)
    stats = talent.offer_stats()
    seg = Div(*[A(s, href=f"/talent/offers?status={s}", cls="active" if status == s else "")
                for s in ["All"] + talent.OFFER_STATUSES], cls="seg")
    return (_title(_c("ats_offers_title"), _c("ats_offers_subtitle")),
            Div(kpi_card(_c("ats_acceptance_rate"), f"{stats['acceptance_rate']}%",
                         _c("ats_accepted_declined").format(accepted=stats["accepted"], declined=stats["declined"])),
                kpi_card(_c("ats_in_flight"), stats["pending"], _c("ats_offer_states")),
                kpi_card(_c("ats_accepted"), stats["accepted"], _c("ats_converted_employees")),
                kpi_card(_c("ats_total_offers"), stats["total"]),
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
            acts.append(Button(_c("ats_declined"), cls="btn sm",
                               **{"hx-post": f"/talent/offers/{o['id']}/status?status=Declined",
                                  "hx-target": "#offers", "hx-swap": "innerHTML"}))
        rows.append(Tr(
            Td(A(f"{o['first_name']} {o['last_name']}",
                 href=f"/talent/candidates/{o['candidate_id']}")),
            Td(o["job_title"]), Td(money(o["salary"]), cls="num"),
            Td(o["start_date"] or "—", style="white-space:nowrap;"),
            Td(o["expires_on"] or "—", style="white-space:nowrap;color:var(--text-mute);"),
            Td(_pill(o["status"])),
            Td(A(_c("ats_letter"), href=f"/talent/offers/{o['id']}", cls="btn sm")),
            Td(Div(*acts, style="display:flex;gap:4px;") if acts
               else Span("—", style="color:var(--text-mute);"))))
    return Div(Div(Table(Thead(Tr(Th(_c("ats_candidate")), Th(_c("ats_role")), Th(_c("ats_salary"), cls="num"),
                                  Th(_c("ats_start")), Th(_c("ats_expires")), Th(_c("ats_status")), Th(""), Th(_c("ats_move")))),
                         Tbody(*rows or [Tr(Td(_c("ats_no_offers"), colspan="8"))]), cls="tbl"),
                   cls="card"))


def offer_detail(offer_id: int):
    o = talent.offer(offer_id)
    if not o:
        return _title(_c("ats_offer_not_found")), P(_c("ats_no_such_offer"))
    emp = db.one("SELECT id FROM employees WHERE candidate_id=?", (o["candidate_id"],))
    info = Div(Div(H3(_c("ats_offer")), _pill(o["status"]), cls="card-header"),
               Div(Span(_c("ats_candidate"), cls="k"),
                   Span(A(f"{o['first_name']} {o['last_name']}",
                          href=f"/talent/candidates/{o['candidate_id']}")),
                   Span(_c("ats_role"), cls="k"), Span(o["job_title"]),
                   Span(_c("ats_department"), cls="k"), Span(o["dept"] or "—"),
                   Span(_c("ats_salary"), cls="k"), Span(Strong(money(o["salary"]))),
                   Span(_c("ats_start_date"), cls="k"), Span(o["start_date"] or "—"),
                   Span(_c("ats_expires"), cls="k"), Span(o["expires_on"] or "—"),
                   Span(_c("ats_approved_by"), cls="k"), Span(o["approved_by"] or "—"),
                   Span(_c("ats_sent"), cls="k"), Span(o["sent_at"] or "—"),
                   Span(_c("ats_signed"), cls="k"), Span(o["signed_at"] or "—"),
                   *([Span(_c("ats_employee_record"), cls="k"),
                      Span(A(_c("ats_view_employee"), href=f"/employees/{emp['id']}"))] if emp else []),
                   cls="kv"), cls="card")
    letter = Div(Div(H3(_c("ats_offer_letter")),
                     Small(_c("ats_letter_help"),
                           style="color:var(--text-mute);"), cls="card-header"),
                 Div(NotStr((o["letter"] or _c("ats_no_letter")).replace("\n", "<br>")),
                     style="font-size:13.5px;line-height:1.65;"), cls="card")
    return (_title(_c("ats_offer_detail_title").format(name=f"{o['first_name']} {o['last_name']}"),
                   f"{o['job_code']} · {o['job_title']}",
                   A(_c("ats_back_offers"), href="/talent/offers", cls="btn")),
            Div(Div(letter), Div(info), cls="detail-grid"))


# ---------- ranking ---------------------------------------------------------

def ranking_panel(job_id: int):
    run, scores = talent.rankings_for_job(job_id)
    head = Div(H3(_c("ats_ranking_title")),
               Button(_c("ats_rank_candidates"), cls="btn sm primary",
                      **{"hx-post": f"/talent/jobs/{job_id}/rank", "hx-target": "#rank-panel",
                         "hx-swap": "innerHTML"}), cls="card-header")
    if not run:
        return Div(Div(head,
                       P(_c("ats_ranking_help"), style="color:var(--text-mute);font-size:12.5px;"),
                       cls="card"))
    if run["status"] == "error":
        return Div(Div(head, P(_c("ats_last_run_failed").format(error=run["error"]), cls="flag"), cls="card"))

    excluded = ", ".join(json.loads(run["excluded_json"] or "[]"))
    tbl = Table(Thead(Tr(Th("#", cls="num"), Th(_c("ats_candidate")), Th(_c("ats_current_title")),
                         Th(_c("ats_score"), cls="num"), Th(_c("ats_why")), Th(_c("ats_stage")))),
                Tbody(*[Tr(Td(str(i), cls="num"),
                           Td(A(f"{s['first_name']} {s['last_name']}",
                                href=f"/talent/candidates/{s['candidate_id']}")),
                           Td(s["current_title"] or "—"),
                           Td(Strong(f"{s['score']:.1f}"), cls="num score-cell"),
                           Td(Div(s["rationale"] or "—", style="font-size:12.5px;"),
                              Div(_c("ats_strengths").format(value=s['strengths']), cls="factors") if s["strengths"] else None,
                              Div(_c("ats_gaps").format(value=s['gaps']), cls="factors") if s["gaps"] else None),
                           Td(_pill(s["stage"])))
                        for i, s in enumerate(scores, 1)]
                      or [Tr(Td(_c("ats_no_scores"), colspan="6"))]), cls="tbl")
    return Div(Div(head,
                   P(_c("ats_ranked_summary").format(candidates=run["candidates"], model=run["model"],
                                                      created=(run["created"] or "")[:16], excluded=excluded),
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

    funnel_card = Div(Div(H3(_c("ats_pipeline_funnel")), cls="card-header"),
                      *[Div(Div(s, style="color:var(--text-dim);"),
                            Div(Div(cls="funnel-bar", style=f"width:{max(2, 100 * n / mx):.0f}%;")),
                            Div(str(n), cls="v"), cls="funnel-row") for s, n in fun], cls="card")

    src_card = Div(Div(H3(_c("ats_source_effectiveness")), cls="card-header"),
                   Table(Thead(Tr(Th(_c("ats_source")), Th(_c("ats_applications"), cls="num"),
                                  Th(_c("ats_progressed"), cls="num"), Th(_c("ats_hires"), cls="num"),
                                  Th(_c("ats_conversion"), cls="num"))),
                         Tbody(*[Tr(Td(_pill(s["source"] or "—")),
                                    Td(str(s["applications"]), cls="num"),
                                    Td(str(s["progressed"] or 0), cls="num"),
                                    Td(str(s["hires"] or 0), cls="num"),
                                    Td(f"{100 * (s['progressed'] or 0) / s['applications']:.0f}%"
                                       if s["applications"] else "—", cls="num"))
                                 for s in src]), cls="tbl"), cls="card")

    stage_card = Div(Div(H3(_c("ats_avg_days_stage")), cls="card-header"),
                     Table(Thead(Tr(Th(_c("ats_stage")), Th(_c("ats_waiting"), cls="num"), Th(_c("ats_avg_days"), cls="num"))),
                           Tbody(*[Tr(Td(_pill(s)),
                                      Td(str((tis.get(s) or {}).get("n", 0)), cls="num"),
                                      Td(f"{(tis.get(s) or {}).get('avg_days') or 0:.0f}", cls="num"))
                                   for s in talent.OPEN_STAGES]), cls="tbl"), cls="card")

    load_card = Div(Div(H3(_c("ats_interviewer_load")), cls="card-header"),
                    Table(Thead(Tr(Th(_c("ats_interviewer")), Th(_c("ats_dept_short")), Th(_c("ats_interviews"), cls="num"),
                                   Th(_c("ats_upcoming"), cls="num"))),
                          Tbody(*[Tr(Td(l["interviewer"]), Td(l["dept"] or "—"),
                                     Td(str(l["interviews"]), cls="num"),
                                     Td(str(l["upcoming"] or 0), cls="num"))
                                  for l in load] or [Tr(Td(_c("ats_no_interviews_recorded"), colspan="4"))]),
                          cls="tbl"), cls="card")

    return (_title(_c("ats_analytics_title"), _c("ats_analytics_subtitle")),
             Div(kpi_card(_c("ats_time_to_fill"), f"{avg_ttf:.0f}d" if ttf else "—",
                          _c("ats_across_hires").format(n=len(ttf))),
                 kpi_card(_c("ats_offer_acceptance"), f"{stats['acceptance_rate']}%",
                          _c("ats_decided").format(accepted=stats["accepted"], total=stats["accepted"] + stats["declined"])),
                kpi_card(_c("ats_kpi_active_apps"), k["active_applications"],
                         _c("ats_kpi_past_screen").format(n=k["in_process"])),
                 kpi_card(_c("ats_cvs_parsed"), k["parsed"], _c("ats_of_candidates").format(n=k["candidates"])),
                cls="kpi-grid"),
            Div(funnel_card, stage_card, cls="grid-2"),
            src_card, load_card)


def prompt_versions_fragment(key: str):
    """Version history table — rendered standalone so the activate button can
    swap it without re-rendering the editor (and losing an unsaved edit)."""
    return Table(
        Thead(Tr(Th(_c("ats_version")), Th(_c("ats_updated")), Th(_c("ats_by")), Th(_c("ats_active")), Th(""))),
        Tbody(*[Tr(Td(Strong(f"v{v['version']}")),
                   Td(Small(v["updated"] or "—", style="color:var(--text-mute);")),
                   Td(v["updated_by"] or "—"),
                   Td(_pill("Active") if v["is_active"] else Span("—", style="color:var(--text-mute);")),
                   Td(Button(_c("ats_activate"), cls="btn sm",
                             **{"hx-post": f"/talent/prompts/{key}/{v['version']}/activate",
                                "hx-target": "#prompt-versions", "hx-swap": "innerHTML"})
                      if not v["is_active"] else Span("—", style="color:var(--text-mute);")))
                for v in talent.prompt_versions(key)]), cls="tbl")
