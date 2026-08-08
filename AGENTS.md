# Repository Guidelines

## Project Structure & Module Organization

FastHRM is a Python 3.12 FastHTML application. `web_app.py` bootstraps routes. Domain and persistence logic lives in `db.py`, `talent.py`, `people.py`, and `integrations.py`; page and API code is under `web/`. Put sequential SQL migrations in `migrations/` (for example, `0004_feature_name.sql`) and tests in `tests/`. Runtime assets belong in `static/` or `web/static/`; guides belong in `docs/`. Seed scripts must use synthetic data only.

## Build, Test, and Development Commands

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.sample .env
.venv/bin/python web_app.py
```

This runs the self-migrating app at `http://localhost:5010`. Use `.venv/bin/python seed.py` to rebuild sample data. Run containers with `docker compose up --build` after setting `FASTHR_SECRET`.

```bash
.venv/bin/python -m pytest tests/ -q
```

The normal suite stubs model calls and requires no API key. Live LLM tests are explicitly opt-in with `FASTHR_LIVE_LLM=1` and incur external calls.

## Coding Style & Naming Conventions

Follow the existing PEP 8-oriented style: four-space indentation, `snake_case` functions and modules, and `UPPER_CASE` constants. Add `from __future__ import annotations` to new modules and use type hints. Keep route handlers thin; place operations in domain modules. No formatter or linter is configured, so match nearby code and group standard-library, third-party, and local imports.

## Testing Guidelines

Name pytest files and functions `test_*.py` and `test_*`. The `fresh_db` fixture creates an isolated, migrated SQLite database per test. Cover state transitions, failures, idempotency, and data preservation. Migrations must work on an empty database, retain existing rows, and be safe on repeated discovery.

## Commit & Pull Request Guidelines

Recent commits use imperative, sentence-case subjects such as `Add ATS module with AI CV extraction`. Keep commits focused. Pull requests should summarize behavior, list verification commands, link issues or roadmap items, and include screenshots or a GIF for UI changes. Call out migrations, environment variables, external services, and deployment implications.

## Roadmap & Change Log Synchronization

Treat `docs/product_roadmap.md` and `docs/change_log.md` as a synchronized pair. Any product change that adds, removes, or changes a roadmap item must update both files in the same commit or pull request. Date each entry (`YYYY-MM-DD`), identify the phase, and record migrations, configuration, and verification. Never mark a roadmap item complete without a matching change-log entry.

## Security & Configuration

Never commit `.env`, API keys, uploaded CVs, production databases, or real employee data. Preserve `FASTHR_SECRET`; rotating it invalidates sessions and makes stored integration credentials unreadable. Update `.env.sample` whenever adding configuration.

## Deployment & Production Verification

Use `skills/coolify-cicd/SKILL.md` for deployment work. The active `main` push webhook is the normal Coolify trigger; do not add a duplicate automatic GitHub Action. From this checkout, run `.venv/bin/python scripts/coolify.py status` for a read-only check and `deploy --yes` only when deployment is explicitly authorized. Always match `HEAD`, `origin/main`, Coolify's deployment commit, and production `/healthz`; never claim dirty or unpushed work is live.
