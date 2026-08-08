-- Public recruitment publishing: branded careers sites, versioned job pages,
-- candidate-facing application answers, and auditable consent records.

CREATE TABLE IF NOT EXISTS career_sites (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL,
    slug               TEXT NOT NULL UNIQUE,
    headline           TEXT,
    introduction       TEXT,
    brand_color        TEXT NOT NULL DEFAULT '#0891b2',
    accent_color       TEXT NOT NULL DEFAULT '#0e7490',
    logo_url           TEXT,
    privacy_policy_url TEXT,
    custom_domain      TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1,
    created            TEXT NOT NULL,
    updated            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_postings (
    id                   INTEGER PRIMARY KEY,
    job_id               INTEGER NOT NULL UNIQUE REFERENCES job_openings(id),
    career_site_id       INTEGER REFERENCES career_sites(id),
    slug                 TEXT NOT NULL UNIQUE,
    public_title         TEXT NOT NULL,
    summary              TEXT,
    description          TEXT,
    requirements         TEXT,
    benefits             TEXT,
    seo_title            TEXT,
    seo_description      TEXT,
    application_deadline TEXT,
    publication_status   TEXT NOT NULL DEFAULT 'Draft',
    published_at         TEXT,
    closed_at            TEXT,
    created_by           TEXT,
    updated_by           TEXT,
    created              TEXT NOT NULL,
    updated              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_posting_versions (
    id             INTEGER PRIMARY KEY,
    job_posting_id INTEGER NOT NULL REFERENCES job_postings(id),
    version        INTEGER NOT NULL,
    snapshot_json  TEXT NOT NULL,
    actor          TEXT,
    created        TEXT NOT NULL,
    UNIQUE(job_posting_id, version)
);

CREATE TABLE IF NOT EXISTS application_answers (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    field_key      TEXT NOT NULL,
    label          TEXT NOT NULL,
    value_text     TEXT,
    created        TEXT NOT NULL,
    UNIQUE(application_id, field_key)
);

CREATE TABLE IF NOT EXISTS candidate_consents (
    id                 INTEGER PRIMARY KEY,
    candidate_id       INTEGER NOT NULL REFERENCES candidates(id),
    application_id     INTEGER REFERENCES applications(id),
    purpose            TEXT NOT NULL,
    lawful_basis       TEXT NOT NULL DEFAULT 'consent',
    privacy_policy_url TEXT,
    consented_at       TEXT NOT NULL,
    expires_at         TEXT,
    withdrawn_at       TEXT,
    proof_json         TEXT
);

CREATE INDEX IF NOT EXISTS idx_posting_status ON job_postings(publication_status, published_at);
CREATE INDEX IF NOT EXISTS idx_posting_site ON job_postings(career_site_id, publication_status);
CREATE INDEX IF NOT EXISTS idx_versions_posting ON job_posting_versions(job_posting_id, version);
CREATE INDEX IF NOT EXISTS idx_answers_application ON application_answers(application_id);
CREATE INDEX IF NOT EXISTS idx_consents_candidate ON candidate_consents(candidate_id, consented_at);
