"""Recruiter job authoring and candidate-facing careers pages."""
from __future__ import annotations

import json

from fasthtml.common import (
    A, Body, Button, Div, Footer, Form, H1, H2, H3, Head, Html, Img, Input, Label,
    Link, Main, Meta, Nav, NotStr, Option, P, Script, Section, Select, Span, Strong, Style,
    Textarea, Title,
)

import recruitment
import recruiting_ops
from web.landing import FAVICON
from web.seo import BASE_URL
from web.views import _pill, _title

CAREERS_CSS = """
:root{--brand:#0891b2;--accent:#0e7490;--ink:#111827;--muted:#667085;--line:#e5e7eb;--wash:#f8fafc}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;background:white}
.c-nav{max-width:1120px;height:70px;margin:auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line)}
.c-brand{display:flex;align-items:center;gap:11px;color:var(--ink);font-weight:750;text-decoration:none}.c-logo{width:34px;height:34px;object-fit:contain;border-radius:9px}.c-mark{width:34px;height:34px;border-radius:9px;background:var(--brand);display:grid;place-items:center;color:#fff}
.c-link{color:var(--accent);text-decoration:none;font-weight:650}.c-hero{background:linear-gradient(145deg,color-mix(in srgb,var(--brand) 12%,white),white 70%);border-bottom:1px solid var(--line)}
.c-hero-in{max-width:1120px;margin:auto;padding:82px 24px 72px}.c-kicker{font-size:12px;color:var(--accent);font-weight:750;letter-spacing:.15em;text-transform:uppercase}.c-hero h1{font-size:clamp(38px,6vw,66px);line-height:1.04;letter-spacing:-.045em;margin:18px 0;max-width:850px}.c-lede{font-size:19px;color:var(--muted);line-height:1.65;max-width:720px}
.c-main{max-width:1120px;margin:auto;padding:54px 24px 88px}.c-main h2{font-size:30px;letter-spacing:-.025em}.jobs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:24px}.job-card{border:1px solid var(--line);border-radius:18px;padding:24px;text-decoration:none;color:var(--ink);transition:.15s;background:white}.job-card:hover{border-color:var(--brand);transform:translateY(-2px);box-shadow:0 12px 30px rgba(15,23,42,.08)}.job-card h3{font-size:21px;margin:0 0 10px}.meta{display:flex;gap:8px;flex-wrap:wrap;color:var(--muted);font-size:13px}.chip{background:var(--wash);border-radius:999px;padding:5px 9px}.summary{color:var(--muted);line-height:1.55;margin:16px 0 0}.empty{padding:40px;border:1px dashed var(--line);border-radius:18px;color:var(--muted);text-align:center}
.job-head{max-width:900px;margin:auto;padding:64px 24px 28px}.back{display:inline-block;margin-bottom:24px}.job-head h1{font-size:clamp(36px,6vw,60px);letter-spacing:-.045em;line-height:1.05;margin:10px 0 20px}.job-layout{max-width:900px;margin:auto;padding:12px 24px 90px;display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:34px}.copy h2{font-size:23px;margin:34px 0 10px}.copy p{white-space:pre-line;color:#374151;line-height:1.75}.apply{border:1px solid var(--line);border-radius:18px;padding:22px;align-self:start;position:sticky;top:20px;background:white;box-shadow:0 12px 30px rgba(15,23,42,.06)}.apply h2{margin:0 0 6px}.field{display:grid;gap:6px;margin:13px 0}.field label{font-size:12px;font-weight:700}.field input,.field textarea{width:100%;border:1px solid #cfd5dd;border-radius:10px;padding:10px 11px;font:inherit}.field textarea{min-height:100px;resize:vertical}.check{display:flex;gap:9px;align-items:flex-start;color:var(--muted);font-size:12px;line-height:1.45}.check input{margin-top:3px}.apply button{width:100%;border:0;border-radius:10px;padding:12px;background:var(--brand);color:white;font-weight:750;cursor:pointer}.error{padding:10px;border-radius:9px;background:#fff1f2;color:#9f1239;font-size:13px}.fine{font-size:11px;color:var(--muted);line-height:1.45}.success{max-width:680px;margin:90px auto;padding:40px 24px;text-align:center}.success h1{font-size:42px}.success p{color:var(--muted);line-height:1.65}.c-footer{border-top:1px solid var(--line);padding:30px 24px;text-align:center;color:var(--muted);font-size:12px}
.preview{background:#fff7ed;color:#9a3412;text-align:center;padding:8px;font-size:12px;font-weight:700}
@media(max-width:760px){.jobs{grid-template-columns:1fr}.job-layout{grid-template-columns:1fr}.apply{position:static}.c-hero-in{padding-top:58px}.c-nav{height:62px}}
"""


def _site_head(site: dict, title: str, description: str, *, path: str,
               structured: dict | None = None):
    canonical = BASE_URL + path
    return Head(
        Title(title), Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=description),
        Link(rel="canonical", href=canonical),
        Link(rel="icon", href=site.get("favicon_url") or FAVICON),
        Meta(property="og:type", content="website"), Meta(property="og:title", content=title),
        Meta(property="og:description", content=description), Meta(property="og:url", content=canonical),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;750&display=swap"),
        Style(f":root{{--brand:{site['brand_color']};--accent:{site['accent_color']}}}" + CAREERS_CSS),
        Script(NotStr(json.dumps(structured).replace("<", "\\u003c")),
               type="application/ld+json") if structured else None,
    )


def _brand(site: dict, href: str = "/careers"):
    visual = Img(src=site["logo_url"], cls="c-logo", alt="") if site.get("logo_url") else Span("F", cls="c-mark")
    return A(visual, Span(site["name"]), href=href, cls="c-brand")


def careers_page(site: dict, jobs: list[dict], *, careers_path: str = "/careers",
                 job_prefix: str = "/jobs"):
    title = f"Careers · {site['name']}"
    description = site.get("introduction") or "Explore our open roles."
    cards = [
        A(H3(j["public_title"]),
          Div(Span(j.get("department") or "Team", cls="chip"),
              Span(j.get("location") or "Flexible", cls="chip"),
              Span(j.get("remote_policy") or "", cls="chip") if j.get("remote_policy") else None,
              cls="meta"),
          P(j.get("summary") or "Learn more about this opportunity.", cls="summary"),
          href=f"{job_prefix}/{j['slug']}", cls="job-card")
        for j in jobs
    ]
    structured = {"@context": "https://schema.org", "@type": "CollectionPage",
                  "name": title, "url": BASE_URL + careers_path, "description": description}
    return Html(
        _site_head(site, title, description, path=careers_path, structured=structured),
        Body(Nav(_brand(site, careers_path), A("FastHRM", href="/", cls="c-link"), cls="c-nav"),
             Main(Section(Div(Span("Join the team", cls="c-kicker"),
                                  H1(site.get("headline") or "Do work that matters."),
                                  P(description, cls="c-lede"), cls="c-hero-in"), cls="c-hero"),
                  Section(H2("Open roles"), Div(*cards, cls="jobs") if cards else
                          Div("There are no open roles right now. Please check back soon.", cls="empty"),
                          cls="c-main")),
             Footer(f"Recruitment managed with {site['name']}", cls="c-footer"))
    )


def job_page(job: dict, *, error: str = "", values: dict | None = None, preview: bool = False,
             careers_path: str = "/careers", job_path: str | None = None,
             apply_path: str | None = None):
    values = values or {}
    site = {"name": job.get("career_site_name") or "FastHRM Careers",
            "brand_color": job.get("brand_color") or "#0891b2",
            "accent_color": job.get("accent_color") or "#0e7490",
            "logo_url": job.get("logo_url") or "",
            "favicon_url": job.get("favicon_url") or ""}
    job_path = job_path or f"/jobs/{job['slug']}"
    apply_path = apply_path or f"/jobs/{job['slug']}/apply"
    title = job.get("seo_title") or f"{job['public_title']} · {site['name']}"
    description = job.get("seo_description") or job.get("summary") or job["public_title"]
    structured = {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": job["public_title"], "description": job.get("description") or "",
        "datePosted": (job.get("published_at") or "")[:10],
        "validThrough": job.get("application_deadline"),
        "employmentType": job.get("employment_type"),
        "hiringOrganization": {"@type": "Organization", "name": site["name"]},
        "jobLocationType": "TELECOMMUTE" if job.get("remote_policy") == "Remote" else None,
        "jobLocation": {"@type": "Place", "address": job.get("location") or ""},
        "url": BASE_URL + job_path,
    }
    privacy = job.get("privacy_policy_url") or "/privacy"
    application_form = recruiting_ops.application_form(job["job_id"])
    custom_fields = []
    for field in (application_form or {}).get("fields", []):
        condition = field.get("condition") or {}
        attrs = {"data-condition-field": condition.get("field", ""),
                 "data-condition-value": condition.get("equals", "")}
        if field["field_type"] == "select":
            control = Select(Option("Select…", value=""),
                             *[Option(option, value=option) for option in field["options"]],
                             name=field["field_key"], required=bool(field["required"]))
        elif field["field_type"] == "textarea":
            control = Textarea(values.get(field["field_key"], ""), name=field["field_key"],
                               required=bool(field["required"]))
        elif field["field_type"] == "checkbox":
            control = Input(type="checkbox", name=field["field_key"], value="yes",
                            required=bool(field["required"]))
        else:
            control = Input(type=field["field_type"] if field["field_type"] in {"date", "number", "email", "url"} else "text",
                            name=field["field_key"], value=values.get(field["field_key"], ""),
                            required=bool(field["required"]))
        custom_fields.append(Div(Label(field["label"]), control, cls="field custom-field", **attrs))
    conditional_script = Script(NotStr("""
document.querySelectorAll('.custom-field[data-condition-field]').forEach(w=>{let key=w.dataset.conditionField;if(!key)return;let source=document.querySelector(`[name="${key}"]`);let control=w.querySelector('input,select,textarea');let required=control&&control.required;let sync=()=>{let show=source&&source.value===w.dataset.conditionValue;w.hidden=!show;if(control)control.required=show&&required;};source&&source.addEventListener('change',sync);sync();});
""")) if custom_fields else None
    return Html(
        _site_head(site, title, description, path=job_path, structured=structured),
        Body(Div("Preview — this page is not public", cls="preview") if preview else None,
             Nav(_brand(site, careers_path), A("All open roles", href=careers_path, cls="c-link"), cls="c-nav"),
             Main(Section(A("← All open roles", href=careers_path, cls="c-link back"),
                          Span(job.get("department") or "Open role", cls="c-kicker"),
                          H1(job["public_title"]),
                          Div(Span(job.get("location") or "Flexible", cls="chip"),
                              Span(job.get("remote_policy") or "", cls="chip") if job.get("remote_policy") else None,
                              Span(job.get("employment_type") or "", cls="chip") if job.get("employment_type") else None,
                              cls="meta"), cls="job-head"),
                  Div(Section(P(job.get("summary") or "", cls="c-lede"),
                              H2("About the role"), P(job.get("description") or "Not provided."),
                              H2("What we’re looking for"), P(job.get("requirements") or "Not provided."),
                              H2("What we offer"), P(job.get("benefits") or "Details will be discussed during the process."),
                              cls="copy"),
                      Section(H2("Apply now"),
                              P(error, cls="error") if error else None,
                              Form(Div(Label("First name"), Input(name="first_name", value=values.get("first_name", ""), required=True), cls="field"),
                                   Div(Label("Last name"), Input(name="last_name", value=values.get("last_name", ""), required=True), cls="field"),
                                   Div(Label("Email"), Input(type="email", name="email", value=values.get("email", ""), required=True), cls="field"),
                                   Div(Label("Phone"), Input(name="phone", value=values.get("phone", "")), cls="field"),
                                   Div(Label("Location"), Input(name="location", value=values.get("location", "")), cls="field"),
                                   Div(Label("CV · PDF, DOCX, TXT or MD"), Input(type="file", name="cv", accept=".pdf,.docx,.txt,.md", required=True), cls="field"),
                                   *custom_fields,
                                   Div(Label("Cover note"), Textarea(values.get("cover_note", ""), name="cover_note"), cls="field"),
                                   Input(name="website", tabindex="-1", autocomplete="off", style="position:absolute;left:-10000px", aria_hidden="true"),
                                   Label(Input(type="checkbox", name="consent", value="yes", required=True),
                                         Span("I acknowledge the recruitment privacy notice and consent to my information being used for this application."), cls="check"),
                                   P(A("Read the privacy notice", href=privacy, target="_blank", cls="c-link"), cls="fine"),
                                   Button("Submit application", type="submit"),
                                   method="post", action=apply_path, enctype="multipart/form-data"),
                              cls="apply"), cls="job-layout")),
             Footer(f"Recruitment managed with {site['name']}", cls="c-footer"), conditional_script)
    )


def application_success(job: dict, *, careers_path: str = "/careers"):
    site = {"name": job.get("career_site_name") or "FastHRM Careers",
            "brand_color": job.get("brand_color") or "#0891b2",
            "accent_color": job.get("accent_color") or "#0e7490",
            "logo_url": job.get("logo_url") or "",
            "favicon_url": job.get("favicon_url") or ""}
    return Html(_site_head(site, "Application received", "Thank you for applying.", path=f"/jobs/{job['slug']}/thanks"),
                Body(Nav(_brand(site, careers_path), A("All open roles", href=careers_path, cls="c-link"), cls="c-nav"),
                     Main(Section(H1("Application received."),
                                  P(f"Thank you for applying for {job['public_title']}. The hiring team now has your application and CV."),
                                  A("View other open roles", href=careers_path, cls="c-link"), cls="success")),
                     Footer(f"Recruitment managed with {site['name']}", cls="c-footer")))


def privacy_page(site: dict):
    return Html(_site_head(site, f"Recruitment privacy · {site['name']}",
                                "How candidate information is used.", path="/privacy"),
                Body(Nav(_brand(site), A("Open roles", href="/careers", cls="c-link"), cls="c-nav"),
                     Main(Section(H1("Recruitment privacy"),
                                  P("We use the information you provide to assess your application, communicate with you, and manage the recruitment process."),
                                  P("Application consent is recorded for 12 months. Contact the hiring organisation to request access, correction, withdrawal, or deletion of your candidate information."),
                                  P("This default notice should be replaced with the organisation’s approved privacy policy before production use."),
                                  cls="job-head")), Footer(site["name"], cls="c-footer")))


def editor(job_id: int | None = None, *, saved: str = "", error: str = ""):
    p = recruitment.ensure_posting(job_id) if job_id else None
    data = p or {}
    action = f"/talent/jobs/{job_id}/edit" if job_id else "/talent/jobs/new"

    def field(label, name, *, kind="text", value=None, required=False):
        value = data.get(name) if value is None else value
        control = Textarea(value or "", name=name, cls="prompt-box", style="min-height:110px") if kind == "textarea" else Input(type=kind, name=name, value=value or "", required=required, cls="hr-inp")
        return Div(Label(label, style="font-size:12px;font-weight:700"), control, style="display:grid;gap:5px")

    dept_options = [Option("— Department —", value="")] + [
        Option(x["name"], value=str(x["id"]), selected=(str(data.get("dept_id") or "") == str(x["id"])))
        for x in recruitment.departments()
    ]
    manager_options = [Option("— Hiring manager —", value="")] + [
        Option(x["name"], value=str(x["id"]), selected=(str(data.get("hiring_manager_id") or "") == str(x["id"])))
        for x in recruitment.hiring_managers()
    ]
    status = data.get("publication_status") or "Draft"
    history = recruitment.versions(job_id) if job_id else []
    actions = None
    if job_id:
        actions = Form(
            *[Button(label, type="submit", name="status", value=value, cls="btn" + (" primary" if value == "Published" else ""),
                     )
              for label, value in (("Send to review", "In review"), ("Publish", "Published"),
                                   ("Close", "Closed"), ("Archive", "Archived"))],
            method="post", action=f"/talent/jobs/{job_id}/publication",
            style="display:flex;gap:7px;flex-wrap:wrap")
    return (
        _title("Edit job" if job_id else "Create job",
               "Author the internal requisition and candidate-facing job page together",
               A("← Requisitions", href="/talent/jobs", cls="btn")),
        P(saved, cls="flag", style="border-left-color:var(--accent)") if saved else None,
        P(error, cls="flag") if error else None,
        Div(Div(H3("Publication"), _pill(status), cls="card-header"),
            Div(A("Preview", href=f"/talent/jobs/{job_id}/preview", target="_blank", cls="btn"),
                actions, style="display:flex;gap:7px;flex-wrap:wrap") if job_id else
            P("Save the draft to enable preview and publishing."), cls="card"),
        Form(Div(H3("Role details"), cls="card-header"),
             Div(field("Internal title", "title", value=data.get("title"), required=True),
                 field("Public title", "public_title"), cls="grid-2"),
             Div(Select(*dept_options, name="dept_id", cls="hr-inp"),
                 Select(*manager_options, name="hiring_manager_id", cls="hr-inp"),
                 Input(type="number", name="headcount", min="1", value=data.get("headcount") or 1, cls="hr-inp"),
                 cls="inline-form", style="margin:12px 0;flex-wrap:wrap"),
             Div(field("Location", "location", value=data.get("location")),
                 Div(Label("Remote policy"), Select(*[Option(x, value=x, selected=(data.get("remote_policy") == x)) for x in ("Onsite", "Hybrid", "Remote")], name="remote_policy", cls="hr-inp")),
                 Div(Label("Employment type"), Select(*[Option(x, value=x, selected=(data.get("employment_type") == x)) for x in ("Permanent", "Contract", "Intern", "Temporary")], name="employment_type", cls="hr-inp")),
                 cls="grid-2"),
             Div(field("Compensation minimum", "comp_min", kind="number", value=data.get("comp_min")),
                 field("Compensation maximum", "comp_max", kind="number", value=data.get("comp_max")),
                 field("Currency", "currency", value=data.get("currency") or "GBP"), cls="grid-2"),
             Div(H3("Public job page"), cls="card-header", style="margin-top:22px"),
             field("URL slug", "slug"), field("Summary", "summary", kind="textarea"),
             field("Description", "description", kind="textarea"),
             field("Requirements", "requirements", kind="textarea"),
             field("Benefits", "benefits", kind="textarea"),
             Div(field("Application deadline", "application_deadline", kind="date"),
                 field("Target hire date", "target_date", kind="date", value=data.get("target_date")), cls="grid-2"),
             Div(field("SEO title", "seo_title"), field("SEO description", "seo_description"), cls="grid-2"),
             Button("Save draft", type="submit", cls="btn primary", style="margin-top:16px"),
             method="post", action=action, cls="card"),
        Div(Div(H3("Version history"), cls="card-header"),
            *[P(Strong(f"v{v['version']}"), f" · {v['created']} · {v['actor'] or 'system'}") for v in history[:10]],
            P("No versions yet.") if not history else None, cls="card") if job_id else None,
    )


def site_settings(*, saved: str = ""):
    site = recruitment.career_site()
    return (
        _title("Careers site", "Brand and privacy settings for public job pages",
               Div(A("View public site", href="/careers", target="_blank", cls="btn"),
                   A("← Requisitions", href="/talent/jobs", cls="btn"), style="display:flex;gap:6px")),
        P(saved, cls="flag", style="border-left-color:var(--accent)") if saved else None,
        Form(Div(H3("Brand"), cls="card-header"),
             Div(Label("Site name"), Input(name="name", value=site["name"], required=True, cls="hr-inp")),
             Div(Label("Headline"), Input(name="headline", value=site.get("headline") or "", cls="hr-inp")),
             Div(Label("Introduction"), Textarea(site.get("introduction") or "", name="introduction", cls="prompt-box")),
             Div(Label("Brand colour"), Input(type="color", name="brand_color", value=site["brand_color"]),
                 Label("Accent colour"), Input(type="color", name="accent_color", value=site["accent_color"]), cls="inline-form"),
             Div(Label("Logo URL"), Input(type="url", name="logo_url", value=site.get("logo_url") or "", cls="hr-inp")),
             Div(Label("Privacy policy URL"), Input(name="privacy_policy_url", value=site.get("privacy_policy_url") or "", cls="hr-inp")),
             Button("Save careers site", type="submit", cls="btn primary"),
             method="post", action="/talent/careers", cls="card", style="display:grid;gap:13px"),
    )
