"""Phase 3 communication, automation, portal, privacy, and survey behavior."""
from __future__ import annotations

import importlib


def _modules():
    import recruitment
    import recruitment_communications
    import recruiting_ops
    import talent
    return (importlib.reload(recruitment), importlib.reload(recruitment_communications),
            importlib.reload(recruiting_ops), importlib.reload(talent))


def _candidate_job(recruitment, talent):
    job_id = recruitment.create_job(
        {"title": "Product Engineer", "description": "Build products.", "requirements": "Python"},
        actor="recruiter@example.com")
    cid = talent.create_candidate(first_name="Ada", last_name="Lovelace",
                                  email="ada@example.com", phone="+3725550100", consent=True)
    app_id = talent.apply_to_job(cid, job_id, actor="recruiter@example.com")
    return job_id, cid, app_id


def test_templates_scheduling_tracking_and_two_way_history(fresh_db):
    recruitment, comms, _, talent = _modules()
    _, cid, app_id = _candidate_job(recruitment, talent)
    mailbox_id = comms.save_mailbox("ms_graph", "jobs@example.com", display_name="Hiring",
                                    signature_html="<p>— Hiring team</p>")
    template_id = comms.save_template("Interview invite", "<p>Hello {{first_name}}</p>",
                                      subject="Next step for {{job_title}}", actor="recruiter@example.com")
    message_id = comms.queue_message(cid, channel="email", application_id=app_id,
                                     template_id=template_id, actor="recruiter@example.com")

    result = comms.dispatch_due()
    message = fresh_db.one("SELECT * FROM communication_messages WHERE id=?", (message_id,))
    assert result == {"processed": 1, "sent": 1, "failed": 0}
    assert message["subject"] == "Next step for Product Engineer"
    assert "Hello Ada" in message["body_html"] and "Hiring team" in message["body_html"]

    comms.record_message_event(message_id, "delivered")
    comms.record_message_event(message_id, "read")
    comms.record_message_event(message_id, "clicked")
    inbound = comms.import_inbound([
        {"provider_message_id": "graph-1", "sender": "ada@example.com",
         "recipient": "jobs@example.com", "subject": "Re: Next step", "body_text": "Thank you"}
    ], mailbox_id=mailbox_id, cursor="next-1")
    assert inbound["imported"] == 1
    assert [m["direction"] for m in comms.communication_history(cid)] == ["outbound", "inbound"]
    assert fresh_db.one("SELECT sync_cursor FROM recruitment_mailboxes WHERE id=?", (mailbox_id,))["sync_cursor"] == "next-1"

    class OutlookAdapter(comms.MailboxAdapter):
        def pull(self, mailbox, cursor):
            assert cursor == "next-1"
            return {"messages": [{"provider_message_id": "graph-2", "sender": "ada@example.com",
                                  "recipient": mailbox["address"], "subject": "Availability",
                                  "body_text": "Tuesday works"}], "cursor": "next-2"}

    synced = comms.sync_mailbox(mailbox_id, adapter=OutlookAdapter())
    assert synced == {"imported": 1, "cursor": "next-2", "mailbox_id": mailbox_id}


def test_ai_drafting_automation_and_bulk_channels(fresh_db):
    recruitment, comms, ops, talent = _modules()
    job_id, cid, app_id = _candidate_job(recruitment, talent)
    assert comms.draft_with_ai("Invite Ada", generator=lambda prompt: "Please join us.") == "Please join us."
    rule_id = comms.save_automation_rule(
        "Screen follow-up", "application.stage_changed",
        [{"type": "tag", "tag": "Screened"},
         {"type": "task", "title": "Call candidate", "assignee": "manager@example.com"},
         {"type": "email", "subject": "Update", "body": "Hello {{first_name}}"}],
        conditions={"stage": "Screen"}, actor="recruiter@example.com")

    runs = comms.emit_event("application.stage_changed",
                            {"entity_type": "application", "entity_id": app_id,
                             "application_id": app_id, "candidate_id": cid,
                             "job_id": job_id, "stage": "Screen"}, actor="recruiter@example.com")
    assert runs[0]["rule_id"] == rule_id and runs[0]["status"] == "Completed"
    assert ops.tags_for(cid)[0]["name"] == "Screened"
    assert ops.tasks(assignee="manager@example.com")[0]["title"] == "Call candidate"
    assert fresh_db.scalar("SELECT COUNT(*) FROM communication_messages WHERE candidate_id=?", (cid,)) == 1

    bulk = ops.run_bulk_action("sms", [cid], payload={"body": "Your interview is tomorrow."},
                               actor="recruiter@example.com")
    assert bulk["succeeded"] == 1


def test_candidate_portal_requests_withdrawal_and_magic_link(fresh_db):
    recruitment, comms, _, talent = _modules()
    _, cid, app_id = _candidate_job(recruitment, talent)
    request_id = comms.create_candidate_request(
        cid, "information", "Confirm availability", application_id=app_id,
        fields=[{"key": "availability", "type": "date"}], actor="recruiter@example.com")
    token = comms.issue_portal_token(cid, actor="recruiter@example.com")

    assert comms.authenticate_portal(token) == cid
    snapshot = comms.portal_snapshot(cid)
    assert snapshot["requests"][0]["id"] == request_id
    assert comms.respond_candidate_request(request_id, cid, {"availability": "2026-09-01"})
    assert comms.withdraw_application(app_id, cid)
    assert fresh_db.one("SELECT status FROM applications WHERE id=?", (app_id,))["status"] == "Withdrawn"


def test_consent_export_anonymize_retention_and_deletion(fresh_db):
    recruitment, comms, _, talent = _modules()
    _, cid, _ = _candidate_job(recruitment, talent)
    consent_id = comms.renew_consent(cid, purpose="Talent pool", proof={"ip": "127.0.0.1"})
    assert consent_id and comms.withdraw_consent(cid) == 1

    export_id = comms.create_privacy_request(cid, "Export")
    export = comms.process_privacy_request(export_id, actor="privacy@example.com")
    assert export["export"]["candidate"]["email"] == "ada@example.com"

    anonymize_id = comms.create_privacy_request(cid, "Anonymize")
    comms.process_privacy_request(anonymize_id, actor="privacy@example.com")
    assert talent.candidate(cid)["first_name"] == "Anonymized"

    other = talent.create_candidate(first_name="Delete", last_name="Me", email="delete@example.com")
    delete_id = comms.create_privacy_request(other, "Delete")
    comms.process_privacy_request(delete_id, actor="privacy@example.com")
    assert talent.candidate(other) is None

    retained = talent.create_candidate(first_name="Old", last_name="Consent", email="old@example.com")
    with fresh_db.cursor() as conn:
        conn.execute("""INSERT INTO candidate_consents
                        (candidate_id,purpose,lawful_basis,consented_at,expires_at)
                        VALUES (?,'Talent pool','consent','2020-01-01','2020-02-01')""", (retained,))
    assert comms.run_retention()["anonymized"] == 1
    assert talent.candidate(retained)["status"] == "Archived"


def test_candidate_and_hiring_manager_surveys_report_cnps(fresh_db):
    recruitment, comms, _, talent = _modules()
    _, cid, _ = _candidate_job(recruitment, talent)
    survey_id = comms.save_survey(
        "Candidate experience", "candidate", [{"key": "recommend", "type": "nps"}],
        trigger_event="application.closed", actor="admin@example.com")
    promoter = comms.invite_survey(survey_id, candidate_id=cid)
    detractor = comms.invite_survey(survey_id, recipient_email="manager@example.com")
    assert comms.submit_survey(promoter, {"recommend": 10}, score=10)
    assert comms.submit_survey(detractor, {"recommend": 4}, score=4)
    assert comms.survey_metrics(survey_id) == {"responses": 2, "average": 7.0, "cnps": 0}


def test_survey_trigger_invites_once_and_queues_message(fresh_db):
    recruitment, comms, _, talent = _modules()
    job_id, cid, app_id = _candidate_job(recruitment, talent)
    survey_id = comms.save_survey(
        "Application feedback", "candidate", [{"key": "recommend", "type": "nps"}],
        trigger_event="application.closed", actor="admin@example.com")
    event = {"entity_type": "application", "entity_id": app_id,
             "application_id": app_id, "candidate_id": cid, "job_id": job_id}

    first = comms.emit_event("application.closed", event)
    second = comms.emit_event("application.closed", event)

    assert first[0]["survey_id"] == survey_id and first[0]["message_id"]
    assert second == []
    assert fresh_db.scalar(
        "SELECT COUNT(*) FROM survey_invitations WHERE survey_id=? AND candidate_id=?",
        (survey_id, cid)) == 1
