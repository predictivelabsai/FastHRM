<div align="center">
  <h1>OpenHR</h1>
  <p><b>Pure-Python, minimal-JavaScript HR platform for Nordic / EU public-sector deployments.</b></p>
  <p>FastHTML + HTMX + SQLAlchemy · MIT-licensed · single-binary deployable · server-rendered HTML · zero build step</p>
</div>

## What this is

OpenHR is a small, auditable HR system designed to be credible in European public-sector procurements where the buyer wants an **existing platform** as an alternative to Visma, Unit4, SAP SuccessFactors, Workday, Simployer, or CatalystOne — but without the closed stack, per-seat licence ceilings or foreign-hyperscaler data paths those incumbents impose.

It covers the features a city, ministry or state enterprise actually runs:

- Employee records + organisational hierarchy
- Leave management (annual, sick, parental, care, study, unpaid)
- Attendance with daily check-in / check-out
- Payroll (gross → tax → pension → net; one payslip per employee per month)
- Expense claims with approval workflow
- Onboarding checklists with owner assignment
- Self-service dashboards per employee
- Dashboard with KPIs for HR / managers

## Technology

**Fully server-rendered. No build step. No npm, no Vite, no Vue, no Ionic.** Every page is HTML emitted by Python; interactivity is HTMX attributes.

| Layer | Technology |
| --- | --- |
| Web framework | **FastHTML** (Python) — Starlette + server-rendered component tree |
| Interactivity | **HTMX** loaded from CDN (≈14 KB over the wire) |
| Styling | Plain CSS (single `<style>` block, no framework) |
| ORM | **SQLAlchemy 2** (async-capable, but we use sync for simplicity) |
| Database | **SQLite** by default; **PostgreSQL** via `pip install openhr[postgres]` |
| Validation | **Pydantic 2** for form/DTO types |
| Packaging | setuptools + `pyproject.toml` |
| Licence | **MIT** |

Everything a public-sector auditor needs to understand the system fits in about **1,100 lines of Python** across `db.py`, `repo.py`, and `app.py`.

## Why no JavaScript framework?

Public-sector IT buyers consistently rank, in order of importance:

1. Source auditability (can our security team read the code?)
2. Data residency (is PII leaving our estate?)
3. Long-term maintainability (will this still build in five years?)
4. Cost at scale (licence tiers vs headcount growth)
5. Accessibility (WCAG 2.2 AA — server-rendered HTML passes trivially)

SPAs hurt every one of these. A 200 MB `node_modules`, a vendor-locked build pipeline, a new JavaScript framework every three years, and a bundle the user has to download before they see the login form. OpenHR is a deliberate reaction to that.

## Install

```bash
git clone https://github.com/predictivelabsai/openhr
cd openhr
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
openhr --init-db --seed           # creates openhr.db and loads demo data
openhr                            # serves on http://127.0.0.1:5060
```

Then open http://127.0.0.1:5060 and navigate the dashboard / employees / leave / attendance / payroll / expenses / onboarding.

## Postgres

```bash
pip install -e ".[postgres]"
export OPENHR_DATABASE_URL="postgresql://user:pass@host:5432/openhr"
openhr --init-db
openhr
```

## Run the tests

```bash
pytest -q
```

## Maintainer

[Predictive Labs Ltd](https://github.com/predictivelabsai) — UK micro-consultancy for public-sector data / AI bids.

## Origin

This repository was briefly a modified fork of [Frappe HRMS](https://github.com/frappe/hrms) (GPL-3.0) and is now a full rewrite from scratch — no Frappe-derived code remains. The rewrite allows OpenHR to be MIT-licensed, which public-sector legal teams prefer when self-hosting.
