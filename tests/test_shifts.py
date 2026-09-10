"""Phase 2 roster and time-clock behavior."""
from __future__ import annotations

from datetime import date, timedelta


def _employee(db, name="Ada"):
    with db.cursor() as conn:
        return conn.execute("INSERT INTO employees(first_name,last_name,status) VALUES (?,?, 'Active')",
                            (name, "Lovelace")).lastrowid


def _shift(db, eid, day="2026-06-11"):
    with db.cursor() as conn:
        tid = conn.execute("SELECT id FROM shift_types WHERE name='Day'").fetchone()
        tid = tid[0] if tid else conn.execute(
            "INSERT INTO shift_types(name,start_time,end_time) VALUES ('Day','09:00','17:00')").lastrowid
    return db.create_shift_assignment(eid, tid, day, "Tallinn HQ")


def test_shift_migration_and_roster(fresh_db):
    tables = {r["name"] for r in fresh_db.rows("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"shift_types", "shift_locations", "shift_assignments", "clock_punches"} <= tables
    eid = _employee(fresh_db)
    aid = _shift(fresh_db, eid)
    assert fresh_db.roster("2026-06-11", "2026-06-11")[0]["id"] == aid


def test_clock_round_trip_derives_attendance(fresh_db):
    eid, aid = _employee(fresh_db), None
    aid = _shift(fresh_db, eid)
    assert fresh_db.clock_in(eid, aid, punched_at="2026-06-11 09:00:00")
    assert fresh_db.clock_in(eid, aid, punched_at="2026-06-11 10:00:00") is None
    result = fresh_db.clock_out(eid, aid, punched_at="2026-06-11 17:00:00")
    assert result["hours"] == 8
    assert fresh_db.one("SELECT status,hours FROM attendance WHERE employee_id=? AND att_date=?", (eid, "2026-06-11")) == {
        "status": "Present", "hours": 8.0}
    assert fresh_db.scalar("SELECT status FROM shift_assignments WHERE id=?", (aid,)) == "Completed"
    assert fresh_db.clock_out(eid, aid, punched_at="2026-06-11 18:00:00") is None


def test_leave_wins_and_gap_report(fresh_db):
    eid = _employee(fresh_db)
    aid = _shift(fresh_db, eid)
    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO attendance(employee_id,att_date,status,hours) VALUES (?,?, 'On Leave',0)",
                     (eid, "2026-06-11"))
    fresh_db.clock_in(eid, aid, punched_at="2026-06-11 09:00:00")
    fresh_db.clock_out(eid, aid, punched_at="2026-06-11 17:00:00")
    assert fresh_db.scalar("SELECT status FROM attendance WHERE employee_id=? AND att_date=?", (eid, "2026-06-11")) == "On Leave"
    assert fresh_db.auto_attendance_gap_report("2026-06-11", "2026-06-11") == []
    eid2 = _employee(fresh_db, "Grace")
    _shift(fresh_db, eid2)
    assert len(fresh_db.auto_attendance_gap_report("2026-06-11", "2026-06-11")) == 1


def test_cancel_and_seed_views(fresh_db):
    eid = _employee(fresh_db)
    aid = _shift(fresh_db, eid)
    assert fresh_db.cancel_shift_assignment(aid)
    assert not fresh_db.cancel_shift_assignment(aid)
    from web import views
    assert "Weekly roster" in str(views.shifts_roster())
    assert "Today's clock board" in str(views.time_clocks())


def test_shift_route_registration_and_seed_idempotency(fresh_db, monkeypatch):
    import web_app
    paths = {route.path for route in web_app.app.routes}
    assert {"/shifts", "/shifts/new", "/shifts/{assignment_id}/cancel", "/timeclock", "/timeclock/in", "/timeclock/out"} <= paths
    import seed
    seed.build()
    counts = tuple(fresh_db.scalar(f"SELECT COUNT(*) FROM {table}") for table in ("shift_types", "shift_locations", "shift_assignments", "clock_punches"))
    seed.build()
    assert counts == tuple(fresh_db.scalar(f"SELECT COUNT(*) FROM {table}") for table in ("shift_types", "shift_locations", "shift_assignments", "clock_punches"))
