# Skills

Capability reference for FastHR + the shared **Frappe → FastHTML migration
playbook** (same recipe across `fasthtml-oss-migrations`; see `FastCRM/SKILLS.md`).

---

## Part 1 — FastHR capabilities

**Entry:** `python web_app.py` → http://localhost:5010
(login `admin@fasthr.example` / `FastHR2026$`).

### Pages

| View | Route | What it shows |
|---|---|---|
| Dashboard | `/` | headcount, attendance %, on-leave, pending leave, dept headcount |
| Employees | `/employees?dept=&q=` | directory; `/employees/{id}` = profile |
| Departments | `/departments` | headcount, head, annual payroll |
| Leave | `/leave?status=` | requests by status |
| Attendance | `/attendance` | today's register + per-status counts |
| Payroll | `/payroll?period=` | payslips; `/payroll/{id}` = breakdown |
| AI Assistant | `/ai` | HR chat (right rail) |

### Data model (`db.py`)

`departments · employees (manager_id self-ref) · leave_balances · leave_requests ·
attendance · payslips · chat_messages`. `kpis()` computes headline metrics;
`employee()` joins dept + manager. Rebuild with `python seed.py`.

### AI (`web/ai.py`)

Grounded chat over `snapshot()` (headcount, attendance, pending leave, payroll).
Slash-commands (no key): `/headcount`, `/leave`, `/today`, `/payroll`.

---

## Part 2 — Frappe → FastHTML migration playbook

1. **Mine the schema** — `python scripts/frappe_doctype_to_schema.py /tmp/frappe-hrms`.
2. **Scope hard** — HRMS is 160 doctypes; pick the pillars a user touches daily
   (people / time / pay) and defer the rest (record it in `docs/ROADMAP.md`).
3. **FastHTML shell** — `fast_app(pico=False, hdrs=[Style(CSS)])`; `page()`
   wrapper; `_guard()` auth.
4. **HTMX over JS** — segmented filters are GET links; the colour-coded
   attendance strip and leave-balance cards are pure server-rendered CSS.
5. **Synthetic data** — fixed RNG seed; derive attendance from approved leave so
   the data is internally consistent; self-seed on boot.
6. **LLM, key-optional** — reuse `_provider_stream`; slash-commands work with no key.
7. **Capture the demo** — Playwright MCP → frames → `build_demo_gif.sh`.
8. **Ship deploy paths** — `.env.sample`, `Dockerfile`, `docker-compose.yml`.

### Reusable assets

| File | Reuse |
|---|---|
| `scripts/frappe_doctype_to_schema.py` | DocType JSON → SQLite DDL |
| `scripts/build_demo_gif.sh` | frames → demo GIF |
| `web/layout.py` | 3-pane shell + CSS tokens + SSE chat JS |
| `web/ai.py` `_provider_stream()` | 4-provider streaming chat |
