"""LLM shortlist ranking and offer-letter drafting.

Ranking is deliberately *explainable and auditable*: identity fields are stripped
before the model sees anything (plan §4.6), the exclusion list is stored on the
run, and every score carries a written rationale that a recruiter can challenge.

This is the LLM-as-ranker approach chosen over embeddings for now. It is honest
to about 200 candidates per requisition; past that, a vector store becomes
necessary (plan §F5).
"""
from __future__ import annotations

import json
import threading

import db
import talent
from web import llm
from web.cv_extract import _strip_to_json

RANK_PROMPT_KEY = "candidate_ranking"
OFFER_PROMPT_KEY = "offer_letter"

DEFAULT_RANK_PROMPT = """You are helping a hiring team shortlist candidates for a role.

For each candidate you are given an anonymised summary: their current title and
employer, years of experience, skills, and the roles they have held. You are not
given their name, contact details or location, and you must not ask for them.

Score each candidate from 0 to 10 on how well their demonstrated experience fits
the requisition. Judge on:
- Depth in the skills the role actually requires, not keyword overlap.
- Transferable experience: someone from an adjacent domain who has solved the
  same class of problem may be a stronger fit than a literal title match.
- Trajectory: whether their responsibilities have grown.

Be sceptical of seniority claimed in a job title and unsupported by the work
described. Say plainly when a candidate is a poor fit — a flat list of high
scores is useless to a hiring team.

For each candidate give a one-sentence rationale, their main strengths against
this role, and the gaps a hiring manager should probe at interview."""

RANK_OUTPUT = """Return STRICT JSON only — no prose, no fences:

{"rankings": [{"application_id": int, "score": number, "rationale": str,
               "strengths": str, "gaps": str}]}

Include every candidate you were given, exactly once. Scores are 0–10 and may
repeat. Keep rationale under 30 words, strengths and gaps under 20 each."""

DEFAULT_OFFER_PROMPT = """Write a warm, clear offer letter for a successful candidate.

Cover: the role and team they are joining, their start date, their salary, and
what happens next. Keep it to four short paragraphs, address them by first name,
and sign off from the People team.

Be straightforward and human — no corporate throat-clearing, no exclamation
marks, no promises about the company's future. State the facts you are given and
nothing more; never invent a benefit, a bonus, an equity grant or a policy that
was not provided to you."""


def _prompt(key: str, default: str) -> tuple[str, int]:
    row = talent.active_prompt(key)
    if row and (row.get("content") or "").strip():
        return row["content"], row["version"]
    return default, 0


def ensure_prompts():
    for key, default, title in ((RANK_PROMPT_KEY, DEFAULT_RANK_PROMPT, "Candidate ranking"),
                                (OFFER_PROMPT_KEY, DEFAULT_OFFER_PROMPT, "Offer letter")):
        if not talent.active_prompt(key):
            talent.save_prompt(key, default, title=title, updated_by="system")


# --- ranking ----------------------------------------------------------------

def rank_job(job_id: int, *, actor: str = "system") -> dict:
    """Score every active applicant against the requisition. Never raises."""
    job = talent.job(job_id)
    candidates = talent.ranking_input(job_id)
    prompt, version = _prompt(RANK_PROMPT_KEY, DEFAULT_RANK_PROMPT)
    run_id = talent.start_ranking_run(job_id, model=llm.model_name(), prompt_version=version,
                                      n=len(candidates))
    if not candidates:
        talent.save_ranking(run_id, [], error="No active applicants to rank.")
        return {"ok": False, "error": "No active applicants to rank."}
    if not llm.available():
        talent.save_ranking(run_id, [], error=llm.unavailable_reason())
        return {"ok": False, "error": llm.unavailable_reason()}

    brief = (f"ROLE: {job['title']}\nDEPARTMENT: {job['dept'] or '—'}\n"
             f"LOCATION: {job['location'] or '—'} ({job['remote_policy'] or '—'})\n"
             f"REQUIREMENTS: {job['requirements'] or '—'}\n"
             f"DESCRIPTION: {job['description'] or '—'}")
    human = (f"{brief}\n\nCANDIDATES (anonymised):\n"
             f"{json.dumps(candidates, indent=1)[:24000]}")
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        resp = llm.get_llm().invoke([SystemMessage(content=prompt + "\n\n" + RANK_OUTPUT),
                                     HumanMessage(content=human)])
        raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        data = json.loads(_strip_to_json(raw))
        valid_ids = {c["application_id"] for c in candidates}
        scored = [r for r in (data.get("rankings") or [])
                  if isinstance(r, dict) and r.get("application_id") in valid_ids]
        talent.save_ranking(run_id, scored)
        return {"ok": True, "run_id": run_id, "scored": len(scored)}
    except Exception as e:  # noqa: BLE001 — the run row is the error channel
        talent.save_ranking(run_id, [], error=str(e))
        return {"ok": False, "error": str(e)}


def rank_job_async(job_id: int, *, actor: str = "system"):
    threading.Thread(target=rank_job, args=(job_id,), kwargs={"actor": actor},
                     daemon=True).start()


# --- offer letters ----------------------------------------------------------

def draft_letter(offer_id: int) -> str:
    """Generate an offer letter, falling back to a plain template without a key."""
    o = talent.offer(offer_id)
    if not o:
        return ""
    facts = (f"Candidate first name: {o['first_name']}\n"
             f"Role: {o['job_title']}\nTeam: {o['dept'] or 'the team'}\n"
             f"Start date: {o['start_date']}\n"
             f"Salary: {o['currency']} {o['salary']:,.0f} per year\n"
             f"Offer expires: {o['expires_on'] or 'not specified'}")
    if not llm.available():
        return _template_letter(o)
    prompt, _v = _prompt(OFFER_PROMPT_KEY, DEFAULT_OFFER_PROMPT)
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        resp = llm.get_llm().invoke([SystemMessage(content=prompt),
                                     HumanMessage(content=f"FACTS:\n{facts}")])
        return resp.content if isinstance(resp.content, str) else _template_letter(o)
    except Exception:  # noqa: BLE001 — a letter must always be produced
        return _template_letter(o)


def _template_letter(o: dict) -> str:
    return (f"Dear {o['first_name']},\n\n"
            f"We are delighted to offer you the role of {o['job_title']} in "
            f"{o['dept'] or 'our team'}, starting on {o['start_date']}.\n\n"
            f"Your salary will be {o['currency']} {o['salary']:,.0f} per year, reviewed "
            f"annually. You will report to the hiring manager for this requisition, and we "
            f"will be in touch before your start date with everything you need for day one.\n\n"
            + (f"This offer is open until {o['expires_on']}. " if o["expires_on"] else "")
            + "Please let us know if you have any questions at all.\n\n"
            "With best wishes,\nThe People team")
