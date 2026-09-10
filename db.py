"""FastHRM data layer — SQLite, collapsed from Frappe HR (HRMS).

Three pillars: people (employees, departments), time (leave + attendance),
and pay (payslips). All synthetic.
"""
from __future__ import annotations

import os
import sqlite3
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from datetime import datetime, date, timedelta
import calendar
from pathlib import Path

DB_PATH = os.getenv("FASTHR_DB") or str(Path(__file__).parent / "fasthr.sqlite")
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

TODAY = date(2026, 6, 11)

LEAVE_TYPES = ["Annual Leave", "Sick Leave", "Casual Leave", "Unpaid Leave", "Parental Leave"]
LEAVE_STATUSES = ["Pending", "Approved", "Rejected", "Cancelled"]
ATTEND_STATUSES = ["Present", "Work From Home", "On Leave", "Half Day", "Absent"]
SHIFT_STATUSES = ["Scheduled", "Completed", "Missed", "Cancelled"]
PUNCH_TYPES = ["In", "Out", "Break Start", "Break End"]
PUNCH_SOURCES = ["Web", "Mobile", "Kiosk", "Terminal"]
EMP_STATUSES = ["Active", "On Leave", "Probation"]
PAY_RUN_STATUSES = ["Draft", "In Review", "Approved", "Paid"]
PAY_RUN_TRANSITIONS = {"Draft": "In Review", "In Review": "Approved", "Approved": "Paid"}
EXPENSE_STATUSES = ["Draft", "Submitted", "Approved", "Rejected", "Reimbursed"]
ADVANCE_STATUSES = ["Requested", "Approved", "Rejected", "Repaid", "Offset"]
TRAVEL_STATUSES = ["Submitted", "Approved", "Rejected", "Returned"]


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


# --- migrations -------------------------------------------------------------
#
# Numbered SQL files in migrations/, applied in filename order and recorded in a
# ledger. The baseline schema is 0001; everything after it is additive.
#
# sqlite3's executescript() commits any open transaction before running, so a
# migration file is not atomic. Migration DDL is therefore written idempotently
# (IF NOT EXISTS) wherever the dialect allows, so re-running after a partial
# failure is safe. Statements that can't be (ALTER TABLE ADD COLUMN) go last.

def migrate() -> list[str]:
    """Apply pending migrations. Returns the versions applied this call."""
    applied = []
    with cursor() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                            version    TEXT PRIMARY KEY,
                            applied_at TEXT NOT NULL)""")
        done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                         (path.stem,))
            applied.append(path.stem)
    return applied


def init_schema():
    """Bring the database up to the latest schema (kept as the legacy name)."""
    migrate()


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
        "monthly_payroll": scalar("""SELECT COALESCE(SUM(p.net),0) FROM payslips p
                                     WHERE p.run_id=(SELECT id FROM pay_runs
                                                     WHERE status IN ('In Review','Approved','Paid')
                                                     ORDER BY period DESC LIMIT 1)""") or
                           scalar("SELECT COALESCE(SUM(net),0) FROM payslips WHERE period=(SELECT MAX(period) FROM payslips)") or 0,
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


def set_employee_password(employee_id: int, password: str) -> None:
    """Store a salted, deliberately slow password hash for portal login."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    encoded = f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"
    with cursor() as conn:
        conn.execute("UPDATE employees SET password_hash=? WHERE id=?", (encoded, employee_id))


def authenticate_employee(email: str, password: str):
    employee = one("SELECT * FROM employees WHERE lower(email)=? AND status!='Inactive'",
                   ((email or "").strip().lower(),))
    if not employee or not employee.get("password_hash"):
        return None
    try:
        algorithm, iterations, salt, expected = employee["password_hash"].split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", (password or "").encode(),
                                    bytes.fromhex(salt), int(iterations))
    except (TypeError, ValueError):
        return None
    return employee if algorithm == "pbkdf2_sha256" and hmac.compare_digest(actual.hex(), expected) else None


# --- expenses, advances and travel ----------------------------------------

def expense_categories() -> list[dict]:
    return rows("SELECT * FROM expense_categories ORDER BY name")


def create_expense_claim(employee_id: int, category_id: int, claim_date: str,
                         description: str, amount: float, currency: str = "EUR",
                         tax_rate: float = 0, receipt_path: str | None = None,
                         notes: str = "") -> int:
    try:
        date.fromisoformat(claim_date)
        amount, tax_rate = float(amount), float(tax_rate)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid expense details") from exc
    if amount < 0 or not description.strip():
        raise ValueError("description and a non-negative amount are required")
    ok, reason = claim_limits_check(employee_id, category_id, amount, claim_date)
    if not ok:
        raise ValueError(reason)
    with cursor() as conn:
        return conn.execute("""INSERT INTO expense_claims
            (employee_id,category_id,claim_date,description,amount,currency,tax_rate,receipt_path,notes)
            VALUES (?,?,?,?,?,?,?,?,?)""", (employee_id, category_id, claim_date, description.strip(),
                                               amount, currency or "EUR", tax_rate, receipt_path, notes)).lastrowid


def submit_expense_claim(claim_id: int) -> bool:
    with cursor() as conn:
        return bool(conn.execute("UPDATE expense_claims SET status='Submitted' WHERE id=? AND status='Draft'",
                                (claim_id,)).rowcount)


def decide_expense_claim(claim_id: int, approver_id: int, decision: str, notes: str = "") -> bool:
    if decision not in ("Approved", "Rejected"):
        return False
    with cursor() as conn:
        claim = conn.execute("SELECT employee_id,status FROM expense_claims WHERE id=?", (claim_id,)).fetchone()
        if not claim or claim["status"] != "Submitted" or claim["employee_id"] == approver_id:
            return False
        return bool(conn.execute("""UPDATE expense_claims SET status=?,approver_id=?,decided_at=?,notes=?
                                  WHERE id=? AND status='Submitted'""",
                                (decision, approver_id, datetime.now().isoformat(sep=" "), notes, claim_id)).rowcount)


def reimburse_expense_claim(claim_id: int) -> bool:
    with cursor() as conn:
        return bool(conn.execute("""UPDATE expense_claims SET status='Reimbursed',reimbursed_at=?
                                  WHERE id=? AND status='Approved'""", (datetime.now().isoformat(sep=" "), claim_id)).rowcount)


def claim_limits_check(employee_id: int, category_id: int, amount: float, claim_date: str) -> tuple[bool, str]:
    try:
        d = date.fromisoformat(claim_date)
        amount = float(amount)
    except (TypeError, ValueError):
        return False, "Claim date and amount are invalid."
    category = one("SELECT * FROM expense_categories WHERE id=?", (category_id,))
    if not category:
        return False, "Expense category not found."
    active = ("Submitted", "Approved", "Reimbursed")
    day_total = scalar("SELECT COALESCE(SUM(amount),0) FROM expense_claims WHERE employee_id=? AND category_id=? AND claim_date=? AND status IN (?,?,?)",
                       (employee_id, category_id, d.isoformat(), *active)) or 0
    month_total = scalar("SELECT COALESCE(SUM(amount),0) FROM expense_claims WHERE employee_id=? AND category_id=? AND substr(claim_date,1,7)=? AND status IN (?,?,?)",
                         (employee_id, category_id, d.strftime("%Y-%m"), *active)) or 0
    if category["daily_limit"] is not None and day_total + amount > category["daily_limit"]:
        return False, f"Daily limit of {category['daily_limit']:.2f} EUR exceeded."
    if category["monthly_limit"] is not None and month_total + amount > category["monthly_limit"]:
        return False, f"Monthly limit of {category['monthly_limit']:.2f} EUR exceeded."
    return True, ""


def request_advance(employee_id: int, requested_amount: float, reason: str,
                    currency: str = "EUR", notes: str = "") -> int:
    if float(requested_amount) < 0 or not reason.strip():
        raise ValueError("reason and a non-negative amount are required")
    with cursor() as conn:
        return conn.execute("""INSERT INTO employee_advances(employee_id,requested_amount,currency,reason,notes)
                              VALUES (?,?,?,?,?)""", (employee_id, requested_amount, currency or "EUR", reason.strip(), notes)).lastrowid


def decide_advance(advance_id: int, approver_id: int, decision: str, offset_run_id: int | None = None) -> bool:
    if decision not in ("Approved", "Rejected", "Repaid", "Offset"):
        return False
    with cursor() as conn:
        row = conn.execute("SELECT employee_id,status FROM employee_advances WHERE id=?", (advance_id,)).fetchone()
        if not row or row["employee_id"] == approver_id:
            return False
        if decision in ("Approved", "Rejected") and row["status"] != "Requested":
            return False
        if decision in ("Repaid", "Offset") and row["status"] != "Approved":
            return False
        if decision == "Offset" and offset_run_id is None:
            return False
        return bool(conn.execute("""UPDATE employee_advances SET status=?,
            approved_amount=CASE WHEN ?='Approved' THEN requested_amount ELSE approved_amount END,
            decided_at=?,offset_run_id=CASE WHEN ?='Offset' THEN ? ELSE offset_run_id END
            WHERE id=?""", (decision, decision, datetime.now().isoformat(sep=" "), decision,
                              offset_run_id, advance_id)).rowcount)


def request_travel(employee_id: int, destination: str, purpose: str, from_date: str, to_date: str,
                   estimated_cost: float, advance_requested: float = 0, notes: str = "") -> int:
    try:
        d0, d1 = date.fromisoformat(from_date), date.fromisoformat(to_date)
        if d1 < d0 or float(estimated_cost) < 0 or float(advance_requested) < 0:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid travel dates or costs") from exc
    if not destination.strip() or not purpose.strip():
        raise ValueError("destination and purpose are required")
    with cursor() as conn:
        return conn.execute("""INSERT INTO travel_requests(employee_id,destination,purpose,from_date,to_date,estimated_cost,advance_requested,notes)
                              VALUES (?,?,?,?,?,?,?,?)""", (employee_id, destination.strip(), purpose.strip(), from_date, to_date, estimated_cost, advance_requested, notes)).lastrowid


def decide_travel(request_id: int, approver_id: int, decision: str) -> bool:
    if decision not in ("Approved", "Rejected", "Returned"):
        return False
    with cursor() as conn:
        row = conn.execute("SELECT employee_id,status FROM travel_requests WHERE id=?", (request_id,)).fetchone()
        if not row or row["status"] != "Submitted" or row["employee_id"] == approver_id:
            return False
        return bool(conn.execute("UPDATE travel_requests SET status=?,approver_id=?,decided_at=? WHERE id=? AND status='Submitted'",
                                (decision, approver_id, datetime.now().isoformat(sep=" "), request_id)).rowcount)


def resubmit_travel(request_id: int) -> bool:
    with cursor() as conn:
        return bool(conn.execute("UPDATE travel_requests SET status='Submitted',decided_at=NULL WHERE id=? AND status='Returned'",
                                (request_id,)).rowcount)


def open_expenses() -> list[dict]:
    return rows("""SELECT c.*, cat.name category, e.first_name,e.last_name FROM expense_claims c
                  JOIN expense_categories cat ON cat.id=c.category_id JOIN employees e ON e.id=c.employee_id
                  WHERE c.status IN ('Submitted','Approved') ORDER BY c.claim_date DESC,c.id DESC""")


def open_advances() -> list[dict]:
    return rows("""SELECT a.*,e.first_name,e.last_name FROM employee_advances a JOIN employees e ON e.id=a.employee_id
                  WHERE a.status IN ('Requested','Approved') ORDER BY a.requested_at DESC,a.id DESC""")


def open_travel() -> list[dict]:
    return rows("""SELECT t.*,e.first_name,e.last_name FROM travel_requests t JOIN employees e ON e.id=t.employee_id
                  WHERE t.status IN ('Submitted','Approved','Returned') ORDER BY t.from_date,t.id DESC""")


def expenses_summary(period: str | None = None) -> dict:
    period = period or TODAY.strftime("%Y-%m")
    pending = scalar("SELECT COALESCE(SUM(amount),0) FROM expense_claims WHERE status='Submitted'") or 0
    approved = scalar("SELECT COALESCE(SUM(amount),0) FROM expense_claims WHERE status IN ('Approved','Reimbursed') AND substr(COALESCE(decided_at,claim_date),1,7)=?", (period,)) or 0
    outstanding = scalar("SELECT COALESCE(SUM(COALESCE(approved_amount,requested_amount)),0) FROM employee_advances WHERE status='Approved'") or 0
    return {"pending_total": round(float(pending), 2), "approved_this_month": round(float(approved), 2), "advances_outstanding": round(float(outstanding), 2)}


# --- shifts and time clocks ------------------------------------------------

def shift_types() -> list[dict]:
    return rows("SELECT * FROM shift_types ORDER BY start_time, name")


def roster(from_date: str, to_date: str, employee_id: int | None = None) -> list[dict]:
    extra = " AND s.employee_id=?" if employee_id else ""
    params = [from_date, to_date] + ([employee_id] if employee_id else [])
    return rows("""SELECT s.*, st.name shift_name, st.start_time, st.end_time,
                        st.break_minutes, st.color, e.first_name, e.last_name
                 FROM shift_assignments s JOIN shift_types st ON st.id=s.shift_type_id
                 JOIN employees e ON e.id=s.employee_id
                 WHERE s.shift_date BETWEEN ? AND ?""" + extra +
                " ORDER BY s.shift_date, e.first_name, e.last_name, st.start_time", tuple(params))


def create_shift_assignment(employee_id: int, shift_type_id: int, shift_date: str,
                            location_label: str = "", notes: str = "") -> int:
    try:
        date.fromisoformat(shift_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("shift_date must be YYYY-MM-DD") from exc
    with cursor() as conn:
        existing = conn.execute("""SELECT id FROM shift_assignments
                                   WHERE employee_id=? AND shift_date=? AND shift_type_id=?""",
                                (employee_id, shift_date, shift_type_id)).fetchone()
        if existing:
            return existing[0]
        return conn.execute("""INSERT INTO shift_assignments
            (employee_id, shift_type_id, shift_date, location_label, status, notes)
            VALUES (?, ?, ?, ?, 'Scheduled', ?)""",
                            (employee_id, shift_type_id, shift_date, location_label, notes)).lastrowid


def cancel_shift_assignment(assignment_id: int) -> bool:
    with cursor() as conn:
        return bool(conn.execute("""UPDATE shift_assignments SET status='Cancelled'
                                   WHERE id=? AND status IN ('Scheduled', 'Missed')""", (assignment_id,)).rowcount)


def _on_site(conn, location_label, lat, lng) -> int | None:
    if lat is None or lng is None or not location_label:
        return None
    location = conn.execute("SELECT * FROM shift_locations WHERE label=?", (location_label,)).fetchone()
    if not location:
        return None
    from math import asin, cos, radians, sin, sqrt
    earth = 6371000
    dlat, dlng = radians(float(lat) - location["latitude"]), radians(float(lng) - location["longitude"])
    a = sin(dlat / 2) ** 2 + cos(radians(location["latitude"])) * cos(radians(float(lat))) * sin(dlng / 2) ** 2
    return int(2 * earth * asin(sqrt(a)) <= location["radius_m"])


def clock_in(employee_id: int, shift_assignment_id: int | None = None, source: str = "Web",
             lat=None, lng=None, accuracy=None, note: str = "", punched_at: str | None = None):
    if source not in PUNCH_SOURCES:
        raise ValueError("invalid punch source")
    punched_at = punched_at or datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with cursor() as conn:
        open_punch = conn.execute("""SELECT id FROM clock_punches
                                     WHERE employee_id=? AND punch_type='In'
                                     AND NOT EXISTS (SELECT 1 FROM clock_punches o
                                                     WHERE o.employee_id=clock_punches.employee_id
                                                     AND o.punch_type='Out' AND o.punched_at>clock_punches.punched_at)
                                     ORDER BY punched_at DESC LIMIT 1""", (employee_id,)).fetchone()
        if open_punch:
            return None
        location = None
        if shift_assignment_id:
            location = conn.execute("SELECT location_label FROM shift_assignments WHERE id=?",
                                    (shift_assignment_id,)).fetchone()
        on_site = _on_site(conn, location[0] if location else None, lat, lng)
        return conn.execute("""INSERT INTO clock_punches
            (employee_id, shift_assignment_id, punch_type, punched_at, source, latitude, longitude, accuracy_m, note, on_site)
            VALUES (?, ?, 'In', ?, ?, ?, ?, ?, ?, ?)""",
                           (employee_id, shift_assignment_id, punched_at, source, lat, lng, accuracy, note, on_site)).lastrowid


def clock_out(employee_id: int, shift_assignment_id: int | None = None, source: str = "Web",
              lat=None, lng=None, accuracy=None, note: str = "", punched_at: str | None = None):
    if source not in PUNCH_SOURCES:
        raise ValueError("invalid punch source")
    punched_at = punched_at or datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with cursor() as conn:
        query = """SELECT * FROM clock_punches WHERE employee_id=? AND punch_type='In'
                   AND NOT EXISTS (SELECT 1 FROM clock_punches o WHERE o.employee_id=clock_punches.employee_id
                                   AND o.punch_type='Out' AND o.punched_at>clock_punches.punched_at)"""
        params = [employee_id]
        if shift_assignment_id:
            query += " AND shift_assignment_id=?"
            params.append(shift_assignment_id)
        query += " ORDER BY punched_at DESC LIMIT 1"
        start = conn.execute(query, tuple(params)).fetchone()
        if not start:
            return None
        hours = max(0, (datetime.fromisoformat(punched_at) - datetime.fromisoformat(start["punched_at"])).total_seconds() / 3600)
        location = conn.execute("SELECT location_label FROM shift_assignments WHERE id=?", (start["shift_assignment_id"],)).fetchone()
        on_site = _on_site(conn, location[0] if location else None, lat, lng)
        punch_id = conn.execute("""INSERT INTO clock_punches
            (employee_id, shift_assignment_id, punch_type, punched_at, source, latitude, longitude, accuracy_m, note, on_site)
            VALUES (?, ?, 'Out', ?, ?, ?, ?, ?, ?, ?)""",
                               (employee_id, start["shift_assignment_id"], punched_at, source, lat, lng, accuracy, note, on_site)).lastrowid
        assignment_id = start["shift_assignment_id"]
        if assignment_id:
            conn.execute("UPDATE shift_assignments SET status='Completed' WHERE id=? AND status='Scheduled'", (assignment_id,))
        att_date = start["punched_at"][:10]
        leave = conn.execute("SELECT id, status FROM attendance WHERE employee_id=? AND att_date=?", (employee_id, att_date)).fetchone()
        if not leave or leave["status"] != "On Leave":
            status = "Present" if hours >= 6 else "Half Day"
            if leave:
                conn.execute("UPDATE attendance SET status=?, hours=? WHERE id=?", (status, round(hours, 2), leave["id"]))
            else:
                conn.execute("INSERT INTO attendance(employee_id,att_date,status,hours) VALUES (?,?,?,?)",
                             (employee_id, att_date, status, round(hours, 2)))
        return {"id": punch_id, "hours": round(hours, 2), "att_date": att_date}


def punches_for(employee_id: int, from_date: str, to_date: str) -> list[dict]:
    return rows("""SELECT p.*, e.first_name, e.last_name FROM clock_punches p
                  JOIN employees e ON e.id=p.employee_id
                  WHERE p.employee_id=? AND substr(p.punched_at,1,10) BETWEEN ? AND ?
                  ORDER BY p.punched_at DESC""", (employee_id, from_date, to_date))


def auto_attendance_gap_report(from_date: str, to_date: str) -> list[dict]:
    return rows("""SELECT s.*, e.first_name, e.last_name, st.name shift_name
                 FROM shift_assignments s JOIN employees e ON e.id=s.employee_id
                 JOIN shift_types st ON st.id=s.shift_type_id
                 WHERE s.shift_date BETWEEN ? AND ? AND s.status IN ('Scheduled','Missed')
                   AND NOT EXISTS (SELECT 1 FROM clock_punches p WHERE p.shift_assignment_id=s.id)
                 ORDER BY s.shift_date, e.first_name""", (from_date, to_date))


# --- pay runs ---------------------------------------------------------------

def pay_runs() -> list[dict]:
    return rows("""SELECT r.*, COUNT(p.id) headcount,
                        COALESCE(SUM(p.gross), 0) gross_total,
                        COALESCE(SUM(p.net), 0) net_total
                 FROM pay_runs r LEFT JOIN payslips p ON p.run_id=r.id
                 GROUP BY r.id ORDER BY r.period DESC""")


def pay_run(run_id: int):
    run = one("SELECT * FROM pay_runs WHERE id=?", (run_id,))
    if not run:
        return None
    run["payslips"] = rows("""SELECT p.*, e.first_name, e.last_name, e.designation,
                                     e.code, d.name dept
                              FROM payslips p JOIN employees e ON e.id=p.employee_id
                              LEFT JOIN departments d ON d.id=e.dept_id
                              WHERE p.run_id=? ORDER BY e.first_name, e.last_name""", (run_id,))
    return run


def _overtime_for(employee_id: int, period: str) -> tuple[float, float]:
    hours = scalar("""SELECT COALESCE(SUM(MAX(hours - 8, 0)), 0)
                     FROM attendance WHERE employee_id=? AND att_date LIKE ?
                     AND status IN ('Present','Work From Home','Half Day')""",
                   (employee_id, period + "%")) or 0
    return float(hours), round(float(hours) * 1.5, 2)


def _as_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    text = str(value)
    return date.fromisoformat(f"{text}-01" if len(text) == 7 else text)


def _average_daily_income(employee_id: int, reference: str | date) -> float:
    """Average prior income over calendar days in available months.

    Estonian average income uses the six calendar months before the relevant
    month, divided by calendar days rather than working days. For employment
    under six months, months before the joining month are omitted. Months with
    no payslip are omitted as unavailable history instead of treated as zero.
    """
    reference_date = _as_date(reference)
    employee = one("SELECT date_of_joining FROM employees WHERE id=?", (employee_id,))
    if not employee:
        return 0.0
    joining = None
    try:
        joining = _as_date(employee["date_of_joining"]) if employee["date_of_joining"] else None
    except ValueError:
        pass
    history = rows("""SELECT period, COALESCE(gross_pay, gross, 0) income
                     FROM payslips WHERE employee_id=? AND period LIKE '____-__'""",
                   (employee_id,))
    by_month = {str(row["period"]): float(row["income"] or 0) for row in history}
    total_income = calendar_days = 0
    year, month = reference_date.year, reference_date.month
    for _ in range(6):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        if joining and (year, month) < (joining.year, joining.month):
            continue
        period = f"{year:04d}-{month:02d}"
        if period not in by_month:
            continue
        total_income += by_month[period]
        calendar_days += calendar.monthrange(year, month)[1]
    return total_income / calendar_days if calendar_days else 0.0


def holiday_pay(employee_id: int, holiday_start: str | date, holiday_end: str | date,
                calc_month: str | date) -> tuple[float, int]:
    """Return holiday pay and full calendar-day holiday count."""
    start, end = _as_date(holiday_start), _as_date(holiday_end)
    days = max(0, (end - start).days + 1)
    return round(_average_daily_income(employee_id, calc_month) * days, 2), days


def incapacity_pay(employee_id: int, sick_start: str | date,
                   sick_end: str | date) -> tuple[float, int]:
    """Return employer sick pay: 70% for calendar days 4 through 8.

    The first three days are the employee's own risk. Haigekassa pays from
    day nine; that part is intentionally out of scope here.
    """
    start, end = _as_date(sick_start), _as_date(sick_end)
    total_days = max(0, (end - start).days + 1)
    employer_days = max(0, min(total_days, 8) - 3)
    return round(_average_daily_income(employee_id, start) * employer_days * 0.70, 2), employer_days


def _prepare_payslip_benefits(conn, payslip_id: int, employee_id: int, period: str):
    """Add approved leave-derived earning lines once and refresh totals."""
    year, month = (int(part) for part in period.split("-"))
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    requests = conn.execute("""SELECT * FROM leave_requests
                              WHERE employee_id=? AND status='Approved'
                                AND leave_type IN ('Annual Leave', 'Sick Leave')
                                AND from_date <= ? AND to_date >= ?""",
                           (employee_id, month_end.isoformat(), month_start.isoformat())).fetchall()
    existing = {row["label"] for row in conn.execute(
        "SELECT label FROM payslip_lines WHERE payslip_id=?", (payslip_id,))}
    holiday_amount = holiday_days = sick_amount = sick_days = 0
    for request in requests:
        start = max(_as_date(request["from_date"]), month_start)
        end = min(_as_date(request["to_date"]), month_end)
        if request["leave_type"] == "Annual Leave":
            amount, days = holiday_pay(employee_id, start, end, period)
            holiday_amount += amount
            holiday_days += days
        else:
            # A certificate crossing a month boundary still has one day 1–8
            # sequence; it must not restart at the first day of each month.
            sick_start = _as_date(request["from_date"])
            employer_start = max(sick_start + timedelta(days=3), month_start)
            employer_end = min(sick_start + timedelta(days=7), _as_date(request["to_date"]), month_end)
            days = max(0, (employer_end - employer_start).days + 1)
            amount = round(_average_daily_income(employee_id, sick_start) * days * 0.70, 2)
            sick_amount += amount
            sick_days += days
    additions = []
    holiday_label = "Puhkusehüvitis / Holiday pay"
    sick_label = "Töövõimetustasu (tööandja 4.-8. päev) / Incapacity pay (employer)"
    if holiday_days and holiday_label not in existing:
        additions.append(("Earning", holiday_label, round(holiday_amount, 2), f"{holiday_days:g} kp"))
    if sick_days and sick_label not in existing:
        additions.append(("Earning", sick_label, round(sick_amount, 2), f"{sick_days:g} kp"))
    if not additions:
        return
    conn.executemany("""INSERT INTO payslip_lines(payslip_id,kind,label,amount,base)
                        VALUES (?,?,?,?,?)""", [(payslip_id, *line) for line in additions])
    extra = round(sum(line[2] for line in additions), 2)
    slip = conn.execute("SELECT * FROM payslips WHERE id=?", (payslip_id,)).fetchone()
    gross = round(float(slip["gross"] or 0) + extra, 2)
    tax, pension = round(gross * 0.22, 2), round(gross * 0.02, 2)
    unemployment = round(gross * 0.016, 2)
    employer_unemployment = round(gross * 0.008, 2)
    net = round(gross - tax - pension - unemployment, 2)
    conn.execute("""UPDATE payslips SET gross=?, gross_pay=?, tax=?, pension=?,
                   other_ded=?, net=? WHERE id=?""",
                 (gross, gross, tax, pension, unemployment, net, payslip_id))
    line_amounts = {"Income tax (22%)": tax, "Funded pension (II pillar, 2%)": pension,
                    "Employee unemployment insurance (1.6%)": unemployment,
                    "Employer unemployment insurance (0.8%)": employer_unemployment}
    for label, amount in line_amounts.items():
        conn.execute("UPDATE payslip_lines SET amount=? WHERE payslip_id=? AND label=?",
                     (amount, payslip_id, label))


def prepare_pay_run(run_id: int) -> int:
    """Refresh leave-derived lines for a pay run without duplicating them."""
    with cursor() as conn:
        run = conn.execute("SELECT period FROM pay_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            raise ValueError("Pay run not found")
        slips = conn.execute("SELECT id, employee_id FROM payslips WHERE run_id=?", (run_id,)).fetchall()
        for slip in slips:
            _prepare_payslip_benefits(conn, slip["id"], slip["employee_id"], run["period"])
    return run_id


def create_pay_run(period: str, employee_ids: list[int] | tuple[int, ...]) -> int:
    """Create a draft run and itemised payslips for selected active employees."""
    if not period or len(period) != 7 or period[4] != "-":
        raise ValueError("period must be YYYY-MM")
    selected = {int(eid) for eid in employee_ids}
    with cursor() as conn:
        existing = conn.execute("SELECT id FROM pay_runs WHERE period=?", (period,)).fetchone()
        if existing:
            run_id = existing[0]
            # Existing periods are deliberately refreshable: approved leave
            # may have been entered after the draft was first prepared.
            slips = conn.execute("SELECT id, employee_id FROM payslips WHERE run_id=?", (run_id,)).fetchall()
            for slip in slips:
                _prepare_payslip_benefits(conn, slip["id"], slip["employee_id"], period)
            return run_id
        run_id = conn.execute("""INSERT INTO pay_runs(period,status,run_date)
                                VALUES (?, 'Draft', ?)""", (period, TODAY.isoformat())).lastrowid
        emps = conn.execute("""SELECT id, base_salary FROM employees
                              WHERE status='Active' AND id IN ({})""".format(
                                  ",".join("?" for _ in selected) or "NULL"), tuple(selected)).fetchall()
        for emp in emps:
            monthly = round((emp["base_salary"] or 0) / 12, 2)
            overtime_hours, overtime = _overtime_for(emp["id"], period)
            gross = round(monthly + overtime, 2)
            tax = round(gross * 0.22, 2)
            pension = round(gross * 0.02, 2)
            employee_unemployment = round(gross * 0.016, 2)
            employer_unemployment = round(gross * 0.008, 2)
            net = round(gross - tax - pension - employee_unemployment, 2)
            payslip_id = conn.execute("""INSERT INTO payslips
                (employee_id,period,gross,tax,pension,other_ded,net,status,run_id,currency,working_days,gross_pay)
                VALUES (?,?,?,?,?,?,?,'Draft',?,'EUR',?,?)""",
                (emp["id"], period, gross, tax, pension, employee_unemployment, net,
                 run_id, 0, gross)).lastrowid
            lines = [("Earning", "Base salary", monthly, "monthly"),
                     ("Earning", "Overtime", overtime, f"{overtime_hours:.2f} hours")]
            lines += [("Deduction", "Income tax (22%)", tax, "22% of gross"),
                      ("Deduction", "Funded pension (II pillar, 2%)", pension, "2% of gross"),
                      ("Deduction", "Employee unemployment insurance (1.6%)",
                       employee_unemployment, "1.6% of gross"),
                      ("Deduction", "Employer unemployment insurance (0.8%)",
                       employer_unemployment, "0.8% of gross · employer cost")]
            conn.executemany("""INSERT INTO payslip_lines(payslip_id,kind,label,amount,base)
                                VALUES (?,?,?,?,?)""", [(payslip_id, *line) for line in lines])
    prepare_pay_run(run_id)
    return run_id


def advance_pay_run(run_id: int, status: str) -> bool:
    if status not in PAY_RUN_STATUSES:
        return False
    current = scalar("SELECT status FROM pay_runs WHERE id=?", (run_id,))
    if not current or PAY_RUN_TRANSITIONS.get(current) != status:
        return False
    with cursor() as conn:
        changed = conn.execute("UPDATE pay_runs SET status=?, run_date=? WHERE id=? AND status=?",
                               (status, TODAY.isoformat(), run_id, current)).rowcount
        if changed:
            conn.execute("UPDATE payslips SET status=? WHERE run_id=?", (status, run_id))
    return bool(changed)


def payslip_lines(payslip_id: int) -> list[dict]:
    return rows("SELECT * FROM payslip_lines WHERE payslip_id=? ORDER BY kind DESC, id", (payslip_id,))


def statutory_export(export_id: int):
    return one("SELECT * FROM statutory_exports WHERE id=?", (export_id,))


def offset_employee_advance(run_id: int, advance_id: int) -> bool:
    """Offset one approved advance against a draft run, atomically."""
    with cursor() as conn:
        run = conn.execute("SELECT status FROM pay_runs WHERE id=?", (run_id,)).fetchone()
        advance = conn.execute("SELECT * FROM employee_advances WHERE id=?", (advance_id,)).fetchone()
        if not run or run["status"] != "Draft" or not advance or advance["status"] != "Approved":
            return False
        slip = conn.execute("SELECT id,net FROM payslips WHERE run_id=? AND employee_id=?",
                            (run_id, advance["employee_id"])).fetchone()
        amount = round(float(advance["approved_amount"] or advance["requested_amount"] or 0), 2)
        if not slip or amount <= 0:
            return False
        changed = conn.execute("UPDATE employee_advances SET status='Offset',offset_run_id=?,decided_at=datetime('now') WHERE id=? AND status='Approved'",
                               (run_id, advance_id)).rowcount
        if not changed:
            return False
        conn.execute("INSERT INTO payslip_lines(payslip_id,kind,label,amount,base) VALUES(?,?,?,?,?)",
                     (slip["id"], "Deduction", "Advance offset", amount, "employee advance"))
        conn.execute("UPDATE payslips SET net=ROUND(net-?,2) WHERE id=?", (amount, slip["id"]))
        return True


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
