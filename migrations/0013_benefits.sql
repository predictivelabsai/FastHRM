-- Employer-paid benefits and employee enrolments. Ended enrolments are retained
-- for auditability; the unique key makes enrolment and reopening idempotent.
CREATE TABLE IF NOT EXISTS benefit_plans (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('health', 'pension_extra', 'sport', 'commute', 'other')),
    employer_contribution REAL NOT NULL DEFAULT 0,
    contribution_frequency TEXT NOT NULL DEFAULT 'monthly'
        CHECK (contribution_frequency IN ('monthly', 'per_payrun')),
    eligibility TEXT NOT NULL DEFAULT 'all_active'
        CHECK (eligibility IN ('all_active', 'department')),
    department_id INTEGER NULL REFERENCES departments(id),
    active INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS benefit_enrolments (
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES benefit_plans(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    started TEXT,
    ended TEXT NULL,
    employee_contribution REAL DEFAULT 0,
    UNIQUE(plan_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_benefit_enrolments_employee
    ON benefit_enrolments(employee_id);
CREATE INDEX IF NOT EXISTS idx_benefit_enrolments_plan
    ON benefit_enrolments(plan_id);
