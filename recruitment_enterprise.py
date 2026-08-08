"""Phase 5 enterprise tenancy, identity, AI screening, video, import, and support."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import secrets
import urllib.parse
import zlib
from datetime import datetime, timedelta, timezone

import db
import integrations
import recruitment
import talent


def ensure_organization(name: str = "FastHRM", *, slug: str = "fasthr",
                        default_locale: str = "en", timezone_name: str = "UTC") -> dict:
    row = db.one("SELECT * FROM organizations WHERE slug=?", (slug,))
    if row:
        return row
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO organizations(name,slug,default_locale,timezone,settings_json,created)
               VALUES (?,?,?,?, '{}',datetime('now'))""", (name.strip(), slug, default_locale, timezone_name),
        )
        organization_id = cur.lastrowid
    return db.one("SELECT * FROM organizations WHERE id=?", (organization_id,))


def create_brand(organization_id: int, name: str, slug: str, *, logo_url: str = "",
                 favicon_url: str = "", primary_color: str = "#0891b2",
                 accent_color: str = "#0e7490", custom_domain: str = "",
                 settings: dict | None = None) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO brands
               (organization_id,name,slug,logo_url,favicon_url,primary_color,accent_color,
                custom_domain,settings_json,created,updated)
               VALUES (?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (organization_id, name.strip(), slug.strip(), logo_url, favicon_url, primary_color,
             accent_color, custom_domain.strip().lower() or None, json.dumps(settings or {})),
        )
        return cur.lastrowid


def create_career_site(brand_id: int, name: str, slug: str, *, locale: str = "en",
                       headline: str = "Join our team", introduction: str = "Explore open roles.") -> int:
    brand = db.one("SELECT * FROM brands WHERE id=?", (brand_id,))
    if not brand:
        raise ValueError("Brand not found.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO career_sites
               (name,slug,headline,introduction,brand_color,accent_color,logo_url,
                privacy_policy_url,is_active,created,updated)
               VALUES (?,?,?,?,?,?,?,'/privacy',1,datetime('now'),datetime('now'))""",
            (name.strip(), slug.strip(), headline, introduction,
             brand.get("primary_color") or "#0891b2", brand.get("accent_color") or "#0e7490",
             brand.get("logo_url") or ""),
        )
        site_id = cur.lastrowid
        conn.execute("INSERT INTO career_site_brands(career_site_id,brand_id,locale) VALUES (?,?,?)",
                     (site_id, brand_id, locale))
    return site_id


def create_team(organization_id: int, name: str, *, parent_id: int | None = None,
                country: str = "", department_id: int | None = None,
                settings: dict | None = None) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO organization_teams
               (organization_id,parent_id,name,country,department_id,settings_json)
               VALUES (?,?,?,?,?,?)""",
            (organization_id, parent_id, name.strip(), country, department_id, json.dumps(settings or {})),
        )
        return cur.lastrowid


def add_member(organization_id: int, email: str, role: str, *, team_id: int | None = None,
               scopes: dict | None = None, active: bool = True) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO organization_members
               (organization_id,team_id,account_email,role,scope_json,active,created)
               VALUES (?,?,?,?,?,?,datetime('now')) ON CONFLICT(organization_id,account_email)
               DO UPDATE SET team_id=excluded.team_id,role=excluded.role,
               scope_json=excluded.scope_json,active=excluded.active""",
            (organization_id, team_id, email.lower(), role, json.dumps(scopes or {}), int(active)),
        )
        return conn.execute(
            "SELECT id FROM organization_members WHERE organization_id=? AND account_email=?",
            (organization_id, email.lower())).fetchone()[0]


def distribute_job(job_id: int, career_site_id: int, *, brand_id: int | None = None,
                   locale: str = "en", slug: str = "", status: str = "Published") -> int:
    posting = recruitment.ensure_posting(job_id)
    slug = slug.strip() or posting["slug"]
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO job_distributions
               (job_posting_id,career_site_id,brand_id,locale,slug,status,published_at)
               VALUES (?,?,?,?,?,?,CASE WHEN ?='Published' THEN datetime('now') END)
               ON CONFLICT(career_site_id,locale,slug) DO UPDATE SET brand_id=excluded.brand_id,
               status=excluded.status,published_at=CASE WHEN excluded.status='Published'
               THEN COALESCE(job_distributions.published_at,datetime('now')) ELSE job_distributions.published_at END""",
            (posting["id"], career_site_id, brand_id, locale, slug, status, status),
        )
        return conn.execute(
            "SELECT id FROM job_distributions WHERE career_site_id=? AND locale=? AND slug=?",
            (career_site_id, locale, slug)).fetchone()[0]


def resolve_brand(*, host: str = "", site_slug: str = "") -> dict | None:
    if host:
        row = db.one(
            """SELECT b.*,c.id career_site_id,c.slug site_slug,c.name site_name,cb.locale default_locale
               FROM brands b LEFT JOIN career_site_brands cb ON cb.brand_id=b.id
               LEFT JOIN career_sites c ON c.id=cb.career_site_id WHERE lower(b.custom_domain)=?""",
            (host.split(":")[0].lower(),),
        )
        if row:
            return row
    if site_slug:
        return db.one(
            """SELECT b.*,c.id career_site_id,c.slug site_slug,c.name site_name,cb.locale default_locale
               FROM career_sites c JOIN career_site_brands cb ON cb.career_site_id=c.id
               JOIN brands b ON b.id=cb.brand_id WHERE c.slug=?""", (site_slug,),
        )
    return None


def public_career_site(site_slug: str, locale: str = "en") -> dict | None:
    return db.one(
        """SELECT c.*,b.id brand_id,b.name brand_name,b.logo_url brand_logo,
                  b.favicon_url,b.primary_color,b.accent_color,b.custom_domain,cb.locale default_locale
           FROM career_sites c LEFT JOIN career_site_brands cb ON cb.career_site_id=c.id
           LEFT JOIN brands b ON b.id=cb.brand_id WHERE c.slug=? AND c.is_active=1
           ORDER BY (cb.locale=?) DESC LIMIT 1""", (site_slug, locale),
    )


def public_site_jobs(site_slug: str, locale: str = "en") -> list[dict]:
    rows = db.rows(
        """SELECT d.id distribution_id,d.slug,d.locale,p.id posting_id,p.slug primary_slug,p.job_id,p.public_title,
                  p.summary,p.description,p.requirements,p.benefits,p.seo_title,p.seo_description,
                  p.application_deadline,p.published_at,j.location,j.remote_policy,j.employment_type,
                  j.currency,j.comp_min,j.comp_max,dep.name department
           FROM job_distributions d JOIN career_sites c ON c.id=d.career_site_id
           JOIN job_postings p ON p.id=d.job_posting_id JOIN job_openings j ON j.id=p.job_id
           LEFT JOIN departments dep ON dep.id=j.dept_id
           WHERE c.slug=? AND d.locale=? AND d.status='Published'
           AND p.publication_status='Published'
           AND (p.application_deadline IS NULL OR p.application_deadline>=date('now'))
           ORDER BY d.published_at DESC,d.id DESC""", (site_slug, locale),
    )
    for row in rows:
        row.update(localized_values("job_posting", row["posting_id"], locale, row))
    return rows


def public_distributed_job(site_slug: str, locale: str, slug: str) -> dict | None:
    jobs = public_site_jobs(site_slug, locale)
    row = next((job for job in jobs if job["slug"] == slug), None)
    if not row:
        return None
    site = public_career_site(site_slug, locale) or {}
    row.update({"career_site_name": site.get("name"),
                "brand_color": site.get("primary_color") or site.get("brand_color"),
                "accent_color": site.get("accent_color"),
                "logo_url": site.get("brand_logo") or site.get("logo_url"),
                "favicon_url": site.get("favicon_url"),
                "privacy_policy_url": site.get("privacy_policy_url")})
    return row


def save_translation(entity_type: str, entity_id: int, locale: str, field_key: str,
                     value: str, *, actor: str, machine_generated: bool = False) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO content_translations
               (entity_type,entity_id,locale,field_key,value_text,machine_generated,updated_by,updated)
               VALUES (?,?,?,?,?,?,?,datetime('now')) ON CONFLICT(entity_type,entity_id,locale,field_key)
               DO UPDATE SET value_text=excluded.value_text,machine_generated=excluded.machine_generated,
               reviewed_at=CASE WHEN excluded.machine_generated=0 THEN datetime('now') ELSE NULL END,
               updated_by=excluded.updated_by,updated=excluded.updated""",
            (entity_type, entity_id, locale, field_key, value, int(machine_generated), actor),
        )
        return conn.execute(
            """SELECT id FROM content_translations WHERE entity_type=? AND entity_id=?
               AND locale=? AND field_key=?""", (entity_type, entity_id, locale, field_key)).fetchone()[0]


def translate_content(entity_type: str, entity_id: int, locale: str, fields: dict[str, str], *,
                      actor: str, translator=None) -> dict:
    translated = {}
    for key, value in fields.items():
        if translator:
            output = translator(value, locale)
        else:
            from web import llm
            response = llm.get_llm(temperature=0).invoke(
                f"Translate the following recruitment content to {locale}. Return only the translation:\n{value}")
            output = response.content if hasattr(response, "content") else str(response)
        translated[key] = str(output).strip()
        save_translation(entity_type, entity_id, locale, key, translated[key], actor=actor,
                         machine_generated=True)
    return translated


def localized_values(entity_type: str, entity_id: int, locale: str, defaults: dict) -> dict:
    values = dict(defaults)
    for row in db.rows(
        "SELECT field_key,value_text FROM content_translations WHERE entity_type=? AND entity_id=? AND locale=?",
        (entity_type, entity_id, locale),
    ):
        values[row["field_key"]] = row["value_text"]
    return values


def enterprise_summary(organization_id: int) -> dict:
    return {
        "brands": db.scalar("SELECT COUNT(*) FROM brands WHERE organization_id=?", (organization_id,)) or 0,
        "teams": db.scalar("SELECT COUNT(*) FROM organization_teams WHERE organization_id=?", (organization_id,)) or 0,
        "members": db.scalar("SELECT COUNT(*) FROM organization_members WHERE organization_id=? AND active=1", (organization_id,)) or 0,
        "published_jobs": db.scalar(
            """SELECT COUNT(DISTINCT d.job_posting_id) FROM job_distributions d
               JOIN brands b ON b.id=d.brand_id WHERE b.organization_id=? AND d.status='Published'""",
            (organization_id,)) or 0,
        "applications": db.scalar(
            """SELECT COUNT(DISTINCT a.id) FROM applications a JOIN job_postings p ON p.job_id=a.job_id
               JOIN job_distributions d ON d.job_posting_id=p.id JOIN brands b ON b.id=d.brand_id
               WHERE b.organization_id=?""", (organization_id,)) or 0,
    }


def save_identity_provider(organization_id: int, protocol: str, name: str, *,
                           entity_id: str = "", metadata_url: str = "", sso_url: str = "",
                           certificate_pem: str = "", client_id: str = "",
                           client_secret: str = "", config: dict | None = None) -> int:
    protocol = protocol.upper()
    if protocol not in {"SAML", "OIDC"}:
        raise ValueError("Identity protocol must be SAML or OIDC.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO identity_providers
               (organization_id,protocol,name,entity_id,metadata_url,sso_url,certificate_pem,
                client_id,client_secret_enc,config_json,active,created,updated)
               VALUES (?,?,?,?,?,?,?,?,?,?,1,datetime('now'),datetime('now'))""",
            (organization_id, protocol, name.strip(), entity_id, metadata_url, sso_url,
             certificate_pem, client_id, integrations.encrypt(client_secret), json.dumps(config or {})),
        )
        return cur.lastrowid


def saml_login_url(provider_id: int, *, acs_url: str, relay_state: str = "") -> str:
    provider = db.one("SELECT * FROM identity_providers WHERE id=? AND protocol='SAML' AND active=1", (provider_id,))
    if not provider:
        raise ValueError("Active SAML provider not found.")
    request_id = "_" + secrets.token_hex(20)
    instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    xml = (f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
           f'ID="{request_id}" Version="2.0" IssueInstant="{instant}" '
           f'AssertionConsumerServiceURL="{acs_url}" Destination="{provider["sso_url"]}">'
           f'<saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">{provider["entity_id"]}</saml:Issuer>'
           '</samlp:AuthnRequest>')
    compressed = zlib.compress(xml.encode())[2:-4]
    encoded = base64.b64encode(compressed).decode()
    query = urllib.parse.urlencode({"SAMLRequest": encoded, "RelayState": relay_state})
    return provider["sso_url"] + ("&" if "?" in provider["sso_url"] else "?") + query


def consume_sso_response(provider_id: int, response: str, *, verifier) -> dict:
    """Consume SAML/OIDC through a signature-validating adapter; unsafe parsing is never accepted."""
    provider = db.one("SELECT * FROM identity_providers WHERE id=? AND active=1", (provider_id,))
    if not provider:
        raise ValueError("Active identity provider not found.")
    identity = verifier.verify(provider, response)
    email = (identity.get("email") or "").strip().lower()
    if not email or not identity.get("verified", False):
        raise ValueError("Identity response was not verified.")
    member = db.one(
        """SELECT * FROM organization_members WHERE organization_id=? AND lower(account_email)=?
           AND active=1""", (provider["organization_id"], email),
    )
    if not member:
        raise PermissionError("The verified identity is not provisioned for this organization.")
    return {"email": email, "name": identity.get("name") or email, "role": member["role"],
            "organization_id": provider["organization_id"]}


def issue_scim_token(organization_id: int, label: str, *, actor: str,
                     expires_days: int = 365) -> str:
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    expires = (datetime.now(timezone.utc) + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO scim_tokens
               (organization_id,token_hash,label,expires_at,created_by,created)
               VALUES (?,?,?,?,?,datetime('now'))""", (organization_id, digest, label, expires, actor),
        )
    return raw


def authenticate_scim(token: str) -> int | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.one(
        """SELECT * FROM scim_tokens WHERE token_hash=? AND revoked_at IS NULL
           AND (expires_at IS NULL OR expires_at>=datetime('now'))""", (digest,),
    )
    if row:
        with db.cursor() as conn:
            conn.execute("UPDATE scim_tokens SET last_used_at=datetime('now') WHERE id=?", (row["id"],))
        return row["organization_id"]
    return None


def scim_upsert_user(organization_id: int, external_id: str, email: str, *,
                     role: str = "employee", active: bool = True,
                     team_id: int | None = None, payload: dict | None = None) -> dict:
    member_id = add_member(organization_id, email, role, team_id=team_id,
                           scopes={"external_id": external_id}, active=active)
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO scim_events
               (organization_id,operation,resource_type,external_id,payload_json,status,created)
               VALUES (?,'UPSERT','User',?,?,'Completed',datetime('now'))""",
            (organization_id, external_id, json.dumps(payload or {})),
        )
    return {"id": str(member_id), "externalId": external_id, "userName": email.lower(),
            "active": active, "roles": [{"value": role}]}


def scim_deactivate_user(organization_id: int, email: str) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            "UPDATE organization_members SET active=0 WHERE organization_id=? AND lower(account_email)=?",
            (organization_id, email.lower()),
        )
        conn.execute(
            """INSERT INTO scim_events
               (organization_id,operation,resource_type,external_id,payload_json,status,created)
               VALUES (?,'DEACTIVATE','User',?,?,'Completed',datetime('now'))""",
            (organization_id, email.lower(), json.dumps({"email": email.lower()})),
        )
    return bool(cur.rowcount)


def save_access_policy(organization_id: int, name: str, resources: list[str],
                       actions: list[str], *, roles: list[str] | None = None,
                       conditions: dict | None = None, effect: str = "allow") -> int:
    if effect not in {"allow", "deny"}:
        raise ValueError("Policy effect must be allow or deny.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO access_policies
               (organization_id,name,effect,roles_json,resources_json,actions_json,conditions_json,active,created)
               VALUES (?,?,?,?,?,?,?,1,datetime('now'))""",
            (organization_id, name, effect, json.dumps(roles or []), json.dumps(resources),
             json.dumps(actions), json.dumps(conditions or {})),
        )
        return cur.lastrowid


def policy_allows(organization_id: int, *, role: str, resource: str, action: str,
                  context: dict | None = None) -> bool:
    context = context or {}
    matched_allow = False
    for policy in db.rows("SELECT * FROM access_policies WHERE organization_id=? AND active=1", (organization_id,)):
        roles, resources, actions = (json.loads(policy[key] or "[]") for key in
                                     ("roles_json", "resources_json", "actions_json"))
        conditions = json.loads(policy["conditions_json"] or "{}")
        if roles and role not in roles or resource not in resources and "*" not in resources or action not in actions and "*" not in actions:
            continue
        if not all(context.get(key) == value for key, value in conditions.items()):
            continue
        if policy["effect"] == "deny":
            return False
        matched_allow = True
    return matched_allow


def save_legal_document(organization_id: int, document_type: str, version: str, *,
                        content: str = "", file_url: str = "", effective_at: str) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO legal_documents
               (organization_id,document_type,version,content_text,file_url,effective_at)
               VALUES (?,?,?,?,?,?)""",
            (organization_id, document_type, version, content, file_url, effective_at),
        )
        return cur.lastrowid


def accept_legal_document(document_id: int, email: str) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            "UPDATE legal_documents SET accepted_by=?,accepted_at=datetime('now') WHERE id=?",
            (email.lower(), document_id),
        )
    return bool(cur.rowcount)


def save_screening_profile(job_id: int, criteria: list[dict], *, threshold: float = 60,
                           anonymize: bool = False, auto_stage: str = "",
                           require_manual_review: bool = True, actor: str) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO ai_screening_profiles
               (job_id,threshold,anonymize,auto_stage,require_manual_review,created_by,created,updated)
               VALUES (?,?,?,?,?,?,datetime('now'),datetime('now')) ON CONFLICT(job_id) DO UPDATE SET
               threshold=excluded.threshold,anonymize=excluded.anonymize,auto_stage=excluded.auto_stage,
               require_manual_review=excluded.require_manual_review,updated=excluded.updated""",
            (job_id, float(threshold), int(anonymize), auto_stage or None,
             int(require_manual_review), actor),
        )
        profile_id = conn.execute("SELECT id FROM ai_screening_profiles WHERE job_id=?", (job_id,)).fetchone()[0]
        conn.execute("DELETE FROM ai_screening_criteria WHERE profile_id=?", (profile_id,))
        for index, criterion in enumerate(criteria):
            conn.execute(
                """INSERT INTO ai_screening_criteria
                   (profile_id,name,prompt,weight,required,sort_order) VALUES (?,?,?,?,?,?)""",
                (profile_id, criterion["name"], criterion.get("prompt", ""),
                 float(criterion.get("weight", 1)), int(criterion.get("required", False)), index),
            )
    return profile_id


def screening_input(application_id: int, *, anonymize: bool) -> dict:
    row = db.one(
        """SELECT a.id application_id,a.job_id,c.*,j.title job_title,j.description job_description,
                  j.requirements job_requirements FROM applications a
           JOIN candidates c ON c.id=a.candidate_id JOIN job_openings j ON j.id=a.job_id WHERE a.id=?""",
        (application_id,),
    )
    if not row:
        raise ValueError("Application not found.")
    row["skills"] = [r["skill"] for r in db.rows("SELECT skill FROM candidate_skills WHERE candidate_id=?", (row["id"],))]
    row["experience"] = db.rows("SELECT employer,title,summary FROM candidate_experience WHERE candidate_id=?", (row["id"],))
    if anonymize:
        for key in ("first_name", "last_name", "email", "phone", "location", "linkedin_url"):
            row.pop(key, None)
        for experience in row["experience"]:
            experience.pop("employer", None)
    return row


def evaluate_application(application_id: int, *, evaluator=None, actor: str = "ai-screening") -> dict:
    app = db.one("SELECT * FROM applications WHERE id=?", (application_id,))
    profile = db.one("SELECT * FROM ai_screening_profiles WHERE job_id=?", (app["job_id"],)) if app else None
    if not profile:
        raise ValueError("Screening profile not configured.")
    criteria = db.rows("SELECT * FROM ai_screening_criteria WHERE profile_id=? ORDER BY sort_order", (profile["id"],))
    data = screening_input(application_id, anonymize=bool(profile["anonymize"]))
    if evaluator:
        evaluated = evaluator(data, criteria)
    else:
        haystack = json.dumps(data).lower()
        evaluated = []
        for criterion in criteria:
            terms = [term for term in criterion["name"].lower().replace("/", " ").split() if len(term) > 2]
            raw = 100 if terms and all(term in haystack for term in terms) else 50 if any(term in haystack for term in terms) else 0
            evaluated.append({"name": criterion["name"], "score": raw,
                              "evidence": "Profile keyword evidence" if raw else "No explicit evidence"})
    by_name = {item["name"]: item for item in evaluated}
    weighted, weights, required_failed = 0.0, 0.0, []
    for criterion in criteria:
        item = by_name.get(criterion["name"], {"score": 0})
        score, weight = float(item.get("score", 0)), float(criterion["weight"])
        weighted += score * weight; weights += weight
        if criterion["required"] and score < 50:
            required_failed.append(criterion["name"])
    total = round(weighted / weights, 2) if weights else 0
    recommended = profile.get("auto_stage") if total >= profile["threshold"] and not required_failed else "Rejected"
    summary = f"Score {total:.1f}. " + ("Required criteria met." if not required_failed else "Missing: " + ", ".join(required_failed))
    location = data.get("location") or "Location hidden or not provided"
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO ai_screening_results
               (profile_id,application_id,total_score,criteria_json,summary,location_summary,recommended_stage,created)
               VALUES (?,?,?,?,?,?,?,datetime('now')) ON CONFLICT(profile_id,application_id) DO UPDATE SET
               total_score=excluded.total_score,criteria_json=excluded.criteria_json,summary=excluded.summary,
               location_summary=excluded.location_summary,recommended_stage=excluded.recommended_stage,
               created=excluded.created""",
            (profile["id"], application_id, total, json.dumps(evaluated), summary, location, recommended),
        )
    if recommended and not profile["require_manual_review"] and recommended in talent.job_stages(app["job_id"]):
        talent.set_stage(application_id, recommended, actor=actor)
    from recruiting_ops import add_tag
    add_tag(app["candidate_id"], "AI screened", actor=actor)
    return db.one("SELECT * FROM ai_screening_results WHERE profile_id=? AND application_id=?",
                  (profile["id"], application_id))


def override_screening(result_id: int, score: float, reason: str, *, reviewer: str) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE ai_screening_results SET overridden_score=?,override_reason=?,reviewed_by=?,
               reviewed_at=datetime('now') WHERE id=?""", (float(score), reason.strip(), reviewer, result_id),
        )
    return bool(cur.rowcount)


def save_video_template(name: str, questions: list[dict], *, intro: str = "",
                        time_limit_minutes: int = 20, actor: str) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO video_interview_templates
               (name,intro_text,questions_json,time_limit_minutes,created_by,created)
               VALUES (?,?,?,?,?,datetime('now')) ON CONFLICT(name) DO UPDATE SET
               intro_text=excluded.intro_text,questions_json=excluded.questions_json,
               time_limit_minutes=excluded.time_limit_minutes""",
            (name.strip(), intro, json.dumps(questions), time_limit_minutes, actor),
        )
        return conn.execute("SELECT id FROM video_interview_templates WHERE name=?", (name.strip(),)).fetchone()[0]


def invite_video_interview(template_id: int, application_id: int, *, expires_days: int = 7) -> str:
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO video_interview_invitations
               (template_id,application_id,token,status,expires_at,sent_at)
               VALUES (?,?,?,'Invited',?,datetime('now'))""", (template_id, application_id, token, expires),
        )
    return token


def submit_video_response(token: str, question_index: int, media_url: str, *,
                          duration_seconds: int = 0, transcriber=None) -> int:
    invitation = db.one(
        """SELECT * FROM video_interview_invitations WHERE token=? AND expires_at>=datetime('now')
           AND status IN ('Invited','Started')""", (token,),
    )
    if not invitation:
        raise ValueError("Video invitation is not available.")
    transcript, summary = ("", "")
    if transcriber:
        output = transcriber(media_url)
        transcript, summary = output.get("transcript", ""), output.get("summary", "")
    with db.cursor() as conn:
        conn.execute("UPDATE video_interview_invitations SET status='Started',started_at=COALESCE(started_at,datetime('now')) WHERE id=?",
                     (invitation["id"],))
        cur = conn.execute(
            """INSERT INTO video_responses
               (invitation_id,question_index,media_url,duration_seconds,transcript_text,summary_text,created)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (invitation["id"], question_index, media_url, duration_seconds, transcript, summary),
        )
        return cur.lastrowid


def complete_video_interview(token: str) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE video_interview_invitations SET status='Completed',completed_at=datetime('now')
               WHERE token=? AND status='Started'""", (token,),
        )
    return bool(cur.rowcount)


def add_video_message(candidate_id: int, media_url: str, *, direction: str,
                      application_id: int | None = None, sender: str = "",
                      transcriber=None) -> int:
    output = transcriber(media_url) if transcriber else {}
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO video_messages
               (candidate_id,application_id,direction,media_url,transcript_text,summary_text,sender,created)
               VALUES (?,?,?,?,?,?,?,datetime('now'))""",
            (candidate_id, application_id, direction, media_url, output.get("transcript", ""),
             output.get("summary", ""), sender),
        )
        return cur.lastrowid


def import_candidates(file_name: str, csv_text: str, mapping: dict[str, str], *,
                      actor: str, job_id: int | None = None) -> dict:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO candidate_imports
               (file_name,mapping_json,status,total,requested_by,created)
               VALUES (?,?,'Running',?,?,datetime('now'))""",
            (file_name, json.dumps(mapping), len(rows), actor),
        )
        import_id = cur.lastrowid
    imported, failed, errors = 0, 0, []
    for index, source in enumerate(rows, 2):
        try:
            values = {target: source.get(column, "") for target, column in mapping.items()}
            email = values.get("email", "").strip().lower()
            if not email:
                raise ValueError("Email is required.")
            existing = talent.find_candidate_by_email(email)
            candidate_id = existing["id"] if existing else talent.create_candidate(
                first_name=values.get("first_name", ""), last_name=values.get("last_name", ""),
                email=email, phone=values.get("phone", ""), location=values.get("location", ""),
                source="Import", consent=values.get("consent", "").lower() in {"1", "yes", "true"},
                current_title=values.get("current_title", ""), current_employer=values.get("current_employer", ""),
            )
            if job_id:
                talent.apply_to_job(candidate_id, job_id, actor=actor)
            status, error, imported = "Imported", None, imported + 1
        except Exception as exc:
            candidate_id, status, error, failed = None, "Failed", str(exc), failed + 1
            errors.append({"row": index, "error": error})
        with db.cursor() as conn:
            conn.execute(
                """INSERT INTO candidate_import_rows
                   (import_id,row_number,source_json,candidate_id,status,error) VALUES (?,?,?,?,?,?)""",
                (import_id, index, json.dumps(source), candidate_id, status, error),
            )
    with db.cursor() as conn:
        conn.execute(
            """UPDATE candidate_imports SET status='Completed',imported=?,failed=?,error_report_json=?,
               completed_at=datetime('now') WHERE id=?""", (imported, failed, json.dumps(errors), import_id),
        )
    return db.one("SELECT * FROM candidate_imports WHERE id=?", (import_id,))


def source_candidate(profile: dict, *, actor: str) -> int:
    email = (profile.get("email") or "").strip().lower()
    existing = talent.find_candidate_by_email(email) if email else None
    if existing:
        return existing["id"]
    candidate_id = talent.create_candidate(
        first_name=profile.get("first_name", ""), last_name=profile.get("last_name", ""),
        email=email, phone=profile.get("phone", ""), location=profile.get("location", ""),
        current_title=profile.get("current_title", ""), current_employer=profile.get("current_employer", ""),
        linkedin_url=profile.get("profile_url", ""), source="Sourcing extension",
    )
    from recruiting_ops import add_tag
    for tag in profile.get("tags", []):
        add_tag(candidate_id, tag, actor=actor)
    talent.log_event("candidate", candidate_id, actor=actor, to_state="Sourced", via="browser-extension")
    return candidate_id


def save_service_plan(organization_id: int, *, support_tier: str = "Community",
                      onboarding_status: str = "Not started", account_manager_email: str = "",
                      response_sla_minutes: int | None = None,
                      resolution_sla_minutes: int | None = None, config: dict | None = None) -> int:
    with db.cursor() as conn:
        existing = conn.execute("SELECT id FROM service_plans WHERE organization_id=?", (organization_id,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE service_plans SET support_tier=?,onboarding_status=?,account_manager_email=?,
                   response_sla_minutes=?,resolution_sla_minutes=?,config_json=?,updated=datetime('now') WHERE id=?""",
                (support_tier, onboarding_status, account_manager_email, response_sla_minutes,
                 resolution_sla_minutes, json.dumps(config or {}), existing[0]),
            )
            return existing[0]
        cur = conn.execute(
            """INSERT INTO service_plans
               (organization_id,support_tier,onboarding_status,account_manager_email,
                response_sla_minutes,resolution_sla_minutes,config_json,created,updated)
               VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (organization_id, support_tier, onboarding_status, account_manager_email,
             response_sla_minutes, resolution_sla_minutes, json.dumps(config or {})),
        )
        return cur.lastrowid


def create_support_request(organization_id: int, requester: str, subject: str, *,
                           body: str = "", channel: str = "email", priority: str = "Normal") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO support_requests
               (organization_id,requester_email,channel,priority,subject,body,status,created)
               VALUES (?,?,?,?,?,?,'Open',datetime('now'))""",
            (organization_id, requester.lower(), channel, priority, subject.strip(), body),
        )
        return cur.lastrowid


def update_support_request(request_id: int, status: str, *, assignee: str = "") -> bool:
    if status not in {"Open", "In progress", "Resolved", "Closed"}:
        return False
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE support_requests SET status=?,assigned_to=COALESCE(NULLIF(?,''),assigned_to),
               first_response_at=CASE WHEN ? IN ('In progress','Resolved','Closed')
                 THEN COALESCE(first_response_at,datetime('now')) ELSE first_response_at END,
               resolved_at=CASE WHEN ? IN ('Resolved','Closed') THEN datetime('now') ELSE NULL END
               WHERE id=?""", (status, assignee, status, status, request_id),
        )
    return bool(cur.rowcount)


def sla_report(organization_id: int) -> dict:
    plan = db.one("SELECT * FROM service_plans WHERE organization_id=? ORDER BY id DESC LIMIT 1", (organization_id,)) or {}
    rows = db.rows("SELECT * FROM support_requests WHERE organization_id=?", (organization_id,))
    response_target, resolution_target = plan.get("response_sla_minutes"), plan.get("resolution_sla_minutes")
    response_met = resolution_met = 0
    for row in rows:
        created = datetime.fromisoformat(row["created"])
        if row.get("first_response_at") and response_target is not None:
            response_met += (datetime.fromisoformat(row["first_response_at"]) - created).total_seconds() <= response_target * 60
        if row.get("resolved_at") and resolution_target is not None:
            resolution_met += (datetime.fromisoformat(row["resolved_at"]) - created).total_seconds() <= resolution_target * 60
    return {"requests": len(rows), "open": sum(r["status"] in {"Open", "In progress"} for r in rows),
            "response_sla_met": int(response_met), "resolution_sla_met": int(resolution_met),
            "support_tier": plan.get("support_tier") or "Community",
            "onboarding_status": plan.get("onboarding_status")}
