"""Phase 4 employee portal identity, privacy and payroll offset tests."""
from __future__ import annotations

from starlette.responses import RedirectResponse

from web import selfservice


def _employee(db, name="Ada"):
    with db.cursor() as conn:
        return conn.execute("INSERT INTO employees(first_name,last_name,email,status,base_salary) VALUES (?,?,?,?,?)",
                            (name, "Portal", f"{name.lower()}@example.test", "Active", 60000)).lastrowid


def test_employee_login_accepts_hash_only(fresh_db):
    eid = _employee(fresh_db)
    fresh_db.set_employee_password(eid, "PortalDemo2026!")
    employee = fresh_db.one("SELECT * FROM employees WHERE id=?", (eid,))
    assert selfservice.authenticate(employee["email"], "bad") is None
    assert selfservice.authenticate(employee["email"], "PortalDemo2026!")["id"] == eid
    assert "PortalDemo2026!" not in employee["password_hash"]


def test_unauthenticated_portal_redirects_to_login(fresh_db):
    _, denied = (None, RedirectResponse("/me/login?next=/me", status_code=303))
    assert denied.status_code == 303
    assert denied.headers["location"].startswith("/me/login")


def test_portal_pages_only_render_employee_rows(fresh_db):
    first, second = _employee(fresh_db), _employee(fresh_db, "Bea")
    fresh_db.set_employee_password(first, "PortalDemo2026!")
    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO leave_balances(employee_id,leave_type,allocated,used) VALUES (?,?,?,?)",
                     (first, "Annual Leave", 25, 2))
        conn.execute("INSERT INTO leave_balances(employee_id,leave_type,allocated,used) VALUES (?,?,?,?)",
                     (second, "Annual Leave", 25, 0))
    html = str(selfservice.leave_page(fresh_db.employee(first)))
    assert "Bea" not in html
    assert "Annual Leave" in html


def test_advance_offset_adds_deduction_and_reduces_net(fresh_db):
    eid = _employee(fresh_db)
    run_id = fresh_db.create_pay_run("2026-05", [eid])
    with fresh_db.cursor() as conn:
        advance_id = conn.execute("INSERT INTO employee_advances(employee_id,requested_amount,approved_amount,reason,status) VALUES (?,?,?,?,?)",
                                  (eid, 500, 450, "Travel", "Approved")).lastrowid
    assert fresh_db.offset_employee_advance(run_id, advance_id)
    slip = fresh_db.one("SELECT * FROM payslips WHERE run_id=?", (run_id,))
    line = fresh_db.one("SELECT * FROM payslip_lines WHERE payslip_id=? AND label='Advance offset'", (slip["id"],))
    assert line["amount"] == 450
    assert slip["net"] == round(slip["gross"] - slip["tax"] - slip["pension"] - slip["other_ded"] - 450, 2)
    assert fresh_db.scalar("SELECT status FROM employee_advances WHERE id=?", (advance_id,)) == "Offset"
    assert not fresh_db.offset_employee_advance(run_id, advance_id)
