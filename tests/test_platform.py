"""Hire conversion, integrations secret handling, and the lifecycle state machines."""
from __future__ import annotations

import json

import pytest


def _org(db):
    """A minimal org: one department, a manager, and a requisition."""
    with db.cursor() as conn:
        conn.execute("INSERT INTO departments(name) VALUES ('Engineering')")
        did = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("""INSERT INTO employees(code,first_name,last_name,email,dept_id,designation,
                            status,date_of_joining,base_salary)
                        VALUES ('EMP-1001','Ada','Lovelace','ada@x.com',?,'Engineering Manager',
                                'Active','2020-01-01',90000)""", (did,))
        mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("""INSERT INTO job_openings(code,title,dept_id,hiring_manager_id,headcount,
                            filled,comp_min,comp_max,status,opened_on,created)
                        VALUES ('REQ-1','Backend Engineer',?,?,1,0,60000,90000,'Open',
                                '2026-01-01',datetime('now'))""", (did, mid))
        jid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return did, mid, jid


# --- hire conversion (plan §A3/§4.7) ---------------------------------------

def test_accepting_an_offer_creates_an_employee(fresh_db):
    import talent
    import people
    did, mid, jid = _org(fresh_db)

    cid = talent.create_candidate(first_name="Grace", last_name="Hopper",
                                  email="grace@example.com", location="London")
    with fresh_db.cursor() as conn:
        conn.execute("""INSERT INTO candidate_skills(candidate_id,skill,level,years,source)
                        VALUES (?,'COBOL','Expert',20,'cv-extraction'),
                               (?,'Compilers','Expert',15,'cv-extraction')""", (cid, cid))
    aid = talent.apply_to_job(cid, jid)
    oid = talent.draft_offer(aid, salary=82000, start_date="2026-09-01")

    res = talent.set_offer_status(oid, "Accepted", actor="tester")
    assert res["ok"], res

    emp = fresh_db.one("SELECT * FROM employees WHERE candidate_id=?", (cid,))
    assert emp is not None, "no employee record was created"
    assert emp["first_name"] == "Grace" and emp["base_salary"] == 82000
    assert emp["designation"] == "Backend Engineer"
    assert emp["manager_id"] == mid, "should report to the hiring manager"
    assert emp["status"] == "Probation"
    assert emp["date_of_joining"] == "2026-09-01"

    # the people graph: skills follow the person
    assert fresh_db.scalar("SELECT COUNT(*) FROM employee_skills WHERE employee_id=?",
                           (emp["id"],)) == 2
    # leave allocated, onboarding started, requisition filled, application closed
    assert fresh_db.scalar("SELECT COUNT(*) FROM leave_balances WHERE employee_id=?",
                           (emp["id"],)) == 3
    assert len(people.onboarding_tasks(emp["id"])) == len(people.DEFAULT_ONBOARDING)
    job = talent.job(jid)
    assert job["filled"] == 1 and job["status"] == "Filled"
    assert fresh_db.one("SELECT stage FROM applications WHERE id=?", (aid,))["stage"] == "Hired"
    assert talent.candidate(cid)["status"] == "Hired"


def test_hire_is_idempotent(fresh_db):
    import talent
    _org(fresh_db)
    jid = fresh_db.scalar("SELECT id FROM job_openings LIMIT 1")
    cid = talent.create_candidate(first_name="Alan", last_name="Turing")
    aid = talent.apply_to_job(cid, jid)
    oid = talent.draft_offer(aid, salary=70000, start_date="2026-09-01")

    first = talent.hire(oid)
    second = talent.hire(oid)
    assert second["employee_id"] == first["employee_id"]
    assert fresh_db.scalar("SELECT COUNT(*) FROM employees WHERE candidate_id=?", (cid,)) == 1


def test_declining_an_offer_rejects_the_application(fresh_db):
    import talent
    _org(fresh_db)
    jid = fresh_db.scalar("SELECT id FROM job_openings LIMIT 1")
    cid = talent.create_candidate(first_name="Katherine", last_name="Johnson")
    aid = talent.apply_to_job(cid, jid)
    oid = talent.draft_offer(aid, salary=70000, start_date="2026-09-01")

    talent.set_offer_status(oid, "Declined", reason="Accepted another offer")
    app = fresh_db.one("SELECT * FROM applications WHERE id=?", (aid,))
    assert app["stage"] == "Rejected" and app["rejection_reason"] == "Accepted another offer"
    assert fresh_db.scalar("SELECT COUNT(*) FROM employees WHERE candidate_id=?", (cid,)) == 0


# --- integrations: secrets must never be stored or shown in the clear ------

def test_api_key_is_encrypted_at_rest(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)

    integrations.save("linkedin", api_key="li_live_supersecret_1234", api_secret="shh_9999",
                      account_ref="acme", actor="tester")
    row = integrations.integration("linkedin")

    assert "li_live_supersecret_1234" not in (row["api_key_enc"] or ""), "key stored in the clear"
    assert "shh_9999" not in (row["api_secret_enc"] or ""), "secret stored in the clear"
    assert integrations.decrypt(row["api_key_enc"]) == "li_live_supersecret_1234"
    assert row["status"] == "Connected"


def test_masking_reveals_only_the_last_four(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)

    integrations.save("slack", api_key="xoxb-abcdefghijkl-9876", actor="t")
    hint = integrations.mask(integrations.integration("slack")["api_key_enc"])
    assert hint.endswith("9876")
    assert "abcdefghijkl" not in hint
    assert hint.count("•") >= 4


def test_blank_field_keeps_the_existing_secret(fresh_db, monkeypatch):
    """Re-saving the form without retyping a key must not wipe it."""
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)

    integrations.save("indeed", api_key="original-key-1111", actor="t")
    integrations.save("indeed", api_key="", account_ref="updated-account", actor="t")
    row = integrations.integration("indeed")
    assert integrations.decrypt(row["api_key_enc"]) == "original-key-1111"
    assert row["account_ref"] == "updated-account"


def test_disconnect_erases_credentials(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)

    integrations.save("docusign", api_key="k-1234567890", api_secret="s-1234", actor="t")
    integrations.disconnect("docusign", actor="t")
    row = integrations.integration("docusign")
    assert row["api_key_enc"] is None and row["api_secret_enc"] is None
    assert row["status"] == "Not configured"


def test_rotated_secret_is_reported_not_silently_wrong(fresh_db, monkeypatch):
    """A changed FASTHR_SECRET must surface as an error, not a false green tick."""
    monkeypatch.setenv("FASTHR_SECRET", "original-secret")
    import importlib
    import integrations
    importlib.reload(integrations)
    integrations.save("checkr", api_key="checkr-key-abcdef", actor="t")

    monkeypatch.setenv("FASTHR_SECRET", "rotated-secret")
    importlib.reload(integrations)
    result = integrations.test_connection("checkr", actor="t")
    assert result["ok"] is False
    assert "FASTHR_SECRET" in result["note"]


def test_untested_connector_does_not_claim_a_live_connection(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)
    integrations.save("linkedin", api_key="li_key_12345678", api_secret="sec_1234", actor="t")
    note = integrations.test_connection("linkedin", actor="t")["note"]
    assert "not enabled" in note.lower(), "must not imply a live API call was made"


# --- lifecycle state machines ----------------------------------------------

def test_change_approval_writes_to_the_employee(fresh_db):
    import people
    did, mid, _ = _org(fresh_db)
    chg = people.propose_change(mid, change_type="Promotion", effective_date="2026-10-01",
                                to_values={"designation": "Director of Engineering",
                                           "base_salary": 120000}, actor="t")
    emp_before = fresh_db.one("SELECT * FROM employees WHERE id=?", (mid,))
    assert emp_before["designation"] == "Engineering Manager", "must not apply before approval"

    people.apply_change(chg, actor="approver")
    emp = fresh_db.one("SELECT * FROM employees WHERE id=?", (mid,))
    assert emp["designation"] == "Director of Engineering" and emp["base_salary"] == 120000
    assert fresh_db.one("SELECT * FROM employee_changes WHERE id=?", (chg,))["status"] == "Applied"
    assert fresh_db.one("""SELECT decision FROM approvals WHERE entity_type='employee_change'
                           AND entity_id=?""", (chg,))["decision"] == "Approved"


def test_rejected_change_leaves_the_record_alone(fresh_db):
    import people
    _did, mid, _ = _org(fresh_db)
    chg = people.propose_change(mid, change_type="Salary change", effective_date="2026-10-01",
                                to_values={"base_salary": 999999}, actor="t")
    people.reject_change(chg, actor="approver")
    assert fresh_db.one("SELECT base_salary FROM employees WHERE id=?", (mid,))["base_salary"] == 90000


def test_change_cannot_write_arbitrary_columns(fresh_db):
    """Only whitelisted fields may be changed — a payload cannot rewrite anything."""
    import people
    _did, mid, _ = _org(fresh_db)
    chg = people.propose_change(mid, change_type="Role change", effective_date="2026-10-01",
                                to_values={"code": "HACKED", "email": "evil@x.com"}, actor="t")
    res = people.apply_change(chg, actor="t")
    assert res["ok"] is False
    emp = fresh_db.one("SELECT * FROM employees WHERE id=?", (mid,))
    assert emp["code"] == "EMP-1001" and emp["email"] == "ada@x.com"


def test_completing_a_separation_makes_an_alumnus(fresh_db):
    import people
    _did, mid, _ = _org(fresh_db)
    sid = people.start_separation(mid, kind="Resignation", notice_date="2026-08-01",
                                  last_day="2026-09-30", reason="New role", actor="t")
    for idx in range(len(people.EXIT_CHECKLIST)):
        people.toggle_exit_task(sid, idx, actor="t")

    sep = people.separation(sid)
    assert sep["status"] == "Complete"
    emp = fresh_db.one("SELECT * FROM employees WHERE id=?", (mid,))
    assert emp["status"] == "Inactive" and emp["alumni"] == 1
    assert emp["termination_date"] == "2026-09-30"
    assert any(a["id"] == mid for a in people.alumni())


def test_goal_checkin_completes_on_target(fresh_db):
    import people
    _org(fresh_db)
    gid = people.create_goal(title="Ship it", owner_type="company", metric="%", target=100,
                             actor="t")
    people.checkin(gid, value=45, actor="t")
    assert people.goal(gid)["status"] == "On track"
    assert people.goal_progress(people.goal(gid)) == 45

    people.checkin(gid, value=100, actor="t")
    assert people.goal(gid)["status"] == "Complete"
    assert len(people.checkins(gid)) == 2


def test_onboarding_is_not_duplicated(fresh_db):
    import people
    _did, mid, _ = _org(fresh_db)
    assert people.start_onboarding(mid, actor="t") == len(people.DEFAULT_ONBOARDING)
    assert people.start_onboarding(mid, actor="t") == 0
    assert len(people.onboarding_tasks(mid)) == len(people.DEFAULT_ONBOARDING)


def test_scorecard_sets_the_application_rating(fresh_db):
    import talent
    _org(fresh_db)
    jid = fresh_db.scalar("SELECT id FROM job_openings LIMIT 1")
    mid = fresh_db.scalar("SELECT id FROM employees LIMIT 1")
    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO competencies(name,category) VALUES ('Delivery','Delivery')")
        c1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO competencies(name,category) VALUES ('Communication','Collab')")
        c2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    cid = talent.create_candidate(first_name="Jean", last_name="Bartik")
    aid = talent.apply_to_job(cid, jid)
    iv = talent.schedule_interview(aid, interviewer_id=mid, kind="Technical",
                                   scheduled_at="2026-08-01 10:00")
    talent.record_scorecard(iv, {c1: 5, c2: 3}, recommendation="Hire", actor="t")

    app = fresh_db.one("SELECT * FROM applications WHERE id=?", (aid,))
    assert app["rating"] == 4.0, "rating is the mean of completed scorecards"
    assert fresh_db.one("SELECT status FROM interviews WHERE id=?", (iv,))["status"] == "Completed"


def test_ranking_input_excludes_identity_fields(fresh_db):
    """The bias guard: the ranker must never receive identifying fields."""
    import talent
    _org(fresh_db)
    jid = fresh_db.scalar("SELECT id FROM job_openings LIMIT 1")
    cid = talent.create_candidate(first_name="Distinctive", last_name="Surname",
                                  email="distinctive@example.com", location="Lagos, Nigeria")
    talent.apply_to_job(cid, jid)

    payload = json.dumps(talent.ranking_input(jid))
    for leaked in ("Distinctive", "Surname", "distinctive@example.com", "Lagos"):
        assert leaked not in payload, f"{leaked} leaked into the ranking input"


def test_attrition_signals_always_carry_their_reasons(fresh_db):
    import people
    _org(fresh_db)
    for r in people.attrition_signals():
        assert r["factors"], "a flag without factors is an unexplained score"
        assert r["score"] >= 3
