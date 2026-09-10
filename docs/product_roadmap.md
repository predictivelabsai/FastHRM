# FastHRM Product Roadmap

**Baseline date:** 2026-08-08  
**Comparison source:** [Teamdash pricing and feature matrix](https://www.teamdash.com/pricing/), reviewed 2026-08-08.

- [x] Completed final public release polish: runtime version in the landing mockup, filled competitor pricing cells, `/pricing` anchor redirect, and scoped dead-CSS cleanup (2026-09-10).

- [x] Phase 2 HR operations: payslips and pay runs shipped (2026-09-10).
- [x] Phase 3 workforce operations: shift scheduling / rostering, time clock / check-in/out, and auto-attendance shipped (2026-09-10).
- [x] Phase 4 employee services: expenses and reimbursements, travel requests, and the employee self-service portal shipped (2026-09-10).
- [x] TÖR and TSD statutory CSV exports shipped; holiday and incapacity pay calculations shipped (2026-09-10).
- [x] Comparison rework PRs #3, #4 and #5 shipped: landing comparison toggle, pricing copy sweep, and removal of source links (2026-09-10).

- [x] Refined landing pricing copy, comparison product-name typography, and canonical five-question FAQ wording in Estonian and English; synchronized the `/compare` FAQ (2026-09-10).

- [x] Wrapped the landing-page FastSME suite descriptor to a readable two-line, centered uppercase label with a 34ch cap and tighter letter-spacing (2026-09-10).
- [x] Changed the landing-page FastSME suite descriptor to sentence case with normal letter spacing while preserving its readable width, weight, colour, centering, and responsive sizing (2026-09-10).

- [x] Completed the public typography consistency pass: unified heading roles and responsive sizing, standardized FAQ/table/auth/mockup typography, capped long public text lines, and added long-token wrapping (2026-09-10).

- [x] Retired the public `/careers` landing with a redirect home; job and application pages remain unchanged (2026-09-10).

- [x] Completed public touch-target adaptation: coarse-pointer targets cover shared navigation, language, footer, CTA, button, and comparison links; always-on link heights preserve comfortable hit areas across public pages (2026-09-10).

- [x] Improved public asset loading by self-hosting and preloading the prepared display/body fonts and serving prepared responsive WebP product-demo sources with the GIF fallback (2026-09-10).
- [x] Fixed public mobile gutter inheritance at the shared landing hero and footer roots, removed redundant compensating padding, and retained the plain-text footer version label (2026-09-10).
- [x] Prevented long Estonian public hero H1 tokens from causing horizontal overflow on mobile (2026-09-10).
- [x] Migrated `/developers` to the shared FastSME shell and hardened all requested public pages with keyboard skip links, corrected careers metadata/branding, and tokenized auth backdrop styling (2026-09-10).

- [x] Reworked the public identity to FastHR, added the Predictive Labs Ltd
  footer identity, and made /compare Estonia-first with a source-linked
  descriptive table followed by global platforms (2026-09-09).
- [x] Completed the public adapt and polish follow-up: contrast sweep, active
  language focus styling, auth focus restoration, intentional landing spacing,
  footer/nav order alignment, comparison sticky/mobile/scroll affordances, and
  bilingual payroll catalogue deduplication (2026-09-09).
- [x] Corrected the FastHR hero mockup brand and ensured auth modal open focus
  skips hidden inputs and enters the visible panel (2026-09-09).
- [x] Completed public auth and identity batch E: aligned the auth modal with
  FastSME tokens, fixed password placeholder copy, removed public Careers links,
  corrected the footer legal line, and made public version labels non-links
  (2026-09-10).
- [x] Completed public product copy batch D: marked Estonian statutory payroll
  with TÖR/TSD available today, removed comparison source-filename fallbacks,
  unified soon-status contrast, raised the suite label, and stabilized the hero
  mock version string (2026-09-10).
- [x] Completed public comparison ergonomics and mobile gutters batch F: reduced
  desktop comparison width and cell padding, layered opaque sticky feature
  cells, raised no-mark contrast across desktop/mobile, and kept public body
  paragraphs inside the mobile viewport gutter (2026-09-10).

This roadmap closes the useful product gaps without copying Teamdash’s packaging. `[x]` means delivered and verified in FastHRM; `[~]` means a baseline exists but the named scope is incomplete; `[ ]` is unimplemented. Dates are target completion dates, not commitments.

## Phase 0 — Safe multi-user foundation (target 2026-08-31)

- [x] Publishing actions restricted to admin, HRBP, and recruiter roles (2026-08-08).
- [x] Versioned job copy, publication audit events, consent proof, upload limits, honeypot, and submission throttling (2026-08-08).
- [ ] Enforce tenant isolation and scoped RBAC on every page, API query, export, and mutation.
- [ ] Invite-only account provisioning; remove unsafe open registration defaults.
- [ ] Add CSRF protection, distributed rate limiting, MIME/malware scanning, retention-safe file storage, and security event review.
- [ ] Add admin-visible, exportable audit logs and two-factor authentication.

## Phase 1 — Publish and receive applications (delivered 2026-08-08)

- [x] Recruiter job authoring for internal/public titles, department, manager, location, remote/employment type, compensation, summary, description, requirements, benefits, deadline, and SEO metadata.
- [x] Draft, review, publish, close, and archive workflow with preview and version history.
- [x] Branded, responsive careers index and unique job subpages with editable colours, logo, headline, privacy link, canonical metadata, sitemap discovery, and JobPosting structured data.
- [x] Public application form with CV, contact details, cover note, privacy consent, candidate deduplication, ATS creation, and asynchronous CV extraction.
- [x] Standard FastHRM-hosted careers route with no product-level caps on jobs, job pages, candidates, or hiring projects.
- [x] Page-builder sections, reusable ad templates, custom fonts, uploaded images/media library, campaign landing pages, social previews, and JPG export (2026-08-08).
- [x] Custom/conditional application forms, internal job ads, scheduled publishing, custom domain/favicon, and applicant confirmation email (2026-08-08).

## Phase 2 — Recruiter operating system (delivered 2026-08-08)

- [x] Drag-and-drop pipelines; custom stages/workflows/categories; project templates, cloning, custom fields, access rules, and confidential projects (2026-08-08).
- [x] Bulk email/SMS/interview invites/comments/tags/tasks; saved views, filters, deduplication/merge, drop reasons, and continuous hiring projects (2026-08-08).
- [x] Candidate comments, ratings, pinned/private notes, searchable personal tags, files, custom profile fields, and task assignment (2026-08-08).
- [x] Resume full-text/faceted search, automatic talent-pool rules, and targeted bulk job offers (2026-08-08).
- [x] Configurable scorecards, reminders, approval workflow, reference requests, and credential validity controls (2026-08-08).
- [x] Hiring-manager workspace with scoped projects, feedback, decisions, surveys, tasks, and notifications (2026-08-08).

## Phase 3 — Communication, automation, and privacy (delivered 2026-08-08)

- [x] Recruitment mailbox with templates, personalised HTML/signatures, AI writing, send-later, delivery/read/click/bounce tracking, and incremental mailbox-sync adapter (2026-08-08).
- [x] Two-way scheduled email/SMS, signed provider events, and complete chronological communication history (2026-08-08).
- [x] Trigger/action engine for messages, stages, tasks, tags, candidate requests, webhooks, and reusable workflows (2026-08-08).
- [x] Magic-link candidate portal with status, dynamic information forms, document uploads, interview choices, withdrawal, and privacy controls (2026-08-08).
- [x] Consent renewal/withdrawal, correction/dispute requests, export, anonymisation, permanent deletion, and automated retention (2026-08-08).
- [x] Candidate and hiring-manager surveys, automatic triggers, cNPS, and experience feedback (2026-08-08).

## Phase 4 — Scheduling, marketing, integrations, and intelligence (delivered 2026-08-08)

- [x] Self-service scheduling, interviewer availability, calendar-sync contracts, configurable live-video rooms, and Teams/Google Meet links (2026-08-08).
- [x] Job-board connector contract, multiposting, signed automatic applicant intake, custom connectors, API access, and signed/retrying webhooks (2026-08-08).
- [x] Page templates/media library, social campaigns, public sharing, inclusive-language checks, AI ad writing, social metadata, and JPG export (2026-08-08).
- [x] Team/custom/group dashboards, filters, funnel/source/channel metrics, recruiter benchmarks, email conversion, and CSV export (2026-08-08).
- [x] Careers/job impressions, application conversion, attribution, deterministic experiments, and variant reporting (2026-08-08).

## Phase 5 — Enterprise and differentiators (delivered 2026-08-08)

- [x] Multiple brands/sites/teams, consolidated reporting, country/department policies, custom domains/favicons, and reviewed or AI-translated localized pages (2026-08-08).
- [x] SAML/OIDC verifier adapters, GET/POST callbacks, SCIM provisioning, conditional allow/deny policies, DPA/terms controls, and enterprise API resources (2026-08-08).
- [x] Weighted/required AI criteria, thresholds, overrides, stage actions, anonymised screening, summaries, tagging, and bias-aware copy checks (2026-08-08).
- [x] Video messaging, uploaded asynchronous interviews, configurable AI transcription/summaries, and token-authenticated sourcing-extension intake (2026-08-08).
- [x] Mapped candidate imports, assisted onboarding plans, email/live-chat/dedicated support records, and configurable SLA reporting (2026-08-08).

## Public product and developer experience (delivered 2026-08-08)

- [x] Public `/features` catalogue lists every current and planned FastHRM module with a single Free price and unambiguous Available/Coming soon status; legacy `/products` permanently redirects to it (2026-08-08).
- [x] Landing, sitemap, and developer navigation expose the feature catalogue without requiring an account (2026-08-08).
- [x] Public `/compare` page compares FastHRM with Gusto, BambooHR, Rippling, Deel, Zoho People, and Odoo using source-linked price, licence, payroll/global, fit, and limitation fields without review-site ratings (2026-08-08).
- [x] Migrated `/features` and `/compare` to the shared FastSME design system with ET/EN page frames and path-preserving language switches; detailed catalogue descriptions, FAQ text, and comparison data remain English (2026-09-09).
- [x] Rebuilt the landing hero mockup to mirror the light-theme app, redesigned the suite band and asymmetric heading, reordered comparison tables with FastHRM first and FastHRM-only pricing, and humanized ET/EN landing copy (2026-09-09).
- [x] Localized the auth modal, landing comparison data and FAQs, and hero dashboard mockup in Estonian and English; added inline recovery errors, accessible labels, focus management, and corrected real-demo copy (2026-09-09).
- [x] Added the real bilingual product-demo recording to the landing between features and the compliance/pricing flow, with browser-style framing and layout-shift-safe image dimensions (2026-09-09).
- [x] Clarified the public pricing formulation and marked the shipped Estonian payroll engine, including TÖR/TSD registration and e-identity copy, as available today across the landing and comparison pages (2026-09-09).
- [x] Completed public experience batches 1–4: ET/EN localization and hardening, clarified copy with the payroll-live decision, mobile navigation adaptation, and final polish for the shared FastSME layer, including the full 375px FastHRM label, WCAG 2.1 AA contrast fixes, semantic inert mockup markup, FastSME favicon/footer identity, and removal of unused legacy landing CSS (2026-09-09).
- [x] SEO/AEO discovery includes every canonical public page and published job in `sitemap.xml`, plus Free/open-source Offer metadata, FAQ/ItemList schema, crawler policy, and `llms.txt` (2026-08-08).
- [x] Regenerated the committed OpenAPI contract and expanded `/developers` with version, pagination, filtering, errors, authentication, and write examples (2026-08-08).
- [x] Generated a dated FastHRM platform guide in Markdown, PDF, and editable PowerPoint formats (2026-08-08).
- [x] Released v0.4.0 with one runtime-derived build/version identity in public page footers and the authenticated app shell (2026-08-08).
- [x] Replaced the stale demo-only `/login` page with Google sign-in, local registration, password reset, and safe return-to-feature routing (2026-08-08).
- [x] Added persistent per-section sidebar minimisation plus global `<<` / `>>` controls for denser in-app navigation (2026-08-08).
- [x] Verified the shared Google OAuth/Postmark production path, including every Google-enabled FastSME service callback and a delivered FastHRM password-reset email (2026-08-08).

## Roadmap/change-log rule

Every roadmap status, scope, or date change must update `docs/change_log.md` in the same commit or pull request. The matching dated entry must name the phase, summarize user-visible behavior, identify migrations/configuration, and record verification. Do not mark `[x]` until implementation and tests are complete.

Teamdash plan quotas, “paid add-on” labels, and pricing tiers are deliberately not replicated. Capabilities are prioritized by candidate experience, recruiter time saved, compliance risk, and fit with FastHRM’s open-source model.
