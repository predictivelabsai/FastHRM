"""Settings → Integrations: connect job boards, social, calendar and e-sign.

API keys are encrypted before storage and only ever rendered back as a masked
hint. The form treats a blank secret field as "leave unchanged", so re-saving
does not require retyping a key you cannot see.
"""
from __future__ import annotations

from fasthtml.common import (
    Div, H3, H4, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button,
    Select, Option, Label, Small, Strong, Details, Summary, NotStr,
)

import integrations
from web.layout import kpi_card
from web.views import _pill, _title

STATUS_TONE = {"Connected": "ok", "Error": "error", "Disabled": "cancelled",
               "Not configured": ""}


def _status_pill(status):
    return Span(status, cls="pill " + (STATUS_TONE.get(status) or "").lower())


def _card(i):
    cls = "int-card" + (" on" if i["status"] == "Connected" else
                        " err" if i["status"] == "Error" else "")
    key_line = (Span(i["key_hint"], cls="int-key") if i["key_hint"]
                else Small("No key stored", style="color:var(--text-mute);"))
    tested = None
    if i["last_test_at"]:
        tested = Div(("✓ " if i["last_test_ok"] else "✕ ") + (i["last_test_note"] or ""),
                     cls="int-meta",
                     style="color:var(--danger);" if not i["last_test_ok"] else "")
    return Div(
        Div(Div(Span(i["label"], cls="nm"),
                Div(integrations.CATEGORY_LABELS.get(i["category"], i["category"]),
                    cls="int-meta")),
            _status_pill(i["status"]), cls="int-head"),
        P(i["blurb"], cls="int-blurb"),
        Div(key_line, style="margin:2px 0;"),
        tested,
        Div(A("Configure", href=f"/settings/integrations/{i['provider']}", cls="btn sm primary"),
            Button("Test", cls="btn sm",
                   **{"hx-post": f"/settings/integrations/{i['provider']}/test",
                      "hx-target": "#int-grid", "hx-swap": "innerHTML"}) if i["key_hint"] else None,
            Button("Sync now", cls="btn sm",
                   **{"hx-post": f"/settings/integrations/{i['provider']}/sync",
                      "hx-target": "#int-grid", "hx-swap": "innerHTML"})
            if i["status"] == "Connected" else None,
            cls="int-actions"),
        cls=cls)


def integrations_grid():
    grouped = integrations.by_category()
    blocks = []
    for cat in integrations.CATEGORIES:
        items = grouped.get(cat) or []
        if not items:
            continue
        blocks.append(Div(H4(integrations.CATEGORY_LABELS.get(cat, cat),
                             style="margin:18px 0 10px;font-size:12px;text-transform:uppercase;"
                                   "letter-spacing:.8px;color:var(--text-mute);"),
                          Div(*[_card(i) for i in items], cls="int-grid")))
    return Div(*blocks)


def integrations_page(saved: str = ""):
    k = integrations.kpis()
    banner = P(saved, cls="flag",
               style="border-left-color:var(--accent);background:var(--accent-light);"
                     "color:var(--accent-hover);") if saved else None
    return (
        _title("Integrations",
               "Connect FastHRM to the job boards, calendars and tools you already use."),
        banner,
        Div(kpi_card("Connected", k["connected"], f"of {k['total']} available"),
            kpi_card("Needs attention", k["error"], "failed connection test",
                     tone="danger" if k["error"] else ""),
            kpi_card("Not configured", k["unconfigured"], "no credentials stored"),
            kpi_card("Providers", k["total"], "across 7 categories"),
            cls="kpi-grid"),
        P(NotStr("Keys are encrypted at rest with the application secret and are never shown "
                 "again in full — only the last four characters. Rotating <code>FASTHR_SECRET</code> "
                 "invalidates stored credentials and they must be re-entered."),
          style="color:var(--text-mute);font-size:12.5px;margin:-4px 0 14px;"),
        Div(integrations_grid(), id="int-grid"),
        Div(Div(H3("Recent integration activity"), cls="card-header"),
            _event_table(integrations.events(limit=15)), cls="card", style="margin-top:20px;"),
    )


ROLES = ["admin", "hrbp", "recruiter", "hiring_manager", "manager", "employee"]
ROLE_BLURB = {
    "admin": "Everything, including integrations and roles.",
    "hrbp": "All people data, cases, performance and lifecycle.",
    "recruiter": "Requisitions, candidates, interviews and offers.",
    "hiring_manager": "Candidates on their own requisitions, and their team.",
    "manager": "Their direct reports: goals, feedback, leave and reviews.",
    "employee": "Their own record only.",
}


def roles_page(saved: str = ""):
    import db
    assigned = db.rows("""SELECT r.*, e.first_name||' '||e.last_name employee
                          FROM account_roles r LEFT JOIN employees e ON e.id=r.employee_id
                          ORDER BY r.account_email, r.role""")
    emps = db.employees_min()
    banner = P(saved, cls="flag",
               style="border-left-color:var(--accent);background:var(--accent-light);"
                     "color:var(--accent-hover);") if saved else None

    tbl = Table(Thead(Tr(Th("Account"), Th("Role"), Th("Scope"), Th("Linked employee"), Th(""))),
                Tbody(*[Tr(Td(r["account_email"]), Td(_pill(r["role"])), Td(_pill(r["scope"])),
                           Td(r["employee"] or "—"),
                           Td(Button("Remove", cls="btn sm",
                                     **{"hx-post": f"/settings/roles/{r['id']}/delete",
                                        "hx-target": "#roles", "hx-swap": "innerHTML"})))
                        for r in assigned] or [Tr(Td("No roles assigned yet.", colspan="5"))]),
                cls="tbl")

    form = Form(
        Input(name="account_email", type="email", placeholder="person@company.com",
              cls="hr-inp", required=True, style="min-width:220px;"),
        Select(*[Option(r, value=r) for r in ROLES], name="role", cls="hr-inp"),
        Select(Option("All data", value="all"), Option("Own department", value="dept"),
               Option("Themselves only", value="self"), name="scope", cls="hr-inp"),
        Select(Option("— link to employee (optional) —", value="0"),
               *[Option(f"{e['first_name']} {e['last_name']}", value=str(e["id"])) for e in emps],
               name="employee_id", cls="hr-inp"),
        Button("Assign role", cls="btn primary", type="submit"),
        method="post", action="/settings/roles", cls="inline-form",
        style="flex-wrap:wrap;gap:8px;")

    return (_title("Roles & access", "Who can see and do what"),
            banner,
            P(NotStr("Roles are recorded here and shown throughout the audit trail. "
                     "<strong>Row-level enforcement is not yet wired into the query layer</strong> — "
                     "every signed-in user still sees all data. Assigning roles now means the "
                     "enforcement pass has real assignments to apply."),
              cls="flag"),
            Div(Div(H3("Assign a role"), cls="card-header"), form, cls="card"),
            Div(Div(Div(H3(f"Assigned roles ({len(assigned)})"), cls="card-header"), tbl,
                    cls="card"), id="roles"),
            Div(Div(H3("What each role is for"), cls="card-header"),
                Table(Thead(Tr(Th("Role"), Th("Intended access"))),
                      Tbody(*[Tr(Td(_pill(r)), Td(ROLE_BLURB[r])) for r in ROLES]), cls="tbl"),
                cls="card"))


def roles_table():
    return roles_page()[4].children[0]


def _event_table(evts):
    return Table(Thead(Tr(Th("When"), Th("Provider"), Th("Event"), Th("Result"), Th("Detail"))),
                 Tbody(*[Tr(Td(Small(e["created"], style="color:var(--text-mute);white-space:nowrap;")),
                            Td(integrations.provider_meta(e["provider"] or "")["label"]),
                            Td(_pill(e["kind"] or "—")),
                            Td(Span("OK" if e["ok"] else "Failed",
                                    cls="pill " + ("ok" if e["ok"] else "error"))),
                            Td(Small(e["detail"] or "—")))
                         for e in evts] or [Tr(Td("Nothing yet.", colspan="5"))]), cls="tbl")


def integration_detail(provider: str, note: str = ""):
    meta = integrations.provider_meta(provider)
    live = next((i for i in integrations.all_integrations() if i["provider"] == provider), None)
    if not live:
        return _title("Unknown integration"), P("No such provider.")

    banner = None
    if note:
        ok = not note.lower().startswith(("no ", "failed", "stored credential"))
        banner = P(note, cls="flag",
                   style=("border-left-color:var(--accent);background:var(--accent-light);"
                          "color:var(--accent-hover);") if ok else "")

    secret_field = None
    if meta["secret_label"]:
        secret_field = Div(
            Label(meta["secret_label"], style="font-size:12px;color:var(--text-mute);"),
            Input(type="password", name="api_secret", cls="hr-inp", style="width:100%;",
                  placeholder=live["secret_hint"] or f"Enter the {meta['secret_label'].lower()}",
                  autocomplete="new-password"),
            style="margin-bottom:12px;")

    form = Form(
        Div(Label(meta["key_label"], style="font-size:12px;color:var(--text-mute);"),
            Input(type="password", name="api_key", cls="hr-inp", style="width:100%;",
                  placeholder=live["key_hint"] or f"Enter the {meta['key_label'].lower()}",
                  autocomplete="new-password"),
            style="margin-bottom:12px;"),
        secret_field,
        Div(Label("Account / organisation reference (optional)",
                  style="font-size:12px;color:var(--text-mute);"),
            Input(name="account_ref", value=live["account_ref"], cls="hr-inp", style="width:100%;",
                  placeholder="e.g. your company page or account id at the provider"),
            style="margin-bottom:12px;"),
        Div(Label(Input(type="checkbox", name="auto_sync", value="1",
                        checked=live["auto_sync"], style="margin-right:7px;"),
                  "Sync automatically once connected",
                  style="font-size:13px;display:flex;align-items:center;"),
            style="margin-bottom:14px;"),
        Div(Button("Save credentials", cls="btn primary", type="submit"),
            Button("Test connection", cls="btn", type="submit", name="test", value="1"),
            style="display:flex;gap:8px;"),
        method="post", action=f"/settings/integrations/{provider}")

    danger = Form(
        Button("Disconnect and erase stored credentials", cls="btn", type="submit",
               style="color:var(--danger);border-color:var(--danger);"),
        method="post", action=f"/settings/integrations/{provider}/disconnect") if live["key_hint"] else None

    detail = Div(Div(H3("Connection"), _status_pill(live["status"]), cls="card-header"),
                 Div(Span("Provider", cls="k"), Span(meta["label"]),
                     Span("Category", cls="k"),
                     Span(integrations.CATEGORY_LABELS.get(meta["category"], meta["category"])),
                     Span(meta["key_label"], cls="k"),
                     Span(Span(live["key_hint"], cls="int-key") if live["key_hint"] else "— not set"),
                     *([Span(meta["secret_label"], cls="k"),
                        Span(Span(live["secret_hint"], cls="int-key") if live["secret_hint"]
                             else "— not set")] if meta["secret_label"] else []),
                     Span("Last tested", cls="k"), Span(live["last_test_at"] or "never"),
                     Span("Last sync", cls="k"), Span(live["last_sync_at"] or "never"),
                     Span("Auto-sync", cls="k"), Span("On" if live["auto_sync"] else "Off"),
                     cls="kv"),
                 P(live["last_test_note"], cls="int-meta",
                   style="margin-top:10px;") if live["last_test_note"] else None,
                 cls="card")

    return (_title(meta["label"], meta["blurb"],
                   A("← Integrations", href="/settings/integrations", cls="btn")),
            banner,
            Div(Div(Div(Div(H3("Credentials"), cls="card-header"),
                        P("Stored encrypted. Leave a field blank to keep the current value.",
                          style="color:var(--text-mute);font-size:12.5px;margin:0 0 12px;"),
                        form,
                        Div(danger, style="margin-top:16px;padding-top:14px;"
                                          "border-top:1px solid var(--border);") if danger else None,
                        cls="card")),
                Div(detail,
                    Div(Div(H3("Activity"), cls="card-header"),
                        _event_table(integrations.events(provider, limit=12)), cls="card")),
                cls="detail-grid"))
