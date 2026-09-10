-- Workforce planning: budgeted positions and approval-led scenarios.
CREATE TABLE IF NOT EXISTS position_budgets (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL,
    department_id        INTEGER NULL REFERENCES departments(id),
    role_title           TEXT NOT NULL,
    headcount_target     INTEGER NOT NULL DEFAULT 1 CHECK (headcount_target >= 0),
    annual_salary_budget REAL NOT NULL DEFAULT 0,
    effective_date       TEXT NULL,
    status               TEXT NOT NULL DEFAULT 'Proposed'
                         CHECK (status IN ('Proposed', 'Approved', 'Rejected')),
    notes                TEXT NOT NULL DEFAULT '',
    created              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workforce_scenarios (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    headcount_delta    INTEGER NOT NULL DEFAULT 0,
    annual_cost_delta  REAL NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'Proposed'
                       CHECK (status IN ('Proposed', 'Approved', 'Rejected')),
    created            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_position_budgets_department
    ON position_budgets(department_id);
CREATE INDEX IF NOT EXISTS idx_workforce_scenarios_status
    ON workforce_scenarios(status);
