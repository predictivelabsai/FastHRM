-- Recruitment platform phases 2-5. All tables are additive so installations can
-- upgrade without rewriting existing ATS, candidate, or publication records.

-- ---------- phase 2: recruiter operating system --------------------------

CREATE TABLE IF NOT EXISTS pipeline_templates (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
    stages_json TEXT NOT NULL, scorecard_template_id INTEGER, is_default INTEGER NOT NULL DEFAULT 0,
    created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recruitment_projects (
    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL UNIQUE REFERENCES job_openings(id),
    template_id INTEGER REFERENCES pipeline_templates(id), category TEXT,
    continuous INTEGER NOT NULL DEFAULT 0, confidential INTEGER NOT NULL DEFAULT 0,
    access_json TEXT, custom_fields_json TEXT, archived_at TEXT,
    created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_members (
    id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES recruitment_projects(id),
    account_email TEXT NOT NULL, role TEXT NOT NULL, can_view_salary INTEGER NOT NULL DEFAULT 0,
    can_decide INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL,
    UNIQUE(project_id, account_email)
);

CREATE TABLE IF NOT EXISTS saved_candidate_views (
    id INTEGER PRIMARY KEY, owner_email TEXT NOT NULL, name TEXT NOT NULL,
    filters_json TEXT NOT NULL, shared INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL,
    UNIQUE(owner_email, name)
);

CREATE TABLE IF NOT EXISTS candidate_pools (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
    filters_json TEXT NOT NULL, automatic INTEGER NOT NULL DEFAULT 1,
    owner_email TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_pool_members (
    pool_id INTEGER NOT NULL REFERENCES candidate_pools(id),
    candidate_id INTEGER NOT NULL REFERENCES candidates(id), source TEXT NOT NULL DEFAULT 'rule',
    added_at TEXT NOT NULL, PRIMARY KEY(pool_id,candidate_id)
);

CREATE TABLE IF NOT EXISTS talent_tags (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_tags (
    candidate_id INTEGER NOT NULL REFERENCES candidates(id), tag_id INTEGER NOT NULL REFERENCES talent_tags(id),
    added_by TEXT, created TEXT NOT NULL, PRIMARY KEY(candidate_id, tag_id)
);

CREATE TABLE IF NOT EXISTS candidate_comments (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    application_id INTEGER REFERENCES applications(id), body TEXT NOT NULL,
    rating REAL, visibility TEXT NOT NULL DEFAULT 'team', pinned INTEGER NOT NULL DEFAULT 0,
    author TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recruiting_tasks (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT, assignee TEXT,
    candidate_id INTEGER REFERENCES candidates(id), application_id INTEGER REFERENCES applications(id),
    job_id INTEGER REFERENCES job_openings(id), due_at TEXT, status TEXT NOT NULL DEFAULT 'Open',
    priority TEXT NOT NULL DEFAULT 'Normal', created_by TEXT, completed_at TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_field_definitions (
    id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, label TEXT NOT NULL, field_type TEXT NOT NULL,
    options_json TEXT, required INTEGER NOT NULL DEFAULT 0, searchable INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_field_values (
    candidate_id INTEGER NOT NULL REFERENCES candidates(id), field_id INTEGER NOT NULL REFERENCES candidate_field_definitions(id),
    value_text TEXT, updated_by TEXT, updated TEXT NOT NULL, PRIMARY KEY(candidate_id, field_id)
);

CREATE TABLE IF NOT EXISTS application_drop_reasons (
    id INTEGER PRIMARY KEY, application_id INTEGER NOT NULL REFERENCES applications(id),
    reason TEXT NOT NULL, detail TEXT, actor TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_merge_events (
    id INTEGER PRIMARY KEY, survivor_id INTEGER NOT NULL REFERENCES candidates(id),
    merged_id INTEGER NOT NULL, snapshot_json TEXT NOT NULL, actor TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bulk_actions (
    id INTEGER PRIMARY KEY, action_type TEXT NOT NULL, payload_json TEXT,
    requested_by TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Queued',
    total INTEGER NOT NULL DEFAULT 0, succeeded INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS bulk_action_items (
    id INTEGER PRIMARY KEY, bulk_action_id INTEGER NOT NULL REFERENCES bulk_actions(id),
    candidate_id INTEGER REFERENCES candidates(id), application_id INTEGER REFERENCES applications(id),
    status TEXT NOT NULL DEFAULT 'Queued', error TEXT, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS scorecard_templates (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scorecard_template_items (
    id INTEGER PRIMARY KEY, template_id INTEGER NOT NULL REFERENCES scorecard_templates(id),
    competency_id INTEGER REFERENCES competencies(id), label TEXT NOT NULL, description TEXT,
    weight REAL NOT NULL DEFAULT 1, required INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reference_requests (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    application_id INTEGER REFERENCES applications(id), referee_name TEXT NOT NULL, referee_email TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'Requested', response_json TEXT,
    requested_by TEXT, requested_at TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS candidate_credentials (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    name TEXT NOT NULL, issuer TEXT, credential_number TEXT, issued_on TEXT, expires_on TEXT,
    verified_at TEXT, status TEXT NOT NULL DEFAULT 'Unverified', document_id INTEGER REFERENCES candidate_documents(id),
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_forms (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
    confirmation_subject TEXT, confirmation_body TEXT, created_by TEXT,
    created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_form_fields (
    id INTEGER PRIMARY KEY, form_id INTEGER NOT NULL REFERENCES application_forms(id),
    field_key TEXT NOT NULL, label TEXT NOT NULL, field_type TEXT NOT NULL,
    options_json TEXT, required INTEGER NOT NULL DEFAULT 0, condition_json TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0, UNIQUE(form_id, field_key)
);

CREATE TABLE IF NOT EXISTS job_application_forms (
    job_posting_id INTEGER NOT NULL UNIQUE REFERENCES job_postings(id),
    form_id INTEGER NOT NULL REFERENCES application_forms(id),
    PRIMARY KEY(job_posting_id, form_id)
);

CREATE TABLE IF NOT EXISTS publication_schedules (
    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES job_openings(id),
    action TEXT NOT NULL, scheduled_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
    requested_by TEXT, created TEXT NOT NULL, processed_at TEXT, error TEXT
);

CREATE TABLE IF NOT EXISTS internal_job_posts (
    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES job_openings(id),
    audience_json TEXT, status TEXT NOT NULL DEFAULT 'Draft', published_at TEXT,
    closes_at TEXT, created_by TEXT, created TEXT NOT NULL
);

-- ---------- phase 3: communication, automation, and privacy --------------

CREATE TABLE IF NOT EXISTS recruitment_mailboxes (
    id INTEGER PRIMARY KEY, provider TEXT NOT NULL, address TEXT NOT NULL UNIQUE,
    display_name TEXT, signature_html TEXT, sync_cursor TEXT, last_sync_at TEXT,
    status TEXT NOT NULL DEFAULT 'Active', config_json TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message_templates (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, channel TEXT NOT NULL DEFAULT 'email',
    subject TEXT, body_html TEXT NOT NULL, body_text TEXT, locale TEXT NOT NULL DEFAULT 'en',
    created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_messages (
    id INTEGER PRIMARY KEY, thread_key TEXT NOT NULL, candidate_id INTEGER REFERENCES candidates(id),
    application_id INTEGER REFERENCES applications(id), channel TEXT NOT NULL, direction TEXT NOT NULL,
    sender TEXT, recipient TEXT, subject TEXT, body_html TEXT, body_text TEXT,
    template_id INTEGER REFERENCES message_templates(id), provider_message_id TEXT,
    status TEXT NOT NULL DEFAULT 'Draft', scheduled_at TEXT, sent_at TEXT, delivered_at TEXT,
    read_at TEXT, clicked_at TEXT, bounced_at TEXT, error TEXT, metadata_json TEXT,
    created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_events (
    id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL REFERENCES communication_messages(id),
    event_type TEXT NOT NULL, payload_json TEXT, occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automation_rules (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, trigger_event TEXT NOT NULL,
    conditions_json TEXT, actions_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY, rule_id INTEGER NOT NULL REFERENCES automation_rules(id),
    entity_type TEXT, entity_id INTEGER, event_json TEXT, status TEXT NOT NULL,
    result_json TEXT, error TEXT, started_at TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS candidate_portal_tokens (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, last_used_at TEXT,
    revoked_at TEXT, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_requests (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    application_id INTEGER REFERENCES applications(id), request_type TEXT NOT NULL,
    title TEXT NOT NULL, fields_json TEXT, response_json TEXT, status TEXT NOT NULL DEFAULT 'Open',
    due_at TEXT, created_by TEXT, created TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS privacy_requests (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    request_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', details TEXT,
    requested_at TEXT NOT NULL, verified_at TEXT, completed_at TEXT, handled_by TEXT,
    export_path TEXT, result_json TEXT
);

CREATE TABLE IF NOT EXISTS retention_policies (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, purpose TEXT NOT NULL,
    retention_months INTEGER NOT NULL, action TEXT NOT NULL DEFAULT 'Anonymize',
    active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS surveys (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, audience TEXT NOT NULL,
    trigger_event TEXT, questions_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS survey_invitations (
    id INTEGER PRIMARY KEY, survey_id INTEGER NOT NULL REFERENCES surveys(id),
    candidate_id INTEGER REFERENCES candidates(id), recipient_email TEXT, token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'Sent', sent_at TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS survey_responses (
    id INTEGER PRIMARY KEY, invitation_id INTEGER NOT NULL UNIQUE REFERENCES survey_invitations(id),
    score REAL, answers_json TEXT NOT NULL, submitted_at TEXT NOT NULL
);

-- ---------- phase 4: scheduling, marketing, integrations, analytics ------

CREATE TABLE IF NOT EXISTS interviewer_availability (
    id INTEGER PRIMARY KEY, account_email TEXT NOT NULL, weekday INTEGER NOT NULL,
    start_time TEXT NOT NULL, end_time TEXT NOT NULL, timezone TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS scheduling_links (
    id INTEGER PRIMARY KEY, application_id INTEGER NOT NULL REFERENCES applications(id),
    token TEXT NOT NULL UNIQUE, duration_minutes INTEGER NOT NULL DEFAULT 30,
    mode TEXT NOT NULL DEFAULT 'Video', provider TEXT, interviewer_emails_json TEXT NOT NULL,
    window_start TEXT NOT NULL, window_end TEXT NOT NULL, timezone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open', expires_at TEXT NOT NULL, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_bookings (
    id INTEGER PRIMARY KEY, scheduling_link_id INTEGER NOT NULL REFERENCES scheduling_links(id),
    interview_id INTEGER REFERENCES interviews(id), starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
    timezone TEXT NOT NULL, meeting_url TEXT, calendar_event_ids_json TEXT,
    status TEXT NOT NULL DEFAULT 'Booked', booked_at TEXT NOT NULL, cancelled_at TEXT
);

CREATE TABLE IF NOT EXISTS connector_accounts (
    id INTEGER PRIMARY KEY, provider TEXT NOT NULL, category TEXT NOT NULL, account_ref TEXT,
    status TEXT NOT NULL DEFAULT 'Connected', config_json TEXT, cursor TEXT,
    last_sync_at TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
    UNIQUE(provider, account_ref)
);

CREATE TABLE IF NOT EXISTS connector_events (
    id INTEGER PRIMARY KEY, connector_id INTEGER REFERENCES connector_accounts(id),
    direction TEXT NOT NULL, event_type TEXT NOT NULL, external_id TEXT,
    payload_json TEXT, status TEXT NOT NULL DEFAULT 'Pending', error TEXT,
    created TEXT NOT NULL, processed_at TEXT
);

CREATE TABLE IF NOT EXISTS job_board_posts (
    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES job_openings(id),
    provider TEXT NOT NULL, external_id TEXT, external_url TEXT,
    status TEXT NOT NULL DEFAULT 'Queued', payload_json TEXT, posted_at TEXT, closed_at TEXT,
    last_error TEXT, UNIQUE(job_id, provider)
);

CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, secret_hash TEXT NOT NULL,
    secret_enc TEXT,
    events_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY, subscription_id INTEGER NOT NULL REFERENCES webhook_subscriptions(id),
    event_type TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
    attempts INTEGER NOT NULL DEFAULT 0, response_code INTEGER, response_body TEXT,
    next_attempt_at TEXT, created TEXT NOT NULL, delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS page_templates (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, sections_json TEXT NOT NULL,
    default_styles_json TEXT, created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marketing_assets (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, asset_type TEXT NOT NULL, url TEXT NOT NULL,
    alt_text TEXT, metadata_json TEXT, uploaded_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recruitment_campaigns (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, job_id INTEGER REFERENCES job_openings(id),
    landing_slug TEXT UNIQUE, content_json TEXT, status TEXT NOT NULL DEFAULT 'Draft',
    starts_at TEXT, ends_at TEXT, created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_channels (
    id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES recruitment_campaigns(id),
    channel TEXT NOT NULL, external_id TEXT, destination_url TEXT, spend REAL,
    status TEXT NOT NULL DEFAULT 'Draft', metrics_json TEXT, UNIQUE(campaign_id, channel)
);

CREATE TABLE IF NOT EXISTS recruitment_analytics_events (
    id INTEGER PRIMARY KEY, event_type TEXT NOT NULL, session_id TEXT,
    candidate_id INTEGER REFERENCES candidates(id), application_id INTEGER REFERENCES applications(id),
    job_id INTEGER REFERENCES job_openings(id), campaign_id INTEGER REFERENCES recruitment_campaigns(id),
    source TEXT, medium TEXT, metadata_json TEXT, occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recruitment_experiments (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, job_id INTEGER REFERENCES job_openings(id),
    variants_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Draft', starts_at TEXT, ends_at TEXT,
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_definitions (
    id INTEGER PRIMARY KEY, owner_email TEXT, name TEXT NOT NULL, scope TEXT NOT NULL,
    filters_json TEXT, widgets_json TEXT NOT NULL, shared INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL, updated TEXT NOT NULL
);

-- ---------- phase 5: enterprise and differentiators ----------------------

CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
    default_locale TEXT NOT NULL DEFAULT 'en', timezone TEXT NOT NULL DEFAULT 'UTC',
    settings_json TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL, slug TEXT NOT NULL, logo_url TEXT, favicon_url TEXT,
    primary_color TEXT, accent_color TEXT, custom_domain TEXT UNIQUE,
    settings_json TEXT, created TEXT NOT NULL, updated TEXT NOT NULL,
    UNIQUE(organization_id, slug)
);

CREATE TABLE IF NOT EXISTS organization_teams (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    parent_id INTEGER REFERENCES organization_teams(id), name TEXT NOT NULL,
    country TEXT, department_id INTEGER REFERENCES departments(id), settings_json TEXT,
    UNIQUE(organization_id, parent_id, name)
);

CREATE TABLE IF NOT EXISTS organization_members (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    team_id INTEGER REFERENCES organization_teams(id), account_email TEXT NOT NULL,
    role TEXT NOT NULL, scope_json TEXT, active INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL, UNIQUE(organization_id, account_email)
);

CREATE TABLE IF NOT EXISTS career_site_brands (
    career_site_id INTEGER NOT NULL REFERENCES career_sites(id), brand_id INTEGER NOT NULL REFERENCES brands(id),
    locale TEXT NOT NULL DEFAULT 'en', PRIMARY KEY(career_site_id, brand_id, locale)
);

CREATE TABLE IF NOT EXISTS job_distributions (
    id INTEGER PRIMARY KEY, job_posting_id INTEGER NOT NULL REFERENCES job_postings(id),
    career_site_id INTEGER NOT NULL REFERENCES career_sites(id), brand_id INTEGER REFERENCES brands(id),
    locale TEXT NOT NULL DEFAULT 'en', slug TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Draft',
    published_at TEXT, UNIQUE(career_site_id, locale, slug)
);

CREATE TABLE IF NOT EXISTS content_translations (
    id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
    locale TEXT NOT NULL, field_key TEXT NOT NULL, value_text TEXT NOT NULL,
    machine_generated INTEGER NOT NULL DEFAULT 0, reviewed_at TEXT, updated_by TEXT, updated TEXT NOT NULL,
    UNIQUE(entity_type, entity_id, locale, field_key)
);

CREATE TABLE IF NOT EXISTS identity_providers (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    protocol TEXT NOT NULL, name TEXT NOT NULL, entity_id TEXT, metadata_url TEXT,
    sso_url TEXT, certificate_pem TEXT, client_id TEXT, client_secret_enc TEXT,
    config_json TEXT, active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scim_tokens (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    token_hash TEXT NOT NULL UNIQUE, label TEXT, last_used_at TEXT, expires_at TEXT,
    revoked_at TEXT, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scim_events (
    id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id),
    operation TEXT NOT NULL, resource_type TEXT NOT NULL, external_id TEXT,
    payload_json TEXT, status TEXT NOT NULL, error TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS access_policies (
    id INTEGER PRIMARY KEY, organization_id INTEGER REFERENCES organizations(id),
    name TEXT NOT NULL, effect TEXT NOT NULL DEFAULT 'allow', roles_json TEXT,
    resources_json TEXT NOT NULL, actions_json TEXT NOT NULL, conditions_json TEXT,
    active INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS legal_documents (
    id INTEGER PRIMARY KEY, organization_id INTEGER REFERENCES organizations(id),
    document_type TEXT NOT NULL, version TEXT NOT NULL, content_text TEXT,
    file_url TEXT, effective_at TEXT NOT NULL, accepted_by TEXT, accepted_at TEXT,
    UNIQUE(organization_id, document_type, version)
);

CREATE TABLE IF NOT EXISTS ai_screening_profiles (
    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL UNIQUE REFERENCES job_openings(id),
    threshold REAL NOT NULL DEFAULT 0, anonymize INTEGER NOT NULL DEFAULT 0,
    auto_stage TEXT, require_manual_review INTEGER NOT NULL DEFAULT 1,
    created_by TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_screening_criteria (
    id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES ai_screening_profiles(id),
    name TEXT NOT NULL, prompt TEXT, weight REAL NOT NULL DEFAULT 1,
    required INTEGER NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_screening_results (
    id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL REFERENCES ai_screening_profiles(id),
    application_id INTEGER NOT NULL REFERENCES applications(id), total_score REAL NOT NULL,
    criteria_json TEXT NOT NULL, summary TEXT, location_summary TEXT,
    recommended_stage TEXT, overridden_score REAL, override_reason TEXT,
    reviewed_by TEXT, reviewed_at TEXT, created TEXT NOT NULL,
    UNIQUE(profile_id, application_id)
);

CREATE TABLE IF NOT EXISTS video_interview_templates (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, intro_text TEXT,
    questions_json TEXT NOT NULL, time_limit_minutes INTEGER, created_by TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS video_interview_invitations (
    id INTEGER PRIMARY KEY, template_id INTEGER NOT NULL REFERENCES video_interview_templates(id),
    application_id INTEGER NOT NULL REFERENCES applications(id), token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'Invited', expires_at TEXT NOT NULL, sent_at TEXT,
    started_at TEXT, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS video_responses (
    id INTEGER PRIMARY KEY, invitation_id INTEGER NOT NULL REFERENCES video_interview_invitations(id),
    question_index INTEGER NOT NULL, media_url TEXT NOT NULL, duration_seconds INTEGER,
    transcript_text TEXT, summary_text TEXT, created TEXT NOT NULL,
    UNIQUE(invitation_id, question_index)
);

CREATE TABLE IF NOT EXISTS video_messages (
    id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    application_id INTEGER REFERENCES applications(id), direction TEXT NOT NULL,
    media_url TEXT NOT NULL, transcript_text TEXT, summary_text TEXT,
    sender TEXT, created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_imports (
    id INTEGER PRIMARY KEY, file_name TEXT NOT NULL, mapping_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Queued', total INTEGER NOT NULL DEFAULT 0,
    imported INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
    error_report_json TEXT, requested_by TEXT, created TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE IF NOT EXISTS candidate_import_rows (
    id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL REFERENCES candidate_imports(id),
    row_number INTEGER NOT NULL, source_json TEXT NOT NULL, candidate_id INTEGER REFERENCES candidates(id),
    status TEXT NOT NULL, error TEXT
);

CREATE TABLE IF NOT EXISTS service_plans (
    id INTEGER PRIMARY KEY, organization_id INTEGER REFERENCES organizations(id),
    support_tier TEXT NOT NULL DEFAULT 'Community', onboarding_status TEXT,
    account_manager_email TEXT, response_sla_minutes INTEGER,
    resolution_sla_minutes INTEGER, config_json TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS support_requests (
    id INTEGER PRIMARY KEY, organization_id INTEGER REFERENCES organizations(id),
    requester_email TEXT NOT NULL, channel TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'Normal',
    subject TEXT NOT NULL, body TEXT, status TEXT NOT NULL DEFAULT 'Open',
    first_response_at TEXT, resolved_at TEXT, assigned_to TEXT, created TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_project_job ON recruitment_projects(job_id);
CREATE INDEX IF NOT EXISTS idx_project_member_email ON project_members(account_email, project_id);
CREATE INDEX IF NOT EXISTS idx_candidate_comment ON candidate_comments(candidate_id, created);
CREATE INDEX IF NOT EXISTS idx_recruiting_task_assignee ON recruiting_tasks(assignee, status, due_at);
CREATE INDEX IF NOT EXISTS idx_message_candidate ON communication_messages(candidate_id, created);
CREATE INDEX IF NOT EXISTS idx_message_due ON communication_messages(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_automation_trigger ON automation_rules(trigger_event, active);
CREATE INDEX IF NOT EXISTS idx_privacy_status ON privacy_requests(status, requested_at);
CREATE INDEX IF NOT EXISTS idx_analytics_job ON recruitment_analytics_events(job_id, event_type, occurred_at);
CREATE INDEX IF NOT EXISTS idx_distribution_public ON job_distributions(career_site_id, locale, status);
CREATE INDEX IF NOT EXISTS idx_screening_application ON ai_screening_results(application_id);
