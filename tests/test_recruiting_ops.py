"""Phase 2 recruiter operating-system behavior."""
from __future__ import annotations

import importlib


def _modules():
    import recruitment
    import recruiting_ops
    import talent
    return importlib.reload(recruitment), importlib.reload(recruiting_ops), importlib.reload(talent)


def _job(recruitment, title="Platform Engineer"):
    return recruitment.create_job(
        {"title": title, "description": "Build the platform.",
         "requirements": "Python", "headcount": "1"}, actor="recruiter@example.com")


def test_pipeline_templates_projects_cloning_and_access(fresh_db):
    recruitment, ops, _ = _modules()
    template_id = ops.save_pipeline_template(
        "Executive", [{"name": "Applied"}, {"name": "Panel"}, {"name": "Decision"}],
        actor="admin@example.com")
    job_id = _job(recruitment)
    configured = ops.configure_project(job_id, category="Leadership", continuous=True,
                                       confidential=True, template_id=template_id,
                                       custom_fields={"cost_center": "ENG"}, actor="admin@example.com")
    ops.add_project_member(job_id, "manager@example.com", can_decide=True)

    assert configured["stages"] == ["Applied", "Panel", "Decision"]
    assert configured["continuous"] == 1 and configured["confidential"] == 1
    assert ops.can_access_project(job_id, "manager@example.com", decision=True)
    assert not ops.can_access_project(job_id, "stranger@example.com")

    clone_id = ops.clone_project(job_id, actor="admin@example.com")
    clone = ops.project(clone_id)
    assert clone["category"] == "Leadership"
    assert clone["stages"] == configured["stages"]


def test_talent_crm_search_comments_fields_tasks_and_bulk_actions(fresh_db):
    recruitment, ops, talent = _modules()
    job_id = _job(recruitment)
    cid = talent.create_candidate(first_name="Ada", last_name="Lovelace",
                                  email="ada@example.com", source="Referral",
                                  location="Tallinn")
    app_id = talent.apply_to_job(cid, job_id, actor="recruiter@example.com")
    ops.add_tag(cid, "Python", actor="recruiter@example.com")
    ops.add_comment(cid, "Excellent systems thinking", author="recruiter@example.com",
                    application_id=app_id, rating=4.5, pinned=True)
    ops.define_candidate_field("notice period", "Notice period")
    ops.set_candidate_field(cid, "notice_period", "30 days", actor="recruiter@example.com")
    ops.save_view("recruiter@example.com", "Estonia Python", {"location": "Tallinn", "tag": "Python"})

    found = ops.search_candidates("30 days", tag="Python", location="Tallinn")
    assert [row["id"] for row in found] == [cid]
    assert ops.comments_for(cid)[0]["pinned"] == 1
    assert ops.candidate_fields(cid)[0]["value_text"] == "30 days"

    result = ops.run_bulk_action("task", [cid], payload={"title": "Call candidate",
                                                         "assignee": "manager@example.com"},
                                 actor="recruiter@example.com")
    assert result["succeeded"] == 1
    task = ops.tasks(assignee="manager@example.com")[0]
    assert ops.set_task_status(task["id"], "Done", actor="manager@example.com")

    assert ops.move_application(app_id, "Rejected", actor="recruiter@example.com",
                                drop_reason="Experience", drop_detail="Needs more depth")
    assert fresh_db.one("SELECT * FROM application_drop_reasons")["reason"] == "Experience"

    # Restore the application for a bulk self-scheduling invitation.
    assert ops.move_application(app_id, "Applied", actor="recruiter@example.com")
    invited = ops.run_bulk_action(
        "interview", [cid],
        payload={"interviewer_emails": ["manager@example.com"],
                 "window_start": "2026-08-10T08:00:00", "window_end": "2026-08-10T18:00:00",
                 "timezone": "UTC", "provider": "fasthr"}, actor="recruiter@example.com")
    assert invited["succeeded"] == 1
    assert "/schedule/" in fresh_db.one(
        "SELECT body_text FROM communication_messages WHERE candidate_id=? ORDER BY id DESC", (cid,))["body_text"]


def test_candidate_merge_preserves_history_and_deduplicates_applications(fresh_db):
    recruitment, ops, talent = _modules()
    job_id = _job(recruitment)
    survivor = talent.create_candidate(first_name="Grace", last_name="Hopper", email="grace@example.com")
    duplicate = talent.create_candidate(first_name="G", last_name="Hopper", email="g@example.com")
    talent.apply_to_job(survivor, job_id)
    talent.apply_to_job(duplicate, job_id)
    ops.add_tag(duplicate, "Compiler")
    ops.add_comment(duplicate, "Imported duplicate", author="system")

    result = ops.merge_candidates(survivor, duplicate, actor="admin@example.com")

    assert result["ok"]
    assert fresh_db.scalar("SELECT COUNT(*) FROM applications WHERE candidate_id=?", (survivor,)) == 1
    assert ops.tags_for(survivor)[0]["name"] == "Compiler"
    assert ops.comments_for(survivor)[0]["body"] == "Imported duplicate"
    assert talent.candidate(duplicate)["status"] == "Archived"


def test_scorecards_approvals_references_and_credentials(fresh_db):
    recruitment, ops, talent = _modules()
    job_id = _job(recruitment)
    cid = talent.create_candidate(first_name="Linus", last_name="Torvalds", email="linus@example.com")
    app_id = talent.apply_to_job(cid, job_id)

    template_id = ops.save_scorecard_template(
        "Engineering panel", [{"label": "System design", "weight": 2, "required": True}],
        actor="recruiter@example.com")
    assert fresh_db.scalar("SELECT COUNT(*) FROM scorecard_template_items WHERE template_id=?", (template_id,)) == 1

    approvals = ops.request_approval("job_opening", job_id, ["manager@example.com"], actor="recruiter@example.com")
    assert ops.decide_approval(approvals[0], "Approved", actor="manager@example.com", note="Proceed")

    token = ops.request_reference(cid, "Kernel Maintainer", "ref@example.com",
                                  application_id=app_id, actor="recruiter@example.com")
    assert ops.complete_reference(token, {"recommend": True, "comment": "Strong"})

    credential_id = ops.add_credential(cid, "Security clearance", expires_on="2000-01-01")
    assert ops.refresh_credential_statuses() == 1
    assert fresh_db.one("SELECT status FROM candidate_credentials WHERE id=?", (credential_id,))["status"] == "Expired"


def test_custom_conditional_forms_internal_jobs_and_scheduled_publication(fresh_db):
    recruitment, ops, talent = _modules()
    job_id = _job(recruitment)
    form_id = ops.save_application_form(
        "Engineering application",
        [{"key": "work_authorization", "label": "Authorized to work?", "type": "select",
          "options": ["Yes", "No"], "required": True},
         {"key": "visa_details", "label": "Visa details", "type": "textarea", "required": True,
          "condition": {"field": "work_authorization", "equals": "No"}}],
        actor="recruiter@example.com")
    ops.attach_application_form(job_id, form_id)
    valid, error, answers = ops.validate_application_form(job_id, {"work_authorization": "Yes"})
    assert valid and not error and answers[0]["field_key"] == "work_authorization"
    valid, error, _ = ops.validate_application_form(job_id, {"work_authorization": "No"})
    assert not valid and "Visa details" in error

    posting = recruitment.transition(job_id, "Published", actor="recruiter@example.com")
    result = recruitment.apply(posting["slug"], {
        "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com",
        "consent": "yes", "work_authorization": "Yes"})
    assert result["ok"]
    assert fresh_db.one("SELECT value_text FROM application_answers WHERE field_key='work_authorization'")["value_text"] == "Yes"

    internal_id = ops.publish_internal_job(job_id, ["all"], actor="recruiter@example.com")
    assert internal_id and ops.internal_jobs()[0]["job_id"] == job_id
    recruitment.schedule_transition(job_id, "Closed", "2000-01-01 00:00:00", actor="recruiter@example.com")
    processed = recruitment.process_publication_schedules()
    assert processed == {"processed": 1, "completed": 1, "failed": 0}
    assert recruitment.public_job(posting["slug"]) is None


def test_automatic_talent_pool_and_targeted_job_offer(fresh_db):
    recruitment, ops, talent = _modules()
    job_id = _job(recruitment, "Staff Engineer")
    recruitment.transition(job_id, "Published", actor="recruiter@example.com")
    match = talent.create_candidate(first_name="Grace", last_name="Hopper",
                                    email="grace@example.com", location="Tallinn")
    talent.create_candidate(first_name="Alan", last_name="Turing",
                            email="alan@example.com", location="London")

    pool_id = ops.save_candidate_pool(
        "Tallinn engineers", {"location": "Tallinn"}, owner="recruiter@example.com")
    assert ops.candidate_pools()[0]["member_count"] == 1
    result = ops.send_pool_job_offer(pool_id, job_id, actor="recruiter@example.com")

    assert result["succeeded"] == 1 and result["failed"] == 0
    message = fresh_db.one("SELECT * FROM communication_messages WHERE candidate_id=?", (match,))
    assert "Staff Engineer" in message["body_text"]
