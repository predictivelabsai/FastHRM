"""Third-party connections — job boards, social, calendar, messaging, e-sign.

Secrets are encrypted at rest with Fernet, using a key derived from
``FASTHR_SECRET``, and are never returned to the browser in full: the UI only
ever sees a masked hint (last four characters).

Every provider is optional. With none configured the product works exactly as it
does today — each connector has a null implementation, so a missing integration
degrades to "not configured" rather than to an error.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

import db

# --- provider catalogue -----------------------------------------------------

CATEGORIES = ["job_board", "social", "calendar", "messaging", "esign", "screening", "hris"]

PROVIDERS = [
    # key,            label,                 category,     key_label,        secret_label,   docs
    ("linkedin",      "LinkedIn Talent",     "job_board",  "Client ID",      "Client secret",
     "Post jobs to LinkedIn and import applicants and profile data."),
    ("indeed",        "Indeed",              "job_board",  "Publisher ID",   "API key",
     "Syndicate open requisitions to Indeed and pull applications back."),
    ("totaljobs",     "Totaljobs",           "job_board",  "Account ID",     "API key",
     "Publish to Totaljobs and receive applicant webhooks."),
    ("greenhouse",    "Greenhouse Harvest",  "job_board",  "Harvest API key", "",
     "Two-way sync with an existing Greenhouse pipeline."),
    ("xing",          "XING",                "social",     "Consumer key",   "Consumer secret",
     "Reach DACH candidates and import XING profiles."),
    ("github",        "GitHub",              "social",     "Personal token", "",
     "Enrich engineering candidates with public repository activity."),
    ("google_calendar", "Google Calendar",   "calendar",   "Client ID",      "Client secret",
     "Book interview slots and write invites to interviewer calendars."),
    ("ms_graph",      "Microsoft 365",       "calendar",   "Application ID", "Client secret",
     "Outlook calendar booking and Teams meeting links."),
    ("slack",         "Slack",               "messaging",  "Bot token",      "Signing secret",
     "Post pipeline digests and approval requests into channels."),
    ("teams",         "Microsoft Teams",     "messaging",  "Webhook URL",    "",
     "Send hiring and leave notifications to a Teams channel."),
    ("docusign",      "DocuSign",            "esign",      "Integration key", "Secret key",
     "Send offer letters and contracts for signature."),
    ("checkr",        "Checkr",              "screening",  "API key",        "",
     "Run right-to-work and background checks on accepted offers."),
    ("bamboohr",      "BambooHR",            "hris",       "Subdomain",      "API key",
     "Export employee records to an existing HRIS of record."),
]

PROVIDER_BY_KEY = {p[0]: p for p in PROVIDERS}
CATEGORY_LABELS = {
    "job_board": "Job boards", "social": "Social & sourcing", "calendar": "Calendar",
    "messaging": "Messaging", "esign": "E-signature", "screening": "Background screening",
    "hris": "HRIS export",
}


def provider_meta(key: str) -> dict:
    p = PROVIDER_BY_KEY.get(key)
    if not p:
        return {"key": key, "label": key.title(), "category": "other",
                "key_label": "API key", "secret_label": "", "blurb": ""}
    return {"key": p[0], "label": p[1], "category": p[2], "key_label": p[3],
            "secret_label": p[4], "blurb": p[5]}


# --- secret handling --------------------------------------------------------

def _fernet():
    """Fernet built from FASTHR_SECRET.

    The secret is stretched with SHA-256 so any length of configured secret
    yields a valid 32-byte key.
    """
    from cryptography.fernet import Fernet
    secret = os.getenv("FASTHR_SECRET") or "fasthr-development-secret"
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt(value: str) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str:
    """Plaintext secret, for use by a connector at call time — never for display."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:  # noqa: BLE001 — a rotated FASTHR_SECRET invalidates old tokens
        return ""


def mask(token: str | None) -> str:
    """What the UI is allowed to show: the last four characters, nothing more."""
    plain = decrypt(token)
    if not plain:
        return ""
    return ("•" * max(4, min(16, len(plain) - 4))) + plain[-4:]


# --- reads ------------------------------------------------------------------

def all_integrations() -> list[dict]:
    """Every known provider, joined to its stored row if it has one."""
    stored = {r["provider"]: r for r in db.rows("SELECT * FROM integrations")}
    out = []
    for key, label, category, key_label, secret_label, blurb in PROVIDERS:
        row = stored.get(key) or {}
        out.append({
            "provider": key, "label": label, "category": category,
            "key_label": key_label, "secret_label": secret_label, "blurb": blurb,
            "id": row.get("id"),
            "status": row.get("status") or "Not configured",
            "account_ref": row.get("account_ref") or "",
            "auto_sync": bool(row.get("auto_sync")),
            "key_hint": mask(row.get("api_key_enc")),
            "secret_hint": mask(row.get("api_secret_enc")),
            "last_test_at": row.get("last_test_at"),
            "last_test_ok": row.get("last_test_ok"),
            "last_test_note": row.get("last_test_note"),
            "last_sync_at": row.get("last_sync_at"),
        })
    return out


def integration(provider: str) -> dict | None:
    return db.one("SELECT * FROM integrations WHERE provider=?", (provider,))


def by_category() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for i in all_integrations():
        grouped.setdefault(i["category"], []).append(i)
    return grouped


def connected(provider: str) -> bool:
    row = integration(provider)
    return bool(row and row["status"] == "Connected")


def kpis() -> dict:
    rows_ = all_integrations()
    return {
        "total": len(rows_),
        "connected": sum(1 for r in rows_ if r["status"] == "Connected"),
        "error": sum(1 for r in rows_ if r["status"] == "Error"),
        "unconfigured": sum(1 for r in rows_ if r["status"] == "Not configured"),
    }


def events(provider: str | None = None, limit: int = 40):
    if provider:
        return db.rows("""SELECT e.*, i.provider FROM integration_events e
                          JOIN integrations i ON i.id=e.integration_id
                          WHERE i.provider=? ORDER BY e.id DESC LIMIT ?""", (provider, limit))
    return db.rows("""SELECT e.*, i.provider FROM integration_events e
                      LEFT JOIN integrations i ON i.id=e.integration_id
                      ORDER BY e.id DESC LIMIT ?""", (limit,))


# --- writes -----------------------------------------------------------------

def save(provider: str, *, api_key: str = "", api_secret: str = "", account_ref: str = "",
         auto_sync: bool = False, config: dict | None = None, actor: str = "") -> dict:
    """Store credentials. Blank key/secret fields leave the stored value alone,
    so re-saving the form without retyping a secret does not wipe it."""
    meta = provider_meta(provider)
    existing = integration(provider)
    key_enc = encrypt(api_key) if api_key else (existing or {}).get("api_key_enc")
    sec_enc = encrypt(api_secret) if api_secret else (existing or {}).get("api_secret_enc")
    status = "Connected" if key_enc else "Not configured"
    cfg = json.dumps(config) if config else (existing or {}).get("config_json")

    with db.cursor() as conn:
        if existing:
            conn.execute("""UPDATE integrations SET label=?, category=?, api_key_enc=?,
                                api_secret_enc=?, account_ref=?, auto_sync=?, config_json=?,
                                status=CASE WHEN status='Disabled' THEN 'Disabled' ELSE ? END,
                                updated=datetime('now')
                            WHERE provider=?""",
                         (meta["label"], meta["category"], key_enc, sec_enc, account_ref,
                          1 if auto_sync else 0, cfg, status, provider))
            iid = existing["id"]
        else:
            cur = conn.execute("""INSERT INTO integrations
                                  (provider,label,category,status,api_key_enc,api_secret_enc,
                                   account_ref,auto_sync,config_json,created,updated)
                                  VALUES (?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                               (provider, meta["label"], meta["category"], status, key_enc,
                                sec_enc, account_ref, 1 if auto_sync else 0, cfg))
            iid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_event(iid, "config", True, f"Credentials saved by {actor or 'admin'}", actor=actor)
    return {"id": iid, "status": status}


def set_status(provider: str, status: str, *, actor: str = "") -> bool:
    row = integration(provider)
    if not row:
        return False
    with db.cursor() as conn:
        conn.execute("UPDATE integrations SET status=?, updated=datetime('now') WHERE provider=?",
                     (status, provider))
    log_event(row["id"], "config", True, f"Status set to {status}", actor=actor)
    return True


def disconnect(provider: str, *, actor: str = "") -> bool:
    """Forget the credentials entirely — the safe default for 'remove'."""
    row = integration(provider)
    if not row:
        return False
    with db.cursor() as conn:
        conn.execute("""UPDATE integrations SET api_key_enc=NULL, api_secret_enc=NULL,
                            account_ref='', status='Not configured', last_test_ok=NULL,
                            last_test_note=NULL, updated=datetime('now')
                        WHERE provider=?""", (provider,))
    log_event(row["id"], "config", True, "Disconnected; stored credentials erased", actor=actor)
    return True


def log_event(integration_id: int, kind: str, ok: bool, detail: str,
              *, records: int = 0, actor: str = ""):
    with db.cursor() as conn:
        conn.execute("""INSERT INTO integration_events
                        (integration_id,kind,ok,detail,records,actor,created)
                        VALUES (?,?,?,?,?,?,datetime('now'))""",
                     (integration_id, kind, 1 if ok else 0, detail, records, actor))


# --- connectors -------------------------------------------------------------
#
# Each provider has a null implementation: without credentials it reports "not
# configured" rather than raising, so the product is fully usable with nothing
# connected. Live API calls are the next step — the credential store, the audit
# trail and the call sites are what this slice puts in place.

def test_connection(provider: str, *, actor: str = "") -> dict:
    """Check that credentials are present and well-formed.

    This validates what can be validated locally; it deliberately does not call
    the provider yet, and says so, rather than reporting a green tick that has
    not been earned.
    """
    row = integration(provider)
    meta = provider_meta(provider)
    if not row or not row["api_key_enc"]:
        return {"ok": False, "note": f"No {meta['key_label'].lower()} stored for {meta['label']}."}

    key = decrypt(row["api_key_enc"])
    if not key:
        note = ("Stored credential could not be decrypted — FASTHR_SECRET has changed "
                "since it was saved. Re-enter the key.")
        ok = False
    elif len(key) < 8:
        note = f"{meta['key_label']} looks too short to be valid ({len(key)} characters)."
        ok = False
    elif meta["secret_label"] and not row["api_secret_enc"]:
        note = f"{meta['label']} also needs a {meta['secret_label'].lower()}."
        ok = False
    else:
        note = (f"Credentials stored and readable ({mask(row['api_key_enc'])}). "
                f"Live {meta['label']} calls are not enabled in this build.")
        ok = True

    with db.cursor() as conn:
        conn.execute("""UPDATE integrations SET last_test_at=datetime('now'), last_test_ok=?,
                            last_test_note=?, status=? WHERE provider=?""",
                     (1 if ok else 0, note, "Connected" if ok else "Error", provider))
    log_event(row["id"], "test", ok, note, actor=actor)
    return {"ok": ok, "note": note}


def sync(provider: str, *, actor: str = "") -> dict:
    """Placeholder sync: records the attempt and reports honestly."""
    row = integration(provider)
    meta = provider_meta(provider)
    if not row or row["status"] != "Connected":
        return {"ok": False, "note": f"{meta['label']} is not connected."}
    note = (f"No live {meta['label']} connector in this build — nothing was fetched. "
            "The credential store and audit trail are ready for one.")
    with db.cursor() as conn:
        conn.execute("UPDATE integrations SET last_sync_at=datetime('now') WHERE provider=?", (provider,))
    log_event(row["id"], "sync", False, note, actor=actor)
    return {"ok": False, "note": note}
