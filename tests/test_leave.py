"""Leave page rendering: single Pending filter, labelled reject actions."""
from __future__ import annotations


def _employee(db):
    with db.cursor() as conn:
        conn.execute("""INSERT INTO employees(first_name,last_name,status,base_salary)
                        VALUES ('Ada','Lovelace','Active',60000)""")
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_leave_filter_segment_has_no_duplicate_pending(fresh_db):
    from web import views

    html = str(views.leave_main())
    assert html.count(">Pending<") == 1
    assert ">All<" in html


def test_leave_reject_button_has_visible_label(fresh_db):
    from web import views

    eid = _employee(fresh_db)
    fresh_db.apply_leave(eid, "Annual", "2026-07-01", "2026-07-02", "Rest")
    html = str(views.leave_main())
    assert "✕ Reject" in html
    assert "✓ Approve" in html
