"""Hire conversion, integrations secret handling, and the lifecycle state machines."""
from __future__ import annotations

import json
import calendar

import pytest


def test_granular_rbac_defaults_and_admin_bypass(fresh_db):
    from web.rbac import can, permissions_for

    assert can({"hrbp"}, "employees")
    assert not can({"recruiter"}, "payroll")
    assert can({"recruiter"}, "payroll", "edit") is False
    assert can({"admin"}, "roles", "edit")
    assert permissions_for({"admin"})["dashboard"] == {"view": True, "edit": True}


def test_granular_rbac_denial_and_toggle(fresh_db):
    import web_app
    from web.rbac import can

    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO account_roles(account_email,role,scope,created) "
                     "VALUES ('recruiter@example.com','recruiter','all',datetime('now'))")
    session = {"user": "recruiter@example.com"}
    built = []
    denied = web_app._guard(session, "payroll", lambda: built.append(True))
    assert not built and "secret" not in str(denied)
    assert not can({"recruiter"}, "payroll")

    with fresh_db.cursor() as conn:
        conn.execute("UPDATE role_permissions SET can_view=1 "
                     "WHERE role_name='recruiter' AND module_key='payroll'")
    assert can({"recruiter"}, "payroll")
    with fresh_db.cursor() as conn:
        conn.execute("UPDATE role_permissions SET can_view=0 "
                     "WHERE role_name='recruiter' AND module_key='payroll'")
    assert not can({"recruiter"}, "payroll")


def test_roles_settings_is_bilingual_and_requires_login(fresh_db):
    from starlette.responses import RedirectResponse
    import web_app
    from web import settings

    assert "Vaata" in str(settings.roles_page(lang="et"))
    assert "View" in str(settings.roles_page(lang="en"))
    response = web_app._guard({}, "roles", settings.roles_page)
    assert isinstance(response, RedirectResponse)
    assert "/login" in response.headers["location"]


def _statutory_employee(db):
    with db.cursor() as conn:
        conn.execute("""INSERT INTO employees(first_name,last_name,status,date_of_joining,
                        employment_type,base_salary,personal_code,working_time_ratio,
                        latest_amendment_date)
                        VALUES ('Ada','Lovelace','Active','2020-01-01','Permanent',120000,
                                '39001010001',1,'2026-05-01')""")
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_tor_export_has_required_employee_columns(fresh_db):
    from web import statutory

    eid = _statutory_employee(fresh_db)
    payload, count = statutory.build_tor("2026-05")
    assert count == 1
    assert payload.startswith("\ufeffEes- ja perekonnanimi;")
    assert "Isikukood" in payload and "Töösuhte algus" in payload
    assert "39001010001" in payload and "Ada Lovelace" in payload


def test_tsd_export_maps_tax_and_social_tax_lines(fresh_db):
    from web import statutory

    eid = _statutory_employee(fresh_db)
    rid = fresh_db.create_pay_run("2026-05", [eid])
    slip = fresh_db.one("SELECT id FROM payslips WHERE run_id=?", (rid,))
    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO payslip_lines(payslip_id,kind,label,amount,base) VALUES(?,?,?,?,?)",
                     (slip["id"], "Deduction", "Sotsiaalmaks (33%)", 3300, "33% of gross"))
    payload, count, period = statutory.build_tsd(rid)
    assert count == 1 and period == "2026-05"
    assert "Tulumaks" in payload and "Sotsiaalmaks" in payload
    assert ";2200.00;" in payload and ";3300.00;" in payload


def _pay_history(db, eid, values):
    with db.cursor() as conn:
        for period, gross in values.items():
            conn.execute("""INSERT INTO payslips(employee_id,period,gross,gross_pay,net,status)
                            VALUES(?,?,?,?,?,'Paid')""", (eid, period, gross, gross, gross))


def test_holiday_pay_uses_six_month_calendar_day_average(fresh_db):
    eid = _statutory_employee(fresh_db)
    _pay_history(fresh_db, eid, {"2025-11": 3000, "2025-12": 3100, "2026-01": 3200,
                                "2026-02": 3300, "2026-03": 3400, "2026-04": 3500})
    amount, days = fresh_db.holiday_pay(eid, "2026-05-10", "2026-05-14", "2026-05")
    calendar_days = sum(calendar.monthrange(*map(int, p.split("-")))[1]
                        for p in ("2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"))
    assert days == 5
    assert amount == round(sum((3000, 3100, 3200, 3300, 3400, 3500)) / calendar_days * 5, 2)


def test_incapacity_pay_is_70_percent_for_days_four_to_eight(fresh_db):
    eid = _statutory_employee(fresh_db)
    _pay_history(fresh_db, eid, {"2025-11": 3000, "2025-12": 3000, "2026-01": 3000,
                                "2026-02": 3000, "2026-03": 3000, "2026-04": 3000})
    amount, days = fresh_db.incapacity_pay(eid, "2026-05-01", "2026-05-10")
    assert days == 5
    assert amount == round((3000 * 6) / (30 + 31 + 31 + 28 + 31 + 30) * 5 * 0.70, 2)


def test_pay_run_adds_benefits_once_and_keeps_tsd_gross(fresh_db):
    from web import statutory

    eid = _statutory_employee(fresh_db)
    _pay_history(fresh_db, eid, {"2025-11": 3000, "2025-12": 3000, "2026-01": 3000,
                                "2026-02": 3000, "2026-03": 3000, "2026-04": 3000})
    with fresh_db.cursor() as conn:
        conn.execute("""INSERT INTO leave_requests(employee_id,leave_type,from_date,to_date,days,status)
                        VALUES(?,?,?,?,?,'Approved')""", (eid, "Annual Leave", "2026-05-10", "2026-05-14", 5))
        conn.execute("""INSERT INTO leave_requests(employee_id,leave_type,from_date,to_date,days,status)
                        VALUES(?,?,?,?,?,'Approved')""", (eid, "Sick Leave", "2026-05-20", "2026-05-29", 10))
    rid = fresh_db.create_pay_run("2026-05", [eid])
    fresh_db.create_pay_run("2026-05", [eid])
    slip = fresh_db.one("SELECT * FROM payslips WHERE run_id=?", (rid,))
    lines = fresh_db.payslip_lines(slip["id"])
    assert sum("Holiday pay" in line["label"] for line in lines) == 1
    assert sum("Incapacity pay" in line["label"] for line in lines) == 1
    payload, _, _ = statutory.build_tsd(rid)
    assert f";{slip['gross']:.2f};" in payload


def test_benefit_plan_crud_enrolment_reopen_and_department_eligibility(fresh_db):
    import benefits

    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO departments(name) VALUES ('Engineering')")
        engineering = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO departments(name) VALUES ('Sales')")
        sales = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO employees(first_name,last_name,status,dept_id) VALUES ('A','One','Active',?)", (engineering,))
        engineering_employee = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO employees(first_name,last_name,status,dept_id) VALUES ('B','Two','Active',?)", (sales,))
        sales_employee = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    plan = benefits.save_plan("Sport", "sport", 40, eligibility="department", department_id=engineering)
    enrolment = benefits.enrol(plan, engineering_employee, "2026-01-01")
    assert benefits.enrol(plan, engineering_employee, "2026-01-01") == enrolment
    assert [row["employee_id"] for row in benefits.active_enrolments("2026-05-01")] == [engineering_employee]
    assert benefits.enrol(plan, sales_employee, "2026-01-01")
    assert [row["employee_id"] for row in benefits.active_enrolments("2026-05-01")] == [engineering_employee]
    assert benefits.unenrol(plan, engineering_employee, "2026-05-31")
    assert not benefits.active_enrolments("2026-06-01")
    benefits.enrol(plan, engineering_employee, "2026-06-01")
    assert len(benefits.enrolments_for(engineering_employee)) == 1
    assert benefits.deactivate_plan(plan)
    assert benefits.list_plans(active_only=True) == []


def test_benefit_pay_run_lines_are_employer_cost_and_idempotent(fresh_db):
    eid = _statutory_employee(fresh_db)
    import benefits

    plan = benefits.save_plan("Health", "health", 75)
    benefits.enrol(plan, eid, "2026-01-01")
    rid = fresh_db.create_pay_run("2026-05", [eid])
    fresh_db.prepare_pay_run(rid)
    slip = fresh_db.one("SELECT * FROM payslips WHERE run_id=?", (rid,))
    lines = fresh_db.payslip_lines(slip["id"])
    benefit_lines = [line for line in lines if "Benefit: Health" in line["label"]]
    assert len(benefit_lines) == 1
    assert benefit_lines[0]["amount"] == 75
    assert "Employer cost" in benefit_lines[0]["base"]
    assert slip["net"] == round(slip["gross"] * (1 - .22 - .02 - .016), 2)


def test_benefit_staff_page_and_portal_card_render_bilingually(fresh_db):
    import benefits
    from web import selfservice

    eid = _statutory_employee(fresh_db)
    plan = benefits.save_plan("Lunch", "other", 25)
    benefits.enrol(plan, eid, "2026-01-01")
    assert "Soodustused" in str(benefits.staff_page("et"))
    assert "Benefits" in str(benefits.staff_page("en"))
    portal = str(selfservice.pay_page(fresh_db.employee(eid)))
    assert "Minu soodustused / My benefits" in portal
    assert "Lunch" in portal and "25.00 EUR" in portal


def test_statutory_export_history_and_route_auth(fresh_db):
    from web import statutory

    from starlette.testclient import TestClient
    import web_app

    eid = _statutory_employee(fresh_db)
    rid = fresh_db.create_pay_run("2026-05", [eid])
    response = TestClient(web_app.app).get(f"/payroll/runs/{rid}/export/tor", follow_redirects=False)
    assert response.status_code == 303 and "/login" in response.headers["location"]
    payload, count = statutory.build_tor("2026-05")
    statutory.record_export("TOR", "2026-05", "tor-2026-05.csv", payload, count, "tester")
    assert fresh_db.scalar("SELECT COUNT(*) FROM statutory_exports") == 1
    assert "tor-2026-05.csv" in str(statutory.export_history())


def test_statutory_history_page_renders_in_both_languages(fresh_db):
    from web import views

    assert "Ekspordi ajalugu" in str(views.statutory_exports_page())
    assert "TÖR-i" in str(views.statutory_exports_page())


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


def test_live_adapter_dispatch_requires_real_success(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)
    integrations.save("github", api_key="ghp_test_credential_123", actor="t")
    calls = []

    def fake_adapter(meta, key, secret, account_ref):
        calls.append((meta["key"], key, secret, account_ref))
        return True, "GET https://api.github.com/user returned HTTP 200; authenticated read succeeded."

    monkeypatch.setitem(integrations.providers.ADAPTERS, "github", fake_adapter)
    result = integrations.test_connection("github", actor="t")
    assert result["ok"] is True and calls[0][0] == "github"
    assert integrations.integration("github")["status"] == "Connected"


def test_bamboohr_sync_records_count_and_snapshot(fresh_db, monkeypatch, tmp_path):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    monkeypatch.setenv("FASTHR_DATA_DIR", str(tmp_path / "data"))
    import importlib
    import integrations
    importlib.reload(integrations)
    integrations.save("bamboohr", api_key="bamboohr_key_123", account_ref="acme", actor="t")
    integrations.set_status("bamboohr", "Connected", actor="t")
    payload = {"employees": [{"id": "1"}, {"id": "2"}]}
    monkeypatch.setattr("web.providers.base.bamboohr_directory",
                        lambda key, account: (True, "GET directory returned HTTP 200; fetched 2 employees.",
                                              payload, 2))
    result = integrations.sync("bamboohr", actor="t")
    event = fresh_db.one("SELECT * FROM integration_events WHERE kind='sync' ORDER BY id DESC")
    assert result["ok"] is True and result["records"] == 2
    assert event["records"] == 2
    assert (tmp_path / "data/integrations/bamboohr/directory-latest.json").exists()


def test_teams_sync_posts_plain_test_message(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)
    integrations.save("teams", api_key="https://example.test/webhook/123", actor="t")
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("httpx.post", fake_post)
    result = integrations.test_connection("teams", actor="t")
    assert result["ok"] is True
    assert calls[0][0] == "https://example.test/webhook/123"
    assert calls[0][1]["content"] == "FastHR integration connection test."


def test_live_timeout_is_reported_without_traceback(fresh_db, monkeypatch):
    monkeypatch.setenv("FASTHR_SECRET", "test-secret-value")
    import importlib
    import integrations
    importlib.reload(integrations)
    integrations.save("github", api_key="ghp_test_credential_123", actor="t")

    def timeout(*args, **kwargs):
        import httpx
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("httpx.get", timeout)
    result = integrations.test_connection("github", actor="t")
    assert result["ok"] is False and "timed out" in result["note"]


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
