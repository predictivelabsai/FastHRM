"""Phase 4 scheduling, connectors, marketing, webhooks, and analytics."""
from __future__ import annotations

import importlib
from pathlib import Path


def _modules():
    import recruitment
    import recruitment_ecosystem
    import talent
    return importlib.reload(recruitment), importlib.reload(recruitment_ecosystem), importlib.reload(talent)


def _published_job(recruitment):
    job_id = recruitment.create_job(
        {"title": "Platform Engineer", "description": "Build reliable systems.",
         "requirements": "Python", "location": "Tallinn", "employment_type": "Permanent"},
        actor="recruiter@example.com")
    return job_id, recruitment.transition(job_id, "Published", actor="recruiter@example.com")


def _application(recruitment, talent):
    job_id, _ = _published_job(recruitment)
    cid = talent.create_candidate(first_name="Ada", last_name="Lovelace",
                                  email="ada@example.com", phone="+3725550100")
    return job_id, cid, talent.apply_to_job(cid, job_id)


def test_self_service_scheduling_calendar_links_and_cancellation(fresh_db):
    recruitment, eco, talent = _modules()
    _, _, app_id = _application(recruitment, talent)
    eco.save_availability("interviewer@example.com", 0, "09:00", "11:00", timezone="UTC")
    token = eco.create_scheduling_link(
        app_id, ["interviewer@example.com"], window_start="2026-08-10T00:00:00",
        window_end="2026-08-10T23:59:00", timezone="UTC", duration_minutes=30,
        provider="ms_graph", actor="recruiter@example.com")
    slots = eco.available_slots(token)

    assert len(slots) == 4
    booking = eco.book_slot(token, slots[0]["starts_at"])
    assert booking["status"] == "Booked"
    assert booking["meeting_url"].startswith("https://teams.microsoft.com/")
    assert eco.available_slots(token) == []
    assert eco.cancel_booking(booking["id"], actor="ada@example.com")
    live = eco.CalendarAdapter().create_event({"id": 99}, ["ada@example.com"], "fasthr")
    assert live["meeting_url"].startswith("https://meet.jit.si/FastHRM-")


def test_connector_contract_job_board_posting_import_and_sync(fresh_db):
    recruitment, eco, talent = _modules()
    job_id, _ = _published_job(recruitment)
    connector_id = eco.register_connector("indeed", "job_board", config={"region": "EU"})

    class PullAdapter(eco.ConnectorAdapter):
        def pull(self, connector, cursor):
            return {"events": [{"type": "application", "external_id": "a-1"}], "cursor": "page-2"}

    sync = eco.sync_connector(connector_id, adapter=PullAdapter())
    posts = eco.publish_to_job_boards(job_id, ["indeed", "linkedin"])
    imported = eco.import_job_board_applicant(
        "indeed", posts[0]["external_id"],
        {"external_id": "candidate-1", "first_name": "Grace", "last_name": "Hopper",
         "email": "grace@example.com", "consent": True})

    assert sync == {"processed": 1, "cursor": "page-2"}
    assert all(post["status"] == "Posted" for post in posts)
    assert talent.candidate(imported["candidate_id"])["source"] == "Job Board"
    assert eco.close_job_board_posts(job_id) == 2
    assert any(c["provider"] == "indeed" and "publish_job" in c["capabilities"]
               for c in eco.connector_contracts())


def test_signed_webhook_queue_delivery_and_retry_audit(fresh_db):
    _, eco, _ = _modules()
    created = eco.create_webhook_subscription(
        "ATS updates", "https://client.example/hooks", ["application.created"],
        actor="admin@example.com")
    assert created["secret"]
    assert eco.enqueue_webhook("application.created", {"application_id": 7}) == 1

    class Adapter:
        def __init__(self): self.headers = None
        def post(self, url, body, headers):
            self.headers = headers
            return {"status_code": 202, "body": "accepted"}

    adapter = Adapter()
    result = eco.deliver_webhooks(adapter=adapter)
    assert result == {"processed": 1, "delivered": 1, "failed": 0}
    assert len(adapter.headers["x-fasthr-signature"]) == 64


def test_marketing_assets_templates_campaigns_ai_and_jpg(fresh_db, tmp_path):
    recruitment, eco, _ = _modules()
    job_id, _ = _published_job(recruitment)
    template_id = eco.save_page_template(
        "Engineering", [{"type": "hero", "fields": ["headline", "image"]}],
        styles={"font": "Inter"}, actor="designer@example.com")
    asset_id = eco.store_marketing_asset(
        "Team", "image", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        file_name="team.svg", alt_text="Engineering team", actor="designer@example.com")
    assert template_id and asset_id

    findings = eco.inclusive_language_review("We need a young and energetic coding ninja.")
    assert {f["term"] for f in findings} == {"young and energetic", "ninja"}
    draft = eco.draft_job_ad("Rewrite", job={"title": "Engineer"},
                             generator=lambda prompt: "A coding ninja joins our workforce.")
    assert "ninja" not in draft.lower() and "specialist" in draft.lower()

    campaign_id = eco.save_campaign(
        "Engineering careers", job_id=job_id, landing_slug="engineering-careers",
        content={"headline": "Build dependable software", "background": "#ecfeff",
                 "template_id": template_id, "asset_id": asset_id, "font_family": "Atkinson Hyperlegible"},
        actor="designer@example.com")
    eco.publish_campaign(campaign_id, ["linkedin", "website"])
    saved_campaign = eco.campaign("engineering-careers")
    assert saved_campaign["content"]["headline"] == "Build dependable software"
    assert saved_campaign["job_url"] == "/jobs/platform-engineer"
    assert saved_campaign["template"]["sections"][0]["type"] == "hero"
    assert saved_campaign["asset"]["alt_text"] == "Engineering team"
    jpg = eco.render_campaign_jpg(campaign_id, tmp_path / "campaign.jpg")
    assert jpg.exists() and jpg.read_bytes().startswith(b"\xff\xd8")


def test_attribution_experiments_custom_dashboards_and_exports(fresh_db):
    recruitment, eco, _ = _modules()
    job_id, _ = _published_job(recruitment)
    eco.track_event("job_view", session_id="s1", job_id=job_id, source="linkedin", medium="social")
    eco.track_event("job_view", session_id="s2", job_id=job_id, source="linkedin", medium="social")
    eco.track_event("application_submitted", session_id="s1", job_id=job_id,
                    source="linkedin", medium="social")
    summary = eco.analytics_summary(job_id=job_id, source="linkedin")
    assert summary["views"] == 2 and summary["applications"] == 1
    assert summary["conversion_rate"] == 50.0

    experiment_id = eco.create_experiment(
        "Headline", [{"key": "a", "headline": "Build"}, {"key": "b", "headline": "Grow"}], job_id=job_id)
    assigned = eco.assign_experiment(experiment_id, "visitor-1")
    assert assigned == eco.assign_experiment(experiment_id, "visitor-1")
    eco.track_event("experiment_exposure", session_id="visitor-1", job_id=job_id,
                    metadata={"experiment_id": experiment_id, "variant": assigned["key"]})
    eco.track_event("application_submitted", session_id="visitor-1", job_id=job_id,
                    metadata={"experiment_id": experiment_id, "variant": assigned["key"]})
    assert eco.experiment_report(experiment_id)["variants"][assigned["key"]]["conversion_rate"] == 100.0
    dashboard_id = eco.save_dashboard(
        "recruiter@example.com", "Hiring overview", "team",
        [{"type": "funnel"}, {"type": "sources"}], filters={"job_id": job_id}, shared=True)
    assert dashboard_id
    export = eco.export_analytics_csv(job_id=job_id)
    assert "event_type,occurred_at" in export and "application_submitted" in export
