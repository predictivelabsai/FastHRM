-- Phase 3: expense claims, employee advances and travel requests.
CREATE TABLE IF NOT EXISTS expense_categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    requires_receipt INTEGER NOT NULL DEFAULT 1,
    daily_limit REAL,
    monthly_limit REAL
);

CREATE TABLE IF NOT EXISTS expense_claims (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    category_id INTEGER NOT NULL REFERENCES expense_categories(id),
    claim_date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    currency TEXT NOT NULL DEFAULT 'EUR',
    tax_rate REAL NOT NULL DEFAULT 0,
    receipt_path TEXT,
    status TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft', 'Submitted', 'Approved', 'Rejected', 'Reimbursed')),
    approver_id INTEGER REFERENCES employees(id),
    decided_at TEXT,
    reimbursed_at TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS employee_advances (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    requested_amount REAL NOT NULL CHECK (requested_amount >= 0),
    approved_amount REAL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Requested' CHECK (status IN ('Requested', 'Approved', 'Rejected', 'Repaid', 'Offset')),
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT,
    offset_run_id INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS travel_requests (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    destination TEXT NOT NULL,
    purpose TEXT NOT NULL,
    from_date TEXT NOT NULL,
    to_date TEXT NOT NULL,
    estimated_cost REAL NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
    advance_requested REAL NOT NULL DEFAULT 0 CHECK (advance_requested >= 0),
    status TEXT NOT NULL DEFAULT 'Submitted' CHECK (status IN ('Submitted', 'Approved', 'Rejected', 'Returned')),
    approver_id INTEGER REFERENCES employees(id),
    decided_at TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_expense_claims_employee ON expense_claims(employee_id);
CREATE INDEX IF NOT EXISTS idx_expense_claims_status ON expense_claims(status);
CREATE INDEX IF NOT EXISTS idx_employee_advances_employee ON employee_advances(employee_id);
CREATE INDEX IF NOT EXISTS idx_employee_advances_status ON employee_advances(status);
CREATE INDEX IF NOT EXISTS idx_travel_requests_employee ON travel_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_travel_requests_status ON travel_requests(status);
