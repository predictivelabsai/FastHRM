"""FastHRM — an open-source HR system built with FastHTML.

A server-side, HTMX-driven port of the core of Frappe HR (HRMS), scoped to three
pillars: people (employee directory + departments), time (leave + attendance),
and pay (payslips) — plus an AI assistant grounded in the live (synthetic) data.

Run:
    python web_app.py            # http://localhost:5010

Login: admin@fasthr.example / FastHR2026$  (override via .env)
"""
from __future__ import annotations

import os
import base64
import hashlib
import hmac
import json
import importlib
import secrets
import time
import uuid
import logging
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

from fasthtml.common import (
    fast_app, serve, Div, H1, P, A, Form, Input, Button, Label, Select, Option,
    Textarea, NotStr, RedirectResponse, Script, Style, Link, Meta, Title,
)
from starlette.responses import FileResponse, StreamingResponse, Response
from starlette.responses import JSONResponse

import db
import talent
import people
import integrations
import recruitment
import recruitment_communications
import recruitment_ecosystem
import recruitment_enterprise
import recruiting_ops
import version
from web.layout import page, LAYOUT_CSS, NAV_ITEMS
from web import views, ai, ats, careers, cv_extract, ranking, performance, lifecycle, recruiting_platform, settings
from web.landing import comparison_page, features_page, landing_page
from web.seo import register_seo_routes
from web.developer import developer_page
from web import account_auth, google_auth
from web.api import api

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("fasthr")

VALID_EMAIL = os.getenv("FASTHR_ADMIN_EMAIL", "admin@fasthr.example")
VALID_PASSWORD = os.getenv("FASTHR_ADMIN_PASSWORD", "FastHR2026$")
ENV_LABEL = os.getenv("FASTHR_ENV_LABEL", "FastHRM")
SECRET = os.getenv("FASTHR_SECRET", secrets.token_hex(32))
PORT = int(os.getenv("FASTHR_PORT", "5010"))

app, rt = fast_app(live=False, pico=False, secret_key=SECRET, hdrs=[Style(LAYOUT_CSS)])
app.mount("/api", api)


@rt("/swagger.json", methods=["GET"])
def swagger_schema():
    return JSONResponse(api.openapi())


@rt("/developers", methods=["GET"])
def developers():
    return developer_page()


@rt("/features", methods=["GET"])
def features():
    return features_page()


@rt("/compare", methods=["GET"])
def compare():
    return comparison_page()


@rt("/products", methods=["GET"])
def legacy_products():
    return RedirectResponse("/features", status_code=308)


account_auth.register_fasthtml_routes(rt, app_name="FastHRM", session_key="user", success_path="/")


def _user(session):
    return session.get("user")


def _thread(session):
    if "thread" not in session:
        session["thread"] = uuid.uuid4().hex
    return session["thread"]


def _guard(session, active, builder):
    if not _user(session):
        destinations = {key: href for _, items in NAV_ITEMS for key, _, _, href in items}
        destination = destinations.get(active, "/")
        return RedirectResponse(f"/login?next={quote(destination, safe='')}", status_code=303)
    content = builder() if callable(builder) else builder
    if not isinstance(content, tuple):
        content = (content,)
    return page(active, ENV_LABEL, _user(session), _thread(session), *content)


PUBLISHER_ROLES = {"admin", "hrbp", "recruiter"}
_application_attempts = defaultdict(deque)


def _can_publish(session) -> bool:
    """Restrict the new publishing surface while platform-wide RBAC is phased in."""
    email = (_user(session) or "").strip().lower()
    if not email:
        return False
    if email == VALID_EMAIL.strip().lower():
        return True
    roles = db.rows("SELECT role FROM account_roles WHERE lower(account_email)=?", (email,))
    return any(row["role"] in PUBLISHER_ROLES for row in roles)


def _roles_for(session) -> set[str]:
    email = (_user(session) or "").strip().lower()
    if not email:
        return set()
    roles = {row["role"] for row in db.rows(
        "SELECT role FROM account_roles WHERE lower(account_email)=?", (email,))}
    if email == VALID_EMAIL.strip().lower():
        roles.add("admin")
    return roles


def _publisher_guard(session):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if not _can_publish(session):
        return Response("Recruiter, HRBP, or admin access is required.", status_code=403)
    return None


def _application_throttled(request) -> bool:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = _application_attempts[key]
    while attempts and attempts[0] < now - 60:
        attempts.popleft()
    if len(attempts) >= 5:
        return True
    attempts.append(now)
    return False


def _scim_organization(request) -> int | None:
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    return recruitment_enterprise.authenticate_scim(authorization.split(None, 1)[1])


def _sso_verifier():
    """Load the deployment's signature-validating SAML/OIDC adapter."""
    target = os.getenv("FASTHR_SSO_VERIFIER", "")
    if not target or ":" not in target:
        return None
    module_name, factory_name = target.split(":", 1)
    return getattr(importlib.import_module(module_name), factory_name)()


def _transcriber():
    target = os.getenv("FASTHR_TRANSCRIBER", "")
    if not target or ":" not in target:
        return None
    module_name, factory_name = target.split(":", 1)
    return getattr(importlib.import_module(module_name), factory_name)()


# ---------- enterprise identity and SCIM ----------------------------------

@rt("/sso/{provider_id}/start")
def get(session, request, provider_id: int):
    provider = db.one("SELECT * FROM identity_providers WHERE id=? AND active=1", (provider_id,))
    if not provider:
        return Response("Identity provider not found.", status_code=404)
    callback = str(request.base_url).rstrip("/") + f"/sso/{provider_id}/callback"
    state = secrets.token_urlsafe(24)
    session["enterprise_sso_state"] = state
    if provider["protocol"] == "SAML":
        url = recruitment_enterprise.saml_login_url(provider_id, acs_url=callback, relay_state=state)
    else:
        verifier = _sso_verifier()
        if not verifier or not hasattr(verifier, "authorization_url"):
            return Response("OIDC verifier adapter is not configured.", status_code=503)
        url = verifier.authorization_url(provider, callback=callback, state=state)
    return RedirectResponse(url, status_code=303)


async def _complete_enterprise_sso(session, request, provider_id: int):
    verifier = _sso_verifier()
    if not verifier:
        return Response("A signature-validating SSO verifier is not configured.", status_code=503)
    payload = dict(request.query_params)
    if request.method == "POST":
        payload.update(dict(await request.form()))
    state = payload.get("RelayState") or payload.get("state")
    if not state or state != session.pop("enterprise_sso_state", None):
        return Response("Invalid SSO state.", status_code=400)
    response = payload.get("SAMLResponse") or payload.get("code") or ""
    identity = recruitment_enterprise.consume_sso_response(provider_id, response, verifier=verifier)
    session["user"] = identity["email"]
    session["organization_id"] = identity["organization_id"]
    return RedirectResponse("/", status_code=303)


@rt("/sso/{provider_id}/callback")
async def post(session, request, provider_id: int):
    return await _complete_enterprise_sso(session, request, provider_id)


@rt("/sso/{provider_id}/callback")
async def get(session, request, provider_id: int):
    return await _complete_enterprise_sso(session, request, provider_id)


@rt("/scim/v2/Users")
def get(request, startIndex: int = 1, count: int = 100):
    organization_id = _scim_organization(request)
    if not organization_id:
        return JSONResponse({"detail": "Invalid SCIM bearer token"}, status_code=401)
    rows = db.rows(
        """SELECT * FROM organization_members WHERE organization_id=?
           ORDER BY id LIMIT ? OFFSET ?""",
        (organization_id, min(count, 200), max(startIndex - 1, 0)),
    )
    resources = [{"id": str(row["id"]), "userName": row["account_email"],
                  "active": bool(row["active"]), "roles": [{"value": row["role"]}]}
                 for row in rows]
    return JSONResponse({"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                         "totalResults": len(resources), "startIndex": startIndex,
                         "itemsPerPage": len(resources), "Resources": resources})


@rt("/scim/v2/Users")
async def post(request):
    organization_id = _scim_organization(request)
    if not organization_id:
        return JSONResponse({"detail": "Invalid SCIM bearer token"}, status_code=401)
    payload = await request.json()
    emails = payload.get("emails") or []
    email = payload.get("userName") or (emails[0].get("value") if emails else "")
    roles = payload.get("roles") or []
    role = roles[0].get("value") if roles else "employee"
    resource = recruitment_enterprise.scim_upsert_user(
        organization_id, payload.get("externalId") or email, email,
        role=role, active=payload.get("active", True), payload=payload)
    return JSONResponse({"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], **resource}, status_code=201)


@rt("/scim/v2/Users/{member_id}")
async def patch(request, member_id: int):
    organization_id = _scim_organization(request)
    member = db.one("SELECT * FROM organization_members WHERE id=? AND organization_id=?",
                    (member_id, organization_id)) if organization_id else None
    if not member:
        return JSONResponse({"detail": "SCIM user not found"}, status_code=404)
    payload = await request.json()
    active, role = bool(member["active"]), member["role"]
    for operation in payload.get("Operations", []):
        path = (operation.get("path") or "").lower()
        if path == "active":
            active = bool(operation.get("value"))
        elif path == "roles":
            value = operation.get("value") or []
            role = value[0].get("value", role) if value else role
    resource = recruitment_enterprise.scim_upsert_user(
        organization_id, str(member_id), member["account_email"], role=role,
        active=active, payload=payload)
    return JSONResponse({"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], **resource})


@rt("/scim/v2/Users/{member_id}")
def delete(request, member_id: int):
    organization_id = _scim_organization(request)
    member = db.one("SELECT * FROM organization_members WHERE id=? AND organization_id=?",
                    (member_id, organization_id)) if organization_id else None
    if not member:
        return Response(status_code=404)
    recruitment_enterprise.scim_deactivate_user(organization_id, member["account_email"])
    return Response(status_code=204)


def _login_card(error="", email=""):
    return Title("FastHRM — Sign in"), Style(LAYOUT_CSS), Div(
        Form(H1("FastHRM"), P("Sign in to your HR workspace"),
             Input(name="email", type="email", placeholder="Email", value=email, required=True),
             Input(name="password", type="password", placeholder="Password", required=True),
             P(error, cls="error") if error else None,
             Button("Sign in", cls="btn primary", type="submit"),
             P(NotStr("Demo: <code>admin@fasthr.example</code> / <code>FastHR2026$</code>"), cls="hint"),
             method="post", action="/login", cls="login-card"), cls="login-wrap")


@rt("/login")
def get(session):
    if _user(session):
        return RedirectResponse("/", status_code=303)
    return landing_page(open_auth=True)


@rt("/login")
def post(session, email: str = "", password: str = ""):
    if email.strip().lower() == VALID_EMAIL.lower() and password == VALID_PASSWORD:
        session["user"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    return _login_card("Invalid email or password.", email)



def _safe_auth_destination(value):
    value = (value or "").strip()
    return value if value.startswith("/") and not value.startswith("//") else "/"


@rt("/auth/google")
def google_start(session, request, next: str = ""):
    if not google_auth.enabled():
        return RedirectResponse("/login?error=Google+sign-in+is+not+configured", status_code=303)
    state = google_auth.new_state()
    session["google_oauth_state"] = state
    session["google_oauth_next"] = _safe_auth_destination(next)
    return RedirectResponse(google_auth.authorize_url(request, state), status_code=303)


@rt("/auth/google/callback")
def google_callback(session, request, code: str = "", state: str = "", error: str = ""):
    destination = _safe_auth_destination(session.pop("google_oauth_next", "/"))
    if error or not code or state != session.pop("google_oauth_state", None):
        return RedirectResponse("/login?error=Google+sign-in+failed", status_code=303)
    identity = google_auth.exchange(request, code)
    if not identity:
        return RedirectResponse("/login?error=Google+account+is+not+authorised", status_code=303)
    account_auth.accounts.link_google(identity["email"], identity["name"])
    session["user"] = identity["email"]
    return RedirectResponse(destination, status_code=303)


@rt("/logout")
def get(session):
    session.pop("user", None)
    return RedirectResponse("/login", status_code=303)


@rt("/")
def get(session, request):
    branded = recruitment_enterprise.resolve_brand(host=request.headers.get("host", ""))
    if branded and branded.get("site_slug"):
        locale = branded.get("default_locale") or "en"
        site = recruitment_enterprise.public_career_site(branded["site_slug"], locale)
        if not site:
            return landing_page() if not _user(session) else _guard(session, "dashboard", views.dashboard)
        site = {**site, "name": site.get("name") or site.get("brand_name"),
                "brand_color": site.get("primary_color") or site.get("brand_color"),
                "logo_url": site.get("brand_logo") or site.get("logo_url")}
        path = f"/sites/{branded['site_slug']}/{locale}"
        return careers.careers_page(site, recruitment_enterprise.public_site_jobs(branded["site_slug"], locale),
                                    careers_path=path, job_prefix=path + "/jobs")
    if not _user(session):
        return landing_page()
    return _guard(session, "dashboard", views.dashboard)


# ---------- public careers and applications -------------------------------

@rt("/careers")
def get():
    recruitment.process_publication_schedules()
    return careers.careers_page(recruitment.career_site(), recruitment.public_jobs())


@rt("/sites/{site_slug}/{locale}")
def get(site_slug: str, locale: str):
    site = recruitment_enterprise.public_career_site(site_slug, locale)
    if not site:
        return Response("Careers site not found.", status_code=404)
    site_view = {**site, "name": site.get("name") or site.get("brand_name"),
                 "brand_color": site.get("primary_color") or site.get("brand_color"),
                 "accent_color": site.get("accent_color"),
                 "logo_url": site.get("brand_logo") or site.get("logo_url")}
    path = f"/sites/{site_slug}/{locale}"
    return careers.careers_page(
        site_view, recruitment_enterprise.public_site_jobs(site_slug, locale),
        careers_path=path, job_prefix=path + "/jobs")


@rt("/sites/{site_slug}/{locale}/jobs/{slug}")
def get(request, site_slug: str, locale: str, slug: str):
    job = recruitment_enterprise.public_distributed_job(site_slug, locale, slug)
    if not job:
        return Response("This job is not available.", status_code=404)
    path = f"/sites/{site_slug}/{locale}"
    job_path = path + f"/jobs/{slug}"
    recruitment_ecosystem.track_event(
        "job_view", job_id=job["job_id"], source=request.query_params.get("utm_source", ""),
        medium=request.query_params.get("utm_medium", ""), metadata={"locale": locale, "site": site_slug})
    return careers.job_page(job, careers_path=path, job_path=job_path, apply_path=job_path + "/apply")


@rt("/privacy")
def get():
    return careers.privacy_page(recruitment.career_site())


@rt("/jobs/{slug}")
def get(request, slug: str):
    job = recruitment.public_job(slug)
    if not job:
        return Response("This job is not available.", status_code=404)
    recruitment_ecosystem.track_event(
        "job_view", job_id=job["job_id"], source=request.query_params.get("utm_source", ""),
        medium=request.query_params.get("utm_medium", ""))
    return careers.job_page(job)


async def _submit_public_application(request, public_slug: str, job: dict, *,
                                     careers_path: str = "/careers", job_path: str | None = None,
                                     apply_path: str | None = None):
    render = {"careers_path": careers_path, "job_path": job_path, "apply_path": apply_path}
    form = await request.form()
    values = dict(form)
    if values.get("website"):
        return careers.application_success(job, careers_path=careers_path)
    if _application_throttled(request):
        return careers.job_page(job, error="Too many attempts. Please wait a minute and try again.",
                                values=values, **render)
    upload = form.get("cv")
    if upload is None or not getattr(upload, "filename", ""):
        return careers.job_page(job, error="Please attach your CV.", values=values, **render)
    if not cv_extract.supported(upload.filename):
        return careers.job_page(job, error="Use a PDF, DOCX, TXT, or MD file.", values=values, **render)
    data = await upload.read()
    if not data:
        return careers.job_page(job, error="The attached CV is empty.", values=values, **render)
    if len(data) > 8 * 1024 * 1024:
        return careers.job_page(job, error="The attached CV must be 8 MB or smaller.", values=values, **render)
    result = recruitment.apply(
        public_slug, values,
        proof={"ip": request.client.host if request.client else "unknown",
               "user_agent": request.headers.get("user-agent", "")[:500]},
    )
    if not result["ok"]:
        return careers.job_page(job, error=result["error"], values=values, **render)
    ingested = cv_extract.ingest_cv(
        file_name=upload.filename, data=data, candidate_id=result["candidate_id"],
        job_id=result["job_id"], source="Direct", actor="public-application",
    )
    cv_extract.run_extraction_async(
        ingested["run_id"], ingested["candidate_id"], ingested["document_id"])
    recruitment_ecosystem.track_event(
        "application_submitted", candidate_id=result["candidate_id"],
        application_id=result["application_id"], job_id=result["job_id"],
        source=request.query_params.get("utm_source", ""), medium=request.query_params.get("utm_medium", ""))
    recruitment_communications.emit_event(
        "application.created", {"entity_type": "application", "entity_id": result["application_id"],
        "application_id": result["application_id"], "candidate_id": result["candidate_id"],
        "job_id": result["job_id"]}, actor="public-application")
    form_config = recruiting_ops.application_form(result["job_id"])
    recruitment_communications.queue_message(
        result["candidate_id"], channel="email", application_id=result["application_id"],
        subject=(form_config or {}).get("confirmation_subject") or "Application received for {{job_title}}",
        body=(form_config or {}).get("confirmation_body") or
             "Hello {{first_name}}, we received your application for {{job_title}}.",
        actor="application-confirmation")
    recruitment_communications.dispatch_due()
    recruitment_ecosystem.enqueue_webhook("application.created", result)
    return careers.application_success(job, careers_path=careers_path)


@rt("/jobs/{slug}/apply")
async def post(request, slug: str):
    job = recruitment.public_job(slug)
    if not job:
        return Response("This job is not accepting applications.", status_code=404)
    return await _submit_public_application(request, slug, job)


@rt("/sites/{site_slug}/{locale}/jobs/{slug}/apply")
async def post(request, site_slug: str, locale: str, slug: str):
    job = recruitment_enterprise.public_distributed_job(site_slug, locale, slug)
    if not job:
        return Response("This job is not accepting applications.", status_code=404)
    path = f"/sites/{site_slug}/{locale}"
    job_path = path + f"/jobs/{slug}"
    return await _submit_public_application(
        request, job["primary_slug"], job, careers_path=path,
        job_path=job_path, apply_path=job_path + "/apply")


def _public_recruiting_shell(title: str, content, *, description: str = "", image_url: str = ""):
    return (Title(f"{title} · FastHRM"),
            Meta(name="description", content=description or title),
            Meta(property="og:title", content=title),
            Meta(property="og:description", content=description or title),
            Meta(property="og:image", content=image_url) if image_url else None,
            Style(LAYOUT_CSS), content)


@rt("/portal/{token}")
def get(token: str):
    candidate_id = recruitment_communications.authenticate_portal(token)
    if not candidate_id:
        return Response("This candidate portal link is invalid or expired.", status_code=404)
    return _public_recruiting_shell(
        "Candidate portal",
        recruiting_platform.portal_page(recruitment_communications.portal_snapshot(candidate_id), token),
    )


@rt("/portal/{token}/requests/{request_id}")
async def post(token: str, request_id: int, request):
    candidate_id = recruitment_communications.authenticate_portal(token)
    if not candidate_id:
        return Response("Invalid portal link.", status_code=404)
    pending = db.one(
        "SELECT * FROM candidate_requests WHERE id=? AND candidate_id=? AND status='Open'",
        (request_id, candidate_id),
    )
    if not pending:
        return Response("Request is not open.", status_code=404)
    form = await request.form()
    payload = {"response": str(form.get("response") or "").strip(),
               "answers": {key: str(value) for key, value in form.items()
                           if key not in {"response", "document"}}}
    upload = form.get("document")
    if upload is not None and getattr(upload, "filename", ""):
        data = await upload.read()
        if not data or len(data) > 8 * 1024 * 1024:
            return Response("Documents must be non-empty and 8 MB or smaller.", status_code=400)
        path = cv_extract.store_upload(upload.filename, data)
        text_content = cv_extract.extract_text(path) if cv_extract.supported(upload.filename) else ""
        document_id = talent.save_document(
            candidate_id, file_name=upload.filename,
            mime=getattr(upload, "content_type", "application/octet-stream"), size=len(data),
            stored_path=str(path), text=text_content, kind="Other",
        )
        payload["document_id"] = document_id
        payload["file_name"] = upload.filename
    if not payload["response"] and not payload["answers"] and not payload.get("document_id"):
        return Response("Add a response or document.", status_code=400)
    recruitment_communications.respond_candidate_request(request_id, candidate_id, payload)
    return RedirectResponse(f"/portal/{token}", status_code=303)


@rt("/portal/{token}/applications/{application_id}/withdraw")
def post(token: str, application_id: int):
    candidate_id = recruitment_communications.authenticate_portal(token)
    if not candidate_id:
        return Response("Invalid portal link.", status_code=404)
    recruitment_communications.withdraw_application(application_id, candidate_id)
    return RedirectResponse(f"/portal/{token}", status_code=303)


@rt("/portal/{token}/privacy")
def post(token: str, action: str = "", details: str = ""):
    candidate_id = recruitment_communications.authenticate_portal(token)
    if not candidate_id:
        return Response("Invalid portal link.", status_code=404)
    if action == "renew":
        recruitment_communications.renew_consent(candidate_id, proof={"source": "candidate-portal"})
    elif action == "withdraw":
        recruitment_communications.withdraw_consent(candidate_id)
    elif action in {"export", "correct", "dispute", "anonymize", "delete"}:
        recruitment_communications.create_privacy_request(candidate_id, action.title(), details=details)
    return RedirectResponse(f"/portal/{token}", status_code=303)


@rt("/schedule/{token}")
def get(token: str):
    return _public_recruiting_shell(
        "Schedule interview",
        recruiting_platform.schedule_public_page(token, recruitment_ecosystem.available_slots(token)),
    )


@rt("/schedule/{token}")
def post(token: str, starts_at: str = ""):
    try:
        booking = recruitment_ecosystem.book_slot(token, starts_at)
        note = f"Booked for {booking['starts_at']}. A calendar invitation is on its way."
    except ValueError as exc:
        note = str(exc)
    return _public_recruiting_shell(
        "Schedule interview",
        recruiting_platform.schedule_public_page(token, recruitment_ecosystem.available_slots(token), note=note),
    )


@rt("/campaigns/{slug}")
def get(slug: str):
    campaign = recruitment_ecosystem.campaign(slug)
    if not campaign:
        return Response("Campaign not found.", status_code=404)
    recruitment_ecosystem.track_event("campaign_view", campaign_id=campaign["id"], job_id=campaign.get("job_id"))
    return _public_recruiting_shell(
        campaign["name"], recruiting_platform.campaign_public_page(campaign),
        description=campaign["content"].get("body") or campaign["content"].get("headline") or campaign["name"],
        image_url=f"/marketing-assets/{campaign['asset']['id']}" if campaign.get("asset") else "")


@rt("/marketing-assets/{asset_id}")
def get(asset_id: int):
    asset = db.one("SELECT url,name FROM marketing_assets WHERE id=?", (asset_id,))
    if not asset or not os.path.isfile(asset["url"]):
        return Response("Marketing asset not found.", status_code=404)
    return FileResponse(asset["url"], filename=Path(asset["url"]).name,
                        headers={"Cache-Control": "public, max-age=86400"})


@rt("/experiments/{experiment_id}/variant")
def get(experiment_id: int, visitor: str = ""):
    if not visitor:
        return JSONResponse({"detail": "A stable visitor identifier is required."}, status_code=400)
    try:
        variant = recruitment_ecosystem.assign_experiment(experiment_id, visitor)
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=404)
    experiment = db.one("SELECT job_id FROM recruitment_experiments WHERE id=?", (experiment_id,))
    recruitment_ecosystem.track_event(
        "experiment_exposure", session_id=visitor, job_id=(experiment or {}).get("job_id"),
        metadata={"experiment_id": experiment_id, "variant": variant.get("key")})
    return JSONResponse({"experiment_id": experiment_id, "variant": variant})


@rt("/survey/{token}")
def get(token: str):
    survey = db.one(
        """SELECT s.* FROM surveys s JOIN survey_invitations i ON i.survey_id=s.id
           WHERE i.token=? AND i.status='Sent'""", (token,))
    if not survey:
        return Response("Survey not found or already completed.", status_code=404)
    return _public_recruiting_shell(survey["name"], recruiting_platform.survey_public_page(survey, token))


@rt("/survey/{token}")
async def post(request, token: str):
    survey = db.one(
        """SELECT s.* FROM surveys s JOIN survey_invitations i ON i.survey_id=s.id
           WHERE i.token=? AND i.status='Sent'""", (token,))
    if not survey:
        return Response("Survey not found or already completed.", status_code=404)
    answers = dict(await request.form())
    scores = [float(value) for value in answers.values() if str(value).replace(".", "", 1).isdigit()]
    recruitment_communications.submit_survey(token, answers, score=scores[0] if scores else None)
    return _public_recruiting_shell(survey["name"], Div(H1("Thank you."), P("Your feedback has been recorded."), cls="public-card"))


@rt("/references/{token}")
def get(token: str):
    reference = db.one("SELECT * FROM reference_requests WHERE token=? AND status='Requested'", (token,))
    if not reference:
        return Response("Reference request not found.", status_code=404)
    return _public_recruiting_shell(
        "Reference request", Div(H1("Candidate reference"), P(f"Requested from {reference['referee_name']}"),
        Form(Label("Would you recommend this candidate?"), Select(Option("Yes", value="yes"), Option("No", value="no"), name="recommend"),
             Textarea(name="comment", placeholder="Your reference", required=True), Button("Submit", cls="btn primary"),
             method="post", action=f"/references/{token}"), cls="public-card"))


@rt("/references/{token}")
def post(token: str, recommend: str = "", comment: str = ""):
    if not recruiting_ops.complete_reference(token, {"recommend": recommend == "yes", "comment": comment}):
        return Response("Reference request not found.", status_code=404)
    return _public_recruiting_shell("Reference received", Div(H1("Thank you."), P("The hiring team has received your reference."), cls="public-card"))


@rt("/video-interview/{token}")
def get(token: str):
    invitation = db.one("SELECT * FROM video_interview_invitations WHERE token=? AND expires_at>=datetime('now')", (token,))
    if not invitation:
        return Response("Video interview link is invalid or expired.", status_code=404)
    template = db.one("SELECT * FROM video_interview_templates WHERE id=?", (invitation["template_id"],))
    return _public_recruiting_shell(template["name"], recruiting_platform.video_public_page(invitation, template, token))


@rt("/video-interview/{token}/response")
async def post(token: str, request):
    form = await request.form()
    media_url = str(form.get("media_url") or "").strip()
    upload = form.get("media")
    if upload is not None and getattr(upload, "filename", ""):
        data = await upload.read()
        content_type = getattr(upload, "content_type", "") or ""
        if not content_type.startswith("video/") or not data or len(data) > 250 * 1024 * 1024:
            return Response("Upload a non-empty video no larger than 250 MB.", status_code=400)
        root = Path(os.getenv("FASTHR_UPLOAD_DIR") or Path(__file__).parent / "data" / "uploads") / "video"
        root.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload.filename).suffix.lower()[:10]
        path = root / f"{uuid.uuid4().hex}{suffix}"
        path.write_bytes(data)
        media_url = str(path)
    if not media_url:
        return Response("Record or attach a video response.", status_code=400)
    recruitment_enterprise.submit_video_response(
        token, int(form.get("question_index") or 0), media_url, transcriber=_transcriber())
    return RedirectResponse(f"/video-interview/{token}", status_code=303)


@rt("/video-interview/{token}/complete")
def post(token: str):
    recruitment_enterprise.complete_video_interview(token)
    return _public_recruiting_shell("Interview complete", Div(H1("Interview complete."), P("Thank you for your time."), cls="public-card"))


@rt("/talent/video-responses/{response_id}/media")
def get(session, response_id: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    response = db.one("SELECT media_url FROM video_responses WHERE id=?", (response_id,))
    if not response:
        return Response("Video response not found.", status_code=404)
    location = response["media_url"] or ""
    if location.startswith(("https://", "http://")):
        return RedirectResponse(location, status_code=302)
    if not location or not os.path.isfile(location):
        return Response("Video file is unavailable.", status_code=404)
    return FileResponse(location, filename=Path(location).name)


@rt("/m/{message_id}/open.gif")
def get(message_id: int):
    if db.one("SELECT id FROM communication_messages WHERE id=?", (message_id,)):
        recruitment_communications.record_message_event(message_id, "read")
    pixel = base64.b64decode("R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=")
    return Response(pixel, media_type="image/gif", headers={"Cache-Control": "no-store"})


@rt("/m/{message_id}/click")
def get(message_id: int, url: str = ""):
    if db.one("SELECT id FROM communication_messages WHERE id=?", (message_id,)):
        recruitment_communications.record_message_event(message_id, "clicked", {"url": url})
    if not url.startswith(("https://", "http://")):
        return Response("Invalid destination.", status_code=400)
    return RedirectResponse(url, status_code=302)


@rt("/webhooks/communications/{provider}")
async def post(request, provider: str):
    """Accept authenticated delivery/read/click/bounce events from mail/SMS adapters."""
    secret = os.getenv("FASTHR_COMMUNICATION_WEBHOOK_SECRET", "")
    if not secret:
        return JSONResponse({"detail": "Communication webhook is not configured."}, status_code=503)
    body = await request.body()
    supplied = request.headers.get("x-fasthr-signature", "").removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        return JSONResponse({"detail": "Invalid signature."}, status_code=401)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Invalid JSON."}, status_code=400)
    message = None
    if payload.get("message_id"):
        message = db.one("SELECT * FROM communication_messages WHERE id=?", (payload["message_id"],))
    if not message and payload.get("provider_message_id"):
        message = db.one(
            "SELECT * FROM communication_messages WHERE provider_message_id=?",
            (payload["provider_message_id"],),
        )
    if not message:
        return JSONResponse({"detail": "Message not found."}, status_code=404)
    event_type = {"delivery": "delivered", "delivered": "delivered", "open": "read",
                  "read": "read", "click": "clicked", "clicked": "clicked",
                  "bounce": "bounced", "bounced": "bounced", "failed": "failed"}.get(
                      str(payload.get("event") or payload.get("event_type") or "").lower())
    if not event_type:
        return JSONResponse({"detail": "Unsupported event."}, status_code=400)
    recruitment_communications.record_message_event(
        message["id"], event_type, {**payload, "provider": provider})
    return JSONResponse({"ok": True, "message_id": message["id"], "event": event_type})


@rt("/webhooks/job-boards/{provider}")
async def post(request, provider: str):
    """Accept signed applicant payloads from configured job-board connectors."""
    secret = os.getenv("FASTHR_JOB_BOARD_WEBHOOK_SECRET", "")
    if not secret:
        return JSONResponse({"detail": "Job-board webhook is not configured."}, status_code=503)
    body = await request.body()
    supplied = request.headers.get("x-fasthr-signature", "").removeprefix("sha256=")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        return JSONResponse({"detail": "Invalid signature."}, status_code=401)
    try:
        payload = json.loads(body)
        result = recruitment_ecosystem.import_job_board_applicant(
            provider, payload["external_job_id"], payload.get("applicant") or payload)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)
    recruitment_communications.emit_event(
        "application.created", {"entity_type": "application", "entity_id": result["application_id"],
        **result}, actor=f"job-board:{provider}")
    recruitment_ecosystem.enqueue_webhook("application.created", result)
    return JSONResponse({"ok": True, **result}, status_code=201)


@rt("/employees")
def get(session, dept: str = "All", q: str = ""):
    return _guard(session, "employees", lambda: views.employees_list(dept, q))


@rt("/employees/{eid}")
def get(session, eid: int):
    return _guard(session, "employees", lambda: views.employee_detail(eid))


@rt("/departments")
def get(session):
    return _guard(session, "departments", views.departments_list)


@rt("/leave")
def get(session, status: str = "Pending"):
    return _guard(session, "leave", lambda: views.leave_list(status))


def _lfrag(session, status="Pending"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    return views.leave_main(status)


@rt("/leave/apply")
def post(session, employee_id: int = 0, leave_type: str = "", from_date: str = "", to_date: str = "", reason: str = ""):
    if employee_id and from_date and to_date:
        db.apply_leave(employee_id, leave_type, from_date, to_date, reason)
    return _lfrag(session, "Pending")


@rt("/leave/{req_id}/approve")
def post(session, req_id: int):
    db.set_leave_status(req_id, "Approved")
    return _lfrag(session, "Pending")


@rt("/leave/{req_id}/reject")
def post(session, req_id: int):
    db.set_leave_status(req_id, "Rejected")
    return _lfrag(session, "Pending")


@rt("/attendance")
def get(session):
    return _guard(session, "attendance", views.attendance_view)


# ---------- talent / ATS ----------------------------------------------------

@rt("/talent/jobs")
def get(session, status: str = "All"):
    return _guard(session, "jobs", lambda: ats.jobs_list(status))


@rt("/talent/jobs/new")
def get(session):
    denied = _publisher_guard(session)
    return denied or _guard(session, "jobs", careers.editor)


@rt("/talent/jobs/new")
async def post(session, request):
    denied = _publisher_guard(session)
    if denied:
        return denied
    values = dict(await request.form())
    try:
        job_id = recruitment.create_job(values, actor=_user(session))
    except (TypeError, ValueError) as exc:
        return page("jobs", ENV_LABEL, _user(session), _thread(session),
                    *careers.editor(error=str(exc)))
    return RedirectResponse(f"/talent/jobs/{job_id}/edit?saved={quote('Draft created.')}", status_code=303)


@rt("/talent/jobs/{job_id}")
def get(session, job_id: int, stage: str = "All"):
    return _guard(session, "jobs", lambda: ats.job_detail(job_id, stage))


@rt("/talent/jobs/{job_id}/edit")
def get(session, job_id: int, saved: str = ""):
    denied = _publisher_guard(session)
    return denied or _guard(session, "jobs", lambda: careers.editor(job_id, saved=saved))


@rt("/talent/jobs/{job_id}/edit")
async def post(session, request, job_id: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    values = dict(await request.form())
    try:
        recruitment.save_job(job_id, values, actor=_user(session))
    except (TypeError, ValueError) as exc:
        return page("jobs", ENV_LABEL, _user(session), _thread(session),
                    *careers.editor(job_id, error=str(exc)))
    return RedirectResponse(f"/talent/jobs/{job_id}/edit?saved={quote('Draft saved.')}", status_code=303)


@rt("/talent/jobs/{job_id}/preview")
def get(session, job_id: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    posting = recruitment.ensure_posting(job_id, actor=_user(session))
    job = recruitment.public_job(posting["slug"], include_unpublished=True)
    return careers.job_page(job, preview=posting["publication_status"] != "Published")


@rt("/talent/jobs/{job_id}/publication")
def post(session, job_id: int, status: str = "Draft"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    try:
        recruitment.transition(job_id, status, actor=_user(session))
    except ValueError as exc:
        return page("jobs", ENV_LABEL, _user(session), _thread(session),
                    *careers.editor(job_id, error=str(exc)))
    return RedirectResponse(
        f"/talent/jobs/{job_id}/edit?saved={quote('Publication status changed to ' + status + '.')}",
        status_code=303,
    )


@rt("/talent/careers")
def get(session, saved: str = ""):
    denied = _publisher_guard(session)
    return denied or _guard(session, "jobs", lambda: careers.site_settings(saved=saved))


@rt("/talent/careers")
async def post(session, request):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment.save_career_site(dict(await request.form()), actor=_user(session))
    return RedirectResponse(f"/talent/careers?saved={quote('Careers site saved.')}", status_code=303)


# ---------- recruiting platform phases 2-5 -------------------------------

def _platform_redirect(section: str, note: str):
    return RedirectResponse(f"/talent/platform?section={section}&note={quote(note)}", status_code=303)


@rt("/talent/platform")
def get(session, section: str = "operations", note: str = ""):
    denied = _publisher_guard(session)
    return denied or _guard(session, "platform", lambda: recruiting_platform.platform_page(section, actor=_user(session), note=note))


@rt("/talent/hiring-manager")
def get(session):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    return _guard(session, "platform", lambda: recruiting_platform.hiring_manager_page(_user(session)))


@rt("/internal-jobs")
def get(session, audience: str = "all"):
    return _guard(session, "platform", lambda: recruiting_platform.internal_jobs_page(audience))


@rt("/talent/jobs/{job_id}/workflow")
def get(session, job_id: int):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if not recruiting_ops.can_access_project(job_id, _user(session), _roles_for(session)):
        return Response("You do not have access to this project.", status_code=403)
    return _guard(session, "platform", lambda: recruiting_platform.workflow_page(job_id, actor=_user(session)))


@rt("/talent/jobs/{job_id}/workflow")
def post(session, job_id: int, category: str = "Standard", template_id: int = 0,
         continuous: str = "", confidential: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.configure_project(job_id, category=category, continuous=bool(continuous),
                                     confidential=bool(confidential), template_id=template_id or None,
                                     actor=_user(session))
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/clone")
def post(session, job_id: int, title: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    clone_id = recruiting_ops.clone_project(job_id, title=title, actor=_user(session))
    return RedirectResponse(f"/talent/jobs/{clone_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/members")
def post(session, job_id: int, email: str = "", role: str = "hiring_manager",
         can_decide: str = "", can_view_salary: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.add_project_member(job_id, email, role, can_decide=bool(can_decide),
                                      can_view_salary=bool(can_view_salary))
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/application-form")
def post(session, job_id: int, form_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.attach_application_form(job_id, form_id)
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/application-form/create")
def post(session, job_id: int, name: str = "", fields: str = "[]",
         confirmation_subject: str = "", confirmation_body: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    form_id = recruiting_ops.save_application_form(
        name, json.loads(fields), confirmation_subject=confirmation_subject,
        confirmation_body=confirmation_body, actor=_user(session))
    recruiting_ops.attach_application_form(job_id, form_id)
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/internal")
def post(session, job_id: int, audiences: str = "all", closes_at: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.publish_internal_job(
        job_id, [a.strip() for a in audiences.split(",") if a.strip()],
        closes_at=closes_at or None, actor=_user(session))
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/schedule-publication")
def post(session, job_id: int, status: str = "Published", scheduled_at: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment.schedule_transition(
        job_id, status, scheduled_at.replace("T", " "), actor=_user(session))
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/scorecard-template")
def post(session, job_id: int, name: str = "", items: str = "[]"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.save_scorecard_template(name, json.loads(items), actor=_user(session))
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/jobs/{job_id}/approvals")
def post(session, job_id: int, approvers: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.request_approval(
        "job_opening", job_id, [email.strip() for email in approvers.split(",") if email.strip()],
        actor=_user(session))
    return RedirectResponse(f"/talent/jobs/{job_id}/workflow", status_code=303)


@rt("/talent/approvals/{approval_id}/decision")
def post(session, approval_id: int, decision: str = "", note: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    approval = db.one("SELECT entity_id FROM approvals WHERE id=?", (approval_id,))
    if not approval or not recruiting_ops.decide_approval(
        approval_id, decision, actor=_user(session), note=note):
        return Response("Approval is unavailable.", status_code=403)
    return RedirectResponse(f"/talent/jobs/{approval['entity_id']}/workflow", status_code=303)


@rt("/talent/scorecard-reminders")
def post(session):
    denied = _publisher_guard(session)
    if denied:
        return denied
    count = recruiting_ops.create_scorecard_reminders(actor=_user(session))
    return _platform_redirect("operations", f"Created {count} scorecard reminders.")


@rt("/talent/pipelines")
def post(session, name: str = "", stages: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    parsed = [{"name": stage.strip()} for stage in stages.split(",") if stage.strip()]
    recruiting_ops.save_pipeline_template(name, parsed, actor=_user(session))
    return _platform_redirect("operations", "Pipeline template saved.")


@rt("/talent/applications/{app_id}/move")
def post(session, app_id: int, stage: str = "", drop_reason: str = "", drop_detail: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    app = db.one("SELECT job_id FROM applications WHERE id=?", (app_id,))
    if not app or not recruiting_ops.can_access_project(app["job_id"], _user(session), _roles_for(session)):
        return Response("Forbidden", status_code=403)
    if not recruiting_ops.move_application(app_id, stage, actor=_user(session),
                                           drop_reason=drop_reason, drop_detail=drop_detail):
        return Response("Invalid stage", status_code=400)
    recruitment_communications.emit_event(
        "application.stage_changed", {"entity_type": "application", "entity_id": app_id,
        "application_id": app_id, "job_id": app["job_id"],
        "candidate_id": db.scalar("SELECT candidate_id FROM applications WHERE id=?", (app_id,)),
        "stage": stage}, actor=_user(session))
    recruitment_ecosystem.enqueue_webhook("application.stage_changed", {"application_id": app_id, "stage": stage})
    return Response("Moved", status_code=200)


@rt("/talent/tasks/{task_id}/status")
def post(session, task_id: int, status: str = "Done"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    recruiting_ops.set_task_status(task_id, status, actor=_user(session))
    return _platform_redirect("operations", "Task updated.")


@rt("/talent/pools")
def post(session, name: str = "", query: str = "", skill: str = "", tag: str = "",
         location: str = "", source: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.save_candidate_pool(
        name, {"query": query, "skill": skill, "tag": tag,
               "location": location, "source": source}, owner=_user(session))
    return _platform_redirect("operations", "Automatic talent pool populated.")


@rt("/talent/saved-views")
def post(session, name: str = "", query: str = "", skill: str = "", tag: str = "",
         location: str = "", shared: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.save_view(
        _user(session), name,
        {key: value for key, value in {"query": query, "skill": skill, "tag": tag,
                                       "location": location}.items() if value},
        shared=bool(shared))
    return _platform_redirect("operations", "Candidate view saved.")


@rt("/talent/pools/{pool_id}/offer")
def post(session, pool_id: int, job_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruiting_ops.send_pool_job_offer(pool_id, job_id, actor=_user(session))
    return _platform_redirect(
        "operations", f"Targeted offer queued for {result['succeeded']} candidates; {result['failed']} failed.")


@rt("/talent/bulk-actions")
def post(session, candidate_ids: str = "", action_type: str = "tag", value: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    ids = [int(value_) for value_ in candidate_ids.split(",") if value_.strip().isdigit()]
    payload = ({"tag": value} if action_type == "tag" else {"title": value, "body": value,
                                                               "assignee": _user(session)})
    result = recruiting_ops.run_bulk_action(action_type, ids, payload=payload, actor=_user(session))
    return _platform_redirect("operations", f"Bulk action completed: {result['succeeded']} succeeded, {result['failed']} failed.")


@rt("/talent/bulk-interviews")
def post(session, candidate_ids: str = "", interviewer_emails: str = "",
         window_start: str = "", window_end: str = "", timezone: str = "UTC",
         provider: str = "fasthr"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    ids = [int(value_) for value_ in candidate_ids.split(",") if value_.strip().isdigit()]
    result = recruiting_ops.run_bulk_action(
        "interview", ids,
        payload={"interviewer_emails": [e.strip() for e in interviewer_emails.split(",") if e.strip()],
                 "window_start": window_start, "window_end": window_end,
                 "timezone": timezone, "provider": provider}, actor=_user(session))
    return _platform_redirect(
        "operations", f"Interview invitations queued: {result['succeeded']} succeeded, {result['failed']} failed.")


@rt("/talent/candidates/{cid}/tags")
def post(session, cid: int, tag: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.add_tag(cid, tag, actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/comments")
def post(session, cid: int, body: str = "", visibility: str = "team", rating: float = 0,
         pinned: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    recruiting_ops.add_comment(cid, body, author=_user(session), visibility=visibility,
                               rating=rating or None, pinned=bool(pinned))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/tasks")
def post(session, cid: int, title: str = "", assignee: str = "", due_at: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    recruiting_ops.create_task(title, candidate_id=cid, assignee=assignee or _user(session),
                               due_at=due_at or None, actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/fields/{key}")
def post(session, cid: int, key: str, value: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.set_candidate_field(cid, key, value, actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/fields")
def post(session, cid: int, key: str = "", label: str = "", value: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.define_candidate_field(key, label)
    recruiting_ops.set_candidate_field(cid, "_".join(key.strip().lower().split()), value,
                                       actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/merge")
def post(session, cid: int, duplicate_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.merge_candidates(cid, duplicate_id, actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/reference")
def post(session, cid: int, referee_name: str = "", referee_email: str = "", application_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.request_reference(cid, referee_name, referee_email,
                                     application_id=application_id or None, actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/portal-link")
def post(session, cid: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    token = recruitment_communications.issue_portal_token(cid, actor=_user(session))
    return Response(f"Candidate portal link: /portal/{token}", media_type="text/plain")


@rt("/talent/candidates/{cid}/requests")
def post(session, cid: int, title: str = "", request_type: str = "information",
         fields: str = "[]", due_at: str = "", application_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.create_candidate_request(
        cid, request_type, title, application_id=application_id or None,
        fields=json.loads(fields or "[]"), due_at=due_at or None, actor=_user(session))
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/candidates/{cid}/credentials")
def post(session, cid: int, name: str = "", issuer: str = "", expires_on: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruiting_ops.add_credential(cid, name, issuer=issuer, expires_on=expires_on or None)
    return RedirectResponse(f"/talent/candidates/{cid}", status_code=303)


@rt("/talent/mailboxes")
def post(session, provider: str = "ms_graph", address: str = "", display_name: str = "",
         signature_html: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.save_mailbox(provider, address, display_name=display_name,
                                            signature_html=signature_html)
    return _platform_redirect("communications", "Mailbox saved.")


@rt("/talent/mailboxes/{mailbox_id}/sync")
def post(session, mailbox_id: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruitment_communications.sync_mailbox(mailbox_id)
    return _platform_redirect("communications", f"Mailbox synced; {result['imported']} messages imported.")


@rt("/talent/message-templates")
def post(session, name: str = "", channel: str = "email", subject: str = "", body: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.save_template(name, body, subject=subject, channel=channel,
                                             actor=_user(session))
    return _platform_redirect("communications", "Template saved.")


@rt("/talent/messages")
def post(session, candidate_id: int = 0, channel: str = "email", subject: str = "",
         body: str = "", scheduled_at: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.queue_message(candidate_id, channel=channel, subject=subject, body=body,
                                             scheduled_at=scheduled_at.replace("T", " ") or None,
                                             actor=_user(session))
    return _platform_redirect("communications", "Message queued.")


@rt("/talent/messages/ai-draft")
def post(session, instruction: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    try:
        draft = recruitment_communications.draft_with_ai(instruction)
    except Exception as exc:
        draft = f"AI drafting is unavailable: {exc}"
    return _platform_redirect("communications", draft)


@rt("/talent/messages/dispatch")
def post(session):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruitment_communications.dispatch_due()
    return _platform_redirect("communications", f"Sent {result['sent']}; {result['failed']} failed.")


@rt("/talent/automations")
def post(session, name: str = "", trigger_event: str = "", conditions: str = "{}",
         actions: str = "[]"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.save_automation_rule(name, trigger_event, json.loads(actions),
                                                    conditions=json.loads(conditions or "{}"), actor=_user(session))
    return _platform_redirect("communications", "Automation saved.")


@rt("/talent/surveys")
def post(session, name: str = "", audience: str = "candidate", trigger_event: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.save_survey(
        name, audience, [{"key": "recommend", "label": "How likely are you to recommend this experience?", "type": "nps"},
                         {"key": "comment", "label": "What should we improve?", "type": "text"}],
        trigger_event=trigger_event, actor=_user(session))
    return _platform_redirect("communications", "Survey created.")


@rt("/talent/surveys/invite")
def post(session, survey_id: int = 0, candidate_id: int = 0, recipient_email: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    token = recruitment_communications.invite_survey(
        survey_id, candidate_id=candidate_id or None, recipient_email=recipient_email)
    return _platform_redirect("communications", f"Survey link created: /survey/{token}")


@rt("/talent/retention-policies")
def post(session, name: str = "", purpose: str = "Talent pool", months: int = 12,
         action: str = "Anonymize"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.save_retention_policy(name, purpose, months, action=action)
    return _platform_redirect("communications", "Retention policy saved.")


@rt("/talent/retention/run")
def post(session):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruitment_communications.run_retention(actor=_user(session))
    return _platform_redirect("communications", f"Retention processed {result['processed']} candidates.")


@rt("/talent/privacy/{request_id}/process")
def post(session, request_id: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_communications.process_privacy_request(request_id, actor=_user(session))
    return _platform_redirect("communications", "Privacy request processed.")


@rt("/talent/availability")
def post(session, email: str = "", weekday: int = 0, start_time: str = "09:00",
         end_time: str = "17:00", timezone: str = "UTC"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_ecosystem.save_availability(email, weekday, start_time, end_time, timezone=timezone)
    return _platform_redirect("scheduling", "Availability saved.")


@rt("/talent/scheduling-links")
def post(session, application_id: int = 0, interviewer_emails: str = "", window_start: str = "",
         window_end: str = "", timezone: str = "UTC", provider: str = "fasthr"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_ecosystem.create_scheduling_link(
        application_id, [e.strip() for e in interviewer_emails.split(",") if e.strip()],
        window_start=window_start, window_end=window_end, timezone=timezone,
        provider=provider, actor=_user(session))
    return _platform_redirect("scheduling", "Scheduling link created.")


@rt("/talent/job-boards/publish")
def post(session, job_id: int = 0, providers: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    results = recruitment_ecosystem.publish_to_job_boards(
        job_id, [p.strip() for p in providers.split(",") if p.strip()])
    return _platform_redirect("marketing", f"Published to {sum(r['status'] == 'Posted' for r in results)} boards.")


@rt("/talent/campaigns")
def post(session, name: str = "", job_id: int = 0, landing_slug: str = "", headline: str = "",
         body: str = "", template_id: int = 0, asset_id: int = 0,
         font_family: str = "Inter", channels: str = "website"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    campaign_id = recruitment_ecosystem.save_campaign(
        name, job_id=job_id or None, landing_slug=landing_slug,
        content={"headline": headline, "body": body, "template_id": template_id or None,
                 "asset_id": asset_id or None, "font_family": font_family}, actor=_user(session))
    recruitment_ecosystem.publish_campaign(campaign_id, [c.strip() for c in channels.split(",") if c.strip()])
    return _platform_redirect("marketing", "Campaign published.")


@rt("/talent/campaigns/{campaign_id}/jpg")
def get(session, campaign_id: int):
    denied = _publisher_guard(session)
    if denied:
        return denied
    root = os.getenv("FASTHR_UPLOAD_DIR") or os.path.join(os.path.dirname(__file__), "data", "uploads")
    path = recruitment_ecosystem.render_campaign_jpg(
        campaign_id, os.path.join(root, "marketing", f"campaign-{campaign_id}.jpg"))
    return FileResponse(path, filename=f"campaign-{campaign_id}.jpg", media_type="image/jpeg")


@rt("/talent/page-templates")
def post(session, name: str = "", sections: str = "[]", font: str = "Inter"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_ecosystem.save_page_template(
        name, json.loads(sections), styles={"font": font}, actor=_user(session))
    return _platform_redirect("marketing", "Page template saved.")


@rt("/talent/marketing-assets")
async def post(session, request):
    denied = _publisher_guard(session)
    if denied:
        return denied
    form = await request.form()
    upload = form.get("asset")
    if upload is None or not getattr(upload, "filename", ""):
        return _platform_redirect("marketing", "Choose an asset file.")
    recruitment_ecosystem.store_marketing_asset(
        form.get("name") or upload.filename, "image", await upload.read(),
        file_name=upload.filename, alt_text=form.get("alt_text") or "", actor=_user(session))
    return _platform_redirect("marketing", "Media asset uploaded.")


@rt("/talent/inclusive-review")
def post(session, text: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    findings = recruitment_ecosystem.inclusive_language_review(text)
    note = "; ".join(f"Replace '{f['term']}' with '{f['replacement']}'" for f in findings) or "No flagged terms."
    return _platform_redirect("marketing", note)


@rt("/talent/job-ads/ai-draft")
def post(session, job_id: int = 0, instruction: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    job = talent.job(job_id)
    if not job:
        return _platform_redirect("marketing", "Job not found.")
    try:
        draft = recruitment_ecosystem.draft_job_ad(instruction, job=job)
    except Exception as exc:
        draft = f"AI job-ad drafting is unavailable: {exc}"
    return _platform_redirect("marketing", draft)


@rt("/talent/webhooks")
def post(session, name: str = "", url: str = "", events: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruitment_ecosystem.create_webhook_subscription(
        name, url, [e.strip() for e in events.split(",") if e.strip()], actor=_user(session))
    return _platform_redirect("marketing", f"Webhook created. Copy its secret now: {result['secret']}")


@rt("/talent/experiments")
def post(session, name: str = "", job_id: int = 0, variants: str = "[]"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_ecosystem.create_experiment(name, json.loads(variants), job_id=job_id or None)
    return _platform_redirect("analytics", "Experiment started.")


@rt("/talent/dashboards")
def post(session, name: str = "", scope: str = "personal", widgets: str = "", shared: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_ecosystem.save_dashboard(
        _user(session), name, scope, [{"type": w.strip()} for w in widgets.split(",") if w.strip()],
        shared=bool(shared))
    return _platform_redirect("analytics", "Dashboard saved.")


@rt("/talent/analytics/export")
def get(session, job_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    return Response(recruitment_ecosystem.export_analytics_csv(job_id=job_id or None), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=recruitment-analytics.csv"})


@rt("/talent/enterprise/brands")
def post(session, organization: str = "", org_slug: str = "", brand: str = "",
         brand_slug: str = "", custom_domain: str = "", logo_url: str = "",
         favicon_url: str = "", primary_color: str = "#0891b2",
         accent_color: str = "#0e7490"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    org = recruitment_enterprise.ensure_organization(organization, slug=org_slug)
    recruitment_enterprise.create_brand(
        org["id"], brand, brand_slug, custom_domain=custom_domain, logo_url=logo_url,
        favicon_url=favicon_url, primary_color=primary_color, accent_color=accent_color)
    return _platform_redirect("enterprise", "Brand created.")


@rt("/talent/enterprise/sites")
def post(session, brand_id: int = 0, name: str = "", slug: str = "", locale: str = "en"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.create_career_site(brand_id, name, slug, locale=locale)
    return _platform_redirect("enterprise", "Careers site created.")


@rt("/talent/enterprise/teams")
def post(session, organization_id: int = 0, team_name: str = "", country: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.create_team(organization_id, team_name, country=country)
    return _platform_redirect("enterprise", "Team created.")


@rt("/talent/enterprise/members")
def post(session, organization_id: int = 0, email: str = "", role: str = "recruiter", team_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.add_member(organization_id, email, role, team_id=team_id or None)
    return _platform_redirect("enterprise", "Organization member added.")


@rt("/talent/enterprise/idp")
def post(session, organization_id: int = 0, protocol: str = "SAML", name: str = "",
         entity_id: str = "", sso_url: str = "", metadata_url: str = "",
         certificate_pem: str = "", client_id: str = "", client_secret: str = "",
         config: str = "{}"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.save_identity_provider(
        organization_id, protocol, name, entity_id=entity_id, sso_url=sso_url,
        metadata_url=metadata_url, certificate_pem=certificate_pem,
        client_id=client_id, client_secret=client_secret, config=json.loads(config or "{}"))
    return _platform_redirect("enterprise", "Identity provider configured.")


@rt("/talent/enterprise/policies")
def post(session, organization_id: int = 0, name: str = "", roles: str = "",
         resources: str = "", actions: str = "", effect: str = "allow",
         conditions: str = "{}"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.save_access_policy(
        organization_id, name, [r.strip() for r in resources.split(",") if r.strip()],
        [a.strip() for a in actions.split(",") if a.strip()],
        roles=[r.strip() for r in roles.split(",") if r.strip()],
        effect=effect, conditions=json.loads(conditions or "{}"))
    return _platform_redirect("enterprise", "Access policy created.")


@rt("/talent/enterprise/scim-token")
def post(session, organization_id: int = 0, label: str = "SCIM"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    token = recruitment_enterprise.issue_scim_token(organization_id, label, actor=_user(session))
    return _platform_redirect("enterprise", f"SCIM token (copy now): {token}")


@rt("/talent/enterprise/legal")
def post(session, organization_id: int = 0, document_type: str = "DPA", version: str = "",
         content: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.save_legal_document(
        organization_id, document_type, version, content=content,
        effective_at=date.today().isoformat())
    return _platform_redirect("enterprise", "Legal document saved.")


@rt("/talent/enterprise/screening")
def post(session, job_id: int = 0, criteria: str = "", threshold: float = 60,
         auto_stage: str = "Screen", anonymize: str = "", automatic: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    parsed = []
    for item in criteria.split(","):
        parts = [part.strip() for part in item.split(":")]
        if parts and parts[0]:
            parsed.append({"name": parts[0], "weight": float(parts[1]) if len(parts) > 1 else 1,
                           "required": len(parts) > 2 and parts[2].lower() == "required"})
    recruitment_enterprise.save_screening_profile(
        job_id, parsed, threshold=threshold, anonymize=bool(anonymize), auto_stage=auto_stage,
        require_manual_review=not bool(automatic), actor=_user(session))
    return _platform_redirect("enterprise", "AI screening profile saved.")


@rt("/talent/enterprise/screening/run")
def post(session, application_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruitment_enterprise.evaluate_application(application_id)
    return _platform_redirect("enterprise", f"Screening score: {result['total_score']}. {result['summary']}")


@rt("/talent/enterprise/distributions")
def post(session, job_id: int = 0, site_id: int = 0, brand_id: int = 0,
         locale: str = "en", slug: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.distribute_job(job_id, site_id, brand_id=brand_id or None,
                                          locale=locale, slug=slug)
    return _platform_redirect("enterprise", "Job distributed to careers site.")


@rt("/talent/enterprise/translations")
def post(session, entity_type: str = "job_posting", entity_id: int = 0, locale: str = "",
         field_key: str = "public_title", value: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.save_translation(
        entity_type, entity_id, locale, field_key, value, actor=_user(session))
    return _platform_redirect("enterprise", "Reviewed translation saved.")


@rt("/talent/enterprise/translations/ai")
def post(session, entity_type: str = "job_posting", entity_id: int = 0,
         locale: str = "", fields: str = "{}"):
    denied = _publisher_guard(session)
    if denied:
        return denied
    try:
        translated = recruitment_enterprise.translate_content(
            entity_type, entity_id, locale, json.loads(fields), actor=_user(session))
        note = f"AI translated {len(translated)} fields; review them before publishing."
    except Exception as exc:
        note = f"AI translation is unavailable: {exc}"
    return _platform_redirect("enterprise", note)


@rt("/talent/enterprise/video-templates")
def post(session, name: str = "", questions: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.save_video_template(
        name, [{"question": q.strip()} for q in questions.splitlines() if q.strip()],
        actor=_user(session))
    return _platform_redirect("enterprise", "Video interview template saved.")


@rt("/talent/enterprise/video-invite")
def post(session, template_id: int = 0, application_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    token = recruitment_enterprise.invite_video_interview(template_id, application_id)
    return _platform_redirect("enterprise", f"Video interview link: /video-interview/{token}")


@rt("/talent/enterprise/video-message")
def post(session, candidate_id: int = 0, media_url: str = "", sender: str = ""):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.add_video_message(
        candidate_id, media_url, direction="outbound", sender=sender or _user(session),
        transcriber=_transcriber())
    return _platform_redirect("enterprise", "Video message recorded.")


@rt("/talent/enterprise/import")
def post(session, file_name: str = "candidates.csv", csv_text: str = "", mapping: str = "{}",
         job_id: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    result = recruitment_enterprise.import_candidates(
        file_name, csv_text, json.loads(mapping), actor=_user(session), job_id=job_id or None)
    return _platform_redirect("enterprise", f"Imported {result['imported']}; {result['failed']} failed.")


@rt("/talent/source-candidate")
async def post(session, request):
    """Authenticated JSON intake used by sourcing extensions and bookmarklets."""
    configured = os.getenv("FASTHR_SOURCE_TOKEN", "")
    authorization = request.headers.get("authorization", "")
    bearer = authorization.split(None, 1)[1] if authorization.lower().startswith("bearer ") else ""
    token_ok = bool(configured and bearer and hmac.compare_digest(configured, bearer))
    session_ok = bool(_user(session) and _can_publish(session))
    if not token_ok and not session_ok:
        return JSONResponse({"detail": "Recruiter session or source token required."}, status_code=401)
    try:
        profile = await request.json()
    except (json.JSONDecodeError, TypeError):
        return JSONResponse({"detail": "Send a JSON candidate profile."}, status_code=400)
    if not isinstance(profile, dict) or not any(
        profile.get(key) for key in ("email", "first_name", "last_name", "profile_url")
    ):
        return JSONResponse({"detail": "Candidate identity is required."}, status_code=400)
    candidate_id = recruitment_enterprise.source_candidate(
        profile, actor=_user(session) or "sourcing-extension")
    return JSONResponse({"ok": True, "candidate_id": candidate_id,
                         "candidate_url": f"/talent/candidates/{candidate_id}"}, status_code=201)


@rt("/talent/enterprise/support")
def post(session, organization_id: int = 0, subject: str = "", channel: str = "email",
         priority: str = "Normal"):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    recruitment_enterprise.create_support_request(
        organization_id, _user(session), subject, channel=channel, priority=priority)
    return _platform_redirect("enterprise", "Support request opened.")


@rt("/talent/enterprise/service-plan")
def post(session, organization_id: int = 0, support_tier: str = "Community",
         onboarding_status: str = "", account_manager_email: str = "",
         response_sla_minutes: int = 0, resolution_sla_minutes: int = 0):
    denied = _publisher_guard(session)
    if denied:
        return denied
    recruitment_enterprise.save_service_plan(
        organization_id, support_tier=support_tier, onboarding_status=onboarding_status,
        account_manager_email=account_manager_email,
        response_sla_minutes=response_sla_minutes or None,
        resolution_sla_minutes=resolution_sla_minutes or None)
    return _platform_redirect("enterprise", "Service plan saved.")


@rt("/talent/candidates")
def get(session, q: str = "", status: str = "All", location: str = "", tag: str = "", skill: str = ""):
    return _guard(session, "candidates", lambda: ats.candidates_list(q, status, location=location, tag=tag, skill=skill))


@rt("/talent/candidates/{cid}")
def get(session, cid: int):
    return _guard(session, "candidates", lambda: (*ats.candidate_detail(cid),
                                                   recruiting_platform.collaboration_panel(cid, actor=_user(session))))


@rt("/talent/applications/{app_id}/stage")
def post(session, app_id: int, stage: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    a = db.one("SELECT job_id FROM applications WHERE id=?", (app_id,))
    if not a:
        return Response("No such application", status_code=404)
    talent.set_stage(app_id, stage, actor=_user(session))
    return ats.job_main(a["job_id"])


@rt("/talent/candidates/{cid}/apply")
def post(session, cid: int, job_id: int = 0):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    if job_id:
        talent.apply_to_job(cid, job_id, actor=_user(session))
        return P("Added to the requisition. Reload to see it listed.", cls="flag",
                 style="border-left-color:var(--accent);background:var(--accent-light);color:var(--accent-hover);")
    return P("Pick a requisition first.", cls="flag")


@rt("/talent/upload")
async def post(session, request):
    """Accept a CV, store it, and kick off extraction on a background thread."""
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    form = await request.form()
    upload = form.get("cv")
    if upload is None or not getattr(upload, "filename", ""):
        return P("Choose a CV file to upload.", cls="flag")
    if not cv_extract.supported(upload.filename):
        return P(f"{upload.filename} is not a supported format — use PDF, DOCX, TXT or MD.", cls="flag")

    data = await upload.read()
    if not data:
        return P("That file is empty.", cls="flag")

    job_id = int(form.get("job_id") or 0) or None
    res = cv_extract.ingest_cv(file_name=upload.filename, data=data, job_id=job_id,
                               source=form.get("source") or "Direct", actor=_user(session))
    cv_extract.run_extraction_async(res["run_id"], res["candidate_id"], res["document_id"])
    return ats.extraction_status(res["candidate_id"])


@rt("/talent/candidates/{cid}/extraction")
def get(session, cid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    return ats.extraction_status(cid)


@rt("/talent/documents/{document_id}")
def get(session, document_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    document = db.one("SELECT * FROM candidate_documents WHERE id=?", (document_id,))
    path = (document or {}).get("stored_path")
    if not path or not os.path.isfile(path):
        return Response("Document not found.", status_code=404)
    return FileResponse(path, filename=document.get("file_name") or "candidate-document")


@rt("/talent/prompts")
def get(session, key: str = "", saved: str = ""):
    return _guard(session, "prompts", lambda: ats.prompts_page(key or cv_extract.PROMPT_KEY, saved))


@rt("/talent/prompts")
def post(session, key: str = "", content: str = "", restore: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    key = key or cv_extract.PROMPT_KEY
    body = cv_extract.DEFAULT_EXTRACTION_PROMPT if restore else (content or "").strip()
    if not body:
        return RedirectResponse(f"/talent/prompts?key={key}", status_code=303)
    version = talent.save_prompt(key, body, title="CV extraction", updated_by=_user(session))
    note = f"Saved as v{version}{' (restored the built-in default)' if restore else ''} — it takes effect on the next upload."
    return RedirectResponse(f"/talent/prompts?key={key}&saved={quote(note)}", status_code=303)


@rt("/talent/prompts/{key}/{version}/activate")
def post(session, key: str, version: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    talent.activate_prompt(key, version)
    return ats.prompt_versions_fragment(key)


# ---------- interviews, offers, ranking, analytics --------------------------

@rt("/talent/applications/{app_id}/interview")
def post(session, app_id: int, kind: str = "Screen", interviewer_id: int = 0,
         scheduled_at: str = "", mode: str = "Video"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    talent.schedule_interview(app_id, interviewer_id=interviewer_id or None, kind=kind,
                              scheduled_at=scheduled_at.replace("T", " "), mode=mode,
                              actor=_user(session))
    return ats.interviews_panel(app_id)


@rt("/talent/interviews/{interview_id}")
def get(session, interview_id: int):
    return _guard(session, "candidates", lambda: ats.scorecard_page(interview_id))


@rt("/talent/interviews/{interview_id}")
async def post(session, interview_id: int, request):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    scores, comments = {}, {}
    for key, val in form.items():
        if key.startswith("score_") and val:
            try:
                scores[int(key[6:])] = float(val)
            except ValueError:
                continue
        elif key.startswith("comment_") and val:
            comments[int(key[8:])] = val
    talent.record_scorecard(interview_id, scores, comment_by=comments,
                            recommendation=form.get("recommendation", ""),
                            notes=form.get("notes", ""), actor=_user(session))
    iv = db.one("SELECT application_id FROM interviews WHERE id=?", (interview_id,))
    cand = db.one("SELECT candidate_id FROM applications WHERE id=?",
                  (iv["application_id"],)) if iv else None
    return RedirectResponse(f"/talent/candidates/{cand['candidate_id']}" if cand
                            else "/talent/candidates", status_code=303)


@rt("/talent/jobs/{job_id}/calibration")
def get(session, job_id: int):
    return _guard(session, "jobs", lambda: ats.calibration_page(job_id))


@rt("/talent/jobs/{job_id}/rank")
def post(session, job_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    ranking.rank_job(job_id, actor=_user(session))
    return ats.ranking_panel(job_id)


@rt("/talent/applications/{app_id}/offer")
def post(session, app_id: int, salary: float = 0, start_date: str = "", expires_on: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    oid = talent.draft_offer(app_id, salary=salary, start_date=start_date,
                             expires_on=expires_on, actor=_user(session))
    letter = ranking.draft_letter(oid)
    with db.cursor() as conn:
        conn.execute("UPDATE offers SET letter=? WHERE id=?", (letter, oid))
    return RedirectResponse(f"/talent/offers/{oid}", status_code=303)


@rt("/talent/offers")
def get(session, status: str = "All"):
    return _guard(session, "offers", lambda: ats.offers_page(status))


@rt("/talent/offers/{offer_id}")
def get(session, offer_id: int):
    return _guard(session, "offers", lambda: ats.offer_detail(offer_id))


@rt("/talent/offers/{offer_id}/status")
def post(session, offer_id: int, status: str = "", reason: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    talent.set_offer_status(offer_id, status, actor=_user(session), reason=reason)
    return ats.offers_table()


@rt("/talent/analytics")
def get(session):
    return _guard(session, "talent-analytics", ats.analytics_page)


# ---------- performance -----------------------------------------------------

@rt("/performance/goals")
def get(session, period: str = "All", status: str = "All", owner_type: str = "All"):
    return _guard(session, "goals", lambda: performance.goals_page(period, status, owner_type))


@rt("/performance/goals")
def post(session, title: str = "", owner_type: str = "employee", owner: str = "0",
         parent_goal_id: int = 0, metric: str = "", target: float = 0, period: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    owner_id = None
    if owner and owner[0] in "ed" and owner[1:].isdigit():
        owner_id = int(owner[1:])
        owner_type = "employee" if owner[0] == "e" else "department"
    elif owner_type == "company":
        owner_id = None
    if title.strip():
        people.create_goal(title=title.strip(), owner_type=owner_type, owner_id=owner_id,
                           parent_goal_id=parent_goal_id or None, metric=metric, target=target,
                           period=period, actor=_user(session))
    return RedirectResponse(f"/performance/goals?period={quote(period)}", status_code=303)


@rt("/performance/goals/{goal_id}")
def get(session, goal_id: int):
    return _guard(session, "goals", lambda: performance.goal_detail(goal_id))


@rt("/performance/goals/{goal_id}/checkin")
def post(session, goal_id: int, value: float = 0, status: str = "", note: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.checkin(goal_id, value=value, status=status, note=note, actor=_user(session))
    return performance.goal_body(goal_id)


@rt("/performance/alignment")
def get(session, period: str = "All"):
    return _guard(session, "goals", lambda: performance.alignment_page(period))


@rt("/performance/feedback")
def get(session, kind: str = "All"):
    return _guard(session, "feedback", lambda: performance.feedback_page(kind))


@rt("/performance/feedback")
def post(session, to_employee_id: int = 0, from_employee_id: int = 0, kind: str = "Praise",
         competency_id: int = 0, visibility: str = "Team", body: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    if to_employee_id and body.strip():
        people.give_feedback(from_employee_id=from_employee_id or None,
                             to_employee_id=to_employee_id, body=body.strip(), kind=kind,
                             competency_id=competency_id or None, visibility=visibility,
                             actor=_user(session))
    return performance.feed_list()


@rt("/performance/reviews")
def get(session):
    return _guard(session, "reviews", performance.reviews_page)


@rt("/performance/reviews")
def post(session, name: str = "", period_start: str = "", period_end: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if name.strip():
        people.create_cycle(name=name.strip(), period_start=period_start,
                            period_end=period_end, actor=_user(session))
    return RedirectResponse("/performance/reviews", status_code=303)


@rt("/performance/reviews/{cycle_id}")
def get(session, cycle_id: int, status: str = "All"):
    return _guard(session, "reviews", lambda: performance.cycle_detail(cycle_id, status))


@rt("/performance/reviews/{cycle_id}/status")
def post(session, cycle_id: int, status: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.set_cycle_status(cycle_id, status, actor=_user(session))
    return performance.cycles_fragment()


@rt("/performance/reviews/{cycle_id}/{review_id}")
def get(session, cycle_id: int, review_id: int):
    return _guard(session, "reviews", lambda: performance.review_form(cycle_id, review_id))


@rt("/performance/reviews/{cycle_id}/{review_id}")
async def post(session, cycle_id: int, review_id: int, request):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    ratings = {k[5:]: v for k, v in form.items() if k.startswith("comp_") and v}
    scores = [float(v) for v in ratings.values() if str(v).replace(".", "").isdigit()]
    people.submit_review(review_id, overall=sum(scores) / len(scores) if scores else 0,
                         narrative=form.get("narrative", ""), ratings=ratings,
                         actor=_user(session))
    return RedirectResponse(f"/performance/reviews/{cycle_id}", status_code=303)


@rt("/performance/signals")
def get(session, dept: str = "All"):
    return _guard(session, "signals", lambda: performance.signals_page(dept))


# ---------- lifecycle -------------------------------------------------------

@rt("/lifecycle/onboarding")
def get(session):
    return _guard(session, "onboarding", lifecycle.onboarding_page)


@rt("/lifecycle/onboarding/{employee_id}")
def get(session, employee_id: int):
    return _guard(session, "onboarding", lambda: lifecycle.onboarding_detail(employee_id))


@rt("/lifecycle/onboarding/task/{task_id}")
def post(session, task_id: int, status: str = "Done"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    eid = people.set_task_status(task_id, status, actor=_user(session))
    return lifecycle.checklist(eid) if eid else Response("Not found", status_code=404)


@rt("/lifecycle/changes")
def get(session, status: str = "All"):
    return _guard(session, "changes", lambda: lifecycle.changes_page(status))


@rt("/lifecycle/changes")
def post(session, employee_id: int = 0, change_type: str = "Role change",
         effective_date: str = "", designation: str = "", dept_id: int = 0,
         base_salary: float = 0):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    to_values = {}
    if designation.strip():
        to_values["designation"] = designation.strip()
    if dept_id:
        to_values["dept_id"] = dept_id
    if base_salary:
        to_values["base_salary"] = base_salary
    if employee_id and to_values:
        people.propose_change(employee_id, change_type=change_type,
                              effective_date=effective_date, to_values=to_values,
                              actor=_user(session))
    return RedirectResponse("/lifecycle/changes", status_code=303)


@rt("/lifecycle/changes/{change_id}/approve")
def post(session, change_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.apply_change(change_id, actor=_user(session))
    return lifecycle.changes_table()


@rt("/lifecycle/changes/{change_id}/reject")
def post(session, change_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.reject_change(change_id, actor=_user(session))
    return lifecycle.changes_table()


@rt("/lifecycle/separations")
def get(session, status: str = "All"):
    return _guard(session, "separations", lambda: lifecycle.separations_page(status))


@rt("/lifecycle/separations")
def post(session, employee_id: int = 0, kind: str = "Resignation", notice_date: str = "",
         last_day: str = "", reason: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if employee_id:
        people.start_separation(employee_id, kind=kind, notice_date=notice_date,
                                last_day=last_day, reason=reason, actor=_user(session))
    return RedirectResponse("/lifecycle/separations", status_code=303)


@rt("/lifecycle/separations/{sep_id}")
def get(session, sep_id: int):
    return _guard(session, "separations", lambda: lifecycle.separation_detail(sep_id))


@rt("/lifecycle/separations/{sep_id}/task/{index}")
def post(session, sep_id: int, index: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.toggle_exit_task(sep_id, index, actor=_user(session))
    return lifecycle.exit_checklist(sep_id)


@rt("/lifecycle/separations/{sep_id}/exit")
def post(session, sep_id: int, notes: str = "", sentiment: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    people.record_exit_interview(sep_id, notes=notes, sentiment=sentiment, actor=_user(session))
    return RedirectResponse(f"/lifecycle/separations/{sep_id}", status_code=303)


@rt("/lifecycle/alumni")
def get(session):
    return _guard(session, "separations", lifecycle.alumni_page)


@rt("/lifecycle/cases")
def get(session, status: str = "All"):
    return _guard(session, "cases", lambda: lifecycle.cases_page(status))


@rt("/lifecycle/cases")
def post(session, employee_id: int = 0, kind: str = "Other", severity: str = "Normal",
         visibility: str = "HR only", summary: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if summary.strip():
        people.open_case(employee_id=employee_id or None, kind=kind, summary=summary.strip(),
                         severity=severity, visibility=visibility, actor=_user(session))
    return RedirectResponse("/lifecycle/cases", status_code=303)


@rt("/lifecycle/cases/{case_id}/status")
def post(session, case_id: int, status: str = "", resolution: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    people.set_case_status(case_id, status, resolution=resolution, actor=_user(session))
    return lifecycle.cases_table()


@rt("/lifecycle/org")
def get(session, dept_id: int = 0, delta: int = 0):
    return _guard(session, "org", lambda: lifecycle.org_page(dept_id, delta))


# ---------- settings --------------------------------------------------------

@rt("/settings/integrations")
def get(session, saved: str = ""):
    return _guard(session, "integrations", lambda: settings.integrations_page(saved))


@rt("/settings/integrations/{provider}")
def get(session, provider: str, note: str = ""):
    return _guard(session, "integrations", lambda: settings.integration_detail(provider, note))


@rt("/settings/integrations/{provider}")
def post(session, provider: str, api_key: str = "", api_secret: str = "",
         account_ref: str = "", auto_sync: str = "", test: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    integrations.save(provider, api_key=api_key.strip(), api_secret=api_secret.strip(),
                      account_ref=account_ref.strip(), auto_sync=bool(auto_sync),
                      actor=_user(session))
    note = "Credentials saved."
    if test:
        note = integrations.test_connection(provider, actor=_user(session))["note"]
    return RedirectResponse(f"/settings/integrations/{provider}?note={quote(note)}",
                            status_code=303)


@rt("/settings/integrations/{provider}/test")
def post(session, provider: str):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    integrations.test_connection(provider, actor=_user(session))
    return settings.integrations_grid()


@rt("/settings/integrations/{provider}/sync")
def post(session, provider: str):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    integrations.sync(provider, actor=_user(session))
    return settings.integrations_grid()


@rt("/settings/integrations/{provider}/disconnect")
def post(session, provider: str):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    integrations.disconnect(provider, actor=_user(session))
    return RedirectResponse(f"/settings/integrations/{provider}"
                            f"?note={quote('Disconnected. Stored credentials were erased.')}",
                            status_code=303)


@rt("/settings/roles")
def get(session, saved: str = ""):
    return _guard(session, "roles", lambda: settings.roles_page(saved))


@rt("/settings/roles")
def post(session, account_email: str = "", role: str = "employee", scope: str = "all",
         employee_id: int = 0):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    if account_email.strip():
        with db.cursor() as conn:
            conn.execute("""INSERT INTO account_roles(account_email,role,scope,employee_id,created)
                            VALUES (?,?,?,?,datetime('now'))""",
                         (account_email.strip().lower(), role, scope, employee_id or None))
    return RedirectResponse(f"/settings/roles?saved={quote('Role assigned.')}", status_code=303)


@rt("/settings/roles/{role_id}/delete")
def post(session, role_id: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    with db.cursor() as conn:
        conn.execute("DELETE FROM account_roles WHERE id=?", (role_id,))
    return settings.roles_table()


@rt("/payroll")
def get(session, period: str = "latest"):
    return _guard(session, "payroll", lambda: views.payroll_list(period))


@rt("/payroll/{pid}")
def get(session, pid: int):
    return _guard(session, "payroll", lambda: views.payslip_detail(pid))


@rt("/ai")
def get(session):
    body = (views._title("AI Assistant", "Chat lives in the right rail. Ask in plain English or use slash-commands."),
            Div(NotStr(
                "<div class='card'><h3>What you can ask</h3><ul style='line-height:1.8;'>"
                "<li>“Who's on leave today?”</li><li>“Which department is biggest?”</li>"
                "<li>“How many leave requests are pending approval?”</li>"
                "<li>“What's the latest payroll total?”</li></ul>"
                "<p style='color:var(--text-mute)'>Slash-commands (no API key): "
                "<code>/headcount</code> <code>/leave</code> <code>/today</code> <code>/payroll</code></p></div>")))
    return _guard(session, "ai", body)


@rt("/healthz")
def healthz():
    """Unauthenticated build probe — confirms which version a deploy is running."""
    return JSONResponse({"status": "ok", "product": "FastHRM", **version.info(),
                         "migrations": db.scalar(
                             "SELECT COUNT(*) FROM schema_migrations") or 0})


@rt("/about")
def get(session):
    v = version.info()
    stamped = bool(v["commit"])
    rows = [("Version", f"v{v['version']}"),
            ("Commit", v["commit"] + (" (uncommitted changes)" if v["dirty"] else "")
             if v["commit"] else "unknown"),
            ("Branch", v["branch"] or "unknown"),
            ("Built", v["build_date"] or "unknown"),
            ("Environment", ENV_LABEL),
            ("Model provider", f"{os.getenv('MODEL_PROVIDER', 'xai')} · "
                               f"{os.getenv('MODEL_NAME', 'grok-4-1-fast-reasoning')}"),
            ("Database", db.DB_PATH),
            ("Migrations applied", str(db.scalar("SELECT COUNT(*) FROM schema_migrations") or 0))]
    applied = db.rows("SELECT * FROM schema_migrations ORDER BY version")
    body = (
        views._title("About this build", "What is running, and where it came from"),
        Div(NotStr("<div class='card'><div class='card-header'><h3>Build</h3></div>"
                   "<div class='kv'>"
                   + "".join(f"<span class='k'>{k}</span><span>{v_}</span>" for k, v_ in rows)
                   + "</div></div>")),
        None if stamped else Div(NotStr(
            "<p class='flag'>No build stamp and no git metadata available, so the exact "
            "commit cannot be confirmed. Deployed images should set "
            "<code>FASTHR_COMMIT</code> and <code>FASTHR_BUILD_DATE</code>.</p>")),
        Div(NotStr("<div class='card'><div class='card-header'><h3>Schema history</h3></div>"
                   "<table class='tbl'><thead><tr><th>Migration</th><th>Applied</th></tr></thead>"
                   "<tbody>"
                   + "".join(f"<tr><td>{m['version']}</td><td>{m['applied_at']}</td></tr>"
                             for m in applied)
                   + "</tbody></table></div>")),
        Div(NotStr("<p style='color:var(--text-mute);font-size:12.5px;'>"
                   "<code>/healthz</code> returns the same build details as JSON, without "
                   "requiring a login — use it to confirm what a deployment is running.</p>")),
    )
    return _guard(session, "about", tuple(b for b in body if b is not None))


@rt("/guide")
def get(session):
    body = (views._title("User Guide", "How to drive FastHRM"), Div(NotStr("""
<div class='card'><h3>Dashboard</h3><p>Headcount, attendance, on-leave-today and pending leave, with headcount by department.</p></div>
<div class='card'><h3>Employees & Departments</h3><p>Searchable directory filtered by department; each employee shows
leave balance, recent attendance, and payslips. Departments lists headcount, head and annual payroll.</p></div>
<div class='card'><h3>Leave & Attendance</h3><p>Leave requests by status, and today's attendance register with a per-status breakdown.</p></div>
<div class='card'><h3>Payroll</h3><p>Payslips per pay period with a full deductions breakdown on each payslip.</p></div>
<div class='card'><h3>Public Careers & Job Pages</h3><p>Author, preview and publish role specifications as shareable
sub-pages. Candidate applications, form answers and consent flow directly into the matching requisition.</p></div>
<div class='card'><h3>Recruiting Platform</h3><p>Use Operations for projects, tasks and talent pools; Communications for
mailboxes, templates, automations and privacy; Scheduling for interview availability; Marketing for job boards and campaigns;
Analytics for conversion reporting; and Enterprise for brands, identity, screening, video and service controls.</p></div>
<div class='card'><h3>Performance & Lifecycle</h3><p>Manage goals, feedback, reviews and explainable signals, then coordinate
onboarding, internal changes, separations, employee-relations cases and the organisation chart.</p></div>
<div class='card'><h3>AI Assistant</h3><p>The right rail chats over a live HR snapshot. Set <code>MODEL_PROVIDER</code> + a key in
<code>.env</code> for free-form chat; slash-commands always work.</p></div>""")))
    return _guard(session, "guide", body)


@rt("/chat/new")
def get(session):
    session["thread"] = uuid.uuid4().hex
    return P("Ask about headcount, leave or attendance — or use /headcount /leave /help.", cls="chat-empty-hint")


@rt("/chat/stream")
async def post(session, message: str = "", thread_id: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    message = (message or "").strip()
    if not message:
        return Response("No message", status_code=400)
    tid = thread_id or _thread(session)

    async def gen():
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "user", message))
        full = []
        async for chunk in ai.stream_chat(message):
            if chunk.startswith("data: "):
                try:
                    tok = json.loads(chunk[6:]).get("token")
                    if tok:
                        full.append(tok)
                except Exception:
                    pass
            yield chunk
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "assistant", "".join(full)))

    return StreamingResponse(gen(), media_type="text/event-stream")


def _ensure_db():
    """Migrate, then seed anything that is still empty.

    Emptiness is judged by row counts, not by whether the file exists: importing
    web.api constructs the SQLite backend, which creates the database before this
    runs, so a file-existence check would skip seeding on a fresh install.
    """
    applied = db.migrate()
    if applied:
        logger.info("Applied migrations: %s", ", ".join(applied))
    if not db.scalar("SELECT COUNT(*) FROM employees"):
        logger.info("No employees found — seeding synthetic HR data…")
        import seed
        seed.build()
    if not db.scalar("SELECT COUNT(*) FROM job_openings"):
        logger.info("No requisitions found — seeding synthetic talent pipeline…")
        import seed_talent
        seed_talent.build()
    if not db.scalar("SELECT COUNT(*) FROM goals"):
        logger.info("No performance data found — seeding goals, feedback and lifecycle…")
        import seed_platform
        seed_platform.build()
    cv_extract.ensure_default_prompt()
    ranking.ensure_prompts()
    recruitment.process_publication_schedules()
    recruitment_communications.dispatch_due()
    recruiting_ops.refresh_credential_statuses()


_ensure_db()


register_seo_routes(app)

if __name__ == "__main__":
    logger.info("FastHRM on http://localhost:%s  (login %s)", PORT, VALID_EMAIL)
    serve(port=PORT, reload=os.getenv("FASTHR_RELOAD", "0") == "1")
