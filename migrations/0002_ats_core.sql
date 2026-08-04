-- ATS core: requisitions, candidates, applications, parsed CV entities,
-- extraction audit, and the versioned prompt store.
--
-- Postgres-shaped on purpose: no SQLite-only constructs, ISO-8601 text dates,
-- explicit types. See docs/TALENT-PLATFORM-PLAN.md §A2.

CREATE TABLE IF NOT EXISTS job_openings (
    id                INTEGER PRIMARY KEY,
    code              TEXT,
    title             TEXT NOT NULL,
    dept_id           INTEGER REFERENCES departments(id),
    hiring_manager_id INTEGER REFERENCES employees(id),
    headcount         INTEGER NOT NULL DEFAULT 1,
    filled            INTEGER NOT NULL DEFAULT 0,
    comp_min          REAL,
    comp_max          REAL,
    currency          TEXT DEFAULT 'GBP',
    location          TEXT,
    remote_policy     TEXT,             -- Onsite | Hybrid | Remote
    employment_type   TEXT,             -- Permanent | Contract | Intern
    status            TEXT NOT NULL DEFAULT 'Draft',  -- Draft|Open|On Hold|Closed|Filled
    description       TEXT,
    requirements      TEXT,
    stages_json       TEXT,             -- pipeline stage list, JSON array
    opened_on         TEXT,
    target_date       TEXT,
    created           TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    id                INTEGER PRIMARY KEY,
    first_name        TEXT,
    last_name         TEXT,
    email             TEXT,
    phone             TEXT,
    location          TEXT,
    headline          TEXT,
    current_title     TEXT,
    current_employer  TEXT,
    years_experience  REAL,
    linkedin_url      TEXT,
    source            TEXT,             -- Direct|Referral|Job Board|Agency|Import
    referred_by       INTEGER REFERENCES employees(id),
    consent_at        TEXT,             -- GDPR: when the candidate consented
    status            TEXT NOT NULL DEFAULT 'Active',  -- Active|Hired|Archived
    notes             TEXT,
    created           TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id                INTEGER PRIMARY KEY,
    candidate_id      INTEGER NOT NULL REFERENCES candidates(id),
    job_id            INTEGER NOT NULL REFERENCES job_openings(id),
    stage             TEXT NOT NULL DEFAULT 'Applied',
    status            TEXT NOT NULL DEFAULT 'Active',  -- Active|Hired|Rejected|Withdrawn
    applied_on        TEXT,
    stage_entered_on  TEXT,
    rating            REAL,
    rejection_reason  TEXT,
    created           TEXT
);

CREATE TABLE IF NOT EXISTS candidate_documents (
    id                INTEGER PRIMARY KEY,
    candidate_id      INTEGER REFERENCES candidates(id),
    kind              TEXT NOT NULL DEFAULT 'CV',   -- CV|Cover Letter|Portfolio|Other
    file_name         TEXT,
    mime              TEXT,
    bytes             INTEGER,
    stored_path       TEXT,
    text_content      TEXT,             -- extracted plain text, fed to the model
    uploaded_on       TEXT
);

CREATE TABLE IF NOT EXISTS candidate_skills (
    id                INTEGER PRIMARY KEY,
    candidate_id      INTEGER REFERENCES candidates(id),
    skill             TEXT NOT NULL,
    level             TEXT,             -- Beginner|Intermediate|Advanced|Expert
    years             REAL,
    evidence          TEXT,             -- where in the CV this came from
    source            TEXT DEFAULT 'cv-extraction'
);

CREATE TABLE IF NOT EXISTS candidate_experience (
    id                INTEGER PRIMARY KEY,
    candidate_id      INTEGER REFERENCES candidates(id),
    employer          TEXT,
    title             TEXT,
    start_date        TEXT,
    end_date          TEXT,             -- NULL = current
    location          TEXT,
    summary           TEXT,
    sort_order        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS candidate_education (
    id                INTEGER PRIMARY KEY,
    candidate_id      INTEGER REFERENCES candidates(id),
    institution       TEXT,
    qualification     TEXT,
    field             TEXT,
    end_year          TEXT
);

-- Every model call is auditable: which prompt version, which model, what it
-- cost, and the raw response for diagnosing a bad parse.
CREATE TABLE IF NOT EXISTS extraction_runs (
    id                INTEGER PRIMARY KEY,
    candidate_id      INTEGER REFERENCES candidates(id),
    document_id       INTEGER REFERENCES candidate_documents(id),
    prompt_key        TEXT,
    prompt_version    INTEGER,
    model             TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',  -- pending|ok|error
    latency_ms        INTEGER,
    raw_response      TEXT,
    error             TEXT,
    created           TEXT
);

-- Business-editable prompts. The output contract stays in code so an edit here
-- can never break parsing. New edits insert a new version; nothing is updated
-- in place.
CREATE TABLE IF NOT EXISTS prompts (
    id                INTEGER PRIMARY KEY,
    key               TEXT NOT NULL,
    version           INTEGER NOT NULL DEFAULT 1,
    title             TEXT,
    content           TEXT NOT NULL,
    is_active         INTEGER NOT NULL DEFAULT 1,
    updated_by        TEXT,
    updated           TEXT
);

-- Append-only history spine, shared by ATS, performance and lifecycle.
CREATE TABLE IF NOT EXISTS lifecycle_events (
    id                INTEGER PRIMARY KEY,
    entity_type       TEXT NOT NULL,
    entity_id         INTEGER NOT NULL,
    actor             TEXT,
    from_state        TEXT,
    to_state          TEXT,
    payload_json      TEXT,
    created           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_app_job ON applications(job_id, stage);
CREATE INDEX IF NOT EXISTS idx_app_cand ON applications(candidate_id);
CREATE INDEX IF NOT EXISTS idx_cdoc_cand ON candidate_documents(candidate_id);
CREATE INDEX IF NOT EXISTS idx_cskill_cand ON candidate_skills(candidate_id);
CREATE INDEX IF NOT EXISTS idx_cexp_cand ON candidate_experience(candidate_id);
CREATE INDEX IF NOT EXISTS idx_cedu_cand ON candidate_education(candidate_id);
CREATE INDEX IF NOT EXISTS idx_xrun_cand ON extraction_runs(candidate_id);
CREATE INDEX IF NOT EXISTS idx_prompt_key ON prompts(key, version);
CREATE INDEX IF NOT EXISTS idx_lifecycle_entity ON lifecycle_events(entity_type, entity_id);

-- The people graph: a hired candidate keeps its history (plan §A3).
-- SQLite has no ADD COLUMN IF NOT EXISTS; the migration ledger guarantees this
-- runs once, and it is last in the file so a re-run after a partial failure
-- only repeats idempotent DDL.
ALTER TABLE employees ADD COLUMN candidate_id INTEGER REFERENCES candidates(id);
