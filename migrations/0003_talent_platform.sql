-- The rest of the platform: interviewing, offers and hire conversion (plan §4.5–4.7),
-- performance (§5), lifecycle (§6), and the cross-cutting integration, approval,
-- notification and role tables (§7, §F2, §F3).

-- ---------- platform ------------------------------------------------------

-- Light RBAC: an account may hold several roles, each with a data scope
-- ('all' | 'dept:<id>' | 'self'). Enforcement lands with slice 1; the store and
-- the admin UI come first so roles can be assigned meanwhile.
CREATE TABLE IF NOT EXISTS account_roles (
    id            INTEGER PRIMARY KEY,
    account_email TEXT NOT NULL,
    role          TEXT NOT NULL,   -- admin|hrbp|recruiter|hiring_manager|manager|employee
    scope         TEXT NOT NULL DEFAULT 'all',
    employee_id   INTEGER REFERENCES employees(id),
    created       TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id            INTEGER PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    entity_id     INTEGER NOT NULL,
    approver      TEXT,
    sequence      INTEGER NOT NULL DEFAULT 1,
    decision      TEXT NOT NULL DEFAULT 'Pending',  -- Pending|Approved|Rejected
    note          TEXT,
    decided_at    TEXT,
    created       TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id            INTEGER PRIMARY KEY,
    recipient     TEXT,
    kind          TEXT,
    title         TEXT NOT NULL,
    body          TEXT,
    link          TEXT,
    read_at       TEXT,
    created       TEXT NOT NULL
);

-- Third-party connections. Secrets are encrypted at rest (Fernet, key derived
-- from FASTHR_SECRET) and never rendered back to the browser in full.
CREATE TABLE IF NOT EXISTS integrations (
    id             INTEGER PRIMARY KEY,
    provider       TEXT NOT NULL UNIQUE,   -- linkedin|indeed|slack|google_calendar|…
    label          TEXT,
    category       TEXT,                   -- job_board|social|calendar|messaging|esign|screening|hris
    status         TEXT NOT NULL DEFAULT 'Not configured',  -- Not configured|Connected|Error|Disabled
    api_key_enc    TEXT,
    api_secret_enc TEXT,
    account_ref    TEXT,                   -- org id / account handle at the provider
    config_json    TEXT,
    auto_sync      INTEGER NOT NULL DEFAULT 0,
    last_test_at   TEXT,
    last_test_ok   INTEGER,
    last_test_note TEXT,
    last_sync_at   TEXT,
    created        TEXT,
    updated        TEXT
);

CREATE TABLE IF NOT EXISTS integration_events (
    id             INTEGER PRIMARY KEY,
    integration_id INTEGER REFERENCES integrations(id),
    kind           TEXT,          -- test|sync|publish|import|error
    ok             INTEGER,
    detail         TEXT,
    records        INTEGER DEFAULT 0,
    actor          TEXT,
    created        TEXT NOT NULL
);

-- ---------- shared competency framework (ATS + performance) ---------------

CREATE TABLE IF NOT EXISTS competencies (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT,           -- Technical|Delivery|Leadership|Collaboration
    description   TEXT,
    levels_json   TEXT
);

-- ---------- interviewing --------------------------------------------------

CREATE TABLE IF NOT EXISTS interviews (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    interviewer_id INTEGER REFERENCES employees(id),
    kind           TEXT,          -- Screen|Technical|Culture|Panel|Final
    scheduled_at   TEXT,
    duration_min   INTEGER DEFAULT 45,
    mode           TEXT,          -- Video|Onsite|Phone
    status         TEXT NOT NULL DEFAULT 'Scheduled',  -- Scheduled|Completed|Cancelled|No show
    recommendation TEXT,          -- Strong hire|Hire|No decision|No hire|Strong no hire
    notes          TEXT,
    ai_summary     TEXT,
    created        TEXT
);

CREATE TABLE IF NOT EXISTS scorecards (
    id            INTEGER PRIMARY KEY,
    interview_id  INTEGER NOT NULL REFERENCES interviews(id),
    competency_id INTEGER REFERENCES competencies(id),
    score         REAL,           -- 1–5
    comment       TEXT
);

-- ---------- ranking (explainable, bias-audited) ---------------------------

CREATE TABLE IF NOT EXISTS ranking_runs (
    id             INTEGER PRIMARY KEY,
    job_id         INTEGER REFERENCES job_openings(id),
    model          TEXT,
    prompt_version INTEGER,
    excluded_json  TEXT,          -- fields withheld from the model, for the bias audit
    candidates     INTEGER DEFAULT 0,
    status         TEXT DEFAULT 'ok',
    error          TEXT,
    created        TEXT
);

CREATE TABLE IF NOT EXISTS ranking_scores (
    id             INTEGER PRIMARY KEY,
    ranking_run_id INTEGER REFERENCES ranking_runs(id),
    application_id INTEGER REFERENCES applications(id),
    score          REAL,
    rationale      TEXT,
    strengths      TEXT,
    gaps           TEXT
);

-- ---------- offers --------------------------------------------------------

CREATE TABLE IF NOT EXISTS offers (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    salary         REAL,
    currency       TEXT DEFAULT 'GBP',
    start_date     TEXT,
    status         TEXT NOT NULL DEFAULT 'Draft',  -- Draft|Pending approval|Approved|Sent|Accepted|Declined|Withdrawn
    letter         TEXT,
    approved_by    TEXT,
    sent_at        TEXT,
    signed_at      TEXT,
    expires_on     TEXT,
    declined_reason TEXT,
    created        TEXT
);

-- ---------- performance ---------------------------------------------------

CREATE TABLE IF NOT EXISTS goals (
    id             INTEGER PRIMARY KEY,
    owner_type     TEXT NOT NULL DEFAULT 'employee',  -- company|department|employee
    owner_id       INTEGER,
    parent_goal_id INTEGER REFERENCES goals(id),
    title          TEXT NOT NULL,
    metric         TEXT,
    target         REAL,
    current        REAL DEFAULT 0,
    unit           TEXT,
    period         TEXT,           -- e.g. 2026-Q3
    status         TEXT NOT NULL DEFAULT 'On track',  -- On track|At risk|Behind|Complete|Cancelled
    due_date       TEXT,
    created        TEXT
);

CREATE TABLE IF NOT EXISTS goal_checkins (
    id            INTEGER PRIMARY KEY,
    goal_id       INTEGER NOT NULL REFERENCES goals(id),
    value         REAL,
    status        TEXT,
    note          TEXT,
    created_by    TEXT,
    created       TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id                INTEGER PRIMARY KEY,
    from_employee_id  INTEGER REFERENCES employees(id),
    to_employee_id    INTEGER NOT NULL REFERENCES employees(id),
    kind              TEXT NOT NULL DEFAULT 'Praise',  -- Praise|Constructive|Peer review|Manager note
    competency_id     INTEGER REFERENCES competencies(id),
    body              TEXT NOT NULL,
    visibility        TEXT NOT NULL DEFAULT 'Team',    -- Public|Team|Private|Manager only
    created           TEXT
);

CREATE TABLE IF NOT EXISTS review_cycles (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    period_start  TEXT,
    period_end    TEXT,
    status        TEXT NOT NULL DEFAULT 'Draft',  -- Draft|Open|Calibration|Closed
    created       TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id            INTEGER PRIMARY KEY,
    cycle_id      INTEGER NOT NULL REFERENCES review_cycles(id),
    employee_id   INTEGER NOT NULL REFERENCES employees(id),
    reviewer_id   INTEGER REFERENCES employees(id),
    kind          TEXT NOT NULL DEFAULT 'Manager',  -- Self|Manager|Peer|Skip-level
    status        TEXT NOT NULL DEFAULT 'Not started',  -- Not started|In progress|Submitted|Calibrated
    overall       REAL,
    ratings_json  TEXT,
    narrative     TEXT,
    submitted_on  TEXT
);

CREATE TABLE IF NOT EXISTS employee_skills (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER NOT NULL REFERENCES employees(id),
    skill         TEXT NOT NULL,
    level         TEXT,
    years         REAL,
    source        TEXT DEFAULT 'manual',
    verified_by   INTEGER REFERENCES employees(id)
);

-- ---------- lifecycle -----------------------------------------------------

CREATE TABLE IF NOT EXISTS onboarding_templates (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    role_filter   TEXT,
    tasks_json    TEXT NOT NULL,
    created       TEXT
);

CREATE TABLE IF NOT EXISTS onboarding_tasks (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER NOT NULL REFERENCES employees(id),
    template_id   INTEGER REFERENCES onboarding_templates(id),
    title         TEXT NOT NULL,
    owner_role    TEXT,           -- HR|Manager|IT|New hire
    due_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'Open',  -- Open|Done|Blocked|N/A
    completed_on  TEXT,
    sort_order    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS employee_changes (
    id             INTEGER PRIMARY KEY,
    employee_id    INTEGER NOT NULL REFERENCES employees(id),
    change_type    TEXT NOT NULL,   -- Promotion|Transfer|Role change|Salary change|Manager change
    effective_date TEXT,
    from_json      TEXT,
    to_json        TEXT,
    status         TEXT NOT NULL DEFAULT 'Pending',  -- Pending|Approved|Applied|Rejected
    approved_by    TEXT,
    note           TEXT,
    created        TEXT
);

CREATE TABLE IF NOT EXISTS separations (
    id                  INTEGER PRIMARY KEY,
    employee_id         INTEGER NOT NULL REFERENCES employees(id),
    kind                TEXT NOT NULL,   -- Resignation|Termination|End of contract|Retirement
    notice_date         TEXT,
    last_day            TEXT,
    reason              TEXT,
    status              TEXT NOT NULL DEFAULT 'Open',  -- Open|In progress|Complete
    checklist_json      TEXT,
    exit_interview      TEXT,
    exit_sentiment      TEXT,
    alumni_status       TEXT DEFAULT 'Eligible',  -- Eligible|Not eligible|Rehired
    created             TEXT
);

CREATE TABLE IF NOT EXISTS cases (
    id            INTEGER PRIMARY KEY,
    employee_id   INTEGER REFERENCES employees(id),
    kind          TEXT NOT NULL,   -- Grievance|Wellbeing|Conduct|Pay query|Other
    severity      TEXT NOT NULL DEFAULT 'Normal',  -- Low|Normal|High|Critical
    visibility    TEXT NOT NULL DEFAULT 'HR only',
    status        TEXT NOT NULL DEFAULT 'Open',  -- Open|Investigating|Resolved|Closed
    summary       TEXT NOT NULL,
    resolution    TEXT,
    opened_by     TEXT,
    created       TEXT,
    closed_at     TEXT
);

-- ---------- indexes -------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_interview_app ON interviews(application_id);
CREATE INDEX IF NOT EXISTS idx_scorecard_iv ON scorecards(interview_id);
CREATE INDEX IF NOT EXISTS idx_offer_app ON offers(application_id);
CREATE INDEX IF NOT EXISTS idx_rscore_run ON ranking_scores(ranking_run_id);
CREATE INDEX IF NOT EXISTS idx_goal_owner ON goals(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_goal_parent ON goals(parent_goal_id);
CREATE INDEX IF NOT EXISTS idx_feedback_to ON feedback(to_employee_id);
CREATE INDEX IF NOT EXISTS idx_review_cycle ON reviews(cycle_id, employee_id);
CREATE INDEX IF NOT EXISTS idx_onb_emp ON onboarding_tasks(employee_id, status);
CREATE INDEX IF NOT EXISTS idx_change_emp ON employee_changes(employee_id);
CREATE INDEX IF NOT EXISTS idx_sep_emp ON separations(employee_id);
CREATE INDEX IF NOT EXISTS idx_case_emp ON cases(employee_id, status);
CREATE INDEX IF NOT EXISTS idx_appr_entity ON approvals(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_ievent_int ON integration_events(integration_id);
CREATE INDEX IF NOT EXISTS idx_empskill_emp ON employee_skills(employee_id);

-- Employment state the lifecycle module needs. Last in the file: SQLite has no
-- ADD COLUMN IF NOT EXISTS, and the ledger guarantees a single run.
ALTER TABLE employees ADD COLUMN employment_type TEXT DEFAULT 'Permanent';
ALTER TABLE employees ADD COLUMN probation_end TEXT;
ALTER TABLE employees ADD COLUMN termination_date TEXT;
ALTER TABLE employees ADD COLUMN alumni INTEGER NOT NULL DEFAULT 0;
