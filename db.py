"""FastHR data layer — SQLite, collapsed from Frappe HR (HRMS).

Three pillars: people (employees, departments), time (leave + attendance),
and pay (payslips). All synthetic.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path

DB_PATH = os.getenv("FASTHR_DB") or str(Path(__file__).parent / "fasthr.sqlite")

TODAY = date(2026, 6, 11)

LEAVE_TYPES = ["Annual Leave", "Sick Leave", "Casual Leave", "Unpaid Leave", "Parental Leave"]
LEAVE_STATUSES = ["Pending", "Approved", "Rejected", "Cancelled"]
ATTEND_STATUSES = ["Present", "Work From Home", "On Leave", "Half Day", "Absent"]
EMP_STATUSES = ["Active", "On Leave", "Probation"]


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def db_exists() -> bool:
    p = Path(DB_PATH)
    return p.exists() and p.stat().st_size > 0


def rows(sql, params=()):
    with cursor() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(sql, params=()):
    with cursor() as conn:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None


def scalar(sql, params=()):
    with cursor() as conn:
        r = conn.execute(sql, params).fetchone()
        return r[0] if r else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY,
    code            TEXT,
    first_name      TEXT,
    last_name       TEXT,
    email           TEXT,
    dept_id         INTEGER REFERENCES departments(id),
    designation     TEXT,
    manager_id      INTEGER REFERENCES employees(id),
    branch          TEXT,
    status          TEXT NOT NULL DEFAULT 'Active',
    date_of_joining TEXT,
    gender          TEXT,
    base_salary     REAL
);
CREATE TABLE IF NOT EXISTS leave_balances (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER REFERENCES employees(id),
    leave_type    TEXT NOT NULL,
    allocated     REAL NOT NULL DEFAULT 0,
    used          REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS leave_requests (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER REFERENCES employees(id),
    leave_type    TEXT NOT NULL,
    from_date     TEXT,
    to_date       TEXT,
    days          REAL,
    status        TEXT NOT NULL DEFAULT 'Pending',
    reason        TEXT,
    applied_on    TEXT
);
CREATE TABLE IF NOT EXISTS attendance (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER REFERENCES employees(id),
    att_date      TEXT NOT NULL,
    status        TEXT NOT NULL,
    hours         REAL
);
CREATE TABLE IF NOT EXISTS payslips (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER REFERENCES employees(id),
    period        TEXT NOT NULL,    -- YYYY-MM
    gross         REAL,
    tax           REAL,
    pension       REAL,
    other_ded     REAL,
    net           REAL,
    status        TEXT DEFAULT 'Paid'
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id            INTEGER PRIMARY KEY,
    thread_id     TEXT NOT NULL,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    created       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(dept_id);
CREATE INDEX IF NOT EXISTS idx_att_emp ON attendance(employee_id, att_date);
CREATE INDEX IF NOT EXISTS idx_leave_emp ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_pay_emp ON payslips(employee_id);
"""


def init_schema():
    with cursor() as conn:
        conn.executescript(SCHEMA)


# --- reads ------------------------------------------------------------------

def kpis() -> dict:
    headcount = scalar("SELECT COUNT(*) FROM employees WHERE status!='Probation' OR status='Probation'") or 0
    on_leave = scalar("SELECT COUNT(DISTINCT employee_id) FROM attendance WHERE att_date=? AND status='On Leave'", (TODAY.isoformat(),)) or 0
    present = scalar("SELECT COUNT(*) FROM attendance WHERE att_date=? AND status IN ('Present','Work From Home','Half Day')", (TODAY.isoformat(),)) or 0
    pending = scalar("SELECT COUNT(*) FROM leave_requests WHERE status='Pending'") or 0
    # attendance rate over last 30 days
    total = scalar("SELECT COUNT(*) FROM attendance") or 1
    presentish = scalar("SELECT COUNT(*) FROM attendance WHERE status IN ('Present','Work From Home','Half Day')") or 0
    return {
        "headcount": headcount,
        "on_leave_today": on_leave,
        "present_today": present,
        "pending_leave": pending,
        "attendance_rate": round(100 * presentish / total),
        "depts": scalar("SELECT COUNT(*) FROM departments") or 0,
        "monthly_payroll": scalar("SELECT COALESCE(SUM(net),0) FROM payslips WHERE period=(SELECT MAX(period) FROM payslips)") or 0,
    }


def headcount_by_dept():
    return rows("""SELECT d.name dept, COUNT(e.id) n FROM departments d
                   LEFT JOIN employees e ON e.dept_id=d.id GROUP BY d.id ORDER BY n DESC""")


def employee(eid: int):
    return one("""SELECT e.*, d.name dept, m.first_name||' '||m.last_name manager
                  FROM employees e LEFT JOIN departments d ON d.id=e.dept_id
                  LEFT JOIN employees m ON m.id=e.manager_id WHERE e.id=?""", (eid,))


def leave_balance(eid: int):
    return rows("SELECT *, (allocated-used) remaining FROM leave_balances WHERE employee_id=? ORDER BY leave_type", (eid,))


def recent_attendance(eid: int, limit=14):
    return rows("SELECT * FROM attendance WHERE employee_id=? ORDER BY att_date DESC LIMIT ?", (eid, limit))


def payslips_for(eid: int):
    return rows("SELECT * FROM payslips WHERE employee_id=? ORDER BY period DESC", (eid,))


def employees_min() -> list[dict]:
    return rows("SELECT id, first_name, last_name FROM employees ORDER BY first_name")


# --- leave workflow (transactional) -----------------------------------------

def apply_leave(employee_id: int, leave_type: str, from_date: str, to_date: str, reason: str = ""):
    from datetime import date
    try:
        d0 = date.fromisoformat(from_date)
        d1 = date.fromisoformat(to_date)
        days = max(1, (d1 - d0).days + 1)
    except ValueError:
        days = 1
    with cursor() as conn:
        conn.execute(
            """INSERT INTO leave_requests(employee_id,leave_type,from_date,to_date,days,status,reason,applied_on)
               VALUES (?,?,?,?,?,'Pending',?,datetime('now'))""",
            (employee_id, leave_type if leave_type in LEAVE_TYPES else "Annual Leave",
             from_date, to_date, days, reason))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def set_leave_status(req_id: int, status: str) -> bool:
    if status not in LEAVE_STATUSES:
        return False
    r = one("SELECT * FROM leave_requests WHERE id=?", (req_id,))
    if not r:
        return False
    was = r["status"]
    with cursor() as conn:
        conn.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, req_id))
        # approving consumes balance; reverting an approval refunds it
        if status == "Approved" and was != "Approved":
            conn.execute("UPDATE leave_balances SET used = used + ? WHERE employee_id=? AND leave_type=?",
                         (r["days"], r["employee_id"], r["leave_type"]))
        elif was == "Approved" and status != "Approved":
            conn.execute("UPDATE leave_balances SET used = MAX(0, used - ?) WHERE employee_id=? AND leave_type=?",
                         (r["days"], r["employee_id"], r["leave_type"]))
    return True
