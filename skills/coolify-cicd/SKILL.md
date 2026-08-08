---
name: coolify-cicd
description: Audit, deploy, verify, or troubleshoot FastHRM on Coolify from this repository. Use for deployment status, GitHub webhook checks, manual redeploys, production smoke tests, and rollback preparation.
---

# Operate FastHRM CI/CD

Use this repository's tracked launcher and ignored local credentials. Never
print `.env` values, API tokens, webhook secrets, or application environment
values.

## Production target

- Repository: `predictivelabsai/FastHRM`
- Branch: `main`
- Coolify application: `fasthrm`
- Application UUID: `g128y3a9wt2fievr0oxlvip6`
- Domain: `https://hrm.fastsme.com`
- Build: `/Dockerfile`, port `5010`
- Runtime health: `/healthz`
- Automatic trigger: active GitHub push webhook to
  `https://coolify.fastsme.com/webhooks/source/github/events/manual`

Treat the UUID as opaque. Confirm it from a Coolify read-back before any
mutation.

## Audit

1. Read `AGENTS.md`, `Dockerfile`, `.env.coolify.sample`, branch/upstream state,
   and the working tree.
2. Run `.venv/bin/python scripts/coolify.py validate`, `doctor`, and `status`.
3. Confirm `HEAD == origin/main`. Uncommitted or unpushed files are not live.
4. Inspect the GitHub hook without retrieving its secret. It must be active for
   `push`, use the manual endpoint above, and report HTTP 200.
5. Read Coolify deployment history for the application and match the full
   commit SHA. A successful hook alone is insufficient.
6. Smoke-test `/`, `/healthz`, `/careers`, affected public routes, static
   assets, TLS, redirects, browser console errors, and failed requests.

## Deploy

Pushing `main` is the normal automatic deployment path. For an explicitly
authorized manual redeploy from this checkout:

```bash
.venv/bin/python scripts/coolify.py deploy --yes
```

The sibling `FastDevOps` checkout is discovered automatically; set
`FASTDEVOPS_DIR` only when it lives elsewhere. Do not add a second automatic
GitHub Action while the repository webhook remains active.

Before deployment, run the tests, `git diff --check`, inspect staged files for
credentials, and identify the exact commit. Afterward, wait for a terminal
Coolify state and confirm production serves that commit. `SOURCE_COMMIT` is the
authoritative runtime commit supplied by Coolify.

## Rollback

Resolve the exact target deployment and commit in Coolify history, then ask for
confirmation unless the user already authorized that specific rollback. Verify
health, TLS, routes, assets, and the resulting commit after rollback.
