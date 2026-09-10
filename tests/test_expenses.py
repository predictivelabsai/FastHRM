"""Phase 3 expense, advance and travel workflows."""
from __future__ import annotations


def _employee(db, name):
    with db.cursor() as conn:
        return conn.execute("INSERT INTO employees(first_name,last_name) VALUES (?,?)", (name, "Test")).lastrowid


def _category(db, **values):
    with db.cursor() as conn:
        return conn.execute("INSERT INTO expense_categories(name,daily_limit,monthly_limit) VALUES ('Meals',?,?)",
                            (values.get("daily_limit"), values.get("monthly_limit"))).lastrowid


def test_expense_claim_lifecycle_and_limits(fresh_db):
    employee, manager = _employee(fresh_db, "Claimant"), _employee(fresh_db, "Manager")
    category = _category(fresh_db, daily_limit=30, monthly_limit=50)
    claim = fresh_db.create_expense_claim(employee, category, "2026-06-11", "Lunch", 25)
    assert not fresh_db.decide_expense_claim(claim, manager, "Approved")
    assert fresh_db.submit_expense_claim(claim)
    assert fresh_db.decide_expense_claim(claim, manager, "Approved")
    assert fresh_db.reimburse_expense_claim(claim)
    assert not fresh_db.reimburse_expense_claim(claim)
    ok, reason = fresh_db.claim_limits_check(employee, category, 30, "2026-06-11")
    assert not ok and "Daily limit" in reason


def test_travel_return_resubmit_and_advance_rules(fresh_db):
    employee, manager = _employee(fresh_db, "Traveller"), _employee(fresh_db, "Approver")
    travel = fresh_db.request_travel(employee, "Tartu", "Workshop", "2026-06-20", "2026-06-21", 200)
    assert fresh_db.decide_travel(travel, manager, "Returned")
    assert fresh_db.resubmit_travel(travel)
    assert fresh_db.decide_travel(travel, manager, "Approved")
    advance = fresh_db.request_advance(employee, 300, "Conference")
    assert not fresh_db.decide_advance(advance, employee, "Approved")
    assert fresh_db.decide_advance(advance, manager, "Approved")
    assert fresh_db.decide_advance(advance, manager, "Offset", 42)


def test_phase3_routes_and_seed_tables(fresh_db):
    import web_app
    paths = {route.path for route in web_app.app.routes}
    assert {"/expenses", "/expenses/new", "/expenses/{claim_id}/submit", "/travel", "/travel/new"} <= paths
    import seed
    seed.build()
    first = tuple(fresh_db.scalar(f"SELECT COUNT(*) FROM {table}") for table in
                  ("expense_categories", "expense_claims", "employee_advances", "travel_requests"))
    seed.build()
    assert first == tuple(fresh_db.scalar(f"SELECT COUNT(*) FROM {table}") for table in
                          ("expense_categories", "expense_claims", "employee_advances", "travel_requests"))
