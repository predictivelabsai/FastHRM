-- Baseline: the original three-pillar schema (people, time, pay) + chat.
-- Applies cleanly to an existing fasthr.sqlite — every statement is IF NOT EXISTS.

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
