"""FastHRM public reads and token-gated integration writes."""

import db

from .api_core import Resource, SQLiteBackend, create_sqlite_api

RESOURCES = (
    Resource("employees", "employees", "Employees", "Employee master records and employment state.", search_fields=("code", "first_name", "last_name", "email", "designation")),
    Resource("departments", "departments", "Departments", "Organisation departments.", search_fields=("name",)),
    Resource("leave", "leave_requests", "Leave requests", "Employee leave requests and approval status.", write_fields=("employee_id", "leave_type", "from_date", "to_date", "days", "status", "reason", "applied_on"), search_fields=("leave_type", "status", "reason")),
    Resource("attendance", "attendance", "Attendance", "Daily attendance and recorded hours.", search_fields=("att_date", "status")),
    Resource("jobs", "job_openings", "Job openings", "Open requisitions and their hiring state.", search_fields=("code", "title", "location", "status")),
    Resource("candidates", "candidates", "Candidates", "Candidate profiles, including CV-extracted fields.", search_fields=("first_name", "last_name", "email", "current_title", "current_employer")),
    Resource("applications", "applications", "Applications", "Candidate applications and pipeline stage.", write_fields=("candidate_id", "job_id", "stage", "status", "applied_on", "stage_entered_on", "rating", "rejection_reason"), search_fields=("stage", "status")),
    Resource("organizations", "organizations", "Organizations", "Enterprise recruitment organizations and locale defaults.", write_fields=("name", "slug", "default_locale", "timezone", "settings_json"), search_fields=("name", "slug")),
    Resource("brands", "brands", "Recruitment brands", "Brand, domain, and visual identity configuration.", write_fields=("organization_id", "name", "slug", "logo_url", "favicon_url", "primary_color", "accent_color", "custom_domain", "settings_json"), search_fields=("name", "slug", "custom_domain")),
    Resource("career-sites", "career_sites", "Career sites", "Candidate-facing careers sites.", write_fields=("name", "slug", "headline", "introduction", "brand_color", "accent_color", "logo_url", "privacy_policy_url", "is_active"), search_fields=("name", "slug")),
    Resource("organization-teams", "organization_teams", "Organization teams", "Country- and department-scoped enterprise recruiting teams.", write_fields=("organization_id", "parent_id", "name", "country", "department_id", "settings_json"), search_fields=("name", "country")),
    Resource("job-distributions", "job_distributions", "Job distributions", "Localized job placements across career sites and brands.", write_fields=("job_posting_id", "career_site_id", "brand_id", "locale", "slug", "status", "published_at"), search_fields=("locale", "slug", "status")),
)

backend = SQLiteBackend(db.DB_PATH, RESOURCES, initialize=db.init_schema)
api = create_sqlite_api(
    product="FastHRM", version="1.0.0",
    description="Open integration access to FastHRM people, recruiting, and enterprise configuration data.",
    base_url="https://hrm.fastsme.com", backend=backend, resources=RESOURCES,
)
