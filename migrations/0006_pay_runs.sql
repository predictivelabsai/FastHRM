-- Phase 1 payroll: pay runs and itemised payslips.
CREATE TABLE IF NOT EXISTS pay_runs (
    id         INTEGER PRIMARY KEY,
    period     TEXT NOT NULL UNIQUE,
    status     TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft', 'In Review', 'Approved', 'Paid')),
    run_date   TEXT,
    notes      TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payslip_lines (
    id         INTEGER PRIMARY KEY,
    payslip_id INTEGER NOT NULL REFERENCES payslips(id),
    kind       TEXT NOT NULL CHECK (kind IN ('Earning', 'Deduction')),
    label      TEXT NOT NULL,
    amount     REAL NOT NULL,
    base       TEXT
);

CREATE INDEX IF NOT EXISTS idx_payslip_lines_payslip ON payslip_lines(payslip_id);
CREATE INDEX IF NOT EXISTS idx_pay_runs_period ON pay_runs(period);

-- SQLite has no ADD COLUMN IF NOT EXISTS. These are deliberately last: the
-- migration ledger makes them safe on normal reruns and keeps partial retries
-- from repeating any preceding DDL.
ALTER TABLE payslips ADD COLUMN run_id INTEGER REFERENCES pay_runs(id);
ALTER TABLE payslips ADD COLUMN currency TEXT DEFAULT 'EUR';
ALTER TABLE payslips ADD COLUMN working_days REAL;
ALTER TABLE payslips ADD COLUMN gross_pay REAL;

CREATE INDEX IF NOT EXISTS idx_payslips_run ON payslips(run_id);
