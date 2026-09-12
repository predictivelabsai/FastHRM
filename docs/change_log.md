# FastHRM Change Log

Product changes are listed newest first. This file must remain synchronized with `docs/product_roadmap.md` under the rule documented there and in `AGENTS.md`.

## 2026-09-12 — New pay run page with employee search and select-all

### Fixed

- Added the missing `GET /payroll/runs/new` page. The route previously 404'd because only the POST handler existed and the path was shadowed by `/payroll/runs/{rid}`; the pay-runs list "+ New pay run" button now links to the page.
- The new-run employee picker gained a search filter and a select-all toggle.

### Verification

- Added regression tests in `tests/test_payroll.py` (new-run form content, route guard resolution); suite passes.

## 2026-09-10 — FastHR logo

### Changed

- Introduced a dedicated FastHR logo mark: a forward-leaning "F" monogram (the italic slant reads as "Fast") in ink on the FastSME lime tile, replacing the plain letter "F" in the shared brand mark and the generic person glyph in the favicon.
- Applied it as `static/favicon.svg` and `web/static/favicon.svg` (browser tab on the public site and the app) and as the `.fs-mark` glyph used in the public navigation and footer brand lockups.

### Data and verification

- SVG/CSS only in `static/favicon.svg`, `web/static/favicon.svg`, and `web/design/system.py`; no schema, dependency, or API changes. The mark scales cleanly from 16px to large and reads on light and dark grounds.

### Roadmap

- Added the FastHR logo mark as complete.

## 2026-09-10 — Public-site mobile polish

### Changed

- Top navigation on phones is now a single compact row (brand + hamburger); the language switch and sign-in moved into the dropdown menu, so the sticky bar no longer takes two tall rows and overlaps hero content as you scroll.
- Hid the decorative fake dashboard mockup in the hero on phones — it read as a cropped, toy-sized screenshot; the hero copy carries the section and the real product demo (GIF) remains in the demo section below.
- Made the mobile comparison cards collapsible: each product is a `<details>` showing its name and a feature count (e.g. 16/16), with FastHR expanded by default and competitors collapsed, cutting the comparison section from ~4600px to ~1600px on the landing page and roughly halving the `/compare` page.

### Data and verification

- CSS/markup only in `web/design/system.py` (shared nav) and `web/landing.py`; no schema, dependency, or API changes.
- Verified with headless Chromium at 360/390px across the landing, `/compare`, and `/features` pages (zero horizontal overflow, both languages); confirmed the in-menu ET→EN switch navigates and a collapsed competitor card expands on tap.

### Roadmap

- Added the public-site mobile polish as complete.

## 2026-09-10 — Mobile fixes for the public site

### Changed

- Fixed the public top navigation on phones: the brand and hamburger sit on the first row and the language switch (ET/EN) and sign-in drop to a full-width second row, so the language switcher is no longer clipped and unusable.
- Replaced the horizontally-overflowing competitor comparison table with stacked per-product cards below 640px (one card per product, a ✓/◐/✕ row per feature, FastHR highlighted), and wired the previously dead mobile-card markup into the shared table builder so it works on both the landing and `/compare` pages.
- Styled the landing Estonia/Global comparison toggle as a proper full-width segmented control (its colours and active state had been defined only in the public-page stylesheet, which the landing page does not load, so it had rendered as default browser buttons).
- Capped the landing dashboard showcase height on mobile and hid its illegible mini-sidebar so it reads as a preview instead of a tall dead block, and centred the FastSME suite banner label and product logos together.

### Data and verification

- CSS/markup only, scoped to `web/design/system.py` (shared nav) and `web/landing.py` (comparison builder, landing and public-page styles); no schema, dependency, or API changes.
- Verified with headless Chromium at 360/390px across the landing, `/compare`, and `/features` pages (zero horizontal overflow); confirmed the ET→EN language switch navigates and the mobile menu opens.

### Roadmap

- Added the public-site mobile fixes as complete.

## 2026-09-10 — Mobile experience for the authenticated app

### Changed

- Made the signed-in HR workspace fully responsive. The desktop three-pane grid (nav / content / AI rail) now collapses to a single column below 900px: the left navigation becomes an off-canvas drawer opened by a topbar hamburger with a dimmed backdrop, and the AI assistant rail becomes a slide-in overlay reachable from the existing Chat control.
- Reflowed content for small screens: KPI grids collapse to two columns (one column below 480px), detail/two-column/goal/stage grids stack, wide data tables scroll horizontally inside their cards instead of overflowing the page, toolbars and search inputs fill the width, and the admin sign-in card is width-capped.
- Enforced finger-friendly hit areas (≥40px) on buttons, segmented controls, nav items, and the chat input on coarse-pointer devices; tightened topbar and content padding on phones.

### Data and verification

- CSS/markup only, scoped to `web/layout.py` (`LAYOUT_CSS`, `LAYOUT_JS`, `topbar`, `page`); no schema, dependency, or API changes. The public marketing/careers site was already responsive and is unchanged.
- Verified visually with headless Chromium across the app and public pages at 360/390/768px, and with a programmatic horizontal-overflow audit over all 35 nav routes at each width (zero overflow); drawer, backdrop, chat overlay, Escape, and resize interactions confirmed. Full pytest suite run: 137 passed, 1 skipped, and 1 pre-existing unrelated failure (`test_committed_swagger_matches_runtime_openapi`, stale committed `swagger.json` — fails on clean `main`).

### Roadmap

- Added the mobile responsiveness of the authenticated app as complete.

## 2026-09-10 — Comparison tables reconciled with shipped modules

### Added

- Added benefits administration, learning and development, and workforce planning rows to the Estonian and global comparison tables, reflecting the modules shipped in this cycle.
- Added bilingual row labels matching the module naming used across the public pages.

### Verification

- Competitor states follow public sources (Sep 2026); verified rendering with both language copies and the full pytest suite.

## 2026-09-10 — Estonian site copy sweep

### Changed

- Fixed coined compounds, non-words, split compounds and wrong-sense terms across the Estonian public copy (tööõiguse järgi, taristul, palgakatvus, litsentsiülevaade, tooteperekond, kasutamine), every replacement verified with the estnltk MCP tools.
- Localised the landing dashboard mockup leave pills in Estonian; the internal tone keys no longer render as visible English text, with the pill styling unchanged.

### Verification

- Verified with `py_compile` and the full pytest suite.

## 2026-09-10 — Workforce planning

### Added

- Shipped budgeted positions, workforce scenarios, and approval-led headcount planning with bilingual staff views and KPI summaries.

### Data and verification

- Added additive migration `0015_workforce.sql`; no new configuration or dependencies.
- Updated the public feature catalogue and roadmap. Verified with the full pytest suite.

### Roadmap

- Marked Workforce planning complete.

## 2026-09-10 — Learning and development

### Added

- Shipped Learning & development with a course catalogue, employee learning plans, progress tracking, certifications, and expiry visibility.

### Data and verification

- Added additive migration `0014_learning.sql`; no new configuration or dependencies.
- Updated the public feature catalogue with shipped product messaging. Verified with the full pytest suite.

### Roadmap

- Marked Learning & development complete.

## 2026-09-10 — Payslip and pay-run completion

### Added

- Completed fully itemised pay-run previews with gross, net, employer-cost, and employee-count totals.
- Added draft-run re-preparation with edit-level payroll RBAC and idempotent benefit lines.
- Split employer costs from deductions on payslips and added latest-payslip line items to the employee portal.

### Data and verification

- No migration, configuration, or dependency changes.
- Updated bilingual payroll marketing copy. Verified with `python -m pytest tests/test_platform.py -q` and the full suite.

### Roadmap

- Marked payslips and pay runs complete.

## 2026-09-10 — Benefits administration

### Added

- Shipped benefit plans with all-active or department eligibility, idempotent employee enrolment, termination dates, and employer contribution tracking.
- Added the staff Benefits page, employee portal benefits card, bilingual payslip employer-cost lines, and pay-run integration without changing employee net pay.

### Data and verification

- Added idempotent migration `0013_benefits.sql`; no new dependencies or configuration.
- Updated the public feature catalogue and bilingual shipped product copy. Verified with the full pytest suite.

### Roadmap

- Marked benefits administration complete.

## 2026-09-10 — Live provider integrations

### Added

- Shipped live credential checks for Slack, GitHub, Greenhouse, BambooHR, Checkr,
  and Teams, with honest HTTP/auth/timeout notes and encrypted credentials retained.
- Shipped BambooHR employee-directory export with employee counts in the
  integration audit event and a local JSON snapshot; Slack can post a plain
  pipeline-digest test message.

### Data and verification

- No migration or new dependency; snapshots use the existing `data/` convention
  and `httpx` already present in requirements.
- OAuth-heavy providers remain explicitly marked as requiring interactive
  authorization or partner approval. Verified with the full pytest suite.

### Roadmap

- Marked live provider credential checks and the BambooHR directory export complete;
  remaining OAuth-heavy adapters remain open pending partner approval.

## 2026-09-10 — Holiday and incapacity pay

### Added

- Shipped automatic Estonian holiday pay and employer incapacity pay in pay-run preparation, with calendar-day averaging, bilingual payslip lines, and idempotent refreshes.
- Added migration `0011_holiday_incapacity_pay.sql`; holiday pay flows into gross taxable pay and TSD exports.

## 2026-09-10 — Granular role permissions

### Added

- Shipped per-role, per-module view and edit permissions with an administrator-only
  Roles settings matrix and bilingual access-denied pages.

### Data and verification

- Added idempotent migration `0012_granular_rbac.sql`; unconfigured modules retain
  the previous staff access behaviour.
- Updated the public feature catalogue and roadmap. Verified with the full pytest suite.

### Roadmap

- Marked granular module permissions complete. Tenant isolation and query-level
  scoping remain open.

## 2026-09-10 — Pay, time, expenses, and employee self-service

### Added

- Shipped pay runs and payslips with line-item breakdowns.
- Shipped shifts and time clocks with auto-attendance and location-aware check-in.
- Shipped expense claims, employee advances, approvals, and travel requests.
- Shipped the employee self-service portal for employee-facing HR workflows.

### Data and configuration

- Added migrations `0006` through `0009` for payroll, shifts and time clocks, expenses and travel, and employee self-service.
- No new environment configuration.

### Verification

- Updated the public feature catalogue, landing comparison, bilingual comparison data, roadmap, and changelog.
- Regenerated `swagger.json` from the runtime OpenAPI schema.
- Full pytest suite passes with 0 failures and 1 skipped opt-in live-model test.

### Roadmap

- Marked the shipped Phase 2, Phase 3, and Phase 4 HR operations items complete. Deeper statutory payroll remains open.

## 2026-09-10 — TÖR/TSD statutory exports and comparison rework

### Added

- Added TÖR employment-register and TSD monthly CSV exports with UTF-8 BOM, semicolon separators, and export history with re-downloads.
- Added payroll-page export actions and the bilingual statutory-payroll marketing copy now describes TÖR and TSD exports as shipped.
- Shipped comparison rework PRs #3, #4 and #5: landing comparison toggle, pricing copy sweep, and removal of comparison source links.

### Data and configuration

- Added migration `0010_tor_tsd_exports.sql` for statutory export history and nullable employee statutory fields.
- No new environment configuration.

### Verification

- Added coverage for TÖR columns, TSD tax and social-tax mapping, export history, route authentication, and Estonian/English rendering.
- Full pytest suite.

### Roadmap

- Marked TÖR/TSD exports shipped; holiday and incapacity pay remain open.

## 2026-09-10 — Public release polish: runtime version, comparison prices, and pricing route

### Changed

- Updated the landing hero mockup to use the runtime version label shared by the public footer.
- Filled competitor pricing cells with compact inquiry-based labels in Estonian and English.
- Added a `/pricing` 302 redirect to the landing-page pricing anchor.
- Removed the obsolete `.fs-footer col-h` selector; `.lh-price-example` remains in use.

### Data and configuration

- No migration, environment configuration, or deployment changes.

### Verification

- Added regression coverage for runtime mock version output, non-empty competitor prices, and the `/pricing` redirect.
- Full pytest suite.

## 2026-09-10 — Landing copy and comparison header refinement

### Changed

- Replaced the pricing formula with a natural sentence in Estonian and English.
- Removed the comparison table's “Meie” and “Us” suffixes and restored readable FastHR product-name typography.
- Replaced the landing FAQ with the canonical five-question free and open-source FAQ, and synchronized the final `/compare` FAQ answer.

### Data and configuration

- No migration, environment configuration, or deployment changes.

### Verification

- Added additive landing copy and comparison-header assertions in `tests/test_public_product_and_docs.py`.
- Full pytest suite.

## 2026-09-10 — Public suite label sentence case

### Changed

- Updated the landing-page `.lh-suite-label` to sentence case by removing tracked uppercase styling and restoring normal letter spacing; size, weight, colour, centering, width cap, and mobile sizing remain unchanged.

### Data and configuration

- No migration or environment configuration changes.

### Verification

- Updated additive CSS-source assertions in `tests/test_public_product_and_docs.py`.
- Full pytest suite.

## 2026-09-10 — Public suite label wrapping

### Changed

- Capped the landing-page `.lh-suite-label` at 34ch and tightened letter-spacing to 0.08em so the uppercase FastSME suite descriptor wraps into two centered lines.

### Data and configuration

- No migration, environment configuration, or other typography treatment changed.

### Verification

- Added additive CSS-source assertions in `tests/test_public_product_and_docs.py`.
- Full pytest suite.

## 2026-09-10 — Public typography consistency pass

### Changed

- Unified public H2/H3 sizing, heading line-height, FAQ answer sizing, mobile eyebrow sizing, comparison table feature-cell typography, auth modal title weight, and mockup chat-button font inheritance across `/`, `/compare`, and `/features`.
- Added readable text caps for footer legal copy, feature/comparison notes, and comparison FAQ answers, plus safe wrapping for long prose tokens.

### Data and configuration

- No migration, environment configuration, palette/token, mockup-internal, button-variant, trust-line, or logo-strip changes.

### Verification

- Added additive CSS-source regression assertions in `tests/test_public_product_and_docs.py`.
- Full pytest suite.

## 2026-09-10 — Public careers landing retired

### Changed

- Retired the public `/careers` landing and redirect it to `/`; job and application pages remain unchanged.
- Removed the retired landing from sitemap and indexing discovery, removed its marketing fallback links, and kept Careers publishing as a shipped feature without a public landing action.

### Data and configuration

- No migration, environment configuration, or styling change was required.

### Verification

- Added a regression assertion for the `/careers` redirect and retained coverage for live careers styling and public discovery routes.
- Full pytest suite.

## 2026-09-10 — Public touch-target adaptation

### Changed

- Added coarse-pointer hit-area rules for shared public navigation, language toggles, footer links, nav buttons, the landing comparison CTA, and comparison product/source links.
- Raised always-on footer column links, the comparison CTA, and comparison table links to comfortable touch heights; careers links now use the same 44px minimum.
- Refined mobile comparison product/source links, developer content buttons, and the careers brand link to preserve 44px touch targets.

### Data and configuration

- No migration, environment configuration, copy, colour, font, or hover behaviour changed.

### Verification

- Added regression assertions for the shared coarse-pointer and always-on touch-target rules.
- Ran the full pytest suite.

## 2026-09-10 — Public asset loading performance

### Changed

- Switched public pages to the prepared self-hosted Bricolage Grotesque and Hanken Grotesk stylesheet, preloading the two Latin faces painted immediately.
- Added responsive prepared WebP sources for the below-fold product demo while retaining the GIF fallback.

### Data and configuration

- No migration or environment configuration was required. Existing local font and WebP assets were wired without modification; the GIF remains on disk.

### Verification

- Added a public landing regression test for local font links, WebP sources, and GIF fallback.
- Ran the full pytest suite and verified no Google Fonts host remains under `web/`.

## 2026-09-10 — Developer shell migration and public-page hardening

### Changed

- Rebuilt `/developers` on the shared FastSME shell, preserving the OpenAPI contract, resources, examples, and token-gated write guidance.
- Added keyboard skip links to the public pages, corrected the English careers document metadata and FastHR branding, and replaced the auth backdrop literal with a design token.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `pytest tests/test_public_product_and_docs.py -q`
- `pytest tests/ -q`

## 2026-09-10 — Public mobile gutter root-cause fix

### Changed

- Preserved `.fs-wrap` horizontal gutters in the landing hero and shared footer containers, removed redundant child padding, and kept the public version label as plain text.
- Added `overflow-wrap:anywhere` to public landing hero H1s so long Estonian words wrap on mobile.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `pytest tests/test_public_product_and_docs.py -q`

## 2026-09-10 — Public comparison ergonomics and mobile gutters batch F

### Changed

- Reduced the desktop comparison table minimum width to 1150px and tightened cell padding so the first two columns fit the 1440px layout before regional scrolling is needed.
- Made sticky comparison feature cells opaque with a separating edge and shadow, and darkened the no-status mark for WCAG AA contrast on white and cream surfaces across desktop and mobile.
- Added explicit mobile paragraph gutters for public main content so body text remains clear of the viewport edges on the landing and comparison pages.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `pytest tests/test_public_product_and_docs.py -q`

## 2026-09-10 — Public auth and identity batch E

### Changed

- Restyled the public auth modal with the FastSME design tokens, including card inputs, pill primary actions, token-based secondary states, and the localized trust line.
- Fixed the login password placeholder to use the password guidance copy instead of duplicating the visible label.
- Removed public Careers/Värbamine links from navigation and footer columns while leaving the `/careers` route live.
- Corrected the shared footer legal identity line and rendered public footer version labels as plain text so visitors do not hit the authenticated `/about` page.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `pytest tests/test_public_product_and_docs.py -q`

## 2026-09-10 — Public product copy batch D

### Changed

- Marked Estonian statutory payroll with TÖR and TSD as available today in the feature catalogue.
- Replaced comparison fallback copy that exposed an internal source filename with clear public price and team wording.
- Unified comparison soon-status contrast, raised the suite-strip label to 12px, and made the hero mock version a maintained module constant.
- Confirmed the existing public footer version link still points to `/about`; no new page was added.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `pytest tests/test_public_product_and_docs.py -q`

## 2026-09-09 — Public identity and auth focus fixes

### Changed

- Corrected the landing hero dashboard mockup brand from FastHRM to FastHR.
- Updated auth modal open focus to skip hidden language inputs and enter the visible panel.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `pytest tests/test_public_product_and_docs.py -q` passes.

## 2026-09-09 — Public adapt and polish follow-up

### Changed

- Refined the comparison affordance with sticky feature columns, mobile comparison cards, scroll locking, and a small mobile status-mark gap.
- Completed the contrast sweep for the active ET/EN toggle, light-surface kickers, comparison CTA, and source links; targets now use the dark emerald ink variant.
- Moved auth focus into the first visible input on open and restored focus to the trigger on close while retaining the focus trap and Escape handling.
- Tightened the landing rhythm after pricing and FAQ, and aligned the footer Product column with the landing navigation order.
- Differentiated the payslip/pay-run workflow from Estonian statutory payroll in the bilingual feature catalogue; both remain Coming soon while the Phase 2 payroll engine is in progress.
- Removed the unused landing `stats` copy block and regenerated the committed OpenAPI document to match the current FastHR runtime and canonical domain.

### Verification

- Rendered landing, features, and comparison pages in Estonian and English with `to_xml`; ran the public product/docs regression file successfully.

## 2026-09-09 — FastHR identity and comparison structure

- Renamed the public product identity to FastHR and moved public SEO/canonical
  references to https://fasthr.eu; internal identifiers and the GitHub
  repository URL remain unchanged.
- Added the Predictive Labs Ltd legal identity line to the shared public footer
  and restyled the FastSME suite strip as an explicit product-family index.
- Added an Estonia-first, source-linked descriptive comparison section before
  the global platform table on /compare, with live Estonian payroll wording.

## 2026-09-09 — Public experience batches 1–4 complete

### Changed

- Completed the public localization and hardening pass: ET/EN copy and auth
  states remain path-aware, labels and recovery states are accessible, and
  public rendering handles the supported language paths consistently.
- Clarified public copy and pricing, including the explicit decision to present
  the Estonian payroll engine as live today with TÖR/TSD registration and
  e-identity support; payroll-live copy does not imply that all provider
  integrations are live.
- Adapted the shared public navigation and page frames for mobile, including a
  full FastHRM brand label at 375px and touch-sized controls without horizontal
  page scrolling.
- Completed the final polish: removed the unused legacy landing layer, aligned
  the favicon and public footer with FastSME identity, repaired mockup semantics
  and missing brand styles, and raised comparison, language-toggle, and auth
  divider contrast to WCAG 2.1 AA targets.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `py_compile` passes for all changed Python files.
- Landing, `/compare`, and `/features` render through `to_xml` in ET and EN;
  rendered HTML contains no public-footer `healthz` link and uses the new
  favicon colours.
- `pytest tests/test_public_product_and_docs.py -q` passes.

## 2026-09-09 — Clarified pricing and statutory payroll copy

### Changed

- Standardized the public hosted-price wording to one per-person, per-month
  formulation and added a worked 30-person example near the pricing cards in
  Estonian and English.
- Marked Estonian statutory payroll as available today in the landing and
  `/compare` copy, specifically naming TÖR/TSD registration, the payroll engine,
  and Estonian e-identity without changing the status of other coming-soon
  features.
- Updated the feature catalogue to link statutory payroll to `/payroll` and show
  it as available. No employee-list Excel import was added because the roadmap
  does not list one.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `python -m py_compile` passes for the changed Python files.
- Estonian and English landing and `/compare` pages render through `to_xml`.
- Public product and documentation tests pass.

## 2026-09-09 — Localized public landing and auth flow

### Changed

- Localized the auth modal, including labels, hints, recovery copy, inline error
  messages, focus trapping, focus return, and accessible field associations, in
  Estonian and English. Auth submit buttons now use the ink-on-paper treatment.
- Moved landing and `/compare` comparison records and FAQs into the shared copy
  layer, with natural Estonian translations while preserving source URLs and
  factual values.
- Localized the landing hero dashboard mockup for Estonian labels, names, and
  dates. Improved the real-demo section copy in both languages.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `python -m py_compile` passes for all changed Python files.
- Estonian and English landing and `/compare` pages render through `to_xml`.
- Render checks pass. The current public/full suite has one legacy assertion
  that still expects the old English signup title on the default ET page;
  excluding that conflicting assertion, the full suite is 85 passed, 1 skipped.

## 2026-09-09 — Real product demo on the landing page

### Added

- Added a bilingual real-screen product demo section to the public landing page
  between the feature cards and the compliance/pricing flow. The existing
  `/static/product-demo.gif` is framed with the same browser chrome language as
  the hero mockup and includes intrinsic dimensions to prevent layout shift.

### Data and configuration

- No migration, environment configuration, or new asset was required.

### Verification

- `python -m py_compile web/landing.py web/i18n.py` passes.
- The landing page renders through `to_xml` in Estonian and English.

## 2026-09-09 — Landing rework + FastSME design system

### Added

- Introduced a shared **FastSME design system** (`web/design/`): tokens (colour,
  type, spacing, radius, shadow, motion), Bricolage Grotesque + Hanken Grotesk
  fonts, and reusable public-page primitives (nav, footer, buttons, eyebrow, logo
  strip). Product colour is injected through a single per-product `--accent` token
  so the other FastSME products can reuse the system.
- Added a lightweight **bilingual (Estonian / English) copy layer** (`web/i18n.py`)
  with `?lang=` + session resolution; Estonian is the default and primary.

### Changed

- Reworked the public home page (`web/landing.py::landing_page`) onto the new
  design system: a confident dark-hero direction with a lime accent, a stylized
  HTML/CSS FastHRM dashboard mockup (no screenshot dependency), and localized
  feature, Estonian-statutory, pricing, comparison, FAQ and CTA sections.
- Rebuilt the hero dashboard mockup to mirror the real light-theme app: white top
  bar, grouped sidebar, KPI cards with coloured right edges, headcount bar chart,
  leave tables with pills, and an AI Assistant panel. Comparison tables now put
  FastHRM first and show pricing for FastHRM only; the logo-strip/features-heading
  area is a compact suite band with an asymmetric header, and ET/EN landing copy
  was humanized without em dashes or AI cliches.
- Migrated `/features` and `/compare` onto the shared design tokens, fonts,
  `fs_nav`/`fs_footer`, and dark page heroes with summary chips. Feature cards now
  use Available/Coming-soon pills; the sourced international comparison table
  uses `COMPARISON_TABLE_CSS`, highlighting the FastHRM column and pricing row
  with a ✓/◐/✕ legend.
- Localized both page frames through the ET/EN `feat_pg_*` and `cmp_pg_*` copy
  keys in `web/i18n.py`; detailed catalogue data, comparison data, and FAQ text
  remain English.
- `/features`, `/compare`, and `/login` now resolve and pass the active language;
  `/` also passes it through the branded-careers path.
- Language switch links preserve the current subpage through the shared
  path-aware `_lang_switch(lang, path)` (for example, `/features?lang=en`).
- Recorded the full programme in `docs/REWORK-PLAN-2026.md` and the design context
  in `.impeccable.md`.

### Data and configuration

- No migration or environment configuration is required.

### Verification

- Public-page tests pass (9 passed); the feature-catalogue test covers ET/EN
  localized labels. The full suite is running separately.
- Playwright screenshots verified `/features` and `/compare` in both ET and EN.

### Roadmap

- Recorded the completed `/features` and `/compare` migration in the public
  product and developer experience section of `docs/product_roadmap.md`.

### Not yet done

- Full ET/EN copy pass for the other public pages (careers, developers, privacy,
  and job pages).
- Localized translations of detailed feature-catalogue descriptions, FAQ text,
  and comparison data, currently rendered in English inside localized frames.

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
