"""Phase 5 brands, identity, AI, video, imports, and service operations."""
from __future__ import annotations

import importlib


def _modules():
    import recruitment
    import recruitment_enterprise
    import recruiting_ops
    import talent
    return (importlib.reload(recruitment), importlib.reload(recruitment_enterprise),
            importlib.reload(recruiting_ops), importlib.reload(talent))


def _application(recruitment, talent):
    job_id = recruitment.create_job(
        {"title": "Python Engineer", "description": "Build Python services.",
         "requirements": "Python and distributed systems"}, actor="recruiter@example.com")
    recruitment.transition(job_id, "Published", actor="recruiter@example.com")
    cid = talent.create_candidate(first_name="Ada", last_name="Lovelace",
                                  email="ada@example.com", location="Tallinn",
                                  current_title="Python Engineer")
    app_id = talent.apply_to_job(cid, job_id)
    return job_id, cid, app_id


def test_multi_brand_sites_teams_domains_locales_and_group_reporting(fresh_db):
    recruitment, ent, _, talent = _modules()
    org = ent.ensure_organization("Acme Group", slug="acme", default_locale="en")
    brand_id = ent.create_brand(org["id"], "Acme Labs", "labs", custom_domain="jobs.acme.test",
                                favicon_url="https://assets.acme.test/favicon.ico")
    second_brand = ent.create_brand(org["id"], "Acme Retail", "retail")
    site_id = ent.create_career_site(brand_id, "Acme Labs Careers", "labs-careers", locale="en")
    ent.create_career_site(second_brand, "Acme Retail Careers", "retail-careers", locale="de")
    team_id = ent.create_team(org["id"], "Estonia Engineering", country="EE")
    ent.add_member(org["id"], "recruiter@acme.test", "recruiter", team_id=team_id,
                   scopes={"country": "EE"})
    job_id, _, _ = _application(recruitment, talent)
    distribution_id = ent.distribute_job(job_id, site_id, brand_id=brand_id, locale="et",
                                         slug="pythoni-insener")
    translated = ent.translate_content(
        "job_posting", recruitment.posting_for_job(job_id)["id"], "et",
        {"public_title": "Python Engineer"}, actor="translator@acme.test",
        translator=lambda text, locale: "Pythoni insener")

    assert distribution_id and translated["public_title"] == "Pythoni insener"
    assert ent.resolve_brand(host="jobs.acme.test")["id"] == brand_id
    assert ent.public_distributed_job("labs-careers", "et", "pythoni-insener")["favicon_url"] == "https://assets.acme.test/favicon.ico"
    assert ent.localized_values("job_posting", recruitment.posting_for_job(job_id)["id"], "et", {})["public_title"] == "Pythoni insener"
    summary = ent.enterprise_summary(org["id"])
    assert summary["brands"] == 2 and summary["teams"] == 1 and summary["published_jobs"] == 1


def test_saml_scim_policy_and_legal_controls(fresh_db):
    _, ent, _, _ = _modules()
    org = ent.ensure_organization("Acme", slug="acme")
    ent.add_member(org["id"], "ada@acme.test", "recruiter", scopes={"country": "EE"})
    provider_id = ent.save_identity_provider(
        org["id"], "SAML", "Acme Identity", entity_id="urn:acme:idp",
        sso_url="https://idp.acme.test/sso", certificate_pem="TEST CERT")
    assert "SAMLRequest=" in ent.saml_login_url(provider_id, acs_url="https://hr.acme.test/sso/acs")

    class Verifier:
        def verify(self, provider, response):
            return {"verified": True, "email": "ada@acme.test", "name": "Ada"}

    identity = ent.consume_sso_response(provider_id, "signed-response", verifier=Verifier())
    assert identity["role"] == "recruiter"

    raw = ent.issue_scim_token(org["id"], "Okta", actor="admin@acme.test")
    assert ent.authenticate_scim(raw) == org["id"]
    user = ent.scim_upsert_user(org["id"], "okta-7", "grace@acme.test", role="hrbp")
    assert user["active"] and ent.scim_deactivate_user(org["id"], "grace@acme.test")

    ent.save_access_policy(org["id"], "EE recruiters", ["candidate"], ["read"],
                           roles=["recruiter"], conditions={"country": "EE"})
    ent.save_access_policy(org["id"], "No salary", ["salary"], ["read"],
                           roles=["recruiter"], effect="deny")
    assert ent.policy_allows(org["id"], role="recruiter", resource="candidate", action="read",
                             context={"country": "EE"})
    assert not ent.policy_allows(org["id"], role="recruiter", resource="salary", action="read")

    document_id = ent.save_legal_document(org["id"], "DPA", "2026-08", content="Data terms",
                                          effective_at="2026-08-08")
    assert ent.accept_legal_document(document_id, "admin@acme.test")


def test_weighted_required_anonymized_ai_screening_and_override(fresh_db):
    recruitment, ent, ops, talent = _modules()
    job_id, cid, app_id = _application(recruitment, talent)
    profile_id = ent.save_screening_profile(
        job_id, [{"name": "Python", "weight": 2, "required": True},
                 {"name": "Communication", "weight": 1, "required": False}],
        threshold=60, anonymize=True, auto_stage="Screen", require_manual_review=False,
        actor="recruiter@example.com")
    seen = {}

    def evaluator(data, criteria):
        seen.update(data)
        return [{"name": "Python", "score": 90, "evidence": "Current title"},
                {"name": "Communication", "score": 60, "evidence": "Profile"}]

    result = ent.evaluate_application(app_id, evaluator=evaluator)
    assert result["profile_id"] == profile_id and result["total_score"] == 80
    assert "email" not in seen and "first_name" not in seen
    assert fresh_db.one("SELECT stage FROM applications WHERE id=?", (app_id,))["stage"] == "Screen"
    assert ops.tags_for(cid)[0]["name"] == "AI screened"
    assert ent.override_screening(result["id"], 75, "Human evidence", reviewer="manager@example.com")


def test_async_video_transcription_and_video_messages(fresh_db):
    recruitment, ent, _, talent = _modules()
    _, cid, app_id = _application(recruitment, talent)
    template_id = ent.save_video_template(
        "Engineering intro", [{"question": "Why this role?", "seconds": 120}],
        actor="recruiter@example.com")
    token = ent.invite_video_interview(template_id, app_id)
    transcriber = lambda url: {"transcript": "I enjoy platform work.", "summary": "Platform motivation"}
    response_id = ent.submit_video_response(token, 0, "https://media.example/answer.webm",
                                            duration_seconds=42, transcriber=transcriber)
    assert response_id and ent.complete_video_interview(token)
    message_id = ent.add_video_message(cid, "https://media.example/welcome.mp4",
                                       direction="outbound", application_id=app_id,
                                       sender="recruiter@example.com", transcriber=transcriber)
    assert fresh_db.one("SELECT * FROM video_messages WHERE id=?", (message_id,))["summary_text"] == "Platform motivation"


def test_candidate_import_sourcing_extension_and_sla_operations(fresh_db):
    recruitment, ent, ops, talent = _modules()
    job_id = recruitment.create_job(
        {"title": "Data Engineer", "description": "Build data systems.", "requirements": "SQL"},
        actor="recruiter@example.com")
    csv_text = "First,Last,Email,Location\nGrace,Hopper,grace@example.com,New York\nBad,Row,,London\n"
    imported = ent.import_candidates(
        "candidates.csv", csv_text,
        {"first_name": "First", "last_name": "Last", "email": "Email", "location": "Location"},
        actor="admin@example.com", job_id=job_id)
    assert imported["total"] == 2 and imported["imported"] == 1 and imported["failed"] == 1

    sourced = ent.source_candidate(
        {"first_name": "Margaret", "last_name": "Hamilton", "email": "margaret@example.com",
         "profile_url": "https://network.example/margaret", "tags": ["Apollo"]},
        actor="sourcer@example.com")
    assert talent.candidate(sourced)["source"] == "Sourcing extension"
    assert ops.tags_for(sourced)[0]["name"] == "Apollo"

    org = ent.ensure_organization("Support Org", slug="support-org")
    ent.save_service_plan(org["id"], support_tier="Enterprise", onboarding_status="In progress",
                          account_manager_email="csm@example.com", response_sla_minutes=60,
                          resolution_sla_minutes=240)
    request_id = ent.create_support_request(org["id"], "admin@example.com", "Import assistance",
                                            channel="live_chat", priority="High")
    assert ent.update_support_request(request_id, "In progress", assignee="csm@example.com")
    assert ent.update_support_request(request_id, "Resolved")
    report = ent.sla_report(org["id"])
    assert report["support_tier"] == "Enterprise" and report["response_sla_met"] == 1
