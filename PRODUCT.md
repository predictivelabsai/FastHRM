# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: HR and office managers at Estonian small and medium businesses and
startups. They run people admin, time, and payroll for roughly 5–150 employees,
often alongside other duties. Many are switching from spreadsheets or from
expensive incumbents (Persona, Wemply, HRM4Baltics).

Secondary: founders/CEOs who self-serve the tool before hiring an HR person,
and accountants/operations leads who process Estonian payroll declarations
(TÖR, TSD) on behalf of client companies.

## Product Purpose

FastHR is Estonian HR, payroll, and hiring software. It manages employee
records, org structure, leave and attendance, Estonian statutory payroll,
recruiting/ATS, performance, and the employee lifecycle in one place, in
Estonian, with Smart-ID/Mobile-ID/ID-card authentication. Success in the next
6 months: complete the product rework (transactional leave, real payroll
engine, multi-tenancy, self-service) and move from soft beta to open hosted
signups.

## Positioning

The only open-source HR platform with native Estonian statutory payroll (TÖR,
TSD, EMTA tax rates, holiday/incapacity pay) and Smart-ID/Mobile-ID/ID-card
auth and signing, at a fraction of incumbent pricing. Part of the FastSME
suite (47 products in progress), sharing one identity and one design system.
Hosting + management at €1/month per seat per product; bring-your-own-cloud
is free. Incumbents cannot truthfully copy both the open-source model and the
Estonian statutory depth.

## Operating Context

- Estonian statutory environment: TÖR (working and rest time), TSD (salary
  data declaration), EMTA tax rates, holiday pay, incapacity/sick pay,
  summated working time. Estonian labour law drives the payroll engine.
- Estonian e-identity: Smart-ID, Mobile-ID, ID-card for login and signing.
- Deployment: self-hosted (BYOC, free, MIT) or hosted by us via Coolify
  (see `skills/coolify-cicd`).
- Suite context: products are tried individually and adopted as a set; shared
  FastSME design system in `web/design/`.
- Public domain: https://fasthr.eu.
- Operator: Predictive Labs Ltd (Company House Reg No: 14857334, London);
  this identity is shown in the public footer.

## Capabilities and Constraints

Shipped: core HR/employee records, departments and reporting lines, deep
recruiting/ATS (rivals Teamdash), careers site + publishing, performance
(goals/feedback/reviews), lifecycle (onboarding/exit/org chart).

In progress (rework plan `docs/REWORK-PLAN-2026.md`): transactional leave and
attendance (Phase 1), real payroll engine with payslips (Phase 2),
multi-tenancy and RBAC with self-service (Phase 1), integration calls
(Phase 6).

Constraints: FastHTML (python-fasthtml) + SQLite with additive, idempotent,
numbered migrations; PEP 8; bilingual Estonian (default) and English via the
`web/i18n.py` copy layer; Coolify deployment; roadmap and change log updated
together per AGENTS.md.

Explicitly undecided: whether the €1/month per seat hosted price is a
permanent commitment or a beta-only offer. Current copy presents it as the
beta offer; future work must not present it as permanent.

## Brand Commitments

- Name: FastHR, part of the FastSME suite. Estonian-first product.
- Open-source under MIT; honest comparisons (competitor feature claims must
  stay grounded in `hrm-competitors.md`).
- In comparison tables FastHR is always the first (leftmost) product column;
  pricing is shown for FastHR only, because competitors' pricing is
  inquiry-based or gated.
- Copy voice: humanized plain language, no em dashes, no AI clichés
  (vibrant, seamless, robust, empower, elevate, forced triples, "not just X
  but Y"). Estonian must read like a person wrote it.
- Hero product mockups must mirror the real application (light theme, white
  top bar, grouped sidebar, KPI cards, real charts and tables), not an
  invented generic dashboard.

## Evidence on Hand

- Competitor feature analysis: `hrm-competitors.md` (eight products, grounded
  feature sets). Never fabricate competitor claims beyond it.
- Real application screenshots: `references/` plus the live app (run with
  `FASTHR_PORT=5010 PYTHONUTF8=1 .venv/Scripts/python.exe web_app.py`,
  demo login `admin@fasthr.example` / `FastHR2026$`).
- Design reference boards: StaffUp (primary anchor), TravelPerk, Slite,
  Ruul, Hireflix, HyreLink in `references/`.
- No customer testimonials, case studies, press, or usage benchmarks exist.
  Future work must not invent any.

## Product Principles

1. Estonian statutory depth before breadth. TÖR/TSD correctness is the moat;
   a feature that is wrong for Estonian law is worse than a missing feature.
2. Honest and open. Open-source, transparent pricing for us, no fake claims
   about competitors or customers.
3. Affordable by design. €1/seat hosted or free BYOC; the product must feel
   like serious software that doesn't cost a fortune.
4. Estonian first, but bilingual. Estonian is the default language and must
   read natively; English is fully supported.
5. Suite-consistent. FastHR shares one design system and identity with the
   other FastSME products; per-product accents, shared components.

## Accessibility & Inclusion

Target: WCAG 2.1 AA. Contrast 4.5:1 for normal text (3:1 large), visible
focus states, full keyboard navigation, labelled form fields, and no
color-only meaning. Estonian glyphs (õ ä ö ü š ž) must render correctly in
the chosen typefaces.
