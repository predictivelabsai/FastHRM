"""FastHTML views for the Phase 2-5 recruiting platform."""
from __future__ import annotations

import json

from fasthtml.common import (
    A, Button, Code, Div, Form, H1, H2, H3, H4, Img, Input, Label, Li, NotStr, Option,
    P, Pre, Script, Section, Select, Small, Span, Strong, Style, Table, Tbody, Td, Textarea, Th,
    Thead, Tr, Ul,
)

import db
import recruitment
import recruitment_communications as comms
import recruitment_ecosystem as ecosystem
import recruitment_enterprise as enterprise
import recruiting_ops as ops
import talent
from web.views import _pill, _title


def _tabs(active: str):
    items = [
        ("operations", "Operations"), ("communications", "Communications"),
        ("scheduling", "Scheduling"), ("marketing", "Marketing & connectors"),
        ("analytics", "Analytics"), ("enterprise", "Enterprise"),
    ]
    return Div(*[A(label, href=f"/talent/platform?section={key}",
                   cls="active" if key == active else "") for key, label in items], cls="seg")


def platform_page(section: str, *, actor: str, note: str = ""):
    renderers = {
        "operations": operations_page, "communications": communications_page,
        "scheduling": scheduling_page, "marketing": marketing_page,
        "analytics": analytics_page, "enterprise": enterprise_page,
    }
    active = section if section in renderers else "operations"
    return (
        _title("Recruiting platform", "Candidate experience, recruiter operations, and enterprise controls"),
        _tabs(active), P(note, cls="flag") if note else None, renderers[active](actor=actor),
    )


def operations_page(*, actor: str):
    jobs = talent.jobs()
    tasks = ops.tasks(assignee=actor)
    templates = ops.pipeline_templates()
    candidates = ops.search_candidates(limit=20)
    pools = ops.candidate_pools()
    saved_views = db.rows(
        "SELECT * FROM saved_candidate_views WHERE owner_email=? OR shared=1 ORDER BY name",
        (actor.lower(),))
    project_rows = [Tr(
        Td(Strong(j["title"]), Small(f" · {j['code']}")),
        Td(", ".join(talent.job_stages(j["id"]))),
        Td("Configured" if db.one("SELECT id FROM recruitment_projects WHERE job_id=?", (j["id"],)) else "Standard"),
        Td(str(j["total_applicants"])),
        Td(A("Board", href=f"/talent/jobs/{j['id']}/workflow", cls="btn sm"),
           A("Edit", href=f"/talent/jobs/{j['id']}/edit", cls="btn sm")),
    ) for j in jobs]
    return Div(
        Div(Div(H3("Projects"), A("New job", href="/talent/jobs/new", cls="btn primary"), cls="card-header"),
            Table(Thead(Tr(Th("Project"), Th("Pipeline"), Th("Access"), Th("Candidates"), Th("Actions"))),
                  Tbody(*project_rows), cls="tbl"), cls="card"),
        Div(Div(H3(f"My tasks ({len(tasks)})"), cls="card-header"),
            *[Div(Strong(t["title"]), Small(f"{t['priority']} · {t['due_at'] or 'No due date'}"),
                  Form(Button("Done", cls="btn sm", name="status", value="Done"), method="post",
                       action=f"/talent/tasks/{t['id']}/status"), cls="row") for t in tasks[:10]] or [P("No open tasks.")], cls="card"),
        Div(Div(H3("Pipeline templates"), cls="card-header"),
            *[P(Strong(t["name"]), " · ", " → ".join(s["name"] for s in t["stages"])) for t in templates],
            Form(Input(name="name", placeholder="Template name", required=True),
                 Input(name="stages", placeholder="Applied, Screen, Interview, Offer, Hired, Rejected", required=True),
                 Button("Add template", cls="btn"), method="post", action="/talent/pipelines", cls="inline-form"), cls="card"),
        Div(Div(H3("Talent CRM"), A("All candidates", href="/talent/candidates", cls="btn"), cls="card-header"),
            *[P(Strong(v["name"]), f" · {v['filters_json']} · {v['owner_email']}") for v in saved_views],
            Form(Input(name="q", placeholder="CV, profile, field or email"), Input(name="tag", placeholder="Tag"),
                 Input(name="skill", placeholder="Skill"), Input(name="location", placeholder="Location"),
                 Button("Search", cls="btn"), method="get", action="/talent/candidates", cls="inline-form"),
            Form(Input(name="name", placeholder="Saved view name", required=True),
                 Input(name="query", placeholder="Keyword"), Input(name="tag", placeholder="Tag"),
                 Input(name="skill", placeholder="Skill"), Input(name="location", placeholder="Location"),
                 Label(Input(type="checkbox", name="shared", value="1"), " Shared"),
                 Button("Save view", cls="btn"), method="post",
                 action="/talent/saved-views", cls="inline-form"),
            Ul(*[Li(A(talent.display_name(c), href=f"/talent/candidates/{c['id']}"),
                       Small(f" · {c.get('tags') or 'untagged'} · {c.get('application_count')} applications"))
                 for c in candidates]), cls="card"),
        Div(Div(H3("Automatic talent pools and targeted offers"), cls="card-header"),
            *[Div(Strong(p["name"]), Small(f" · {p['member_count']} candidates · {p['filters_json']}"),
                  Form(Input(type="number", name="job_id", placeholder="Published job ID", required=True),
                       Button("Send job offer", cls="btn sm"), method="post",
                       action=f"/talent/pools/{p['id']}/offer"), cls="row") for p in pools],
            Form(Input(name="name", placeholder="Pool name", required=True),
                 Input(name="query", placeholder="CV/profile keyword"), Input(name="skill", placeholder="Skill"),
                 Input(name="tag", placeholder="Tag"), Input(name="location", placeholder="Location"),
                 Input(name="source", placeholder="Source"), Button("Create and populate", cls="btn"),
                 method="post", action="/talent/pools", cls="inline-form"), cls="card"),
        Div(Div(H3("Bulk action"), cls="card-header"),
            P("Enter candidate IDs separated by commas. Actions are independently audited."),
            Form(Input(name="candidate_ids", placeholder="1,2,3", required=True),
                 Select(*[Option(x.title(), value=x) for x in ("tag", "task", "comment", "email", "sms")], name="action_type"),
                 Input(name="value", placeholder="Tag, task title, comment, or message"),
                 Button("Run", cls="btn"), method="post", action="/talent/bulk-actions", cls="inline-form"),
            Form(Input(name="candidate_ids", placeholder="Candidate IDs", required=True),
                 Input(name="interviewer_emails", placeholder="Interviewer emails", required=True),
                 Input(type="datetime-local", name="window_start", required=True),
                 Input(type="datetime-local", name="window_end", required=True),
                 Input(name="timezone", value="UTC"),
                 Select(Option("FastHRM video", value="fasthr"), Option("Teams", value="ms_graph"),
                        Option("Google Meet", value="google_calendar"), name="provider"),
                 Button("Invite to self-schedule", cls="btn"), method="post",
                 action="/talent/bulk-interviews", cls="inline-form"), cls="card"),
    )


def workflow_page(job_id: int, *, actor: str):
    job = talent.job(job_id)
    project = ops.project(job_id)
    applications = talent.applications_for_job(job_id)
    application_forms = db.rows("SELECT * FROM application_forms ORDER BY name")
    attached_form = ops.application_form(job_id)
    schedules = db.rows("SELECT * FROM publication_schedules WHERE job_id=? ORDER BY id DESC", (job_id,))
    scorecard_templates = db.rows(
        """SELECT t.*,COUNT(i.id) item_count FROM scorecard_templates t
           LEFT JOIN scorecard_template_items i ON i.template_id=t.id GROUP BY t.id ORDER BY t.name""")
    approvals = db.rows("SELECT * FROM approvals WHERE entity_type='job_opening' AND entity_id=? ORDER BY sequence,id", (job_id,))
    columns = []
    for stage in project["stages"]:
        cards = [Div(A(talent.display_name(a), href=f"/talent/candidates/{a['candidate_id']}"),
                     Small(a.get("current_title") or "Candidate"), draggable="true",
                     data_app=str(a["id"]), cls="pipeline-card") for a in applications if a["stage"] == stage]
        columns.append(Div(H4(stage), Div(*cards, cls="pipeline-drop", data_stage=stage), cls="pipeline-col"))
    script = Script(NotStr("""
document.querySelectorAll('.pipeline-card').forEach(c=>c.addEventListener('dragstart',e=>e.dataTransfer.setData('text/plain',c.dataset.app)));
document.querySelectorAll('.pipeline-drop').forEach(col=>{col.addEventListener('dragover',e=>e.preventDefault());col.addEventListener('drop',async e=>{e.preventDefault();let id=e.dataTransfer.getData('text/plain');let data={stage:col.dataset.stage};if(col.dataset.stage==='Rejected'){data.drop_reason=prompt('Drop reason')||'Not selected';data.drop_detail=prompt('Optional detail')||'';}await fetch(`/talent/applications/${id}/move`,{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams(data)});location.reload();});});
"""))
    return (
        _title(job["title"], "Drag candidates between stages; every move is audited",
               A("← Recruiting platform", href="/talent/platform", cls="btn")),
        Div(Div(H3("Project controls"), _pill("Confidential" if project["confidential"] else "Shared"), cls="card-header"),
            Form(Input(name="category", value=project["category"], placeholder="Category"),
                 Select(*[Option(t["name"], value=str(t["id"]), selected=t["id"] == project["template_id"]) for t in ops.pipeline_templates()], name="template_id"),
                 Label(Input(type="checkbox", name="continuous", value="1", checked=bool(project["continuous"])), " Continuous hiring"),
                 Label(Input(type="checkbox", name="confidential", value="1", checked=bool(project["confidential"])), " Confidential"),
                 Button("Save", cls="btn"), method="post", action=f"/talent/jobs/{job_id}/workflow", cls="inline-form"),
            Form(Input(name="title", placeholder="Clone title"), Button("Clone project", cls="btn"),
                 method="post", action=f"/talent/jobs/{job_id}/clone", cls="inline-form"), cls="card"),
        Div(*columns, cls="pipeline-board"), script,
        Div(Div(H3("Hiring team"), cls="card-header"),
            *[P(m["account_email"], " · ", m["role"], " · ", "Decision rights" if m["can_decide"] else "Feedback") for m in project["members"]],
            Form(Input(type="email", name="email", placeholder="manager@example.com", required=True),
                 Select(*[Option(x, value=x) for x in ("hiring_manager", "interviewer", "observer")], name="role"),
                 Label(Input(type="checkbox", name="can_decide", value="1"), " Can decide"),
                 Label(Input(type="checkbox", name="can_view_salary", value="1"), " Salary access"),
                 Button("Add member", cls="btn"), method="post", action=f"/talent/jobs/{job_id}/members", cls="inline-form"), cls="card"),
        Div(Div(H3("Application form, internal audience, and scheduling"), cls="card-header"),
            P("Attached form: ", Strong(attached_form["name"] if attached_form else "Standard FastHRM form")),
            Form(Select(Option("Standard form", value="0"),
                        *[Option(f["name"], value=str(f["id"]), selected=bool(attached_form and f["id"] == attached_form["id"])) for f in application_forms],
                        name="form_id"), Button("Attach", cls="btn"), method="post",
                 action=f"/talent/jobs/{job_id}/application-form", cls="inline-form"),
            Form(Input(name="name", placeholder="New form name", required=True),
                 Textarea(name="fields", placeholder='[{"key":"work_authorization","label":"Authorized to work?","type":"select","options":["Yes","No"],"required":true}]', required=True),
                 Input(name="confirmation_subject", value="Application received for {{job_title}}"),
                 Textarea(name="confirmation_body", placeholder="Confirmation message"),
                 Button("Create and attach form", cls="btn"), method="post",
                 action=f"/talent/jobs/{job_id}/application-form/create", cls="inline-form"),
            Form(Input(name="audiences", value="all", placeholder="all,department:3,country:EE"),
                 Input(type="date", name="closes_at"), Button("Publish internally", cls="btn"),
                 method="post", action=f"/talent/jobs/{job_id}/internal", cls="inline-form"),
            *[P(Strong(s["action"]), f" · {s['scheduled_at']} · {s['status']}") for s in schedules],
            Form(Select(*[Option(s, value=s) for s in recruitment.PUBLICATION_STATUSES], name="status"),
                 Input(type="datetime-local", name="scheduled_at", required=True), Button("Schedule status", cls="btn"),
                 method="post", action=f"/talent/jobs/{job_id}/schedule-publication", cls="inline-form"), cls="card"),
        Div(Div(H3("Scorecards, approvals, and reminders"), cls="card-header"),
            *[P(Strong(t["name"]), f" · {t['item_count']} criteria") for t in scorecard_templates],
            Form(Input(name="name", placeholder="Scorecard template", required=True),
                 Textarea(name="items", placeholder='[{"label":"System design","weight":2,"required":true}]', required=True),
                 Button("Save scorecard", cls="btn"), method="post",
                 action=f"/talent/jobs/{job_id}/scorecard-template", cls="inline-form"),
            *[Div(Strong(a["approver"]), Small(f" · step {a['sequence']} · {a['decision']}"),
                  Form(Button("Approve", name="decision", value="Approved", cls="btn sm"),
                       Button("Reject", name="decision", value="Rejected", cls="btn sm"),
                       method="post", action=f"/talent/approvals/{a['id']}/decision")
                  if a["decision"] == "Pending" and a["approver"].lower() == actor.lower() else None,
                  cls="row") for a in approvals],
            Form(Input(name="approvers", placeholder="manager@example.com,finance@example.com", required=True),
                 Button("Request approval", cls="btn"), method="post",
                 action=f"/talent/jobs/{job_id}/approvals", cls="inline-form"),
            Form(Button("Create missing-scorecard reminders", cls="btn"), method="post",
                 action="/talent/scorecard-reminders"), cls="card"),
    )


def collaboration_panel(candidate_id: int, *, actor: str):
    tags = ops.tags_for(candidate_id)
    comments = ops.comments_for(candidate_id, viewer=actor)
    fields = ops.candidate_fields(candidate_id)
    tasks = ops.tasks(candidate_id=candidate_id)
    history = comms.communication_history(candidate_id)
    references = db.rows("SELECT * FROM reference_requests WHERE candidate_id=? ORDER BY id DESC", (candidate_id,))
    credentials = db.rows("SELECT * FROM candidate_credentials WHERE candidate_id=? ORDER BY id DESC", (candidate_id,))
    return Div(
        Div(Div(H3("Talent CRM"), cls="card-header"),
            Div(*[Span(t["name"], cls="pill") for t in tags] or [Small("No tags")]),
            Form(Input(name="tag", placeholder="Add tag", required=True), Button("Add", cls="btn sm"),
                 method="post", action=f"/talent/candidates/{candidate_id}/tags", cls="inline-form"),
            *[Form(Label(f["label"]), Input(name="value", value=f.get("value_text") or ""),
                   Button("Save", cls="btn sm"), method="post",
                   action=f"/talent/candidates/{candidate_id}/fields/{f['key']}", cls="inline-form")
              for f in fields],
            Form(Input(name="key", placeholder="custom_field_key", required=True),
                 Input(name="label", placeholder="Custom field label", required=True),
                 Input(name="value", placeholder="Value"), Button("Add field", cls="btn sm"),
                 method="post", action=f"/talent/candidates/{candidate_id}/fields", cls="inline-form"),
            Form(Input(type="number", name="duplicate_id", placeholder="Duplicate candidate ID", required=True),
                 Button("Merge into this candidate", cls="btn sm"), method="post",
                 action=f"/talent/candidates/{candidate_id}/merge", cls="inline-form"), cls="card"),
        Div(Div(H3("Collaboration"), cls="card-header"),
            *[Div(Strong(c["author"]), Small(f" · {c['visibility']} · {c['created']}"),
                  P(c["body"]), cls="note") for c in comments],
            Form(Textarea(name="body", placeholder="Add evidence-based feedback", required=True),
                 Select(*[Option(x, value=x) for x in ("team", "hiring_manager", "private")], name="visibility"),
                 Input(type="number", name="rating", min="1", max="5", step="0.5", placeholder="Rating"),
                 Label(Input(type="checkbox", name="pinned", value="1"), " Pin"),
                 Button("Comment", cls="btn"), method="post", action=f"/talent/candidates/{candidate_id}/comments"), cls="card"),
        Div(Div(H3("Tasks"), cls="card-header"),
            *[P(Strong(t["title"]), f" · {t['assignee'] or 'Unassigned'} · {t['status']}") for t in tasks],
            Form(Input(name="title", placeholder="Task", required=True), Input(name="assignee", placeholder="Assignee email"),
                 Input(type="datetime-local", name="due_at"), Button("Assign", cls="btn"), method="post",
                 action=f"/talent/candidates/{candidate_id}/tasks", cls="inline-form"), cls="card"),
        Div(Div(H3("Communication history"), cls="card-header"),
            *[P(_pill(m["channel"]), Strong(m["subject"] or (m["body_text"] or "")[:60]),
                Small(f" · {m['direction']} · {m['status'] or ''}")) for m in history[-10:]] or [P("No messages yet.")], cls="card"),
        Div(Div(H3("Candidate portal, references, and credentials"), cls="card-header"),
            Form(Button("Create candidate portal link", cls="btn"), method="post",
                 action=f"/talent/candidates/{candidate_id}/portal-link"),
            Form(Input(name="title", placeholder="Candidate request", required=True),
                 Select(*[Option(label, value=value) for value, label in
                          (("information", "Additional information"),
                           ("document", "Document upload"), ("interview", "Interview choices"))],
                        name="request_type"),
                 Input(name="fields", value='[]', placeholder='[{"key":"availability","type":"date"}]'),
                 Input(type="date", name="due_at"), Button("Send request", cls="btn"),
                 method="post", action=f"/talent/candidates/{candidate_id}/requests",
                 cls="inline-form"),
            *[P(Strong(r["referee_name"]), f" · {r['referee_email']} · {r['status']}") for r in references],
            Form(Input(name="referee_name", placeholder="Referee name", required=True),
                 Input(type="email", name="referee_email", placeholder="Referee email", required=True),
                 Button("Request reference", cls="btn"), method="post",
                 action=f"/talent/candidates/{candidate_id}/reference", cls="inline-form"),
            *[P(Strong(c["name"]), f" · {c['issuer'] or 'Unknown issuer'} · {c['status']} · expires {c['expires_on'] or 'never'}") for c in credentials],
            Form(Input(name="name", placeholder="Credential", required=True), Input(name="issuer", placeholder="Issuer"),
                 Input(type="date", name="expires_on"), Button("Add credential", cls="btn"),
                 method="post", action=f"/talent/candidates/{candidate_id}/credentials", cls="inline-form"), cls="card"),
    )


def communications_page(*, actor: str):
    mailboxes = db.rows("SELECT * FROM recruitment_mailboxes ORDER BY address")
    templates = db.rows("SELECT * FROM message_templates ORDER BY name")
    messages = db.rows("SELECT m.*,c.first_name,c.last_name FROM communication_messages m LEFT JOIN candidates c ON c.id=m.candidate_id ORDER BY m.id DESC LIMIT 30")
    rules = db.rows("SELECT * FROM automation_rules ORDER BY active DESC,name")
    surveys = db.rows("SELECT * FROM surveys ORDER BY id DESC")
    privacy = db.rows("SELECT p.*,c.first_name,c.last_name FROM privacy_requests p LEFT JOIN candidates c ON c.id=p.candidate_id ORDER BY p.id DESC")
    message_rows = [Tr(
        Td(f"{m.get('first_name') or ''} {m.get('last_name') or ''}"), Td(m["channel"]),
        Td(m["direction"]), Td(m["subject"] or (m["body_text"] or "")[:50]),
        Td(_pill(m["status"])), Td(m["scheduled_at"] or m["sent_at"] or m["created"]),
    ) for m in messages]
    return Div(
        Div(Div(H3("Recruitment mailbox"), Form(Button("Send queued", cls="btn primary"), method="post", action="/talent/messages/dispatch"), cls="card-header"),
            *[Div(Strong(m["address"]), Small(f" · {m['provider']} · synced {m['last_sync_at'] or 'never'}"),
                  Form(Button("Sync now", cls="btn sm"), method="post",
                       action=f"/talent/mailboxes/{m['id']}/sync"), cls="row") for m in mailboxes],
            Form(Input(name="provider", value="ms_graph", placeholder="Provider"), Input(type="email", name="address", placeholder="jobs@example.com", required=True),
                 Input(name="display_name", placeholder="Display name"), Textarea(name="signature_html", placeholder="HTML signature"),
                 Button("Connect mailbox", cls="btn"), method="post", action="/talent/mailboxes", cls="inline-form"), cls="card"),
        Div(Div(H3("Templates and AI-assisted messages"), cls="card-header"),
            *[P(Strong(t["name"]), f" · {t['channel']} · {t['subject'] or 'No subject'}") for t in templates],
            Form(Input(name="name", placeholder="Template name", required=True), Select(Option("Email", value="email"), Option("SMS", value="sms"), name="channel"),
                 Input(name="subject", placeholder="Subject with {{first_name}}"), Textarea(name="body", placeholder="Message HTML", required=True),
                 Button("Save template", cls="btn"), method="post", action="/talent/message-templates", cls="inline-form"),
            Form(Input(type="number", name="candidate_id", placeholder="Candidate ID", required=True),
                 Select(Option("Email", value="email"), Option("SMS", value="sms"), name="channel"),
                 Input(name="subject", placeholder="Subject"), Textarea(name="body", placeholder="Message", required=True),
                 Input(type="datetime-local", name="scheduled_at"), Button("Queue message", cls="btn primary"),
                 method="post", action="/talent/messages", cls="inline-form"),
            Form(Input(name="instruction", placeholder="Draft a warm interview invitation", required=True),
                 Button("Draft with AI", cls="btn"), method="post",
                 action="/talent/messages/ai-draft", cls="inline-form"), cls="card"),
        Div(Div(H3("Recent communication"), cls="card-header"),
            Table(Thead(Tr(Th("Candidate"), Th("Channel"), Th("Direction"), Th("Subject"), Th("Status"), Th("When"))),
                  Tbody(*message_rows), cls="tbl"), cls="card"),
        Div(Div(H3("Triggers & actions"), cls="card-header"),
            *[P(Strong(r["name"]), f" · when {r['trigger_event']} · ", Code(r["actions_json"])) for r in rules],
            Form(Input(name="name", placeholder="Rule name", required=True), Input(name="trigger_event", placeholder="application.stage_changed", required=True),
                 Textarea(name="conditions", placeholder='{"stage":"Screen"}'),
                 Textarea(name="actions", placeholder='[{"type":"email","body":"Hello"}]', required=True),
                 Button("Save automation", cls="btn"), method="post", action="/talent/automations", cls="inline-form"), cls="card"),
        Div(Div(H3("Surveys and cNPS"), cls="card-header"),
            *[P(Strong(s["name"]), f" · {s['audience']} · {comms.survey_metrics(s['id'])['responses']} responses") for s in surveys],
            Form(Input(name="name", placeholder="Survey name", required=True),
                 Select(Option("Candidate", value="candidate"), Option("Hiring manager", value="hiring_manager"), name="audience"),
                 Input(name="trigger_event", placeholder="application.closed"), Button("Create survey", cls="btn"),
                 method="post", action="/talent/surveys", cls="inline-form"),
            Form(Input(type="number", name="survey_id", placeholder="Survey ID", required=True),
                 Input(type="number", name="candidate_id", placeholder="Candidate ID"),
                 Input(type="email", name="recipient_email", placeholder="Recipient email"),
                 Button("Send survey", cls="btn"), method="post", action="/talent/surveys/invite", cls="inline-form"), cls="card"),
        Div(Div(H3("Privacy and retention"), cls="card-header"),
            *[Div(Strong(f"{p.get('first_name') or 'Candidate'} {p.get('last_name') or p['candidate_id']}"),
                  Small(f" · {p['request_type']} · {p['status']}"),
                  Form(Button("Process", cls="btn sm"), method="post", action=f"/talent/privacy/{p['id']}/process")
                  if p["status"] == "Open" else None, cls="row") for p in privacy] or [P("No privacy requests.")],
            Form(Input(name="name", placeholder="Policy name", required=True), Input(name="purpose", value="Talent pool"),
                 Input(type="number", name="months", value="12"), Select(Option("Anonymize", value="Anonymize"), Option("Delete", value="Delete"), name="action"),
                 Button("Save retention policy", cls="btn"), method="post", action="/talent/retention-policies", cls="inline-form"),
            Form(Button("Run retention now", cls="btn"), method="post", action="/talent/retention/run"), cls="card"),
    )


def scheduling_page(*, actor: str):
    availability = db.rows("SELECT * FROM interviewer_availability ORDER BY account_email,weekday,start_time")
    links = db.rows("SELECT l.*,j.title,c.first_name,c.last_name FROM scheduling_links l JOIN applications a ON a.id=l.application_id JOIN candidates c ON c.id=a.candidate_id JOIN job_openings j ON j.id=a.job_id ORDER BY l.id DESC")
    bookings = db.rows("SELECT * FROM interview_bookings ORDER BY id DESC LIMIT 30")
    return Div(
        Div(Div(H3("Interviewer availability"), cls="card-header"),
            *[P(Strong(a["account_email"]), f" · weekday {a['weekday']} · {a['start_time']}–{a['end_time']} {a['timezone']}") for a in availability],
            Form(Input(type="email", name="email", placeholder="interviewer@example.com", required=True),
                 Select(*[Option(day, value=str(i)) for i, day in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"))], name="weekday"),
                 Input(type="time", name="start_time", value="09:00"), Input(type="time", name="end_time", value="17:00"),
                 Input(name="timezone", value="UTC"), Button("Add availability", cls="btn"), method="post", action="/talent/availability", cls="inline-form"), cls="card"),
        Div(Div(H3("Self-scheduling links"), cls="card-header"),
            *[P(A(f"{l['first_name']} {l['last_name']} · {l['title']}", href=f"/schedule/{l['token']}", target="_blank"),
                f" · {l['status']} · {l['window_start']}–{l['window_end']}") for l in links],
            Form(Input(type="number", name="application_id", placeholder="Application ID", required=True),
                 Input(name="interviewer_emails", placeholder="one@example.com,two@example.com", required=True),
                 Input(type="datetime-local", name="window_start", required=True), Input(type="datetime-local", name="window_end", required=True),
                 Input(name="timezone", value="UTC"), Select(Option("FastHRM video", value="fasthr"), Option("Teams", value="ms_graph"), Option("Google Meet", value="google_calendar"), name="provider"),
                 Button("Create link", cls="btn primary"), method="post", action="/talent/scheduling-links", cls="inline-form"), cls="card"),
        Div(Div(H3("Bookings"), cls="card-header"),
            *[P(Strong(b["starts_at"]), f" · {b['timezone']} · ", A("Meeting", href=b["meeting_url"] or "#"), f" · {b['status']}") for b in bookings] or [P("No bookings.")], cls="card"),
    )


def marketing_page(*, actor: str):
    campaigns = db.rows("SELECT * FROM recruitment_campaigns ORDER BY id DESC")
    posts = db.rows("SELECT p.*,j.title FROM job_board_posts p JOIN job_openings j ON j.id=p.job_id ORDER BY p.id DESC")
    hooks = db.rows("SELECT id,name,url,events_json,active FROM webhook_subscriptions ORDER BY id DESC")
    assets = db.rows("SELECT * FROM marketing_assets ORDER BY id DESC LIMIT 20")
    templates = db.rows("SELECT * FROM page_templates ORDER BY name")
    return Div(
        Div(Div(H3("Job-board multiposting"), A("Integration credentials", href="/settings/integrations", cls="btn"), cls="card-header"),
            *[P(Strong(p["title"]), f" · {p['provider']} · {p['status']} · ", A("View", href=p["external_url"] or "#")) for p in posts],
            Form(Input(type="number", name="job_id", placeholder="Job ID", required=True),
                 Input(name="providers", value="linkedin,indeed", placeholder="linkedin,indeed"),
                 Button("Publish", cls="btn primary"), method="post", action="/talent/job-boards/publish", cls="inline-form"), cls="card"),
        Div(Div(H3("Campaigns and landing pages"), cls="card-header"),
            *[P(A(c["name"], href=f"/campaigns/{c['landing_slug']}", target="_blank"),
                f" · {c['status']} · {c['starts_at'] or 'Any time'} · ",
                A("JPG", href=f"/talent/campaigns/{c['id']}/jpg")) for c in campaigns],
            Form(Input(name="name", placeholder="Campaign", required=True), Input(type="number", name="job_id", placeholder="Job ID"),
                 Input(name="landing_slug", placeholder="landing-page-slug"), Input(name="headline", placeholder="Headline"),
                 Textarea(name="body", placeholder="Campaign story"),
                 Input(type="number", name="template_id", placeholder="Page template ID"),
                 Input(type="number", name="asset_id", placeholder="Media asset ID"),
                 Input(name="font_family", placeholder="Custom font family", value="Inter"),
                 Input(name="channels", value="website,linkedin"), Button("Create and publish", cls="btn"),
                 method="post", action="/talent/campaigns", cls="inline-form"), cls="card"),
        Div(Div(H3("Page templates and media library"), cls="card-header"),
            *[P(Strong(f"#{t['id']} {t['name']}"), " · ", Code(t["default_styles_json"] or "{}")) for t in templates],
            Form(Input(name="name", placeholder="Template name", required=True),
                 Textarea('[{"type":"hero"},{"type":"content"},{"type":"apply"}]', name="sections"),
                 Input(name="font", value="Inter", placeholder="Custom font"), Button("Save template", cls="btn"),
                 method="post", action="/talent/page-templates", cls="inline-form"),
            *[P(Strong(f"#{a['id']} {a['name']}"), f" · {a['asset_type']} · {a['alt_text'] or 'No alt text'}") for a in assets],
            Form(Input(name="name", placeholder="Asset name", required=True), Input(name="alt_text", placeholder="Accessible description"),
                 Input(type="file", name="asset", accept=".png,.jpg,.jpeg,.webp,.svg", required=True),
                 Button("Upload asset", cls="btn"), method="post", action="/talent/marketing-assets",
                 enctype="multipart/form-data", cls="inline-form"), cls="card"),
        Div(Div(H3("Inclusive language review"), cls="card-header"),
            Form(Textarea(name="text", placeholder="Paste job copy", required=True), Button("Review", cls="btn"),
                 method="post", action="/talent/inclusive-review"),
            Form(Input(type="number", name="job_id", placeholder="Job ID", required=True),
                 Input(name="instruction", placeholder="Rewrite for a concise social advert", required=True),
                 Button("Draft inclusive ad with AI", cls="btn"), method="post",
                 action="/talent/job-ads/ai-draft", cls="inline-form"), cls="card"),
        Div(Div(H3("Webhook subscriptions"), cls="card-header"),
            *[P(Strong(h["name"]), f" · {h['url']} · {h['events_json']}") for h in hooks],
            Form(Input(name="name", placeholder="Subscription", required=True), Input(type="url", name="url", placeholder="https://client.example/webhook", required=True),
                 Input(name="events", value="application.created,application.stage_changed"),
                 Button("Create", cls="btn"), method="post", action="/talent/webhooks", cls="inline-form"), cls="card"),
    )


def analytics_page(*, actor: str):
    summary = ecosystem.analytics_summary()
    fill_rows = summary["time_to_fill"]
    average_fill = (round(sum(float(row["days"]) for row in fill_rows) / len(fill_rows), 1)
                    if fill_rows else "—")
    dashboards = db.rows("SELECT * FROM dashboard_definitions WHERE owner_email=? OR shared=1 ORDER BY id DESC", (actor.lower(),))
    experiments = db.rows("SELECT * FROM recruitment_experiments ORDER BY id DESC")
    experiment_reports = {e["id"]: ecosystem.experiment_report(e["id"]) for e in experiments}
    return Div(
        Div(*[Div(Strong(str(value)), Small(label.replace("_", " ").title()), cls="kpi") for label, value in
               (("Views", summary["views"]), ("Applications", summary["applications"]),
               ("Conversion rate", f"{summary['conversion_rate']}%"),
               ("Email click rate", f"{summary['email_conversion']['click_rate']}%"),
               ("Time to fill", average_fill))], cls="kpi-grid"),
        Div(Div(H3("Custom dashboards"), A("Export events CSV", href="/talent/analytics/export", cls="btn"), cls="card-header"),
            *[P(Strong(d["name"]), f" · {d['scope']} · ", Code(d["widgets_json"])) for d in dashboards],
            Form(Input(name="name", placeholder="Dashboard name", required=True),
                 Select(*[Option(x.title(), value=x) for x in ("personal", "team", "group")], name="scope"),
                 Input(name="widgets", value="funnel,sources,time_to_fill,email_conversion"),
                 Label(Input(type="checkbox", name="shared", value="1"), " Shared"),
                 Button("Save dashboard", cls="btn"), method="post", action="/talent/dashboards", cls="inline-form"), cls="card"),
        Div(Div(H3("Funnel"), cls="card-header"),
            Table(Thead(Tr(Th("Stage"), Th("Candidates"))), Tbody(*[Tr(Td(stage), Td(str(count))) for stage, count in summary["funnel"]]), cls="tbl"), cls="card"),
        Div(Div(H3("Sources"), cls="card-header"), Pre(json.dumps(summary["sources"], indent=2)), cls="card"),
        Div(Div(H3("Recruiter performance and benchmarks"), cls="card-header"),
            Table(Thead(Tr(Th("Recruiter"), Th("Audited actions"), Th("Hires"))),
                  Tbody(*[Tr(Td(row["actor"]), Td(str(row["actions"])), Td(str(row["hires"])))
                          for row in summary["recruiter_performance"]]), cls="tbl"), cls="card"),
        Div(Div(H3("Recruitment experiments"), cls="card-header"),
            *[P(Strong(e["name"]), f" · {e['status']} · {json.dumps(experiment_reports[e['id']]['variants'])} · ",
                  A("Variant API", href=f"/experiments/{e['id']}/variant?visitor=preview", target="_blank"))
              for e in experiments],
            Form(Input(name="name", placeholder="Experiment name", required=True),
                 Input(type="number", name="job_id", placeholder="Job ID"),
                 Textarea('[{"key":"a","headline":"Build"},{"key":"b","headline":"Grow"}]',
                          name="variants", required=True),
                 Button("Start experiment", cls="btn"), method="post",
                 action="/talent/experiments", cls="inline-form"), cls="card"),
    )


def enterprise_page(*, actor: str):
    organizations = db.rows("SELECT * FROM organizations ORDER BY name")
    organization_summaries = {o["id"]: enterprise.enterprise_summary(o["id"]) for o in organizations}
    brands = db.rows("SELECT b.*,o.name organization FROM brands b JOIN organizations o ON o.id=b.organization_id ORDER BY o.name,b.name")
    idps = db.rows("SELECT id,organization_id,protocol,name,entity_id,sso_url,active FROM identity_providers ORDER BY id DESC")
    imports = db.rows("SELECT * FROM candidate_imports ORDER BY id DESC LIMIT 10")
    support = db.rows("SELECT * FROM support_requests ORDER BY id DESC LIMIT 10")
    sites = db.rows("SELECT c.*,b.name brand FROM career_sites c LEFT JOIN career_site_brands cb ON cb.career_site_id=c.id LEFT JOIN brands b ON b.id=cb.brand_id ORDER BY c.name")
    video_templates = db.rows("SELECT * FROM video_interview_templates ORDER BY name")
    video_responses = db.rows(
        """SELECT r.*,c.first_name,c.last_name,t.name template_name
           FROM video_responses r JOIN video_interview_invitations i ON i.id=r.invitation_id
           JOIN video_interview_templates t ON t.id=i.template_id
           JOIN applications a ON a.id=i.application_id JOIN candidates c ON c.id=a.candidate_id
           ORDER BY r.id DESC LIMIT 20""")
    return Div(
        Div(Div(H3("Organizations, brands, and custom domains"), cls="card-header"),
            *[P(Strong(o["name"]),
                  f" · {organization_summaries[o['id']]['brands']} brands · "
                  f"{organization_summaries[o['id']]['teams']} teams · "
                  f"{organization_summaries[o['id']]['published_jobs']} published jobs · "
                  f"{organization_summaries[o['id']]['applications']} applications") for o in organizations],
            *[P(Strong(b["organization"]), f" (organization #{b['organization_id']}) / {b['name']} "
                  f"(brand #{b['id']}) · {b['custom_domain'] or 'platform domain'}") for b in brands],
            Form(Input(name="organization", placeholder="Organization", required=True), Input(name="org_slug", placeholder="org-slug", required=True),
                 Input(name="brand", placeholder="Brand", required=True), Input(name="brand_slug", placeholder="brand-slug", required=True),
                 Input(name="custom_domain", placeholder="jobs.example.com"),
                 Input(type="url", name="logo_url", placeholder="Logo URL"),
                 Input(type="url", name="favicon_url", placeholder="Favicon URL"),
                 Input(type="color", name="primary_color", value="#0891b2", title="Primary colour"),
                 Input(type="color", name="accent_color", value="#0e7490", title="Accent colour"),
                 Button("Add brand", cls="btn"),
                 method="post", action="/talent/enterprise/brands", cls="inline-form"),
            *[P(Strong(s["name"]), f" (site #{s['id']}) · {s.get('brand') or 'default brand'} · /sites/{s['slug']}") for s in sites],
            Form(Input(type="number", name="brand_id", placeholder="Brand ID", required=True), Input(name="name", placeholder="Careers site", required=True),
                 Input(name="slug", placeholder="site-slug", required=True), Input(name="locale", value="en"),
                 Button("Add careers site", cls="btn"), method="post", action="/talent/enterprise/sites", cls="inline-form"),
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Input(name="team_name", placeholder="Team", required=True), Input(name="country", placeholder="Country code"),
                 Button("Add team", cls="btn"), method="post", action="/talent/enterprise/teams", cls="inline-form"),
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Input(type="email", name="email", placeholder="Member email", required=True), Input(name="role", value="recruiter"),
                 Input(type="number", name="team_id", placeholder="Team ID"), Button("Add member", cls="btn"),
                 method="post", action="/talent/enterprise/members", cls="inline-form"), cls="card"),
        Div(Div(H3("SSO, SCIM, and policy controls"), cls="card-header"),
            *[P(_pill(i["protocol"]), Strong(i["name"]), f" · {i['entity_id']}") for i in idps],
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Select(Option("SAML", value="SAML"), Option("OIDC", value="OIDC"), name="protocol"),
                 Input(name="name", placeholder="Identity provider", required=True), Input(name="entity_id", placeholder="Entity ID"),
                 Input(type="url", name="sso_url", placeholder="SSO/authorization URL"),
                 Input(type="url", name="metadata_url", placeholder="Metadata/discovery URL"),
                 Input(name="client_id", placeholder="OIDC client ID"),
                 Input(type="password", name="client_secret", placeholder="OIDC client secret"),
                 Textarea(name="certificate_pem", placeholder="SAML signing certificate PEM"),
                 Input(name="config", value="{}", placeholder="Provider JSON settings"),
                 Button("Configure", cls="btn"),
                 method="post", action="/talent/enterprise/idp", cls="inline-form"),
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Input(name="name", placeholder="Policy name", required=True), Input(name="roles", placeholder="recruiter,hrbp"),
                 Input(name="resources", placeholder="candidate,salary"), Input(name="actions", placeholder="read,update"),
                 Select(Option("Allow", value="allow"), Option("Deny", value="deny"), name="effect"),
                 Input(name="conditions", value="{}", placeholder='{"country":"EE","department_id":3}'),
                 Button("Add policy", cls="btn"), method="post", action="/talent/enterprise/policies", cls="inline-form"),
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Input(name="label", value="Identity provider SCIM"), Button("Issue SCIM token", cls="btn"),
                 method="post", action="/talent/enterprise/scim-token", cls="inline-form"),
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Select(Option("DPA", value="DPA"), Option("Terms of Use", value="Terms"), name="document_type"),
                 Input(name="version", placeholder="2026-08", required=True), Textarea(name="content", placeholder="Approved legal text"),
                 Button("Save legal document", cls="btn"), method="post", action="/talent/enterprise/legal", cls="inline-form"), cls="card"),
        Div(Div(H3("AI screening profiles"), cls="card-header"),
            Form(Input(type="number", name="job_id", placeholder="Job ID", required=True),
                 Input(name="criteria", value="Skills:2:required,Experience:1", placeholder="Name:weight:required"),
                 Input(type="number", name="threshold", value="60"), Select(*[Option(s, value=s) for s in talent.STAGES], name="auto_stage"),
                 Label(Input(type="checkbox", name="anonymize", value="1"), " Anonymize"),
                 Label(Input(type="checkbox", name="automatic", value="1"), " Automatic stage"),
                 Button("Save profile", cls="btn"), method="post", action="/talent/enterprise/screening", cls="inline-form"),
            Form(Input(type="number", name="application_id", placeholder="Application ID", required=True),
                 Button("Run screening", cls="btn primary"), method="post", action="/talent/enterprise/screening/run", cls="inline-form"), cls="card"),
        Div(Div(H3("Multilingual content and multi-site distribution"), cls="card-header"),
            Form(Input(type="number", name="job_id", placeholder="Job ID", required=True), Input(type="number", name="site_id", placeholder="Careers site ID", required=True),
                 Input(type="number", name="brand_id", placeholder="Brand ID"), Input(name="locale", value="en"), Input(name="slug", placeholder="localized-slug"),
                 Button("Distribute job", cls="btn"), method="post", action="/talent/enterprise/distributions", cls="inline-form"),
            Form(Input(name="entity_type", value="job_posting"), Input(type="number", name="entity_id", placeholder="Posting ID", required=True),
                 Input(name="locale", placeholder="et", required=True), Input(name="field_key", value="public_title"),
                 Textarea(name="value", placeholder="Reviewed translation", required=True), Button("Save translation", cls="btn"),
                 method="post", action="/talent/enterprise/translations", cls="inline-form"),
            Form(Input(name="entity_type", value="job_posting"),
                 Input(type="number", name="entity_id", placeholder="Posting ID", required=True),
                 Input(name="locale", placeholder="et", required=True),
                 Textarea(name="fields", placeholder='{"public_title":"Platform Engineer","summary":"Build products"}', required=True),
                 Button("Translate with AI", cls="btn"), method="post",
                 action="/talent/enterprise/translations/ai", cls="inline-form"), cls="card"),
        Div(Div(H3("Video interviews and messages"), cls="card-header"),
            *[P(Strong(v["name"]), f" · {len(json.loads(v['questions_json']))} questions") for v in video_templates],
            *[P(Strong(f"{r['first_name']} {r['last_name']}"),
                  f" · {r['template_name']} · question {r['question_index'] + 1} · ",
                  A("View response", href=f"/talent/video-responses/{r['id']}/media", target="_blank"))
              for r in video_responses],
            Form(Input(name="name", placeholder="Template name", required=True),
                 Textarea(name="questions", placeholder="Why this role?\nDescribe a difficult decision.", required=True),
                 Button("Save video template", cls="btn"), method="post", action="/talent/enterprise/video-templates", cls="inline-form"),
            Form(Input(type="number", name="template_id", placeholder="Template ID", required=True),
                 Input(type="number", name="application_id", placeholder="Application ID", required=True),
                 Button("Invite candidate", cls="btn primary"), method="post", action="/talent/enterprise/video-invite", cls="inline-form"),
            Form(Input(type="number", name="candidate_id", placeholder="Candidate ID", required=True),
                 Input(type="url", name="media_url", placeholder="Video URL", required=True), Input(name="sender", value=actor),
                 Button("Send video message", cls="btn"), method="post", action="/talent/enterprise/video-message", cls="inline-form"), cls="card"),
        Div(Div(H3("Candidate import and sourcing"), cls="card-header"),
            P("Browser extensions can send a JSON profile to ", Code("POST /talent/source-candidate"),
              " with a recruiter session or FASTHR_SOURCE_TOKEN bearer token."),
            *[P(Strong(i["file_name"]), f" · {i['imported']} imported · {i['failed']} failed") for i in imports],
            Form(Input(name="file_name", value="candidates.csv"), Textarea(name="csv_text", placeholder="First,Last,Email\nAda,Lovelace,ada@example.com", required=True),
                 Input(name="mapping", value='{"first_name":"First","last_name":"Last","email":"Email"}'),
                 Input(type="number", name="job_id", placeholder="Optional job ID"), Button("Import", cls="btn"),
                 method="post", action="/talent/enterprise/import", cls="inline-form"), cls="card"),
        Div(Div(H3("Support, onboarding, and SLA"), cls="card-header"),
            *[P(Strong(s["subject"]), f" · {s['priority']} · {s['status']} · {s['channel']}") for s in support],
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Input(name="subject", placeholder="Support request", required=True),
                 Select(*[Option(x, value=x) for x in ("email", "live_chat", "phone")], name="channel"),
                 Select(*[Option(x, value=x) for x in ("Normal", "High", "Urgent")], name="priority"),
                 Button("Open request", cls="btn"), method="post", action="/talent/enterprise/support", cls="inline-form"),
            Form(Input(type="number", name="organization_id", placeholder="Organization ID", required=True),
                 Select(*[Option(x, value=x) for x in ("Community", "Email", "Live chat", "Enterprise")], name="support_tier"),
                 Input(name="onboarding_status", value="In progress"), Input(type="email", name="account_manager_email", placeholder="Account manager"),
                 Input(type="number", name="response_sla_minutes", placeholder="Response SLA minutes"),
                 Input(type="number", name="resolution_sla_minutes", placeholder="Resolution SLA minutes"),
                 Button("Save service plan", cls="btn"), method="post", action="/talent/enterprise/service-plan", cls="inline-form"), cls="card"),
    )


def hiring_manager_page(email: str):
    projects = ops.hiring_manager_workspace(email)
    approvals = db.rows(
        """SELECT a.*,j.title FROM approvals a JOIN job_openings j ON j.id=a.entity_id
           WHERE a.entity_type='job_opening' AND lower(a.approver)=? ORDER BY a.id DESC""",
        (email.lower(),))
    tasks = ops.tasks(assignee=email)
    surveys = db.rows(
        """SELECT i.*,s.name FROM survey_invitations i JOIN surveys s ON s.id=i.survey_id
           WHERE lower(i.recipient_email)=? ORDER BY i.id DESC""", (email.lower(),))
    return (_title("Hiring manager workspace", "Only projects explicitly shared with you are listed"),
            Div(*[Div(H3(p["title"]), P(f"{p['active_candidates']} active candidates"),
                      A("Open board", href=f"/talent/jobs/{p['job_id']}/workflow", cls="btn"), cls="card")
                  for p in projects] or [P("No projects have been shared with this account.", cls="card")]),
            Div(Div(H3("Decisions and notifications"), cls="card-header"),
                *[Div(Strong(a["title"]), Small(f" · {a['decision']}"),
                      Form(Button("Approve", name="decision", value="Approved", cls="btn sm"),
                           Button("Reject", name="decision", value="Rejected", cls="btn sm"),
                           method="post", action=f"/talent/approvals/{a['id']}/decision")
                      if a["decision"] == "Pending" else None, cls="row") for a in approvals],
                *[P(Strong(t["title"]), f" · {t['status']} · due {t['due_at'] or 'not set'}") for t in tasks],
                *[P(Strong(s["name"]), f" · {s['status']} · ",
                      A("Complete survey", href=f"/survey/{s['token']}") if s["status"] == "Sent" else None)
                  for s in surveys], cls="card"))


def internal_jobs_page(audience: str = "all"):
    jobs = ops.internal_jobs(audience=audience)
    return (_title("Internal opportunities", "Roles published for employees"),
            Div(*[Div(H3(job["title"]), P(f"{job['location'] or 'Flexible'} · {job['remote_policy'] or ''}"),
                      A("View requisition", href=f"/talent/jobs/{job['job_id']}", cls="btn"), cls="card")
                  for job in jobs] or [P("No internal opportunities are open.", cls="card")]))


def _candidate_request_form(item: dict, token: str):
    controls = []
    for field in json.loads(item.get("fields_json") or "[]"):
        key = field.get("key") or "response"
        label = field.get("label") or key.replace("_", " ").title()
        if field.get("type") == "select":
            control = Select(*[Option(option, value=option) for option in field.get("options", [])],
                             name=key, required=bool(field.get("required", True)))
        else:
            control = Input(type=field.get("type") or "text", name=key,
                            required=bool(field.get("required", True)))
        controls.append(Div(Label(label), control, cls="field"))
    return Form(*controls, Textarea(name="response", placeholder="Additional context"),
                Input(type="file", name="document", accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"),
                Button("Submit", cls="btn"), method="post",
                action=f"/portal/{token}/requests/{item['id']}",
                enctype="multipart/form-data")


def portal_page(snapshot: dict, token: str, *, note: str = ""):
    c = snapshot["candidate"]
    return Div(H1(f"Welcome, {c.get('first_name') or 'candidate'}"), P(note) if note else None,
               H2("Applications"), *[Div(H3(a["title"]), _pill(a["stage"]), P(a["status"]),
                    Form(Button("Withdraw application", cls="btn"), method="post",
                         action=f"/portal/{token}/applications/{a['id']}/withdraw"), cls="card") for a in snapshot["applications"]],
               H2("Requests"), *[Div(H3(r["title"]), P(r["request_type"]),
                    _candidate_request_form(r, token), cls="card")
                                  for r in snapshot["requests"] if r["status"] == "Open"],
               H2("Privacy"), Form(Button("Renew consent", name="action", value="renew", cls="btn"),
                                    Button("Withdraw consent", name="action", value="withdraw", cls="btn"),
                                    Button("Request export", name="action", value="export", cls="btn"),
                                    Button("Request correction", name="action", value="correct", cls="btn"),
                                    Button("Dispute processing", name="action", value="dispute", cls="btn"),
                                    Button("Request anonymisation", name="action", value="anonymize", cls="btn"),
                                    Button("Request deletion", name="action", value="delete", cls="btn"),
                                    Textarea(name="details", placeholder="Explain the correction or dispute"),
                                    method="post", action=f"/portal/{token}/privacy", cls="card"))


def schedule_public_page(token: str, slots: list[dict], *, note: str = ""):
    return Div(H1("Choose an interview time"), P(note) if note else None,
               *[Form(Button(f"{s['starts_at']} ({s['timezone']})", name="starts_at", value=s["starts_at"], cls="btn"),
                      method="post", action=f"/schedule/{token}", cls="slot") for s in slots] or
               [P("No times are currently available. Please contact the hiring team.")], cls="public-card")


def campaign_public_page(campaign: dict):
    content = campaign["content"]
    template = campaign.get("template") or {}
    styles = template.get("styles") or {}
    sections = template.get("sections") or [{"type": "hero"}, {"type": "content"}, {"type": "apply"}]
    font = content.get("font_family") or styles.get("font") or "Inter"
    nodes = []
    for section in sections:
        kind = section.get("type")
        if kind == "hero":
            nodes.append(Section(Span("Recruitment campaign"),
                                 Img(src=f"/marketing-assets/{campaign['asset']['id']}",
                                     alt=campaign["asset"].get("alt_text") or "") if campaign.get("asset") else None,
                                 H1(content.get("headline") or campaign["name"]), cls="campaign-hero"))
        elif kind == "apply":
            nodes.append(Section(A("View open role", href=campaign.get("job_url") or "/careers",
                                   cls="btn primary"), cls="campaign-apply"))
        else:
            nodes.append(Section(P(content.get("body") or "Explore this opportunity and meet the team."),
                                 cls="campaign-content"))
    return Div(Style(f".campaign-public{{font-family:{font},sans-serif}}.campaign-public img{{max-width:100%;height:auto}}"),
               *nodes, cls="campaign-public")


def survey_public_page(survey: dict, token: str, *, note: str = ""):
    questions = json.loads(survey["questions_json"])
    return Div(H1(survey["name"]), P(note) if note else None,
               Form(*[Div(Label(q.get("label") or q.get("key")),
                           Input(type="number" if q.get("type") == "nps" else "text",
                                 name=q.get("key"), min="0", max="10", required=True)) for q in questions],
                    Button("Submit feedback", cls="btn primary"), method="post", action=f"/survey/{token}"), cls="public-card")


def video_public_page(invitation: dict, template: dict, token: str, *, note: str = ""):
    questions = json.loads(template["questions_json"])
    return Div(H1(template["name"]), P(template.get("intro_text") or "Record your responses when ready."),
               P(note) if note else None,
               *[Form(H3(q.get("question") or f"Question {i + 1}"),
                      Input(name="media", type="file", accept="video/*", capture="user"),
                      Input(name="media_url", type="url", placeholder="Or paste a secure video URL"),
                      Input(type="hidden", name="question_index", value=str(i)), Button("Save response", cls="btn"),
                      method="post", action=f"/video-interview/{token}/response",
                      enctype="multipart/form-data", cls="card") for i, q in enumerate(questions)],
               Form(Button("Complete interview", cls="btn primary"), method="post", action=f"/video-interview/{token}/complete"))
