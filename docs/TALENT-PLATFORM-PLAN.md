# FastHRM → Talent Platform: extension plan

Turning the three-pillar demonstrator (people, time, pay) into a production-grade
**Talent + Performance + Lifecycle** platform, without abandoning what makes it
work: Python-first, server-rendered FastHTML, HTMX transactions, no SPA.

**Target fidelity: production SaaS.** Foundations land before feature surface.
Synthetic seed data stays — as a demo mode and as test fixtures, not as the
architecture's assumption.

---

## 1. Where we're starting from

| Area | Today | Consequence for this plan |
|---|---|---|
| Schema | One `SCHEMA` string in `db.py`, 6 tables, `CREATE TABLE IF NOT EXISTS` | New tables are cheap; **altering** existing ones has no path. Migrations are prerequisite zero. |
| Data access | Raw SQL helpers `rows/one/scalar` + `cursor()` context manager | Keep. It's legible and fast. No ORM. |
| Views | `web/views.py`, one module, function-per-page returning FastHTML tuples | Will not survive three more modules. Split into a package. |
| Routes | `web_app.py`, `@rt` per route, `_guard(session, active, builder)` | `_guard` becomes the RBAC choke point. |
| Nav | `web/layout.py: NAV_ITEMS` | Add TALENT / PERFORMANCE / LIFECYCLE sections. |
| API | `web/api.py` — `Resource(...)` tuples auto-generate REST + OpenAPI | New tables get an API almost free. Big win; use it deliberately. |
| AI | `web/ai.py` — static text `snapshot()` stuffed into a system prompt | Does not scale past ~6 tables. Replace with tool-calling. |
| Auth | Hardcoded admin + `web/account_auth.py` account store | No roles, no scoping. Blocks every self-service surface. |
| Tests | None | Add alongside foundations, not after. |

Sibling repos already solve pieces of this. **Reuse, don't reinvent:**

- `FastPPM/rag/llm.py` — Grok via `langchain-openai` (xAI is OpenAI-compatible).
- `FastPPM/ingest/{extract,normalize,service}.py` — file → text → editable prompt
  + code-side JSON contract → structured entities. This *is* the CV parser.
- `FastPPM/web/prompts.py` — versioned, business-editable prompt manager.
- `FastVC`, `FastFund` — further LangChain structured-output precedents.

---

## 2. Architecture decisions

**A1 — Migrations, not a schema blob.** Numbered SQL files in `migrations/`,
applied in order, recorded in a `schema_migrations` ledger. `db.SCHEMA` stays as
migration `0001` for continuity. Every subsequent change is additive and
replayable against an existing `fasthr.sqlite`.

**A2 — SQLite now, Postgres-shaped.** No SQLite-only constructs in new tables
(no `WITHOUT ROWID` tricks, no `rowid` reliance, explicit types, ISO-8601 text
dates as already used). Migration files stay ANSI-ish so the Postgres port is
mechanical.

**A3 — One people graph.** A candidate who is hired does **not** get copied into
`employees` and forgotten. `employees.candidate_id` links back, skills and
documents follow the person, and `lifecycle_events` is the single append-only
history spine for both.

**A4 — One workflow engine, four consumers.** Leave already has an ad-hoc state
machine in `db.set_leave_status`. Generalise it: a declarative
`{entity, from, to, requires_role, side_effect}` transition table serving leave,
requisition approval, offer approval, and lifecycle changes. Every transition
writes an audit row. Retrofitting leave onto it is the proof it works.

**A5 — AI gets tools, not a bigger snapshot.** Typed Python functions registered
as LangChain tools over the same `db` helpers the views use. The model chooses;
the functions enforce scoping. New module = new tools, no prompt surgery.

**A6 — Prompts are data.** Extraction, offer drafting, and review summarisation
prompts live in a `prompts` table, versioned, editable in-app. The **output
contract stays in code** so a business edit can never break parsing. Straight
from the FastPPM pattern.

**A7 — Explainability is stored, not regenerated.** Ranking scores, risk flags,
and extraction runs persist their inputs and rationale. Required for the bias
audit; also makes the AI cheap to re-display.

---

## 3. Foundations

### F1 — Migrations `[slice 0]`

```
migrations/
  0001_baseline.sql          # current 6 tables, verbatim
  0002_ats_core.sql          # job_openings, candidates, applications, ...
  0003_rbac.sql
  ...
db.migrate()                 # run at startup, before _ensure_db()
```

`schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT)`. Each file runs in
one transaction. Idempotent by ledger, not by `IF NOT EXISTS`.

`seed.py` splits: `build()` (baseline) + `build_talent()` etc., each safe to
re-run against an existing DB so demo data can be topped up per module.

### F2 — RBAC and data scoping `[slice 1]`

Roles: `admin`, `hrbp`, `recruiter`, `hiring_manager`, `manager`, `employee`,
`candidate`. Stored on the account, resolved to an `Actor` at request start.

```python
# web/rbac.py
Actor(account_id, employee_id, roles, scope)   # scope: 'all' | 'dept:{id}' | 'self'
requires(*perms)                               # decorator on route builders
scope_employees(actor, sql, params)            # appends the WHERE clause
```

`_guard()` in `web_app.py` grows an `Actor` and passes it to view builders. This
is the single enforcement point — no view constructs an unscoped query. The
`/api` layer gets the same treatment via the existing token gate.

**Data-scoping rule:** a `hiring_manager` sees candidates on *their* requisitions;
a `manager` sees goals/feedback for *their* reports; an `employee` sees self.
Enforced in SQL, never in the template.

### F3 — Workflow + audit engine `[slice 1]`

```python
# web/workflow.py
TRANSITIONS = {
  ("leave_request", "Pending", "Approved"): Transition(roles={"manager","hrbp"}, effect=consume_balance),
  ("application", "Screen", "Interview"):   Transition(roles={"recruiter"},      effect=schedule_prompt),
  ("offer", "Draft", "Pending Approval"):   Transition(roles={"recruiter"},      effect=notify_approvers),
  ...
}
transition(actor, entity, entity_id, to_state) -> Result
```

Every call appends to `lifecycle_events(entity_type, entity_id, actor_id, from_state,
to_state, payload_json, created)`. Approval chains are rows in
`approvals(entity_type, entity_id, approver_id, sequence, decision, decided_at)`.

Migrating leave onto this is the acceptance test: `db.set_leave_status` becomes a
thin wrapper, balance side-effects move into `effect=`, and the existing HTMX
approve/reject buttons keep working unchanged.

### F4 — Self-service portals `[slice 3]`

Two authenticated surfaces beyond the HR cockpit, sharing the layout shell but
with their own nav and a hard scope ceiling:

- **Candidate portal** (`/portal/candidate`) — application status timeline,
  document upload, interview scheduling, offer view + e-sign handoff.
  Auth via magic link on `candidates.email` (the `auth_tokens` table in
  `account_auth.py` already does magic links — reuse it).
- **Employee portal** (`/portal/me`) — leave request, clock in/out, goals,
  feedback given/received, onboarding checklist, payslips.

### F5 — AI tool layer `[slice 2]`

Replace `ai.snapshot()` with a tool registry:

```python
# web/ai_tools.py
@tool_for("recruiter", "hrbp")
def pipeline_health(job_id: int | None = None) -> dict: ...
@tool_for("manager", "hrbp")
def team_goal_progress(manager_id: int) -> dict: ...
@tool_for("hrbp")
def attrition_signals(dept: str | None = None) -> dict: ...
```

Tools receive the caller's `Actor` and scope their own SQL — the model cannot
widen its own access. Slash-commands stay as the no-key fallback path.
`snapshot()` survives as a small always-on context header (headcount, today's
date, open reqs), not as the data source.

> **Deferred decision:** semantic JD↔CV matching without a vector store. Slice 2
> ships LLM-as-ranker over shortlists (explainable, stored rationale, fine to
> ~200 candidates per req). Beyond that, embeddings become necessary — revisit
> when a real pipeline exceeds that, and choose the provider then.

---

## 4. Module 1 — Recruitment / ATS

The flagship. Built first, built deepest.

### 4.1 Requisition and job opening
Structured req: headcount, budget, hiring manager, department, comp band,
required/nice-to-have skills, location/remote, diversity goal. Approval chain via
F3. On approval: publish to a public job page (`/jobs/{slug}` — no auth, SEO
metadata via the existing `web/seo.py`) and an internal posting.

### 4.2 Sourcing and ingestion
Manual entry, CSV import, **CV upload with LLM extraction** (see 4.3), referral
portal with tracked referrer and reward state, job-board webhook endpoint
(`POST /api/v1/webhooks/{source}`) reusing the API token gate.

### 4.3 CV extraction — the built-this-turn slice
```
upload → extract.py (pdfplumber / python-docx → text)
       → cv_extract.py: editable prompt (prompts table) + code-side JSON contract
       → Grok via langchain-openai
       → candidates + candidate_skills + candidate_documents + extraction_runs
```
Captures: identity, contact, current title/employer, total years, education,
work history with dates, skills with evidence, languages, certifications,
red flags (gaps, inconsistencies). `extraction_runs` stores prompt version,
model, latency, token cost, and raw response — so a bad parse is diagnosable and
a prompt change is measurable.

### 4.4 Pipeline
Stages configurable per req (default: Applied → Screen → Interview → Offer →
Hired / Rejected). Kanban with HTMX drag-drop (`hx-post` on drop → transition →
re-render the two affected columns only). SLA timer per stage, bulk actions,
stage-entry checklists.

### 4.5 Interviewing
Scorecards bound to a competency matrix (shared taxonomy with Performance —
`competencies` table serves both). Structured feedback per interviewer,
AI summarisation of free-text notes, calibration view (all scores for one
candidate, side by side, with interviewer bias deltas).

### 4.6 Matching and ranking
LLM ranker over the shortlist with a stored rationale per candidate, surfacing
transferable experience rather than keyword hits. Bias audit: ranking inputs
exclude name/gender/age fields by construction, and `ranking_runs` records what
was passed so the exclusion is auditable. "Similar candidates" and internal
mobility (match a req against `employees` + their skills) fall out of the same
matcher.

### 4.7 Offer and onboarding handoff
Template + AI-drafted offer letter, approval chain, e-sign handoff, and on
acceptance: create the `employees` row pre-populated from the candidate profile,
set `employees.candidate_id`, fire the onboarding checklist, write the
`lifecycle_events` "hired" row. One transaction.

### 4.8 Analytics
Time-to-fill, source effectiveness, diversity funnel, interviewer load, offer
acceptance, cost-per-hire — each also exposed as an AI tool.

---

## 5. Module 2 — Performance

- **Goals/OKRs** — `goals` with `parent_goal_id` for company → team → individual
  cascade, `key_results` with progress, check-in cadence, alignment tree view
  (same renderer as the org chart).
- **Continuous feedback** — peer/360-lite, praise feed, private manager notes
  (visibility flag enforced in SQL, not UI).
- **Review cycles** — `review_cycles` + `reviews` (self / manager / skip-level),
  calibration session view, optional distribution guidance.
- **Competency framework** — `competencies` + `employee_skills`, shared with ATS.
  Gap analysis vs. role profile; development plan generation.
- **Signals** — opt-in, privacy-aware: goal progress, attendance patterns,
  feedback volume. Every flag stores its contributing factors; no unexplained
  scores ever surface. Predictive risk stays advisory and is never shown to
  anyone outside HRBP + the employee's manager.
- **Outcomes** — promotion readiness, succession view, comp recommendation
  inputs feeding the future payroll engine.

---

## 6. Module 3 — Employee lifecycle

- **Onboarding** — templated checklists (IT, equipment, training, paperwork,
  buddy), assigned across HR/manager/new hire, progress visible to all three,
  auto-triggered by the Hired transition.
- **Changes** — promotion, transfer, role/manager change, with approval,
  **effective dating**, and downstream impact (leave allocation, salary).
  `employee_changes` is the record; `employees` holds current state only.
- **Development** — IDPs, mentoring matches, internal job board reusing the ATS
  matcher against current employees.
- **Separation** — resignation/termination workflow, knowledge transfer, exit
  interview (structured + AI sentiment), asset recovery, final payslip trigger,
  alumni status for rehire.
- **Cases** — ticket-style employee relations with restricted visibility and a
  full audit trail.
- **Org design** — org chart from `manager_id` (already on the near-term
  roadmap), plus what-if headcount scenarios costed against `base_salary`.

---

## 7. Cross-cutting

**Notifications** — `notifications` table + in-app rail, digest email via the
existing Postmark integration, Slack/Teams webhook per org. `@mentions` in
feedback and notes.

**Integrations** — calendar (interview scheduling), e-sign, job boards,
background check, HRIS export. Each behind a thin adapter with a null
implementation, so the product is fully usable with none configured.

**Compliance** — GDPR/CCPA: retention policy per entity, consent capture at
application, right-to-be-forgotten as a documented cascade (anonymise, don't
delete, preserving aggregate analytics), bias monitoring on ranking and
performance outputs, complete change log via `lifecycle_events`.

**Multi-tenancy** — deliberately **not** in slices 0–3. If it's wanted, `org_id`
must be added before real data exists; the migration runner makes it a
mechanical change, but it is a one-way door. Flag for an explicit decision at
the end of slice 1.

---

## 8. Schema sketch

```sql
-- ATS
job_openings(id, code, title, dept_id→departments, hiring_manager_id→employees,
             headcount, filled, comp_min, comp_max, currency, location, remote_policy,
             status, stages_json, description, requirements, opened_on, target_date,
             created_by, created)
candidates(id, first_name, last_name, email, phone, location, headline,
           current_title, current_employer, years_experience, linkedin_url,
           source, referred_by→employees, consent_at, status, created)
applications(id, candidate_id→candidates, job_id→job_openings, stage, status,
             applied_on, stage_entered_on, rating, rejection_reason, created_by)
candidate_documents(id, candidate_id, kind, file_name, mime, bytes, stored_path,
                    text_content, uploaded_on)
candidate_skills(id, candidate_id, skill, level, years, evidence, source)
candidate_experience(id, candidate_id, employer, title, start_date, end_date, summary)
candidate_education(id, candidate_id, institution, qualification, field, end_year)
extraction_runs(id, candidate_id, document_id, prompt_key, prompt_version, model,
                status, latency_ms, raw_response, error, created)
interviews(id, application_id, interviewer_id→employees, scheduled_at, mode,
           status, notes, ai_summary)
scorecards(id, interview_id, competency_id→competencies, score, comment)
offers(id, application_id, salary, currency, start_date, status, letter_html,
       approved_by, signed_at, expires_on)
ranking_runs(id, job_id, model, prompt_version, inputs_json, created)
ranking_scores(id, ranking_run_id, application_id, score, rationale)

-- Performance
competencies(id, name, category, description, levels_json)
goals(id, owner_type, owner_id, parent_goal_id, title, metric, target, current,
      period, status, created)
feedback(id, from_employee_id, to_employee_id, kind, competency_id, body,
         visibility, created)
review_cycles(id, name, period_start, period_end, status)
reviews(id, cycle_id, employee_id, reviewer_id, kind, status, ratings_json,
        narrative, submitted_on)
employee_skills(id, employee_id, skill, level, source, verified_by)

-- Lifecycle
onboarding_templates(id, name, role_filter, tasks_json)
onboarding_tasks(id, employee_id, template_id, title, owner_role, owner_id,
                 due_date, status, completed_on)
employee_changes(id, employee_id, change_type, effective_date, from_json,
                 to_json, approved_by, status)
separations(id, employee_id, kind, notice_date, last_day, reason, checklist_json,
            exit_interview_json, alumni_status)
cases(id, employee_id, kind, severity, visibility, status, opened_by, summary)

-- Platform
schema_migrations(version, applied_at)
prompts(id, key, version, title, content_html, is_active, updated_by, updated)
lifecycle_events(id, entity_type, entity_id, actor_id, from_state, to_state,
                 payload_json, created)
approvals(id, entity_type, entity_id, approver_id, sequence, decision, decided_at)
account_roles(id, account_id, role, scope)
notifications(id, recipient_id, kind, title, body, link, read_at, created)
```

`employees` gains: `candidate_id`, `employment_type`, `probation_end`,
`termination_date`, `alumni` — via `ALTER TABLE` in a migration, which is exactly
why F1 comes first.

---

## 9. HTMX interaction patterns

Consistent with what's already in `views.py` (`hx-post` → target a container →
swap `innerHTML`):

| Interaction | Pattern |
|---|---|
| Pipeline drag-drop | `hx-post="/talent/applications/{id}/stage"` → returns *only* the source + destination column fragments, `hx-swap="multi:#col-a,#col-b"` |
| CV upload | `hx-post` multipart → immediate optimistic row + `hx-trigger="every 2s"` poll on the extraction-status fragment until terminal |
| Scorecard entry | Inline form per competency, `hx-post` on change, debounce 500ms, swap a saved-tick |
| Goal check-in | `hx-patch` progress slider → swap the goal card |
| Approval chain | Button per pending step → `transition()` → swap the whole workflow strip |
| Prompt editor | `contenteditable` → `hx-post` → new version row, never an in-place update |

No new JS libraries. Drag-drop via the HTML5 API in ~30 lines, degrading to a
stage `<select>` when unavailable.

---

## 10. Phasing

| Slice | Contents | Status |
|---|---|---|
| **0** | Migration runner; ATS core tables; CV extraction (LangChain + xAI); prompt manager; candidate/job UI; seeded pipeline | ✅ **Done** — upload a PDF CV → structured candidate persisted and rendered |
| **2** | Scorecards + calibration; LLM ranking with stored rationale and bias audit; talent analytics | ✅ **Done** — ranking withholds identity fields and records the exclusion list |
| **3** | Offers + approval + hire→employee conversion; onboarding checklists | ✅ **Done** — accepting an offer creates the employee, carries skills, allocates leave, starts onboarding |
| **4** | Goals/OKRs with cascade and check-ins; continuous feedback; competency framework | ✅ **Done** — competencies shared between scorecards and reviews |
| **5** | Review cycles; calibration grid; explainable signals | ✅ **Done** — every flag carries its contributing factors |
| **6** | Lifecycle changes; separation; alumni; cases; org chart + scenarios | ✅ **Done** — hire → promote → exit → alumni, fully audited |
| **7** | Integrations: encrypted credential store, 13 providers, connection tests, audit trail | ✅ **Store done**, live connectors pending (see below) |
| **1** | **RBAC + row-level scoping**; workflow engine generalised; leave retrofitted | 🔜 **Next — the remaining gap** |

### What is deliberately not finished

Two things are stubbed, and are stubbed *visibly* rather than pretending:

1. **RBAC is stored but not enforced.** `account_roles` exists and `/settings/roles`
   assigns roles, but no query is scoped by them yet — every signed-in user still
   sees all data. The roles page says so on the page itself. Enforcement means
   threading an `Actor` through `_guard()` and every view builder; doing it
   half-way would be worse than not at all, because it would look enforced.
2. **Integration connectors do not call their providers.** The credential store,
   encryption, connection test and audit trail are real; `test_connection` checks
   what it can locally and says plainly that live calls are not enabled, rather
   than showing a green tick it has not earned. `sync()` records the attempt and
   reports that nothing was fetched.

Also outstanding: candidate and employee self-service portals (§F4), the AI tool
layer (§F5 — the assistant still uses the static snapshot, so the new modules are
not yet queryable in chat), and notifications.

Near-term roadmap items already listed in `ROADMAP.md` (leave self-service,
clock-in, org chart, salary structure, holidays/shifts) fold into slices 1, 3
and 6 rather than blocking the ATS.

---

## 11. Testing

Introduced with slice 1, not deferred:

- `tests/test_migrations.py` — every migration applies to an empty DB *and* to a
  baseline-seeded DB; ledger is honoured.
- `tests/test_rbac.py` — each role × each entity, asserting the scoping clause.
- `tests/test_workflow.py` — every declared transition, including the leave
  retrofit and balance side-effects.
- `tests/test_cv_extract.py` — fixture CVs against a stubbed LLM, asserting the
  JSON contract and the DB rows; one live-API test behind an env flag.

---

## 12. Open decisions

1. **Multi-tenancy** — decide by end of slice 1. One-way door.
2. **Embeddings** — deferred (see F5). Trigger: a req exceeding ~200 candidates.
3. **File storage** — local disk now; S3-compatible adapter needed before real
   CVs land (GDPR: CVs are personal data at rest).
4. **Postgres cutover** — when concurrent writers appear. SQLite's single-writer
   lock is fine for the cockpit, not for a public candidate portal at volume.
5. **E-sign provider** — DocuSign vs. HelloSign vs. a lightweight in-app
   click-to-accept for slice 3.
