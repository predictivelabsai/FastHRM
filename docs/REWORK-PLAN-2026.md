# FastHR Rework Plan — 2026

*Status: draft for review · Author: platform team · Date: 2026-09-09*

This is the master plan for reworking **the landing page, the demo, and the full
product**. It supersedes the day-to-day framing in `docs/ROADMAP.md` and
`docs/TALENT-PLATFORM-PLAN.md` (which stay accurate for the modules already
shipped). Roadmap/change-log discipline from `AGENTS.md` still applies: every
product change updates `docs/product_roadmap.md` **and** `docs/change_log.md` in
the same commit.

## 0. Decisions locked (2026-09-09)

| Decision | Choice | Consequence |
|---|---|---|
| Technical direction | **Overhaul the existing FastHTML app** | Keep Python/FastHTML + SQLite/migrations + the ATS/performance/lifecycle work. Redesign UI/UX, add missing modules on top. No rewrite. |
| First product priority | **Estonian statutory depth** | TÖR, TSD, full payroll engine, holiday/sick pay, Smart-ID/Mobile-ID, summated working time come before broad breadth. This is the moat vs. international HR tools. |
| Landing scope | **FastHR page on a reusable FastSME design system** | Build tokens/components once; the other 46 FastSME products reuse them. |

## 1. Positioning

**FastHR** — *Estonian HR, payroll and recruiting without the licence fees.*

- Part of the **FastSME suite** (47 products in progress: FastMail, FastOffice,
  FastDrive, FastMeet, FastAccounts, …). Shared identity, shared design system.
- **Open-source (MIT)**; hosting + management at the beta offer of **€1 / month
  per seat per product**. "Bring your own cloud" stays free.
- Wedge: the only **open-source** HR platform with **native Estonian statutory
  payroll** (TÖR, TSD, EMTA tax rates, holiday/incapacity pay) and **Smart-ID /
  Mobile-ID / ID-card** auth and signing — at a fraction of Persona/Wemply/
  HRM4Baltics pricing.

## 2. Competitor landscape (grounding)

Feature sets pulled from the eight products in `hrm-competitors.md`:

| Product | Centre of gravity |
|---|---|
| **PlanPro** | Strategy/goals, dev conversations, 360, pulse surveys, risk (E-ITS), projects/budget — public sector & mid-market |
| **HRM4Baltics** | Full HR + payroll + T&A + self-service + analytics + OHS + gov integration — mid/large Baltic |
| **Teamdash** | Recruiting/ATS: career site, scorecards, video interviews, AI screening, scheduling, multi-language, analytics |
| **PocoBit** | LMS: AI course generation, adaptive scenarios, SCORM, exams, gamified, white-label |
| **hours24** | Time tracking (biometric/QR/beacon/POS), AI scheduling, leave, contracts+signing, chat, projects, doc register — €0/5 free → €3–5/emp |
| **Yester** | Self-service portal: personnel, absences, OHS guidelines, equipment, requests, travel, expenses, mileage, tasks |
| **Wemply** | HR + scheduling + time + leave + **Estonian payroll (TSD, TÖR)** + analytics + open API — ~€7/emp (+€1 payroll) |
| **Persona** | Personnel + **payroll (tax, holiday pay, incapacity, auto tax rates)** + T&A + self-service — 56k employees, 327 clients |

### 2.1 Gap analysis vs. FastHR today

| Capability | Competitors with it | FastHR status | Plan phase |
|---|---|---|---|
| Core HR / employee records / org | all | ✅ shipped | maintain |
| Departments / reporting line | all | ✅ shipped | maintain |
| Recruiting / ATS (deep) | Teamdash | ✅ shipped (rivals Teamdash) | maintain |
| Careers site + publishing | Teamdash | ✅ shipped | maintain |
| Performance (goals/feedback/reviews) | PlanPro | ✅ shipped | maintain |
| Lifecycle (onboarding/exit/org chart) | HRM4Baltics, Yester | ✅ shipped | maintain |
| Leave & attendance | all | 🟡 mostly read-only | Phase 1 (transactional) |
| Payslips | Wemply, Persona, HRM4B | 🟡 static breakdown | Phase 2 (real engine) |
| Integrations catalogue | Wemply, HRM4B | 🟡 stored, not calling | Phase 6 |
| **Employee self-service portal** | all | ❌ | **Phase 1** |
| **Multi-tenancy + enforced RBAC + 2FA** | all (SaaS) | ❌ roles unenforced | **Phase 1** |
| **Smart-ID / Mobile-ID / ID-card auth+sign** | ET tools | ❌ | **Phase 1→4** |
| **TÖR (Töötamise register) integration** | Wemply, Persona | ❌ | **Phase 2** |
| **Statutory payroll engine (salary structures)** | Wemply, Persona, HRM4B | ❌ | **Phase 2** |
| **TSD filing + EMTA tax rates** | Wemply, Persona | ❌ | **Phase 2** |
| **Holiday pay / incapacity (sick) benefits** | Persona | ❌ | **Phase 2** |
| **Summated working-time accounting** | Wemply, Persona | ❌ | **Phase 2/3** |
| **Time clock (web/mobile/QR/biometric)** | hours24, Wemply, Persona | ❌ | **Phase 3** |
| **Shift scheduling / rostering (rules, AI)** | hours24, Wemply, Persona | ❌ | **Phase 3** |
| **Document management + templates + e-sign** | hours24, Wemply, Yester | ❌ | **Phase 4** |
| **Expenses & reimbursements** | Yester, Wemply, HRM4B | ❌ | **Phase 4** |
| **Business travel + mileage logs** | Yester, Persona | ❌ | **Phase 4** |
| **Work equipment / asset management** | Yester, hours24, Wemply | ❌ | **Phase 4** |
| **Occupational health & safety + doc register** | HRM4B, hours24, Yester | ❌ | **Phase 4** |
| **Engagement: pulse / eNPS / surveys** | PlanPro | ❌ | **Phase 5** |
| **Learning & development / LMS** | PocoBit, HRM4B | ❌ | **Phase 5** |
| **Analytics dashboards (diversity/turnover)** | HRM4B, Wemply, Persona | 🟡 partial | **Phase 5** |
| **Projects & tasks / billable hours** | hours24, PlanPro, Yester | ❌ | **Phase 5 (optional)** |
| **Team chat / notifications centre** | hours24 | ❌ | **Phase 5 (optional)** |
| **Accounting integrations (e-arveldaja/Merit/SmartAccounts)** | Wemply, HRM4B | ❌ | **Phase 6** |
| **Open API (published)** | Wemply | 🟡 OpenAPI exists | Phase 6 (harden) |

## 3. Workstream A — Landing page (do first)

**Goal:** a new marketing site for FastHR's own domain, built on a reusable
**FastSME design system** so the rest of the suite inherits it. Waiting on the
reference screenshots you're adding to `references/`.

### A1. FastSME design system (`web/design/`)
- Extract design tokens (colour, type scale, spacing, radius, shadow, motion)
  into one module — currently the accent (`#0891b2`) and CSS are hard-coded in
  `web/landing.py` and `web/layout.py`. Single source of truth for all 47 products.
- Component primitives: nav, hero, feature grid/cards, pricing cards, comparison
  table, partner grid, FAQ, footer, auth modal (already in `account_auth.py`),
  CTA band. Parameterised by product (name, accent, tagline, feature list).
- Ship as reusable FastHTML components + a token CSS file; document in
  `docs/DESIGN-SYSTEM.md`. Light/dark, responsive, WCAG AA.

### A2. FastHR landing content
- Rework hero, feature narrative, demo embed, pricing (€1/seat beta + BYOC free),
  competitor comparison (extend the existing `COMPARISONS` to include the ET
  competitors, honestly), partners, FAQ, SEO/sitemap (already in `web/seo.py`).
- Estonian-first messaging + language switch (ET / EN / RU) — see §6 i18n.
- New product domain: parameterise base URL / canonical; keep `hrm.fastsme.com`
  working during transition.

### A3. Reference-driven visual pass
- Once `references/` has screenshots, translate the chosen direction into the
  design tokens + component styling. Use the design skills (`frontend-design`,
  `ui-ux-pro-max`, `typeset`, `polish`) for the visual build.

**Deliverable:** redesigned `web/landing.py` on top of `web/design/`, a
`docs/DESIGN-SYSTEM.md`, and a suite-ready token file.

## 4. Workstream B — Product platform

Overhaul in phases. Each phase = migrations + domain module + `web/` views +
tests + roadmap/change-log entries. UI reskinned onto the design system as we go.

### Phase 1 — Foundation & self-service *(unblocks everything, SaaS-ready)*
1. **Design system in-app** — reskin `web/layout.py` shell onto the shared tokens.
2. **Multi-tenancy** — tenant/organisation scoping on every table + query; row-level
   isolation (competitors all assume it; we currently do not enforce it).
3. **RBAC enforcement** — enforce roles at the query layer (README flags this as
   deliberately unfinished), admin/manager/employee/recruiter, audited.
4. **Auth hardening** — 2FA/TOTP; scaffold **Smart-ID / Mobile-ID / ID-card**
   login via the shared `web/account_auth.py` (Estonian identity is table stakes).
5. **Employee self-service portal** — dedicated employee view: my profile, payslips,
   leave (apply → approve → balance), attendance, documents, tasks. Manager
   inbox for approvals. *Every competitor has this; we don't.*
6. **Transactional leave** — finish apply/approve/balance recompute (ROADMAP §2).

### Phase 2 — Estonian statutory core *(the moat)*
1. **Salary structures** — formula-based components (earnings/deductions), replacing
   the fixed gross/tax payslip. Estonian defaults: income tax, funded pension (II
   pillar), unemployment insurance (töötuskindlustus), employer social tax.
2. **Payroll engine** — pay runs (`Payroll Entry`), per-employee calculation,
   payslip generation, payment files (SEPA), wage statements.
3. **EMTA tax parameters** — auto-updated tax-free minimum, rates, thresholds by
   year; configurable.
4. **TÖR integration** — Töötamise register: register/amend/end employment entries
   (mandatory in Estonia). Design as a provider adapter (see Phase 6 pattern).
5. **TSD filing** — monthly tax & social-contribution declaration export/submission.
6. **Holiday & incapacity pay** — automatic holiday-pay reserve/calculation and
   sick-leave/incapacity benefit handling (Persona-parity).
7. **Estonian leave & holiday calendar** — statutory leave types, public holidays,
   accrual rules.

### Phase 3 — Time & scheduling
1. **Time clock** — clock in/out (`Employee Checkin`) via web + mobile; QR codes;
   adapters for biometric terminals / beacons / POS (contract now, wire later).
2. **Shift scheduling / rostering** — shift types, patterns, coverage; rule engine
   for labour-law compliance; optional AI-assisted schedule generation.
3. **Summated working-time accounting** — reference-period balance vs. norm hours,
   overtime/undertime, break rules (Estonian labour law).
4. **Auto-attendance** — derive attendance from check-ins + shifts.

### Phase 4 — Documents, expenses, assets, safety
1. **Document management** — contracts, templates with merge fields, versioning,
   acknowledgment tracking, **e-signing** (Smart-ID/Mobile-ID/ID-card).
2. **Expenses & reimbursements** — claims, categories, approval, export to payroll/
   accounting.
3. **Business travel & mileage** — travel requests, per-diem, mileage logs.
4. **Work equipment / assets** — assignment, return, inventory per employee.
5. **Occupational health & safety** — guidelines/procedures register with read-&-
   acknowledge, health records, training/instruction tracking.

### Phase 5 — Engagement, learning, analytics
1. **Engagement** — pulse surveys, eNPS, satisfaction surveys, 360 (PlanPro-parity;
   builds on the existing performance module).
2. **Learning & development** — learning plans, courses, certifications, exams;
   consider a light LMS (PocoBit-parity) or integrate.
3. **Analytics dashboards** — headcount, turnover, diversity, absence, time-to-fill,
   cost; CSV/export. Extends current dashboard + talent analytics.
4. *(Optional)* Projects & tasks + billable hours; notifications/chat centre.

### Phase 6 — Live integrations, API, hardening
1. **Turn the integrations catalogue live** — real adapters (README flags these as
   stored-but-not-calling). Priorities for Estonia: accounting (e-arveldaja / Merit
   / SmartAccounts), banks (SEPA), calendars, job boards, e-signing, TÖR/EMTA.
2. **Published open API** — harden the existing OpenAPI (`swagger.json`,
   `web/api*.py`); keys, scopes, webhooks, docs at `/developers`.
3. **Security & audit** — encrypted secrets (already for integrations), audit
   export, GDPR data-subject tooling, retention.

## 5. Workstream C — Demo rework

- **Seed data:** extend `seed*.py` with a believable Estonian org — realistic ET
  names, statutory payroll numbers, shifts, expenses, documents, surveys — so every
  new module demos with data. Keep it deterministic and synthetic (no PII).
- **Guided demo / walkthrough:** refresh `docs/demo/` GIF and the guided tour to
  cover the new modules; regenerate screenshots + user/platform guides via the
  existing `scripts/`.
- **Demo tenant:** a public read-only or reset-on-schedule demo org for the landing
  "Try it" CTA.

## 6. Cross-cutting

- **i18n:** ET (primary) / EN / RU, later LT/LV/FI to match Baltic competitors.
  Introduce a translation layer; ET-first copy across product + landing.
- **GDPR:** consent (already in careers), retention, export/erase, audit — required
  and a selling point.
- **Testing:** keep the `pytest` + `fresh_db` discipline; every migration idempotent
  and additive; cover state transitions, especially payroll math and TÖR/TSD outputs.
- **Deployment:** Coolify via `skills/coolify-cicd`; always reconcile HEAD /
  origin/main / Coolify commit / `/healthz` before claiming anything is live.
- **Docs discipline:** `product_roadmap.md` + `change_log.md` updated with every change.

## 7. Sequencing & immediate next actions

```
Now → landing:   A1 design system → A2 FastHR content → A3 visual pass (needs references/)
In parallel:     Phase 1 foundation (design system in-app, tenancy, RBAC, self-service, leave)
Then:            Phase 2 Estonian statutory core (the differentiator)
Then:            Phase 3 → 4 → 5 → 6
Continuous:      demo/seed refresh + docs sync as each module lands
```

**Immediate (this week):**
1. You add landing inspiration to `references/`.
2. Stand up `web/design/` tokens + core components (design-system extraction).
3. Rebuild the FastHR landing on top of it.
4. Draft the Phase 1 migration set (tenant scoping + RBAC) as a spike.

## 8. Open questions

- Target customer size for launch (micro 1–10 vs SME 10–200)? Sets payroll depth
  and self-service priorities.
- Pricing granularity: €1/seat/product across the suite vs bundled — how does
  FastHR's beta price interact with multi-product accounts?
- Smart-ID/Mobile-ID: certified provider (SK ID Solutions) account/timeline?
- Do we build the LMS or integrate (e.g. PocoBit) for Phase 5?
- Hosting/tenancy model: single shared DB with row-level isolation vs DB-per-tenant?
