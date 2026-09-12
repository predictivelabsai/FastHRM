"""Phase 1 pay-run persistence, calculations, and workflow rules."""
from __future__ import annotations


def _employee(db, salary=120000):
    with db.cursor() as conn:
        conn.execute("""INSERT INTO employees(first_name,last_name,status,base_salary)
                        VALUES ('Ada','Lovelace','Active',?)""", (salary,))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_pay_run_migration_and_calculation(fresh_db):
    columns = {row["name"] for row in fresh_db.rows("PRAGMA table_info(payslips)")}
    assert {"run_id", "currency", "working_days", "gross_pay"} <= columns
    eid = _employee(fresh_db)
    rid = fresh_db.create_pay_run("2026-05", [eid])
    slip = fresh_db.one("SELECT * FROM payslips WHERE run_id=?", (rid,))
    assert slip["gross"] == slip["gross_pay"] == 10000
    assert slip["net"] == round(slip["gross"] - slip["tax"] - slip["pension"] - slip["other_ded"], 2)
    assert len(fresh_db.payslip_lines(slip["id"])) == 6


def test_pay_run_transitions_are_sequential(fresh_db):
    rid = fresh_db.create_pay_run("2026-05", [_employee(fresh_db)])
    assert not fresh_db.advance_pay_run(rid, "Approved")
    assert fresh_db.advance_pay_run(rid, "In Review")
    assert fresh_db.advance_pay_run(rid, "Approved")
    assert fresh_db.advance_pay_run(rid, "Paid")
    assert not fresh_db.advance_pay_run(rid, "In Review")
    assert fresh_db.scalar("SELECT status FROM pay_runs WHERE id=?", (rid,)) == "Paid"
    assert fresh_db.scalar("SELECT DISTINCT status FROM payslips WHERE run_id=?", (rid,)) == "Paid"


def test_new_pay_run_page_has_form_with_select_all_and_search(fresh_db):
    from web import views

    _employee(fresh_db)
    html = str(views.pay_run_new())
    assert 'action="/payroll/runs/new"' in html
    assert "Vali kõik" in html
    assert 'type="search"' in html
    assert "prToggle" in html and "prFilter" in html


def test_new_pay_run_route_requires_login_and_beats_run_id_shadow(fresh_db):
    from starlette.testclient import TestClient

    import web_app

    response = TestClient(web_app.app).get("/payroll/runs/new", follow_redirects=False)
    assert response.status_code == 303 and "/login" in response.headers["location"]
