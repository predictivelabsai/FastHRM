"""Recruiter publishing, public discovery, applications, and consent."""
from __future__ import annotations

import importlib

import pytest


def _service():
    import recruitment
    return importlib.reload(recruitment)


def _complete_job(recruitment, title="Platform Engineer"):
    return recruitment.create_job(
        {
            "title": title,
            "public_title": title,
            "summary": "Help build a dependable people platform.",
            "description": "Design and deliver reliable product capabilities.",
            "requirements": "Professional Python experience.",
            "location": "Tallinn",
            "remote_policy": "Hybrid",
            "employment_type": "Permanent",
            "headcount": "1",
        },
        actor="recruiter@example.com",
    )


def test_draft_can_be_edited_previewed_and_published(fresh_db):
    recruitment = _service()
    job_id = _complete_job(recruitment)
    posting = recruitment.posting_for_job(job_id)

    assert posting["publication_status"] == "Draft"
    assert recruitment.public_job(posting["slug"]) is None
    assert recruitment.public_job(posting["slug"], include_unpublished=True)

    recruitment.save_job(
        job_id,
        {**posting, "title": posting["title"], "headcount": "2",
         "summary": "A revised public summary."},
        actor="recruiter@example.com",
    )
    published = recruitment.transition(job_id, "Published", actor="recruiter@example.com")

    assert published["publication_status"] == "Published"
    assert published["job_status"] == "Open"
    assert recruitment.public_job(published["slug"])["summary"] == "A revised public summary."
    assert [v["version"] for v in recruitment.versions(job_id)] == [3, 2, 1]


def test_publish_requires_candidate_facing_copy(fresh_db):
    recruitment = _service()
    job_id = recruitment.create_job({"title": "Unfinished role"}, actor="recruiter@example.com")

    with pytest.raises(ValueError, match="description"):
        recruitment.transition(job_id, "Published", actor="recruiter@example.com")


def test_create_preserves_distinct_public_title(fresh_db):
    recruitment = _service()
    job_id = recruitment.create_job(
        {"title": "Internal P4 Engineer", "public_title": "Platform Engineer",
         "description": "Build products.", "requirements": "Python"},
        actor="recruiter@example.com")

    assert recruitment.posting_for_job(job_id)["public_title"] == "Platform Engineer"


def test_public_application_is_idempotent_and_records_consent(fresh_db):
    recruitment = _service()
    job_id = _complete_job(recruitment)
    posting = recruitment.transition(job_id, "Published", actor="recruiter@example.com")
    values = {
        "first_name": "Ada", "last_name": "Lovelace", "email": "ADA@example.com",
        "phone": "+372 555 0100", "location": "Tallinn", "consent": "yes",
        "cover_note": "I enjoy dependable systems.",
    }

    first = recruitment.apply(posting["slug"], values, proof={"ip": "127.0.0.1"})
    second = recruitment.apply(posting["slug"], values, proof={"ip": "127.0.0.1"})

    assert first["ok"] and second["ok"]
    assert first["application_id"] == second["application_id"]
    assert fresh_db.scalar("SELECT COUNT(*) FROM candidates") == 1
    assert fresh_db.scalar("SELECT COUNT(*) FROM applications") == 1
    assert fresh_db.scalar("SELECT COUNT(*) FROM candidate_consents") == 2
    answer = fresh_db.one("SELECT * FROM application_answers")
    assert answer["value_text"] == values["cover_note"]


def test_slugs_are_unique_and_closing_removes_public_page(fresh_db):
    recruitment = _service()
    first_id = _complete_job(recruitment, "Data & Insights")
    second_id = _complete_job(recruitment, "Data & Insights")
    first = recruitment.transition(first_id, "Published", actor="recruiter@example.com")
    second = recruitment.posting_for_job(second_id)

    assert first["slug"] == "data-insights"
    assert second["slug"] == "data-insights-2"

    recruitment.transition(first_id, "Closed", actor="recruiter@example.com")
    assert recruitment.public_job(first["slug"]) is None


def test_career_site_rejects_invalid_colours(fresh_db):
    recruitment = _service()
    original = recruitment.career_site()
    saved = recruitment.save_career_site(
        {"name": "Acme Careers", "brand_color": "red", "accent_color": "#123456"},
        actor="admin@example.com",
    )

    assert saved["name"] == "Acme Careers"
    assert saved["brand_color"] == original["brand_color"]
    assert saved["accent_color"] == "#123456"
