"""Phase 4 scheduling, connector, recruitment marketing, and analytics services."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import textwrap
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import db
import integrations
import talent


INCLUSIVE_TERMS = {
    "rockstar": "skilled professional", "ninja": "specialist", "guru": "expert",
    "young and energetic": "collaborative and motivated", "native speaker": "fluent speaker",
    "manpower": "workforce", "chairman": "chairperson", "aggressive": "results-oriented",
}


def save_availability(email: str, weekday: int, start_time: str, end_time: str, *,
                      timezone: str = "UTC", active: bool = True) -> int:
    if weekday not in range(7) or start_time >= end_time:
        raise ValueError("Availability requires a weekday and a valid time range.")
    ZoneInfo(timezone)
    with db.cursor() as conn:
        existing = conn.execute(
            """SELECT id FROM interviewer_availability
               WHERE lower(account_email)=? AND weekday=? AND start_time=? AND end_time=? AND timezone=?""",
            (email.lower(), weekday, start_time, end_time, timezone),
        ).fetchone()
        if existing:
            conn.execute("UPDATE interviewer_availability SET active=? WHERE id=?", (int(active), existing[0]))
            return existing[0]
        cur = conn.execute(
            """INSERT INTO interviewer_availability
               (account_email,weekday,start_time,end_time,timezone,active) VALUES (?,?,?,?,?,?)""",
            (email.lower(), weekday, start_time, end_time, timezone, int(active)),
        )
        return cur.lastrowid


def create_scheduling_link(application_id: int, interviewer_emails: list[str], *,
                           window_start: str, window_end: str, timezone: str = "UTC",
                           duration_minutes: int = 30, mode: str = "Video",
                           provider: str = "", actor: str = "system", expires_days: int = 14) -> str:
    if not db.one("SELECT id FROM applications WHERE id=?", (application_id,)):
        raise ValueError("Application not found.")
    if not interviewer_emails:
        raise ValueError("At least one interviewer is required.")
    ZoneInfo(timezone)
    if datetime.fromisoformat(window_start) >= datetime.fromisoformat(window_end):
        raise ValueError("Scheduling window end must be after its start.")
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now(dt_timezone.utc) + timedelta(days=expires_days)).strftime("%Y-%m-%d %H:%M:%S")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO scheduling_links
               (application_id,token,duration_minutes,mode,provider,interviewer_emails_json,
                window_start,window_end,timezone,status,expires_at,created_by,created)
               VALUES (?,?,?,?,?,?,?, ?,?,'Open',?,?,datetime('now'))""",
            (application_id, token, max(15, duration_minutes), mode, provider,
             json.dumps([e.lower() for e in interviewer_emails]), window_start, window_end,
             timezone, expires_at, actor),
        )
    return token


def _email_slots(email: str, link: dict) -> set[str]:
    tz = ZoneInfo(link["timezone"])
    start = datetime.fromisoformat(link["window_start"]).replace(tzinfo=tz)
    end = datetime.fromisoformat(link["window_end"]).replace(tzinfo=tz)
    duration = timedelta(minutes=link["duration_minutes"])
    availability = db.rows(
        """SELECT * FROM interviewer_availability WHERE lower(account_email)=? AND active=1""",
        (email.lower(),),
    )
    busy = db.rows(
        """SELECT b.starts_at,b.ends_at FROM interview_bookings b
           JOIN scheduling_links l ON l.id=b.scheduling_link_id
           WHERE b.status='Booked' AND l.interviewer_emails_json LIKE ?""", (f"%{email.lower()}%",),
    )
    slots: set[str] = set()
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day.date() <= end.date():
        for rule in availability:
            if day.weekday() != rule["weekday"]:
                continue
            hour, minute = map(int, rule["start_time"].split(":"))
            finish_hour, finish_minute = map(int, rule["end_time"].split(":"))
            point = day.replace(hour=hour, minute=minute)
            finish = day.replace(hour=finish_hour, minute=finish_minute)
            while point + duration <= finish:
                if point >= start and point + duration <= end:
                    point_text = point.isoformat()
                    point_end = point + duration
                    overlaps = any(point < datetime.fromisoformat(b["ends_at"]) and
                                   point_end > datetime.fromisoformat(b["starts_at"]) for b in busy)
                    if not overlaps:
                        slots.add(point_text)
                point += duration
        day += timedelta(days=1)
    return slots


def available_slots(token: str) -> list[dict]:
    link = db.one(
        """SELECT * FROM scheduling_links WHERE token=? AND status='Open'
           AND expires_at>=datetime('now')""", (token,),
    )
    if not link:
        return []
    emails = json.loads(link["interviewer_emails_json"])
    common = None
    for email in emails:
        slots = _email_slots(email, link)
        common = slots if common is None else common.intersection(slots)
    return [{"starts_at": value,
             "ends_at": (datetime.fromisoformat(value) + timedelta(minutes=link["duration_minutes"])).isoformat(),
             "timezone": link["timezone"]} for value in sorted(common or set())]


class CalendarAdapter:
    def create_event(self, booking: dict, attendees: list[str], provider: str) -> dict:
        event_id = f"calendar-{booking['id']}"
        room_key = hmac.new(os.getenv("FASTHR_SECRET", "fasthr-development").encode(),
                            str(booking["id"]).encode(), hashlib.sha256).hexdigest()[:24]
        video_base = os.getenv("FASTHR_VIDEO_BASE_URL", "https://meet.jit.si").rstrip("/")
        meeting_url = (f"https://meet.google.com/fas-thr-{booking['id']}" if provider == "google_calendar"
                       else f"https://teams.microsoft.com/l/meetup-join/fasthr-{booking['id']}"
                       if provider in {"ms_graph", "teams"} else f"{video_base}/FastHRM-{room_key}")
        return {"ok": True, "event_ids": [event_id], "meeting_url": meeting_url}


def book_slot(token: str, starts_at: str, *, adapter=None) -> dict:
    link = db.one("SELECT * FROM scheduling_links WHERE token=? AND status='Open'", (token,))
    if not link or starts_at not in {slot["starts_at"] for slot in available_slots(token)}:
        raise ValueError("That interview slot is no longer available.")
    emails = json.loads(link["interviewer_emails_json"])
    ends_at = (datetime.fromisoformat(starts_at) + timedelta(minutes=link["duration_minutes"])).isoformat()
    interviewer = db.one("SELECT id FROM employees WHERE lower(email)=?", (emails[0],))
    interview_id = talent.schedule_interview(
        link["application_id"], interviewer_id=(interviewer or {}).get("id"), kind="Interview",
        scheduled_at=starts_at, mode=link["mode"], duration=link["duration_minutes"], actor="candidate-scheduler")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO interview_bookings
               (scheduling_link_id,interview_id,starts_at,ends_at,timezone,status,booked_at)
               VALUES (?,?,?,?,?,'Booked',datetime('now'))""",
            (link["id"], interview_id, starts_at, ends_at, link["timezone"]),
        )
        booking_id = cur.lastrowid
        conn.execute("UPDATE scheduling_links SET status='Booked' WHERE id=?", (link["id"],))
    booking = db.one("SELECT * FROM interview_bookings WHERE id=?", (booking_id,))
    calendar = (adapter or CalendarAdapter()).create_event(booking, emails, link["provider"] or "fasthr")
    with db.cursor() as conn:
        conn.execute(
            """UPDATE interview_bookings SET meeting_url=?,calendar_event_ids_json=? WHERE id=?""",
            (calendar.get("meeting_url"), json.dumps(calendar.get("event_ids") or []), booking_id),
        )
    return db.one("SELECT * FROM interview_bookings WHERE id=?", (booking_id,))


def cancel_booking(booking_id: int, *, actor: str = "system") -> bool:
    booking = db.one("SELECT * FROM interview_bookings WHERE id=? AND status='Booked'", (booking_id,))
    if not booking:
        return False
    with db.cursor() as conn:
        conn.execute("UPDATE interview_bookings SET status='Cancelled',cancelled_at=datetime('now') WHERE id=?", (booking_id,))
        conn.execute("UPDATE interviews SET status='Cancelled' WHERE id=?", (booking["interview_id"],))
        conn.execute("UPDATE scheduling_links SET status='Open' WHERE id=?", (booking["scheduling_link_id"],))
    talent.log_event("interview_booking", booking_id, actor=actor, to_state="Cancelled")
    return True


def register_connector(provider: str, category: str, *, account_ref: str = "default",
                       config: dict | None = None) -> int:
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO connector_accounts
               (provider,category,account_ref,status,config_json,created,updated)
               VALUES (?,?,?,'Connected',?,datetime('now'),datetime('now'))
               ON CONFLICT(provider,account_ref) DO UPDATE SET category=excluded.category,
               config_json=excluded.config_json,status='Connected',updated=excluded.updated""",
            (provider, category, account_ref, json.dumps(config or {})),
        )
        return conn.execute("SELECT id FROM connector_accounts WHERE provider=? AND account_ref=?",
                            (provider, account_ref)).fetchone()[0]


class ConnectorAdapter:
    def publish_job(self, provider: str, payload: dict) -> dict:
        return {"ok": True, "external_id": f"{provider}-{payload['job_id']}",
                "external_url": f"https://jobs.example/{provider}/{payload['slug']}"}

    def close_job(self, provider: str, external_id: str) -> dict:
        return {"ok": True, "external_id": external_id}

    def pull(self, connector: dict, cursor: str | None) -> dict:
        return {"events": [], "cursor": cursor}


def connector_contracts() -> list[dict]:
    return [{"provider": p[0], "label": p[1], "category": p[2], "capabilities":
             ["test", "sync"] + (["publish_job", "import_applicant"] if p[2] == "job_board" else [])}
            for p in integrations.PROVIDERS]


def sync_connector(connector_id: int, *, adapter=None) -> dict:
    connector = db.one("SELECT * FROM connector_accounts WHERE id=? AND status='Connected'", (connector_id,))
    if not connector:
        raise ValueError("Connected account not found.")
    result = (adapter or ConnectorAdapter()).pull(connector, connector.get("cursor"))
    processed = 0
    with db.cursor() as conn:
        for event in result.get("events", []):
            conn.execute(
                """INSERT INTO connector_events
                   (connector_id,direction,event_type,external_id,payload_json,status,created,processed_at)
                   VALUES (?,'inbound',?,?,?,'Processed',datetime('now'),datetime('now'))""",
                (connector_id, event.get("type", "unknown"), event.get("external_id"), json.dumps(event)),
            )
            processed += 1
        conn.execute("UPDATE connector_accounts SET cursor=?,last_sync_at=datetime('now') WHERE id=?",
                     (result.get("cursor"), connector_id))
    return {"processed": processed, "cursor": result.get("cursor")}


def _job_payload(job_id: int) -> dict:
    import recruitment
    posting = recruitment.ensure_posting(job_id)
    return {"job_id": job_id, "code": posting["code"], "title": posting["public_title"],
            "slug": posting["slug"], "description": posting["description"],
            "requirements": posting["requirements"], "location": posting["location"],
            "employment_type": posting["employment_type"], "url": f"/jobs/{posting['slug']}"}


def publish_to_job_boards(job_id: int, providers: list[str], *, adapter=None) -> list[dict]:
    payload, adapter, results = _job_payload(job_id), adapter or ConnectorAdapter(), []
    for provider in list(dict.fromkeys(providers)):
        with db.cursor() as conn:
            conn.execute(
                """INSERT INTO job_board_posts(job_id,provider,status,payload_json)
                   VALUES (?,?,'Publishing',?) ON CONFLICT(job_id,provider) DO UPDATE SET
                   status='Publishing',payload_json=excluded.payload_json,last_error=NULL""",
                (job_id, provider, json.dumps(payload)),
            )
        try:
            result = adapter.publish_job(provider, payload)
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or "Publishing failed.")
            with db.cursor() as conn:
                conn.execute(
                    """UPDATE job_board_posts SET external_id=?,external_url=?,status='Posted',
                       posted_at=datetime('now'),last_error=NULL WHERE job_id=? AND provider=?""",
                    (result.get("external_id"), result.get("external_url"), job_id, provider),
                )
        except Exception as exc:
            with db.cursor() as conn:
                conn.execute("UPDATE job_board_posts SET status='Failed',last_error=? WHERE job_id=? AND provider=?",
                             (str(exc), job_id, provider))
        results.append(db.one("SELECT * FROM job_board_posts WHERE job_id=? AND provider=?", (job_id, provider)))
    return results


def close_job_board_posts(job_id: int, *, adapter=None) -> int:
    adapter, closed = adapter or ConnectorAdapter(), 0
    for post in db.rows("SELECT * FROM job_board_posts WHERE job_id=? AND status='Posted'", (job_id,)):
        if adapter.close_job(post["provider"], post["external_id"]).get("ok"):
            with db.cursor() as conn:
                conn.execute("UPDATE job_board_posts SET status='Closed',closed_at=datetime('now') WHERE id=?", (post["id"],))
            closed += 1
    return closed


def import_job_board_applicant(provider: str, external_job_id: str, payload: dict) -> dict:
    post = db.one("SELECT * FROM job_board_posts WHERE provider=? AND external_id=?",
                  (provider, external_job_id))
    if not post:
        raise ValueError("Published job mapping not found.")
    email = (payload.get("email") or "").strip().lower()
    candidate = talent.find_candidate_by_email(email) if email else None
    candidate_id = candidate["id"] if candidate else talent.create_candidate(
        first_name=payload.get("first_name", ""), last_name=payload.get("last_name", ""),
        email=email, phone=payload.get("phone", ""), source="Job Board",
        location=payload.get("location", ""), consent=bool(payload.get("consent")),
    )
    application_id = talent.apply_to_job(candidate_id, post["job_id"], actor=f"connector:{provider}")
    track_event("application_submitted", candidate_id=candidate_id, application_id=application_id,
                job_id=post["job_id"], source=provider, metadata={"external_id": payload.get("external_id")})
    return {"candidate_id": candidate_id, "application_id": application_id, "job_id": post["job_id"]}


def create_webhook_subscription(name: str, url: str, events: list[str], *, actor: str) -> dict:
    secret = secrets.token_urlsafe(32)
    digest = hashlib.sha256(secret.encode()).hexdigest()
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO webhook_subscriptions
               (name,url,secret_hash,secret_enc,events_json,active,created_by,created)
               VALUES (?,?,?,?,?,1,?,datetime('now'))""",
            (name.strip(), url.strip(), digest, integrations.encrypt(secret), json.dumps(events), actor),
        )
    return {"id": cur.lastrowid, "secret": secret}


def enqueue_webhook(event_type: str, payload: dict) -> int:
    queued = 0
    for sub in db.rows("SELECT * FROM webhook_subscriptions WHERE active=1"):
        if event_type not in json.loads(sub["events_json"]):
            continue
        with db.cursor() as conn:
            conn.execute(
                """INSERT INTO webhook_deliveries
                   (subscription_id,event_type,payload_json,status,created)
                   VALUES (?,?,?,'Pending',datetime('now'))""",
                (sub["id"], event_type, json.dumps(payload, default=str)),
            )
        queued += 1
    return queued


class WebhookAdapter:
    def post(self, url: str, body: str, headers: dict) -> dict:
        import httpx
        response = httpx.post(url, content=body, headers=headers, timeout=10)
        return {"status_code": response.status_code, "body": response.text[:2000]}


def deliver_webhooks(*, adapter=None, limit: int = 100) -> dict:
    adapter, delivered, failed = adapter or WebhookAdapter(), 0, 0
    rows = db.rows(
        """SELECT d.*,s.url,s.secret_enc FROM webhook_deliveries d
           JOIN webhook_subscriptions s ON s.id=d.subscription_id
           WHERE d.status IN ('Pending','Retry') AND (d.next_attempt_at IS NULL OR d.next_attempt_at<=datetime('now'))
           ORDER BY d.id LIMIT ?""", (limit,),
    )
    for row in rows:
        secret = integrations.decrypt(row["secret_enc"])
        signature = hmac.new(secret.encode(), row["payload_json"].encode(), hashlib.sha256).hexdigest()
        try:
            result = adapter.post(row["url"], row["payload_json"],
                                  {"content-type": "application/json", "x-fasthr-signature": signature,
                                   "x-fasthr-event": row["event_type"]})
            ok = 200 <= int(result["status_code"]) < 300
            status = "Delivered" if ok else "Retry"
            with db.cursor() as conn:
                conn.execute(
                    """UPDATE webhook_deliveries SET status=?,attempts=attempts+1,response_code=?,
                       response_body=?,next_attempt_at=CASE WHEN ?='Retry' THEN datetime('now','+5 minutes') ELSE NULL END,
                       delivered_at=CASE WHEN ?='Delivered' THEN datetime('now') ELSE NULL END WHERE id=?""",
                    (status, result["status_code"], result.get("body", ""), status, status, row["id"]),
                )
            delivered += int(ok); failed += int(not ok)
        except Exception as exc:
            with db.cursor() as conn:
                conn.execute(
                    """UPDATE webhook_deliveries SET status='Retry',attempts=attempts+1,
                       response_body=?,next_attempt_at=datetime('now','+5 minutes') WHERE id=?""",
                    (str(exc), row["id"]),
                )
            failed += 1
    return {"processed": len(rows), "delivered": delivered, "failed": failed}


def save_page_template(name: str, sections: list[dict], *, styles: dict | None = None,
                       actor: str = "system") -> int:
    if not sections:
        raise ValueError("A page template needs at least one section.")
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO page_templates(name,sections_json,default_styles_json,created_by,created,updated)
               VALUES (?,?,?,?,datetime('now'),datetime('now')) ON CONFLICT(name) DO UPDATE SET
               sections_json=excluded.sections_json,default_styles_json=excluded.default_styles_json,
               updated=excluded.updated""", (name.strip(), json.dumps(sections), json.dumps(styles or {}), actor),
        )
        return conn.execute("SELECT id FROM page_templates WHERE name=?", (name.strip(),)).fetchone()[0]


def store_marketing_asset(name: str, asset_type: str, data: bytes, *, file_name: str,
                          alt_text: str = "", actor: str = "system") -> int:
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".svg"} or len(data) > 10 * 1024 * 1024:
        raise ValueError("Use a PNG, JPG, WEBP, or SVG asset no larger than 10 MB.")
    root = Path(os.getenv("FASTHR_UPLOAD_DIR", Path(__file__).parent / "data" / "uploads")) / "marketing"
    root.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in Path(file_name).stem if ch.isalnum() or ch in "-_") or "asset"
    path = root / f"{secrets.token_hex(8)}-{safe}{suffix}"
    path.write_bytes(data)
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO marketing_assets(name,asset_type,url,alt_text,metadata_json,uploaded_by,created)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (name.strip(), asset_type, str(path), alt_text.strip(), json.dumps({"bytes": len(data)}), actor),
        )
        return cur.lastrowid


def inclusive_language_review(text: str) -> list[dict]:
    lowered = text.lower()
    return [{"term": term, "replacement": replacement, "index": lowered.index(term)}
            for term, replacement in INCLUSIVE_TERMS.items() if term in lowered]


def draft_job_ad(instruction: str, *, job: dict, generator=None) -> str:
    prompt = ("Write an inclusive, specific job advertisement. Avoid hype and biased language. "
              f"Instruction: {instruction}\nJob: {json.dumps(job, default=str)}")
    if generator:
        draft = str(generator(prompt)).strip()
    else:
        from web import llm
        response = llm.get_llm(temperature=0.3).invoke(prompt)
        draft = str(response.content if hasattr(response, "content") else response).strip()
    for finding in inclusive_language_review(draft):
        draft = re_sub_case_insensitive(draft, finding["term"], finding["replacement"])
    return draft


def re_sub_case_insensitive(text: str, old: str, new: str) -> str:
    import re
    return re.sub(re.escape(old), new, text, flags=re.IGNORECASE)


def save_campaign(name: str, *, job_id: int | None = None, landing_slug: str = "",
                  content: dict | None = None, starts_at: str | None = None,
                  ends_at: str | None = None, actor: str = "system") -> int:
    slug = landing_slug.strip().lower().replace(" ", "-") or f"campaign-{secrets.token_hex(4)}"
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO recruitment_campaigns
               (name,job_id,landing_slug,content_json,status,starts_at,ends_at,created_by,created,updated)
               VALUES (?,?,?,?, 'Draft',?,?,?,datetime('now'),datetime('now'))""",
            (name.strip(), job_id, slug, json.dumps(content or {}), starts_at, ends_at, actor),
        )
        return cur.lastrowid


def publish_campaign(campaign_id: int, channels: list[str]) -> dict:
    with db.cursor() as conn:
        conn.execute("UPDATE recruitment_campaigns SET status='Published',updated=datetime('now') WHERE id=?", (campaign_id,))
        for channel in channels:
            conn.execute(
                """INSERT INTO campaign_channels(campaign_id,channel,status)
                   VALUES (?,?,'Published') ON CONFLICT(campaign_id,channel) DO UPDATE SET status='Published'""",
                (campaign_id, channel),
            )
    return db.one("SELECT * FROM recruitment_campaigns WHERE id=?", (campaign_id,))


def campaign(slug: str) -> dict | None:
    row = db.one("SELECT * FROM recruitment_campaigns WHERE landing_slug=? AND status='Published'", (slug,))
    if row:
        row["content"] = json.loads(row["content_json"] or "{}")
        row["channels"] = db.rows("SELECT * FROM campaign_channels WHERE campaign_id=?", (row["id"],))
        template_id = int(row["content"].get("template_id") or 0)
        template = db.one("SELECT * FROM page_templates WHERE id=?", (template_id,)) if template_id else None
        row["template"] = ({"sections": json.loads(template["sections_json"]),
                            "styles": json.loads(template["default_styles_json"] or "{}")}
                           if template else None)
        asset_id = int(row["content"].get("asset_id") or 0)
        row["asset"] = db.one("SELECT id,name,alt_text FROM marketing_assets WHERE id=?", (asset_id,)) if asset_id else None
        if row.get("job_id"):
            distributed = db.one(
                """SELECT c.slug site_slug,d.locale,d.slug FROM job_distributions d
                   JOIN career_sites c ON c.id=d.career_site_id
                   JOIN job_postings p ON p.id=d.job_posting_id
                   WHERE p.job_id=? AND d.status='Published' AND p.publication_status='Published'
                   ORDER BY d.id DESC LIMIT 1""", (row["job_id"],))
            if distributed:
                row["job_url"] = (f"/sites/{distributed['site_slug']}/{distributed['locale']}"
                                  f"/jobs/{distributed['slug']}")
            else:
                posting = db.one(
                    "SELECT slug FROM job_postings WHERE job_id=? AND publication_status='Published'",
                    (row["job_id"],))
                row["job_url"] = f"/jobs/{posting['slug']}" if posting else "/careers"
    return row


def render_campaign_jpg(campaign_id: int, destination: str | Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    row = db.one("SELECT * FROM recruitment_campaigns WHERE id=?", (campaign_id,))
    if not row:
        raise ValueError("Campaign not found.")
    content = json.loads(row["content_json"] or "{}")
    image = Image.new("RGB", (1200, 630), content.get("background", "#ecfeff"))
    draw, font = ImageDraw.Draw(image), ImageFont.load_default(size=34)
    draw.text((70, 70), row["name"], fill=content.get("color", "#111827"), font=font)
    body = content.get("headline") or content.get("body") or "Explore this opportunity with us."
    y = 155
    for line in textwrap.wrap(body, 55):
        draw.text((70, y), line, fill=content.get("color", "#111827"), font=font)
        y += 46
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=90)
    return path


def track_event(event_type: str, *, session_id: str = "", candidate_id: int | None = None,
                application_id: int | None = None, job_id: int | None = None,
                campaign_id: int | None = None, source: str = "", medium: str = "",
                metadata: dict | None = None) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO recruitment_analytics_events
               (event_type,session_id,candidate_id,application_id,job_id,campaign_id,source,medium,metadata_json,occurred_at)
               VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))""",
            (event_type, session_id, candidate_id, application_id, job_id, campaign_id,
             source, medium, json.dumps(metadata or {})),
        )
        return cur.lastrowid


def create_experiment(name: str, variants: list[dict], *, job_id: int | None = None) -> int:
    if len(variants) < 2:
        raise ValueError("An experiment requires at least two variants.")
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO recruitment_experiments(name,job_id,variants_json,status,starts_at,created)
               VALUES (?,?,?,'Running',datetime('now'),datetime('now'))""",
            (name.strip(), job_id, json.dumps(variants)),
        )
        return cur.lastrowid


def assign_experiment(experiment_id: int, session_id: str) -> dict:
    experiment = db.one("SELECT * FROM recruitment_experiments WHERE id=? AND status='Running'", (experiment_id,))
    if not experiment:
        raise ValueError("Running experiment not found.")
    variants = json.loads(experiment["variants_json"])
    index = int(hashlib.sha256(f"{experiment_id}:{session_id}".encode()).hexdigest(), 16) % len(variants)
    return variants[index]


def analytics_summary(*, job_id: int | None = None, source: str = "",
                      date_from: str = "", date_to: str = "") -> dict:
    where, params = [], []
    if job_id:
        where.append("job_id=?"); params.append(job_id)
    if source:
        where.append("source=?"); params.append(source)
    if date_from:
        where.append("date(occurred_at)>=?"); params.append(date_from)
    if date_to:
        where.append("date(occurred_at)<=?"); params.append(date_to)
    clause = " WHERE " + " AND ".join(where) if where else ""
    counts = db.rows(
        "SELECT event_type,COUNT(*) n FROM recruitment_analytics_events" + clause + " GROUP BY event_type", tuple(params))
    by_event = {row["event_type"]: row["n"] for row in counts}
    views, applications = by_event.get("job_view", 0), by_event.get("application_submitted", 0)
    sent = db.scalar("SELECT COUNT(*) FROM communication_messages WHERE direction='outbound' AND status NOT IN ('Queued','Scheduled','Failed')") or 0
    clicked = db.scalar("SELECT COUNT(DISTINCT message_id) FROM communication_events WHERE event_type='clicked'") or 0
    recruiter_performance = db.rows(
        """SELECT actor,COUNT(*) actions,
                  SUM(CASE WHEN to_state='Hired' THEN 1 ELSE 0 END) hires
           FROM lifecycle_events WHERE entity_type IN ('application','job_opening')
           AND actor IS NOT NULL AND actor!='system' GROUP BY actor ORDER BY hires DESC,actions DESC""")
    return {"events": by_event, "views": views, "applications": applications,
            "conversion_rate": round(100 * applications / views, 2) if views else 0,
            "email_conversion": {"sent": sent, "clicked": clicked,
                                 "click_rate": round(100 * clicked / sent, 2) if sent else 0},
            "recruiter_performance": recruiter_performance,
            "funnel": talent.funnel(job_id), "sources": talent.source_effectiveness(),
            "time_in_stage": talent.time_in_stage(), "time_to_fill": talent.time_to_fill(),
            "interviewer_load": talent.interviewer_load(), "offers": talent.offer_stats()}


def save_dashboard(owner_email: str, name: str, scope: str, widgets: list[dict], *,
                   filters: dict | None = None, shared: bool = False) -> int:
    with db.cursor() as conn:
        cur = conn.execute(
            """INSERT INTO dashboard_definitions
               (owner_email,name,scope,filters_json,widgets_json,shared,created,updated)
               VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (owner_email.lower(), name.strip(), scope, json.dumps(filters or {}),
             json.dumps(widgets), int(shared)),
        )
        return cur.lastrowid


def experiment_report(experiment_id: int) -> dict:
    experiment = db.one("SELECT * FROM recruitment_experiments WHERE id=?", (experiment_id,))
    if not experiment:
        raise ValueError("Experiment not found.")
    variants = {item["key"]: {"exposures": 0, "applications": 0}
                for item in json.loads(experiment["variants_json"])}
    for event in db.rows(
        """SELECT event_type,metadata_json FROM recruitment_analytics_events
           WHERE json_extract(metadata_json,'$.experiment_id')=?""", (experiment_id,)):
        metadata = json.loads(event["metadata_json"] or "{}")
        result = variants.get(metadata.get("variant"))
        if result:
            if event["event_type"] == "experiment_exposure":
                result["exposures"] += 1
            elif event["event_type"] == "application_submitted":
                result["applications"] += 1
    for result in variants.values():
        result["conversion_rate"] = round(
            100 * result["applications"] / result["exposures"], 2) if result["exposures"] else 0
    return {"id": experiment_id, "name": experiment["name"], "variants": variants}


def export_analytics_csv(*, job_id: int | None = None) -> str:
    events = db.rows(
        """SELECT event_type,occurred_at,job_id,candidate_id,application_id,source,medium,metadata_json
           FROM recruitment_analytics_events WHERE (? IS NULL OR job_id=?) ORDER BY occurred_at""",
        (job_id, job_id),
    )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["event_type", "occurred_at", "job_id", "candidate_id",
                                                     "application_id", "source", "medium", "metadata_json"])
    writer.writeheader(); writer.writerows(events)
    return output.getvalue()
