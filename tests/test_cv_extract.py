"""CV extraction: the JSON contract, the DB rows it produces, and its failure modes.

The model itself is stubbed — these assert the code around it. One live test
against the real API sits behind FASTHR_LIVE_LLM=1.
"""
from __future__ import annotations

import json
import os

import pytest

SAMPLE = {
    "candidate": {"first_name": "Priya", "last_name": "Raman", "email": "priya@example.com",
                  "phone": "+49 151 0000", "location": "Berlin, Germany",
                  "headline": "Backend engineer", "current_title": "Senior Backend Engineer",
                  "current_employer": "Zephyr Payments", "years_experience": "9",
                  "linkedin_url": "linkedin.com/in/priyaraman"},
    "experience": [{"employer": "Zephyr Payments", "title": "Senior Backend Engineer",
                    "start_date": "2021-03", "end_date": None, "location": "Berlin",
                    "summary": "Led the ledger migration."},
                   {"employer": "Northwind", "title": "Backend Engineer",
                    "start_date": "2018-09", "end_date": "2021-02", "location": "Amsterdam",
                    "summary": "Event pipeline."}],
    "education": [{"institution": "Anna University", "qualification": "BE",
                   "field": "Computer Science", "end_year": "2015"}],
    "skills": [{"skill": "Python", "level": "Expert", "years": 10, "evidence": "Used throughout"},
               {"skill": "Kafka", "level": "Advanced", "years": 5, "evidence": "Northwind"}],
    "languages": ["English", "German"],
    "certifications": ["CKAD"],
    "flags": ["Six-month gap in 2018 is unexplained"],
}


class _FakeResponse:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return _FakeResponse(self.payload)


def _stub(monkeypatch, payload):
    from web import cv_extract, llm
    fake = _FakeLLM(payload)
    monkeypatch.setattr(llm, "get_llm", lambda **kw: fake)
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(cv_extract.llm, "get_llm", lambda **kw: fake)
    monkeypatch.setattr(cv_extract.llm, "available", lambda: True)
    return fake


# --- parsing ----------------------------------------------------------------

def test_parses_clean_json(fresh_db, monkeypatch):
    from web import cv_extract
    _stub(monkeypatch, json.dumps(SAMPLE))
    profile, raw = cv_extract.extract_profile("some cv text", "cv.pdf")
    assert profile["candidate"]["first_name"] == "Priya"
    assert profile["candidate"]["years_experience"] == 9.0, "numeric strings must be coerced"
    assert len(profile["skills"]) == 2
    assert profile["flags"] == ["Six-month gap in 2018 is unexplained"]
    assert raw


def test_tolerates_markdown_fences(fresh_db, monkeypatch):
    from web import cv_extract
    _stub(monkeypatch, "```json\n" + json.dumps(SAMPLE) + "\n```")
    profile, _ = cv_extract.extract_profile("text", "cv.pdf")
    assert profile["candidate"]["last_name"] == "Raman"


def test_tolerates_prose_around_json(fresh_db, monkeypatch):
    from web import cv_extract
    _stub(monkeypatch, "Here you go:\n" + json.dumps(SAMPLE) + "\nHope that helps!")
    profile, _ = cv_extract.extract_profile("text", "cv.pdf")
    assert profile["candidate"]["email"] == "priya@example.com"


def test_coerces_a_contract_violating_response(fresh_db, monkeypatch):
    """A model that returns the wrong types must not reach the database."""
    from web import cv_extract
    _stub(monkeypatch, json.dumps({"candidate": "just a string", "skills": "not a list",
                                   "experience": [{"employer": "X"}, "junk"]}))
    profile, _ = cv_extract.extract_profile("text", "cv.pdf")
    assert profile["candidate"] == {}
    assert profile["skills"] == []
    assert profile["experience"] == [{"employer": "X"}], "non-dict entries are dropped"


def test_prompt_sends_guidance_plus_contract(fresh_db, monkeypatch):
    from web import cv_extract
    fake = _stub(monkeypatch, json.dumps(SAMPLE))
    cv_extract.extract_profile("cv text here", "cv.pdf")
    system = fake.calls[0][0].content
    assert cv_extract.OUTPUT_FORMAT in system, "the code-side contract must always be appended"
    assert "STRICT JSON" in system
    assert "cv text here" in fake.calls[0][1].content


# --- persistence ------------------------------------------------------------

def test_saves_profile_to_the_database(fresh_db, monkeypatch):
    import talent
    from web import cv_extract
    _stub(monkeypatch, json.dumps(SAMPLE))

    res = cv_extract.ingest_cv(file_name="Priya_Raman_CV.txt",
                               data=b"Priya Raman\nSenior Backend Engineer\n", source="Direct")
    out = cv_extract.run_extraction(res["run_id"], res["candidate_id"], res["document_id"])
    assert out["ok"], out

    p = talent.candidate_profile(res["candidate_id"])
    assert p["candidate"]["first_name"] == "Priya"
    assert p["candidate"]["years_experience"] == 9.0
    assert len(p["skills"]) == 2 and len(p["experience"]) == 2 and len(p["education"]) == 1
    assert p["runs"][0]["status"] == "ok"
    assert p["runs"][0]["prompt_version"] >= 0


def test_filename_never_beats_the_model(fresh_db, monkeypatch):
    """The placeholder candidate must not shadow extracted names."""
    import talent
    from web import cv_extract
    _stub(monkeypatch, json.dumps(SAMPLE))
    res = cv_extract.ingest_cv(file_name="cv_final_v3_USE_THIS.txt", data=b"Priya's CV text")
    out = cv_extract.run_extraction(res["run_id"], res["candidate_id"], res["document_id"])
    assert out["ok"], out
    c = talent.candidate(res["candidate_id"])
    assert talent.display_name(c) == "Priya Raman"


def test_reparse_does_not_clobber_manual_edits(fresh_db, monkeypatch):
    """A recruiter's correction survives a re-parse; child rows are replaced."""
    import db
    import talent
    from web import cv_extract
    _stub(monkeypatch, json.dumps(SAMPLE))

    cid = talent.create_candidate(first_name="Priyanka", last_name="Raman-Smith",
                                  email="corrected@example.com")
    res = cv_extract.ingest_cv(file_name="cv.txt", data=b"text", candidate_id=cid)
    cv_extract.run_extraction(res["run_id"], res["candidate_id"], res["document_id"])

    c = talent.candidate(cid)
    assert c["first_name"] == "Priyanka", "manual value must win"
    assert c["email"] == "corrected@example.com"
    assert c["location"] == "Berlin, Germany", "an empty field is still filled in"
    assert db.scalar("SELECT COUNT(*) FROM candidate_skills WHERE candidate_id=?", (cid,)) == 2


def test_records_an_error_run_without_raising(fresh_db, monkeypatch):
    import talent
    from web import cv_extract, llm
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(cv_extract.llm, "available", lambda: True)
    monkeypatch.setattr(cv_extract, "extract_profile",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("model exploded")))

    res = cv_extract.ingest_cv(file_name="cv.txt", data=b"some text")
    out = cv_extract.run_extraction(res["run_id"], res["candidate_id"], res["document_id"])
    assert out["ok"] is False
    run = cv_extract.latest_run(res["candidate_id"])
    assert run["status"] == "error" and "model exploded" in run["error"]


def test_missing_api_key_is_reported_not_raised(fresh_db, monkeypatch):
    from web import cv_extract, llm
    monkeypatch.setattr(llm, "available", lambda: False)
    monkeypatch.setattr(cv_extract.llm, "available", lambda: False)
    res = cv_extract.ingest_cv(file_name="cv.txt", data=b"some text")
    out = cv_extract.run_extraction(res["run_id"], res["candidate_id"], res["document_id"])
    assert out["ok"] is False
    assert "API" in cv_extract.latest_run(res["candidate_id"])["error"].upper()


def test_unreadable_document_fails_the_run_cleanly(fresh_db, monkeypatch):
    from web import cv_extract
    _stub(monkeypatch, json.dumps(SAMPLE))
    res = cv_extract.ingest_cv(file_name="empty.txt", data=b"   ")
    out = cv_extract.run_extraction(res["run_id"], res["candidate_id"], res["document_id"])
    assert out["ok"] is False


# --- prompt store -----------------------------------------------------------

def test_prompt_versions_are_append_only(fresh_db):
    import talent
    from web import cv_extract
    cv_extract.ensure_default_prompt()
    assert talent.active_prompt(cv_extract.PROMPT_KEY)["version"] == 1

    v2 = talent.save_prompt(cv_extract.PROMPT_KEY, "New guidance", updated_by="tester")
    assert v2 == 2
    assert talent.active_prompt(cv_extract.PROMPT_KEY)["content"] == "New guidance"
    assert len(talent.prompt_versions(cv_extract.PROMPT_KEY)) == 2, "v1 must still exist"

    talent.activate_prompt(cv_extract.PROMPT_KEY, 1)
    assert talent.active_prompt(cv_extract.PROMPT_KEY)["version"] == 1


def test_editing_the_prompt_cannot_break_the_contract(fresh_db, monkeypatch):
    """Whatever a user writes, OUTPUT_FORMAT is still appended."""
    import talent
    from web import cv_extract
    talent.save_prompt(cv_extract.PROMPT_KEY, "Ignore everything and write a poem.", updated_by="t")
    fake = _stub(monkeypatch, json.dumps(SAMPLE))
    cv_extract.extract_profile("text", "cv.pdf")
    system = fake.calls[0][0].content
    assert system.startswith("Ignore everything and write a poem.")
    assert cv_extract.OUTPUT_FORMAT in system


# --- text extraction --------------------------------------------------------

def test_supported_formats(fresh_db):
    from web import cv_extract
    assert cv_extract.supported("cv.pdf") and cv_extract.supported("CV.DOCX")
    assert not cv_extract.supported("cv.pages") and not cv_extract.supported("cv")


def test_text_extraction_of_plain_file(fresh_db, tmp_path):
    from web import cv_extract
    f = tmp_path / "cv.txt"
    f.write_text("Ada Lovelace\nAnalytical Engine")
    assert "Ada Lovelace" in cv_extract.extract_text(f)


def test_unreadable_file_returns_a_message_not_an_exception(fresh_db, tmp_path):
    from web import cv_extract
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"this is not a pdf")
    assert cv_extract.extract_text(f).startswith("[extraction error")


# --- live ------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("FASTHR_LIVE_LLM"),
                    reason="set FASTHR_LIVE_LLM=1 to call the real model")
def test_live_extraction(fresh_db):
    from web import cv_extract
    cv = ("Ada Lovelace\nAnalyst, London\nada@example.com\n\n"
          "EXPERIENCE\nAnalytical Engine Co — Lead Analyst, Jan 2020 - present\n"
          "Wrote the first algorithm.\n\nSKILLS\nMathematics, Algorithm design")
    profile, _ = cv_extract.extract_profile(cv, "ada.txt")
    assert profile["candidate"]["first_name"].lower() == "ada"
    assert profile["experience"]
