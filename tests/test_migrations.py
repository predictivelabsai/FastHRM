"""Migrations must apply to an empty DB, be idempotent, and preserve data."""
from __future__ import annotations

import db as db_module


def test_applies_all_migrations_to_empty_db(fresh_db):
    versions = [r["version"] for r in fresh_db.rows("SELECT version FROM schema_migrations ORDER BY version")]
    assert "0001_baseline" in versions
    assert "0002_ats_core" in versions
    assert "0004_recruitment_publishing" in versions
    assert "0005_recruitment_platform" in versions

    tables = {r["name"] for r in fresh_db.rows("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("employees", "leave_requests", "payslips",          # baseline
              "job_openings", "candidates", "applications",        # ATS
              "candidate_skills", "extraction_runs", "prompts", "lifecycle_events",
              "career_sites", "job_postings", "job_posting_versions",
              "application_answers", "candidate_consents",
              "recruitment_projects", "candidate_comments", "candidate_pools", "communication_messages",
              "application_forms", "publication_schedules", "internal_job_posts",
              "automation_rules", "scheduling_links", "job_board_posts",
              "recruitment_analytics_events", "organizations", "identity_providers",
              "ai_screening_profiles", "video_interview_invitations"):
        assert t in tables, f"{t} missing after migration"


def test_migrate_is_idempotent(fresh_db):
    assert fresh_db.migrate() == [], "a second run should apply nothing"


def test_employees_gains_candidate_id(fresh_db):
    cols = {r["name"] for r in fresh_db.rows("PRAGMA table_info(employees)")}
    assert "candidate_id" in cols, "the people-graph link column is missing"


def test_migration_preserves_existing_rows(fresh_db):
    """A migration run must never disturb data already in the database."""
    with fresh_db.cursor() as conn:
        conn.execute("INSERT INTO departments(name) VALUES ('Engineering')")
        conn.execute("""INSERT INTO employees(code,first_name,last_name,status)
                        VALUES ('EMP-1','Ada','Lovelace','Active')""")
    fresh_db.migrate()
    e = fresh_db.one("SELECT * FROM employees WHERE code='EMP-1'")
    assert e["first_name"] == "Ada"
    assert fresh_db.scalar("SELECT COUNT(*) FROM departments") == 1


def test_migration_files_are_ordered_and_named(fresh_db):
    files = sorted(db_module.MIGRATIONS_DIR.glob("*.sql"))
    assert files, "no migration files found"
    for f in files:
        assert f.stem[:4].isdigit(), f"{f.name} must start with a 4-digit version"
