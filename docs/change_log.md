# FastHRM Change Log

Product changes are listed newest first. This file must remain synchronized with `docs/product_roadmap.md` under the rule documented there and in `AGENTS.md`.

## 2026-08-08 — Phases 2–5: recruiting platform completion

### Added

- Recruiter operations: configurable drag-and-drop projects, confidential access, hiring teams, collaboration, saved views, automatic talent pools, bulk actions/interview invitations, merge/drop workflows, custom fields, scorecards, approvals, references, credentials, and hiring-manager workspace.
- Communications: recruitment mailboxes and sync contracts, templates/signatures, AI drafts, scheduled email/SMS, signed delivery events, automations, magic-link candidate requests/uploads, consent/privacy/retention workflows, surveys, and cNPS.
- Scheduling and growth: self-service booking, calendar/video connector contracts, job-board multiposting and signed applicant intake, retrying outbound webhooks, page templates/media, campaigns/social previews/JPGs, inclusive/AI copy tools, attribution, experiments, dashboards, benchmarks, and CSV export.
- Enterprise: multi-brand/localized career sites, custom domains/favicons, teams and consolidated metrics, SAML/OIDC verification adapters, SCIM, conditional policies, legal controls, enterprise API resources, advanced screening, video interviews/transcription adapters, sourcing intake, mapped imports, service plans, support, and SLA reporting.

### Data and configuration

- Added additive migration `0005_recruitment_platform.sql`, covering Phase 2–5 operational, communication, scheduling, marketing, analytics, enterprise, AI, video, import, support, and audit records.
- Added `Pillow` for deterministic campaign JPG rendering.
- Added optional `FASTHR_SOURCE_TOKEN`, `FASTHR_COMMUNICATION_WEBHOOK_SECRET`, `FASTHR_JOB_BOARD_WEBHOOK_SECRET`, `FASTHR_VIDEO_BASE_URL`, `FASTHR_SSO_VERIFIER`, and `FASTHR_TRANSCRIBER`; updated `.env.sample` with deployment contracts.

### Verification

- Added focused Phase 2–5 service and migration coverage; the final full suite passes with 73 tests and one opt-in live-model test skipped.
- Playwright-verified all six recruiting-platform tabs on a fresh database, a drag-and-drop stage move, brand/site creation, localized job publication, conditional application plus CV submission, confirmation history, portal document upload, self-scheduling, campaign landing/JPG flow, experiment assignment, workflow controls, and candidate collaboration.
- Browser discovery found and regression-tested an analytics aggregate crash, distinct public-title creation, and a campaign CTA that incorrectly linked to a private recruiter page.

### Roadmap

- Marked Phases 2–5 delivered and closed the Phase 1 follow-on publishing/marketing items. Phase 0 security-foundation work remains explicitly open.

## 2026-08-08 — Phase 1: public recruitment publishing

### Added

- Recruiter editor covering requisition and public job content, preview, version history, and Draft → In review → Published → Closed/Archived transitions.
- Branded responsive `/careers` index and `/jobs/{slug}` subpages with job metadata, SEO canonicals, sitemap entries, and JobPosting structured data.
- Public CV application flow with candidate deduplication, ATS application creation, cover notes, consent evidence/expiry, document ingestion, and asynchronous extraction.
- Careers-site brand/privacy settings and navigation from the ATS and public landing page.
- Admin/HRBP/recruiter authorization for publishing plus honeypot, per-IP throttling, supported-file validation, and an 8 MB upload limit.

### Data and configuration

- Added migration `0004_recruitment_publishing.sql` with `career_sites`, `job_postings`, `job_posting_versions`, `application_answers`, and `candidate_consents`.
- No new environment variables. Existing `FASTHR_DB`, `FASTHR_UPLOAD_DIR`, and `FASTHR_SECRET` continue to apply.

### Verification

- Added publishing, validation, consent, idempotency, slug, close, and migration regression tests.
- Passed the full suite: 50 tests passed and the opt-in live-model test was skipped.
- Playwright-verified recruiter login, job creation, publication, careers discovery, public CV application, and appearance of the applicant in the requisition pipeline against a fresh seeded database.

### Roadmap

- Marked Phase 1 delivered. Recorded all incomplete Teamdash-comparison capabilities in Phases 0 and 2–5 with target dates.
