-- Learning and development: courses, employee plans, and certifications.
CREATE TABLE IF NOT EXISTS courses (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'skills'
        CHECK (category IN ('onboarding', 'compliance', 'skills', 'leadership', 'other')),
    provider TEXT NOT NULL DEFAULT '',
    active   INTEGER NOT NULL DEFAULT 1,
    created  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learning_plans (
    id           INTEGER PRIMARY KEY,
    employee_id  INTEGER NOT NULL REFERENCES employees(id),
    course_id    INTEGER NOT NULL REFERENCES courses(id),
    assigned_by  TEXT NOT NULL DEFAULT '',
    due_date     TEXT NULL,
    status       TEXT NOT NULL DEFAULT 'Planned'
        CHECK (status IN ('Planned', 'In progress', 'Completed')),
    progress     INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    completed_on TEXT NULL,
    UNIQUE(employee_id, course_id)
);

CREATE TABLE IF NOT EXISTS certifications (
    id         INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    name       TEXT NOT NULL,
    issued_on  TEXT NULL,
    expires_on TEXT NULL,
    files_note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_learning_plans_employee
    ON learning_plans(employee_id);
CREATE INDEX IF NOT EXISTS idx_certifications_employee
    ON certifications(employee_id);
