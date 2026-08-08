"""Phase 3 recruitment communications, automation, candidate portal, and privacy."""
from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import db
import talent


CHANNELS = {"email", "sms"}
MESSAGE_EVENTS = {"sent", "delivered", "read", "clicked", "bounced", "failed", "received"}


def _iso_after(*, hours: int = 0, days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours, days=days)).strftime("%Y-%m-%d %H:%M:%S")


def save_mailbox(provider: str, address: str, *, display_name: str = "",
                 signature_html: str = "", config: dict | None = None) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO recruitment_mailboxes
               (provider,address,display_name,signature_html,status,config_json,created,updated)
               VALUES (?,?,?,?,'Active',?,datetime('now'),datetime('now'))
               ON CONFLICT(address) DO UPDATE SET provider=excluded.provider,
               display_name=excluded.display_name,signature_html=excluded.signature_html,
               config_json=excluded.config_json,status='Active',updated=excluded.updated""",
            (provider, address.strip().lower(), display_name.strip(), signature_html,
             json.dumps(config or {})),
        )
        return conn.execute("SELECT id FROM recruitment_mailboxes WHERE address=?",
                            (address.strip().lower(),)).fetchone()[0]


def save_template(name: str, body_html: str, *, subject: str = "", body_text: str = "",
                  channel: str = "email", locale: str = "en", actor: str = "system") -> int:
    if channel not in CHANNELS:
        raise ValueError("Channel must be email or sms.")
    if not name.strip() or not body_html.strip():
        raise ValueError("Template name and content are required.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO message_templates
               (name,channel,subject,body_html,body_text,locale,created_by,created,updated)
               VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))
               ON CONFLICT(name) DO UPDATE SET channel=excluded.channel,subject=excluded.subject,
               body_html=excluded.body_html,body_text=excluded.body_text,locale=excluded.locale,
               updated=excluded.updated""",
            (name.strip(), channel, subject, body_html, body_text, locale, actor),
        )
        return conn.execute("SELECT id FROM message_templates WHERE name=?", (name.strip(),)).fetchone()[0]


def _render(text: str, context: dict) -> str:
    def replace(match):
        return html.escape(str(context.get(match.group(1), "")))
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace, text or "")


def candidate_context(candidate_id: int, application_id: int | None = None) -> dict:
    c = talent.candidate(candidate_id) or {}
    context = {**c, "candidate_name": talent.display_name(c), "first_name": c.get("first_name") or ""}
    if application_id:
        app = db.one(
            """SELECT a.*,j.title job_title,j.code job_code FROM applications a
               JOIN job_openings j ON j.id=a.job_id WHERE a.id=? AND a.candidate_id=?""",
            (application_id, candidate_id),
        ) or {}
        context.update(app)
    return context


def queue_message(candidate_id: int, *, channel: str, subject: str = "", body: str = "",
                  application_id: int | None = None, template_id: int | None = None,
                  scheduled_at: str | None = None, sender: str = "", actor: str = "system") -> int:
    if channel not in CHANNELS:
        raise ValueError("Channel must be email or sms.")
    candidate = talent.candidate(candidate_id)
    if not candidate:
        raise ValueError("Candidate not found.")
    recipient = candidate.get("email") if channel == "email" else candidate.get("phone")
    if not recipient:
        raise ValueError(f"Candidate has no {channel} destination.")
    template = db.one("SELECT * FROM message_templates WHERE id=?", (template_id,)) if template_id else None
    context = candidate_context(candidate_id, application_id)
    rendered_subject = _render(template["subject"], context) if template else _render(subject, context)
    rendered_html = _render(template["body_html"], context) if template else _render(body, context)
    rendered_text = _render(template["body_text"], context) if template and template.get("body_text") else re.sub("<[^>]+>", "", rendered_html)
    mailbox = db.one("SELECT * FROM recruitment_mailboxes WHERE status='Active' ORDER BY id LIMIT 1")
    sender = sender or ((mailbox or {}).get("address") if channel == "email" else "FastHRM") or actor
    if channel == "email" and mailbox and mailbox.get("signature_html"):
        rendered_html += mailbox["signature_html"]
    status = "Scheduled" if scheduled_at else "Queued"
    thread_key = f"candidate:{candidate_id}:application:{application_id or 0}"
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO communication_messages
               (thread_key,candidate_id,application_id,channel,direction,sender,recipient,
                subject,body_html,body_text,template_id,status,scheduled_at,created_by,created)
               VALUES (?,?,?,?,'outbound',?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (thread_key, candidate_id, application_id, channel, sender, recipient,
             rendered_subject, rendered_html, rendered_text, template_id, status, scheduled_at, actor),
        )
        message_id = cur.lastrowid
        if channel == "email":
            conn.execute(
                """UPDATE communication_messages SET body_html=body_html||?
                   WHERE id=?""", (f'<img src="/m/{message_id}/open.gif" width="1" height="1" alt="">', message_id),
            )
        return message_id


def draft_with_ai(instruction: str, *, context: dict | None = None, generator=None) -> str:
    prompt = ("Write a concise, professional recruitment message. Return only the message body.\n"
              f"Instruction: {instruction}\nContext: {json.dumps(context or {}, default=str)}")
    if generator:
        return str(generator(prompt)).strip()
    from web import llm
    response = llm.get_llm(temperature=0.3).invoke(prompt)
    return str(response.content if hasattr(response, "content") else response).strip()


class OutboxAdapter:
    """Deterministic built-in transport; production connectors implement the same method."""
    def send(self, message: dict) -> dict:
        return {"ok": True, "provider_message_id": f"outbox-{message['id']}"}


def dispatch_due(*, adapter=None, now: str | None = None, limit: int = 100) -> dict:
    adapter = adapter or OutboxAdapter()
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    pending = db.rows(
        """SELECT * FROM communication_messages
           WHERE status IN ('Queued','Scheduled') AND (scheduled_at IS NULL OR scheduled_at<=?)
           ORDER BY COALESCE(scheduled_at,created),id LIMIT ?""", (now, limit),
    )
    sent, failed = 0, 0
    for message in pending:
        try:
            result = adapter.send(message)
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or "Provider rejected the message.")
            with db.cursor() as conn:
                conn.execute(
                    """UPDATE communication_messages SET status='Sent',provider_message_id=?,
                       sent_at=datetime('now'),error=NULL WHERE id=?""",
                    (result.get("provider_message_id"), message["id"]),
                )
            record_message_event(message["id"], "sent", result)
            sent += 1
        except Exception as exc:
            with db.cursor() as conn:
                conn.execute("UPDATE communication_messages SET status='Failed',error=? WHERE id=?",
                             (str(exc), message["id"]))
            record_message_event(message["id"], "failed", {"error": str(exc)})
            failed += 1
    return {"processed": len(pending), "sent": sent, "failed": failed}


def record_message_event(message_id: int, event_type: str, payload: dict | None = None) -> None:
    if event_type not in MESSAGE_EVENTS:
        raise ValueError("Unsupported message event.")
    column = {"delivered": "delivered_at", "read": "read_at", "clicked": "clicked_at",
              "bounced": "bounced_at"}.get(event_type)
    with db.cursor() as conn:
        conn.execute(
            "INSERT INTO communication_events(message_id,event_type,payload_json,occurred_at) VALUES (?,?,?,datetime('now'))",
            (message_id, event_type, json.dumps(payload or {})),
        )
        if column:
            conn.execute(f"UPDATE communication_messages SET {column}=datetime('now'),status=? WHERE id=?",
                         (event_type.title(), message_id))


def import_inbound(messages: list[dict], *, mailbox_id: int | None = None,
                   cursor: str | None = None) -> dict:
    imported = 0
    for item in messages:
        external_id = item.get("provider_message_id")
        if external_id and db.one("SELECT id FROM communication_messages WHERE provider_message_id=?", (external_id,)):
            continue
        candidate = talent.find_candidate_by_email(item.get("sender") or "")
        if not candidate and item.get("candidate_id"):
            candidate = talent.candidate(int(item["candidate_id"]))
        if not candidate:
            continue
        application_id = item.get("application_id")
        with db.cursor() as conn:
            cur = conn.execute(
                """INSERT INTO communication_messages
                   (thread_key,candidate_id,application_id,channel,direction,sender,recipient,
                    subject,body_html,body_text,provider_message_id,status,sent_at,metadata_json,created)
                   VALUES (?,?,?,'email','inbound',?,?,?,?,?,?,'Received',?,?,datetime('now'))""",
                (f"candidate:{candidate['id']}:application:{application_id or 0}", candidate["id"],
                 application_id, item.get("sender"), item.get("recipient"), item.get("subject", ""),
                 item.get("body_html", ""), item.get("body_text", ""), external_id,
                 item.get("sent_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                 json.dumps(item.get("metadata") or {})),
            )
            message_id = cur.lastrowid
        record_message_event(message_id, "received", item)
        imported += 1
    if mailbox_id:
        with db.cursor() as conn:
            conn.execute("UPDATE recruitment_mailboxes SET sync_cursor=?,last_sync_at=datetime('now') WHERE id=?",
                         (cursor, mailbox_id))
    return {"imported": imported, "cursor": cursor}


class MailboxAdapter:
    """Provider contract for incremental Outlook/Google mailbox synchronization."""

    def pull(self, mailbox: dict, cursor: str | None) -> dict:
        return {"messages": [], "cursor": cursor}


def sync_mailbox(mailbox_id: int, *, adapter=None) -> dict:
    mailbox = db.one("SELECT * FROM recruitment_mailboxes WHERE id=? AND status='Active'", (mailbox_id,))
    if not mailbox:
        raise ValueError("Active recruitment mailbox not found.")
    result = (adapter or MailboxAdapter()).pull(mailbox, mailbox.get("sync_cursor"))
    imported = import_inbound(result.get("messages") or [], mailbox_id=mailbox_id,
                              cursor=result.get("cursor"))
    return {**imported, "mailbox_id": mailbox_id}


def communication_history(candidate_id: int) -> list[dict]:
    return db.rows(
        """SELECT * FROM communication_messages WHERE candidate_id=?
           ORDER BY COALESCE(sent_at,created),id""", (candidate_id,),
    )


def save_automation_rule(name: str, trigger_event: str, actions: list[dict], *,
                         conditions: dict | None = None, actor: str = "system") -> int:
    if not actions:
        raise ValueError("Automation requires at least one action.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO automation_rules
               (name,trigger_event,conditions_json,actions_json,active,created_by,created,updated)
               VALUES (?,?,?,?,1,?,datetime('now'),datetime('now'))
               ON CONFLICT(name) DO UPDATE SET trigger_event=excluded.trigger_event,
               conditions_json=excluded.conditions_json,actions_json=excluded.actions_json,
               active=1,updated=excluded.updated""",
            (name.strip(), trigger_event, json.dumps(conditions or {}), json.dumps(actions), actor),
        )
        return conn.execute("SELECT id FROM automation_rules WHERE name=?", (name.strip(),)).fetchone()[0]


def _conditions_match(conditions: dict, event: dict) -> bool:
    return all(event.get(key) == value for key, value in conditions.items())


def emit_event(event_type: str, event: dict, *, actor: str = "system") -> list[dict]:
    results = []
    for rule in db.rows("SELECT * FROM automation_rules WHERE trigger_event=? AND active=1", (event_type,)):
        conditions = json.loads(rule["conditions_json"] or "{}")
        if not _conditions_match(conditions, event):
            continue
        with db.cursor() as conn:
            cur = conn.execute(
                """INSERT INTO automation_runs(rule_id,entity_type,entity_id,event_json,status,started_at)
                   VALUES (?,?,?,?, 'Running',datetime('now'))""",
                (rule["id"], event.get("entity_type"), event.get("entity_id"), json.dumps(event)),
            )
            run_id = cur.lastrowid
        action_results = []
        try:
            for action in json.loads(rule["actions_json"]):
                action_results.append(_execute_action(action, event, actor=actor))
            status, error = "Completed", None
        except Exception as exc:
            status, error = "Failed", str(exc)
        with db.cursor() as conn:
            conn.execute(
                """UPDATE automation_runs SET status=?,result_json=?,error=?,completed_at=datetime('now') WHERE id=?""",
                (status, json.dumps(action_results), error, run_id),
            )
        results.append({"rule_id": rule["id"], "run_id": run_id, "status": status,
                        "actions": action_results, "error": error})
    candidate_id = int(event.get("candidate_id") or 0)
    if candidate_id:
        for survey in db.rows(
            "SELECT id,name FROM surveys WHERE trigger_event=? AND active=1", (event_type,)
        ):
            already_invited = db.one(
                """SELECT id FROM survey_invitations
                   WHERE survey_id=? AND candidate_id=? AND status IN ('Sent','Completed')""",
                (survey["id"], candidate_id),
            )
            if already_invited:
                continue
            token = invite_survey(survey["id"], candidate_id=candidate_id)
            try:
                message_id = queue_message(
                    candidate_id, channel="email",
                    subject=f"Feedback: {survey['name']}",
                    body=f"We value your feedback. Complete the survey: /survey/{token}",
                    application_id=int(event.get("application_id") or 0) or None,
                    actor=actor,
                )
            except ValueError:
                message_id = None
            results.append({"survey_id": survey["id"], "token": token,
                            "message_id": message_id, "status": "Invited"})
    return results


def _execute_action(action: dict, event: dict, *, actor: str) -> dict:
    kind = action.get("type")
    candidate_id = int(event.get("candidate_id") or 0)
    application_id = int(event.get("application_id") or 0) or None
    if kind in {"email", "sms"}:
        message_id = queue_message(candidate_id, channel=kind, subject=action.get("subject", ""),
                                   body=action.get("body", ""), application_id=application_id,
                                   template_id=action.get("template_id"), actor=actor)
        return {"type": kind, "message_id": message_id}
    if kind == "stage":
        from recruiting_ops import move_application
        return {"type": kind, "ok": move_application(application_id, action["stage"], actor=actor)}
    if kind == "tag":
        from recruiting_ops import add_tag
        return {"type": kind, "tag_id": add_tag(candidate_id, action["tag"], actor=actor)}
    if kind == "task":
        from recruiting_ops import create_task
        return {"type": kind, "task_id": create_task(action["title"], assignee=action.get("assignee", actor),
                                                       candidate_id=candidate_id, application_id=application_id,
                                                       due_at=action.get("due_at"), actor=actor)}
    if kind == "comment":
        from recruiting_ops import add_comment
        return {"type": kind, "comment_id": add_comment(candidate_id, action["body"], author=actor,
                                                          application_id=application_id)}
    if kind == "candidate_request":
        request_id = create_candidate_request(candidate_id, action.get("request_type", "information"),
                                              action.get("title", "Additional information"),
                                              application_id=application_id, fields=action.get("fields"), actor=actor)
        return {"type": kind, "request_id": request_id}
    if kind == "webhook":
        from recruitment_ecosystem import enqueue_webhook
        return {"type": kind, "deliveries": enqueue_webhook(action.get("event", "automation"), event)}
    raise ValueError(f"Unsupported automation action: {kind}")


def issue_portal_token(candidate_id: int, *, actor: str, expires_days: int = 30) -> str:
    if not talent.candidate(candidate_id):
        raise ValueError("Candidate not found.")
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO candidate_portal_tokens
               (candidate_id,token_hash,expires_at,created_by,created)
               VALUES (?,?,?, ?,datetime('now'))""",
            (candidate_id, digest, _iso_after(days=expires_days), actor),
        )
    return raw


def authenticate_portal(token: str) -> int | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.one(
        """SELECT * FROM candidate_portal_tokens WHERE token_hash=? AND revoked_at IS NULL
           AND expires_at>=datetime('now')""", (digest,),
    )
    if not row:
        return None
    with db.cursor() as conn:
        conn.execute("UPDATE candidate_portal_tokens SET last_used_at=datetime('now') WHERE id=?", (row["id"],))
    return row["candidate_id"]


def portal_snapshot(candidate_id: int) -> dict:
    candidate = talent.candidate(candidate_id)
    if not candidate:
        raise ValueError("Candidate not found.")
    return {
        "candidate": candidate,
        "applications": db.rows(
            """SELECT a.id,a.stage,a.status,a.applied_on,j.title,j.code,p.slug,p.publication_status
               FROM applications a JOIN job_openings j ON j.id=a.job_id
               LEFT JOIN job_postings p ON p.job_id=j.id WHERE a.candidate_id=? ORDER BY a.id DESC""",
            (candidate_id,),
        ),
        "requests": db.rows("SELECT * FROM candidate_requests WHERE candidate_id=? ORDER BY created DESC", (candidate_id,)),
        "messages": db.rows(
            """SELECT id,channel,direction,sender,recipient,subject,body_text,status,sent_at,created
               FROM communication_messages WHERE candidate_id=? ORDER BY id DESC LIMIT 50""", (candidate_id,),
        ),
        "consents": db.rows("SELECT * FROM candidate_consents WHERE candidate_id=? ORDER BY consented_at DESC", (candidate_id,)),
    }


def create_candidate_request(candidate_id: int, request_type: str, title: str, *,
                             application_id: int | None = None, fields: list[dict] | None = None,
                             due_at: str | None = None, actor: str) -> int:
    if request_type not in {"information", "document", "interview"}:
        raise ValueError("Unsupported candidate request type.")
    if not title.strip() or not talent.candidate(candidate_id):
        raise ValueError("A valid candidate and request title are required.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO candidate_requests
               (candidate_id,application_id,request_type,title,fields_json,status,due_at,created_by,created)
               VALUES (?,?,?,?,?,'Open',?,?,datetime('now'))""",
            (candidate_id, application_id, request_type, title.strip(), json.dumps(fields or []), due_at, actor),
        )
        return cur.lastrowid


def respond_candidate_request(request_id: int, candidate_id: int, response: dict) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE candidate_requests SET response_json=?,status='Completed',completed_at=datetime('now')
               WHERE id=? AND candidate_id=? AND status='Open'""",
            (json.dumps(response), request_id, candidate_id),
        )
    return bool(cur.rowcount)


def withdraw_application(application_id: int, candidate_id: int) -> bool:
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE applications SET status='Withdrawn' WHERE id=? AND candidate_id=?
               AND status='Active'""", (application_id, candidate_id),
        )
    if cur.rowcount:
        talent.log_event("application", application_id, actor="candidate-portal", to_state="Withdrawn")
    return bool(cur.rowcount)


def renew_consent(candidate_id: int, *, purpose: str = "Talent pool", months: int = 12,
                  proof: dict | None = None) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO candidate_consents
               (candidate_id,purpose,lawful_basis,consented_at,expires_at,proof_json)
               VALUES (?,?,'consent',datetime('now'),date('now',?),?)""",
            (candidate_id, purpose, f"+{months} months", json.dumps(proof or {})),
        )
        conn.execute("UPDATE candidates SET consent_at=datetime('now') WHERE id=?", (candidate_id,))
        return cur.lastrowid


def withdraw_consent(candidate_id: int) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """UPDATE candidate_consents SET withdrawn_at=datetime('now')
               WHERE candidate_id=? AND withdrawn_at IS NULL""", (candidate_id,),
        )
        conn.execute("UPDATE candidates SET consent_at=NULL WHERE id=?", (candidate_id,))
        return cur.rowcount


def create_privacy_request(candidate_id: int, request_type: str, *, details: str = "") -> int:
    if request_type not in {"Export", "Correct", "Dispute", "Anonymize", "Delete", "Withdraw consent"}:
        raise ValueError("Unsupported privacy request.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO privacy_requests(candidate_id,request_type,status,details,requested_at)
               VALUES (?,?,'Open',?,datetime('now'))""", (candidate_id, request_type, details.strip()),
        )
        return cur.lastrowid


def candidate_export(candidate_id: int) -> dict:
    return {
        "candidate": talent.candidate(candidate_id),
        "profile": talent.candidate_profile(candidate_id),
        "comments": db.rows("SELECT body,rating,visibility,author,created FROM candidate_comments WHERE candidate_id=?", (candidate_id,)),
        "communications": communication_history(candidate_id),
        "consents": db.rows("SELECT * FROM candidate_consents WHERE candidate_id=?", (candidate_id,)),
        "requests": db.rows("SELECT * FROM candidate_requests WHERE candidate_id=?", (candidate_id,)),
    }


def anonymize_candidate(candidate_id: int, *, actor: str) -> None:
    with db.cursor() as conn:
        conn.execute(
            """UPDATE candidates SET first_name='Anonymized',last_name=?,email=NULL,phone=NULL,
               location=NULL,headline=NULL,current_title=NULL,current_employer=NULL,linkedin_url=NULL,
               notes=NULL,status='Archived',consent_at=NULL WHERE id=?""",
            (f"Candidate {candidate_id}", candidate_id),
        )
        conn.execute("UPDATE candidate_documents SET file_name='[anonymized]',text_content=NULL,stored_path=NULL WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidate_skills WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidate_experience WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidate_education WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidate_field_values WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidate_tags WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE candidate_comments SET body='[anonymized]' WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE communication_messages SET body_html=NULL,body_text='[anonymized]',recipient=NULL,sender=CASE WHEN direction='inbound' THEN NULL ELSE sender END WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE candidate_consents SET proof_json=NULL,withdrawn_at=COALESCE(withdrawn_at,datetime('now')) WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE candidate_import_rows SET source_json='{}' WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE candidate_merge_events SET snapshot_json='{}' WHERE survivor_id=? OR merged_id=?", (candidate_id, candidate_id))
        conn.execute("UPDATE recruitment_analytics_events SET metadata_json='{}',source=NULL,medium=NULL WHERE candidate_id=?", (candidate_id,))
        conn.execute(
            """UPDATE ai_screening_results SET criteria_json='[]',summary='[anonymized]',location_summary=NULL
               WHERE application_id IN (SELECT id FROM applications WHERE candidate_id=?)""", (candidate_id,))
    talent.log_event("candidate", candidate_id, actor=actor, to_state="Anonymized")


def _delete_candidate(candidate_id: int, *, actor: str) -> None:
    application_ids = [r["id"] for r in db.rows("SELECT id FROM applications WHERE candidate_id=?", (candidate_id,))]
    with db.cursor() as conn:
        if application_ids:
            marks = ",".join("?" for _ in application_ids)
            interview_ids = [r[0] for r in conn.execute(f"SELECT id FROM interviews WHERE application_id IN ({marks})", application_ids)]
            if interview_ids:
                imarks = ",".join("?" for _ in interview_ids)
                conn.execute(f"DELETE FROM scorecards WHERE interview_id IN ({imarks})", interview_ids)
                conn.execute(f"DELETE FROM interviews WHERE id IN ({imarks})", interview_ids)
            invitation_ids = [r[0] for r in conn.execute(
                f"SELECT id FROM video_interview_invitations WHERE application_id IN ({marks})", application_ids)]
            if invitation_ids:
                vmarks = ",".join("?" for _ in invitation_ids)
                conn.execute(f"DELETE FROM video_responses WHERE invitation_id IN ({vmarks})", invitation_ids)
                conn.execute(f"DELETE FROM video_interview_invitations WHERE id IN ({vmarks})", invitation_ids)
            for table in ("application_answers", "application_drop_reasons", "offers", "ai_screening_results"):
                conn.execute(f"DELETE FROM {table} WHERE application_id IN ({marks})", application_ids)
            conn.execute(f"DELETE FROM ranking_scores WHERE application_id IN ({marks})", application_ids)
            conn.execute(f"DELETE FROM applications WHERE id IN ({marks})", application_ids)
        conn.execute("DELETE FROM extraction_runs WHERE candidate_id=?", (candidate_id,))
        for table in ("candidate_tags", "candidate_comments", "candidate_field_values",
                      "candidate_skills", "candidate_experience", "candidate_education", "candidate_consents",
                      "reference_requests", "candidate_credentials", "communication_messages", "candidate_requests",
                      "survey_invitations", "video_messages", "candidate_portal_tokens",
                      "recruiting_tasks", "bulk_action_items", "recruitment_analytics_events"):
            conn.execute(f"DELETE FROM {table} WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidate_documents WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE candidate_import_rows SET candidate_id=NULL,source_json='{}' WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE candidate_merge_events SET snapshot_json='{}' WHERE survivor_id=? OR merged_id=?", (candidate_id, candidate_id))
        conn.execute("UPDATE privacy_requests SET details=NULL,result_json=NULL WHERE candidate_id=?", (candidate_id,))
        conn.execute("UPDATE employees SET candidate_id=NULL WHERE candidate_id=?", (candidate_id,))
        conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
    talent.log_event("privacy_deletion", candidate_id, actor=actor, to_state="Permanently deleted")


def process_privacy_request(request_id: int, *, actor: str) -> dict:
    request = db.one("SELECT * FROM privacy_requests WHERE id=? AND status='Open'", (request_id,))
    if not request:
        raise ValueError("Open privacy request not found.")
    kind, candidate_id = request["request_type"], request["candidate_id"]
    result: dict = {"type": kind}
    if kind == "Export":
        result["export"] = candidate_export(candidate_id)
    elif kind == "Anonymize":
        anonymize_candidate(candidate_id, actor=actor)
    elif kind == "Delete":
        _delete_candidate(candidate_id, actor=actor)
    elif kind == "Withdraw consent":
        result["withdrawn"] = withdraw_consent(candidate_id)
    elif kind == "Correct":
        result["note"] = "Correction verified and assigned for manual application."
    elif kind == "Dispute":
        result["note"] = "Dispute reviewed and recorded for the privacy officer."
    with db.cursor() as conn:
        conn.execute(
            """UPDATE privacy_requests SET status='Completed',verified_at=datetime('now'),
               completed_at=datetime('now'),handled_by=?,result_json=? WHERE id=?""",
            (actor, json.dumps(result, default=str), request_id),
        )
    return result


def save_retention_policy(name: str, purpose: str, months: int, *, action: str = "Anonymize") -> int:
    if action not in {"Anonymize", "Delete"}:
        raise ValueError("Retention action must be Anonymize or Delete.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO retention_policies(name,purpose,retention_months,action,active,created,updated)
               VALUES (?,?,?,?,1,datetime('now'),datetime('now')) ON CONFLICT(name) DO UPDATE SET
               purpose=excluded.purpose,retention_months=excluded.retention_months,
               action=excluded.action,active=1,updated=excluded.updated""",
            (name, purpose, int(months), action),
        )
        return conn.execute("SELECT id FROM retention_policies WHERE name=?", (name,)).fetchone()[0]


def run_retention(*, actor: str = "retention-worker") -> dict:
    expired = db.rows(
        """SELECT DISTINCT c.id FROM candidates c JOIN candidate_consents cc ON cc.candidate_id=c.id
           WHERE cc.expires_at<date('now') AND cc.withdrawn_at IS NULL
           AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.candidate_id=c.id AND a.status='Active')"""
    )
    for row in expired:
        anonymize_candidate(row["id"], actor=actor)
    return {"processed": len(expired), "anonymized": len(expired)}


def save_survey(name: str, audience: str, questions: list[dict], *,
                trigger_event: str = "", actor: str = "system") -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO surveys(name,audience,trigger_event,questions_json,active,created_by,created)
               VALUES (?,?,?,?,1,?,datetime('now'))""",
            (name.strip(), audience, trigger_event, json.dumps(questions), actor),
        )
        return cur.lastrowid


def invite_survey(survey_id: int, *, candidate_id: int | None = None,
                  recipient_email: str = "") -> str:
    if candidate_id and not recipient_email:
        recipient_email = (talent.candidate(candidate_id) or {}).get("email") or ""
    token = secrets.token_urlsafe(24)
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO survey_invitations
               (survey_id,candidate_id,recipient_email,token,status,sent_at)
               VALUES (?,?,?,?,'Sent',datetime('now'))""",
            (survey_id, candidate_id, recipient_email, token),
        )
    return token


def submit_survey(token: str, answers: dict, *, score: float | None = None) -> bool:
    invitation = db.one("SELECT * FROM survey_invitations WHERE token=? AND status='Sent'", (token,))
    if not invitation:
        return False
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO survey_responses(invitation_id,score,answers_json,submitted_at)
               VALUES (?,?,?,datetime('now'))""", (invitation["id"], score, json.dumps(answers)),
        )
        conn.execute("UPDATE survey_invitations SET status='Completed',completed_at=datetime('now') WHERE id=?",
                     (invitation["id"],))
    return True


def survey_metrics(survey_id: int) -> dict:
    scores = [r["score"] for r in db.rows(
        """SELECT r.score FROM survey_responses r JOIN survey_invitations i ON i.id=r.invitation_id
           WHERE i.survey_id=? AND r.score IS NOT NULL""", (survey_id,),
    )]
    promoters = sum(1 for s in scores if s >= 9)
    detractors = sum(1 for s in scores if s <= 6)
    return {"responses": len(scores), "average": round(sum(scores) / len(scores), 2) if scores else None,
            "cnps": round(100 * (promoters - detractors) / len(scores)) if scores else None}
