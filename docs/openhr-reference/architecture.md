# Reference architecture — Frappe-shaped CRM (Python back-end, Vue front-end)

This is the architectural shape that a Frappe-CRM-style deployment takes: a
Python back-end built on the Frappe framework, a Vue 3 / Frappe-UI front-end,
MariaDB (or Postgres) for the site database, Redis for queues and cache, and
site-per-tenant isolation. It is the reference stack assumed throughout the
rest of this review.

## Runtime topology

```mermaid
flowchart LR
    Browser["Browser<br/>Vue 3 SPA (Frappe-UI)"]
    subgraph Proc["Python process (gunicorn / uvicorn)"]
      WebApp["Frappe web app<br/>REST + /api/method RPC<br/>WebSockets"]
      ORM["Frappe ORM<br/>DocType metadata layer"]
      Queue["Background workers<br/>(RQ)"]
    end
    Redis[("Redis<br/>queue + cache + pub/sub")]
    Store[("MariaDB (default)<br/>or PostgreSQL")]
    Files[("/sites/&lt;tenant&gt;/public/files<br/>attachments, receipts")]

    Browser -- "HTTPS + WS" --> WebApp
    WebApp --> ORM
    ORM --> Store
    WebApp --> Redis
    Queue --> Redis
    Queue --> ORM
    WebApp --> Files
```

## Module layout (Frappe CRM shape)

```mermaid
flowchart TB
    subgraph Backend["Python back-end (crm app on Frappe framework)"]
      DocTypes["crm/fcrm/doctype/<br/>Lead · Deal · Task · Note · CallLog ·<br/>Organization · Contact · SLA · Territory"]
      API["crm/api/<br/>contact · deal · dashboard · notifications ·<br/>views · todo · whatsapp · onboarding"]
      Integrations["crm/integrations/<br/>twilio · exotel · (whatsapp via frappe_whatsapp)"]
      Overrides["crm/overrides/ · crm/utils/<br/>hooks, server scripts"]
      Patches["crm/patches/<br/>schema migrations"]
    end
    subgraph Frontend["Vue 3 front-end (frontend/)"]
      Views["Lead · Deal · Kanban ·<br/>Contacts · Organizations ·<br/>Email templates · Call UI"]
      FUI["Frappe-UI components"]
      SDK["Frappe JS SDK<br/>(call resource, RPC)"]
    end
    Views --> FUI --> SDK
    SDK -- "REST / RPC / WS" --> API
    API --> DocTypes
    Integrations --> DocTypes
```

## DocType-driven functional model

```mermaid
erDiagram
    LEAD ||--o{ DEAL : "converts to"
    ORGANIZATION ||--o{ CONTACT : "employs"
    ORGANIZATION ||--o{ DEAL : "party"
    CONTACT ||--o{ DEAL : "primary contact"
    DEAL ||--o{ TASK : "has"
    DEAL ||--o{ NOTE : "has"
    DEAL ||--o{ CALL_LOG : "has"
    LEAD ||--o{ CALL_LOG : "has"
    USER ||--o{ TASK : "assigned"
    SLA ||--o{ DEAL : "governs"

    LEAD {
      string name PK
      string lead_name
      string email
      string phone
      string status
      string source
      string industry
      string territory
      link organization
      datetime created
    }
    DEAL {
      string name PK
      link lead FK
      link organization FK
      link contact FK
      string status
      currency amount
      date close_date
      string probability
      link assigned_to
    }
    TASK {
      string name PK
      string title
      string status
      date due_date
      link reference_doctype
      string reference_name
      link assigned_to
    }
    CALL_LOG {
      string name PK
      string from_number
      string to_number
      string provider
      string recording_url
      string reference_doctype
      string reference_name
    }
```

## Request lifecycle (typical CRM read)

```mermaid
sequenceDiagram
    actor U as Sales user (browser)
    participant V as Vue view
    participant API as /api/method/crm.api.deal
    participant F as Frappe framework
    participant DB as MariaDB / Postgres

    U->>V: open Kanban
    V->>API: fetch deals (filters, sort, fields)
    API->>F: DocType query + permissions
    F->>DB: SELECT with perm filter
    DB-->>F: rows
    F-->>API: dict payload
    API-->>V: JSON
    V-->>U: Kanban rendered (Frappe-UI)
    V-->>F: WS subscribe (doc_update)
    F-->>V: pushes on edits
```

## Integration surface

```mermaid
flowchart LR
    CRM["Frappe CRM"]
    ERP["ERPNext<br/>invoicing, accounting"]
    Twilio["Twilio<br/>click-to-call, SMS"]
    Exotel["Exotel<br/>agent mobile calls"]
    WA["WhatsApp<br/>(frappe_whatsapp)"]
    Email["IMAP/SMTP<br/>inbound + templates"]
    SSO["LDAP / OAuth / SAML<br/>(Frappe auth)"]
    Webhooks["Webhooks + REST<br/>+ /api/method RPC"]
    Cloud["External services<br/>(custom)"]

    Twilio --- CRM
    Exotel --- CRM
    WA --- CRM
    Email --- CRM
    SSO --- CRM
    CRM --- ERP
    CRM --- Webhooks --- Cloud
```

## Deployment shape

```mermaid
flowchart LR
    subgraph Prod["Production"]
      LB["Reverse proxy<br/>(nginx / caddy)"]
      Web["crm web workers<br/>gunicorn"]
      Workers["RQ workers"]
      Redis2[("Redis")]
      PG[("MariaDB / Postgres")]
      Files2[("/sites/&lt;tenant&gt;")]
      LB --> Web --> PG
      Web --> Redis2
      Workers --> Redis2
      Workers --> PG
      Web --> Files2
      Workers --> Files2
    end
```

## Design properties that matter for an enterprise

1. **Metadata-driven extension.** Adding a new object is a DocType (JSON);
   permissions are data; workflows are data; reports are data. Customisation
   survives version upgrades.
2. **Site-per-tenant isolation.** Each customer / business unit can be its own
   site with its own DB — clean data-residency story.
3. **Python-typed back-end, thin JS front-end.** Boring, readable,
   inspectable. No 200 MB `node_modules` on the server.
4. **Built-in job queue, websockets, permissions, file store.** You don't
   reinvent these per integration.
5. **Open licence (AGPL-3) + self-host.** Exit cost is a database export and a
   Docker image.
