-- Phase 2 statutory payroll exports: generated TÖR/TSD files and history.
CREATE TABLE IF NOT EXISTS statutory_exports (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('TOR', 'TSD')),
    period       TEXT NOT NULL,
    file_name    TEXT NOT NULL,
    row_count    INTEGER NOT NULL DEFAULT 0,
    payload      TEXT NOT NULL,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_statutory_exports_period ON statutory_exports(period);
CREATE INDEX IF NOT EXISTS idx_statutory_exports_kind ON statutory_exports(kind);

-- The baseline employee record is the current employment source. These
-- nullable fields fill the statutory identifiers that the earlier schema did
-- not need; existing rows remain valid and can be completed before export.
ALTER TABLE employees ADD COLUMN personal_code TEXT;
ALTER TABLE employees ADD COLUMN working_time_ratio REAL DEFAULT 1.0;
ALTER TABLE employees ADD COLUMN latest_amendment_date TEXT;
