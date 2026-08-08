# FastHRM Change Log

Product changes are listed newest first. This file must remain synchronized with `docs/product_roadmap.md` under the rule documented there and in `AGENTS.md`.

## 2026-08-08 — v0.4.0 build identity

### Changed

- Bumped the FastHRM release from v0.3.0 to v0.4.0.
- Added the runtime-derived version and commit identity to the bottom of every public product page; the authenticated top bar continues to expose the same linked build identity.
- Replaced the stale demo-only `/login` surface with the shared Google/local account experience, including registration and forgotten-password recovery.
- Preserved safe same-origin feature destinations through local and Google authentication, so opening Payroll returns to `/payroll` after sign-in.
- Added persistent collapse controls to every in-app sidebar group, with `<<` / `>>` actions to minimise or expand all sections at once.
- Regenerated the walkthrough GIF, guide screenshots, and v0.4.0 user-guide/platform-guide PDF and PowerPoint outputs.

### Data and configuration

- No migration or environment configuration is required. Coolify continues to stamp the deployed source commit into the existing build metadata.
- Audited all 22 FastSME services configured for Google sign-in: every production route and Coolify key is present. The shared GCP OAuth client already covered the fleet except FastVC, whose missing callback was added, bringing the client to 26 authorized redirects.
- Confirmed FastHRM already uses the same non-empty Postmark token as its sister repositories; no secret was copied into source control or rotated.

### Verification

- Added regression checks for the v0.4.0 release file, public footers, authenticated shell, collapsible navigation, shared `/about` build link, current login surface, and open-redirect rejection.
- Browser-verified Google sign-in through the FastHRM callback, safe `/payroll` return routing, persistent sidebar collapse state, the GCP callback inventory, and Postmark delivery of a password-reset email.

### Roadmap

- Synchronized the v0.4.0 build-identity delivery in `docs/product_roadmap.md`.

## 2026-08-08 — Features, comparison, and SEO/AEO discovery

### Added

- Renamed the public Products navigation and canonical catalogue to Features at `/features`; `/products` remains as a permanent compatibility redirect.
- Added `/compare`, a source-linked table covering FastHRM, Gusto, BambooHR, Rippling, Deel, Zoho People, and Odoo. The grid highlights Free/open-source status and omits Capterra or other review-site ratings.
- Added FAQPage and ItemList structured data, explicit zero-price Offer metadata, and `/llms.txt` for answer-engine discovery.
- Expanded `sitemap.xml` to cover the home, Features, comparison, careers, developer, privacy, and every published job page with page-specific crawl hints.

### Data and configuration

- No migration or environment configuration is required. Comparison prices are dated 2026-08-08 and link directly to official vendor pages.

### Verification

- Added regression checks for the renamed catalogue, comparison vendor set, absence of ratings, canonical URLs, structured data, sitemap coverage, dynamic job discovery, and `llms.txt`.
- Browser-verified the public navigation, wide comparison grid, internal mobile table scrolling, legacy redirect, and SEO endpoints.

### Roadmap

- Updated the public product/developer-experience section in `docs/product_roadmap.md` with the canonical Features route, comparison page, and SEO/AEO coverage.

## 2026-08-08 — Public product catalogue, API docs, and platform guide

### Added

- Added a public `/products` catalogue covering shipped and planned FastHRM modules. Every card displays Free pricing; incomplete scope is explicitly labelled Coming soon.
- Added product navigation to the landing and developer pages, and `/products` to the public sitemap.
- Expanded `/developers` with the v1 contract, pagination, filtering, structured errors, bearer-token writes, and executable examples.
- Added `docs/fasthrm_platform_guide_2026-08-08` in Markdown, PDF, and editable PowerPoint formats.

### Data and configuration

- No migration or new runtime configuration is required. The API access model remains public reads plus optional `FASTSME_API_TOKEN`-gated writes.
- Regenerated `swagger.json` from the running FastAPI schema and added a reproducible generation command.

### Verification

- Added regression coverage for product pricing/status, landing navigation, developer documentation, and exact committed/runtime OpenAPI parity.
- Browser-checked the product catalogue and developer documentation at desktop and mobile widths; visually inspected the generated PDF and PowerPoint.

### Roadmap

- Added and completed the public product/developer-experience section. Phase 0 security-foundation work remains open and the product catalogue labels it Coming soon.

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
