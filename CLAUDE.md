# FastHR

Part of the FastSME suite (open-source, MIT). Estonian HR, payroll & hiring platform.

## Workflow

### Delegate to Codex by default
Claude plans and writes prompts. Codex executes. This applies to all task types,
not just code: writing, editing, analysis, refactoring, docs, config, data files,
and anything that lives in this repo working directory.

When a task is given:
1. Turn it into a scoped prompt (do not show the prompt to the user).
2. Delegate it to Codex via the codex MCP tool spawn_agent (or
   spawn_agents_parallel for independent tasks).
3. Review Codex's result and re-delegate if it is wrong.
4. Report a short summary. Do the work directly only when it is out of Codex's
   reach (browser verification, web search, artifacts).

## Repo conventions
- Update `docs/product_roadmap.md` and `docs/change_log.md` together when shipping.
- PEP 8; SQL migrations are additive and idempotent (numbered files in `migrations/`).
- Never commit `.env`, keys, tokens, or personal data.
- Deployed via Coolify (see `skills/coolify-cicd`).
- Public pages use the shared FastSME design system (`web/design/`) and the
  bilingual copy layer (`web/i18n.py`); Estonian (`et`) is the default language.
