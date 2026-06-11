"""FastHR AI — grounded chat + slash-commands over HR data."""
from __future__ import annotations

import json
import os

import db

PROVIDER = os.getenv("MODEL_PROVIDER", "xai")
MODEL = os.getenv("MODEL_NAME", "grok-4-1-fast-reasoning")


def snapshot() -> str:
    k = db.kpis()
    by_dept = db.headcount_by_dept()
    lines = [
        "HR SNAPSHOT (synthetic demo data):",
        f"- Headcount {k['headcount']} across {k['depts']} departments. "
        f"Present today {k['present_today']}, on leave {k['on_leave_today']}.",
        f"- 30-day attendance rate {k['attendance_rate']}%. Pending leave requests: {k['pending_leave']}.",
        f"- Latest monthly net payroll: £{k['monthly_payroll']:,.0f}.",
        "Headcount by department: " + ", ".join(f"{d['dept']} {d['n']}" for d in by_dept),
    ]
    return "\n".join(lines)


SYSTEM_PROMPT = """You are the FastHR assistant, embedded in an open-source HR system.
Help HR and managers with headcount, leave, attendance and payroll questions. Be concise;
use Markdown (short tables, bold figures). All data is synthetic — never claim it's real.
Base answers on the HR SNAPSHOT below; if something isn't there, say so."""


def _table(headers, rows_):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows_:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def handle_command(text):
    if not text.startswith("/"):
        return None
    parts = text[1:].split()
    cmd = parts[0].lower() if parts else ""
    arg = " ".join(parts[1:])
    if cmd in ("help", "?"):
        return ("**FastHR shortcuts**\n\n- `/headcount` — by department\n- `/leave` — pending requests\n"
                "- `/today` — who's in / out today\n- `/payroll` — latest run summary\n\nOr ask a question in plain English.")
    if cmd == "headcount":
        return "**Headcount by department**\n\n" + _table(
            ["Department", "People"], [[d["dept"], d["n"]] for d in db.headcount_by_dept()])
    if cmd == "leave":
        r = db.rows("""SELECT e.first_name||' '||e.last_name nm, lr.leave_type, lr.from_date, lr.days
                       FROM leave_requests lr JOIN employees e ON e.id=lr.employee_id
                       WHERE lr.status='Pending' ORDER BY lr.from_date LIMIT 15""")
        if not r:
            return "No pending leave requests. 🎉"
        return "**Pending leave**\n\n" + _table(["Employee", "Type", "From", "Days"],
                                                [[x["nm"], x["leave_type"], x["from_date"], x["days"]] for x in r])
    if cmd == "today":
        r = db.rows("""SELECT a.status, COUNT(*) n FROM attendance a WHERE a.att_date=? GROUP BY a.status""",
                    (db.TODAY.isoformat(),))
        return "**Attendance today**\n\n" + _table(["Status", "Count"], [[x["status"], x["n"]] for x in r])
    if cmd == "payroll":
        per = db.scalar("SELECT MAX(period) FROM payslips")
        tot = db.scalar("SELECT SUM(net) FROM payslips WHERE period=?", (per,)) or 0
        n = db.scalar("SELECT COUNT(*) FROM payslips WHERE period=?", (per,)) or 0
        return f"**Payroll {per}**\n\n{n} payslips · net £{tot:,.0f}"
    return f"Unknown command `/{cmd}`. Try `/help`."


async def stream_chat(message):
    cmd = handle_command(message)
    if cmd is not None:
        yield f"data: {json.dumps({'token': cmd})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        return
    system = SYSTEM_PROMPT + "\n\n" + snapshot()
    try:
        async for tok in _provider_stream(system, message):
            yield f"data: {json.dumps({'token': tok})}\n\n"
    except Exception as e:  # noqa: BLE001
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield f"data: {json.dumps({'done': True})}\n\n"


async def _provider_stream(system, message):
    import httpx
    provider, model = PROVIDER, MODEL
    if provider in ("xai", "openai"):
        url = "https://api.x.ai/v1/chat/completions" if provider == "xai" else "https://api.openai.com/v1/chat/completions"
        key = os.getenv("XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", url, headers={"Authorization": f"Bearer {key}"},
                                     json={"model": model, "stream": True,
                                           "messages": [{"role": "system", "content": system},
                                                        {"role": "user", "content": message}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            tok = json.loads(line[6:])["choices"][0]["delta"].get("content", "")
                            if tok: yield tok
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    elif provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                                     json={"model": model, "max_tokens": 1500, "stream": True, "system": system,
                                           "messages": [{"role": "user", "content": message}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if ev.get("type") == "content_block_delta":
                                tok = ev.get("delta", {}).get("text", "")
                                if tok: yield tok
                        except json.JSONDecodeError:
                            pass
    elif provider == "google":
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}"
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", url, json={"system_instruction": {"parts": [{"text": system}]},
                                                        "contents": [{"role": "user", "parts": [{"text": message}]}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            tok = json.loads(line[6:])["candidates"][0]["content"]["parts"][0].get("text", "")
                            if tok: yield tok
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    else:
        yield "No LLM provider configured. Slash-commands like /headcount work without a key."


def _no_key(provider):
    env = {"xai": "XAI_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY"}[provider]
    return (f"⚠ No **{env}** set, so free-form chat is disabled. Add it to `.env` and restart. "
            "Slash-commands (`/headcount`, `/leave`, `/today`) work without any key.")
