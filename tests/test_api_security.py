"""Bearer-token access and response redaction for the JSON API."""
from __future__ import annotations

import importlib

from fastapi import FastAPI
from starlette.testclient import TestClient


def _client():
    from web import api as api_module

    importlib.reload(api_module)
    app = FastAPI()
    app.mount("/api", api_module.api)
    return TestClient(app), api_module.api


def _employee(db) -> int:
    with db.cursor() as connection:
        cursor = connection.execute(
            "INSERT INTO employees "
            "(first_name, last_name, status, base_salary, personal_code, password_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Ada", "Lovelace", "Active", 120000, "39001010001", "secret-hash"),
        )
        return cursor.lastrowid


def _contains_key(value, forbidden: str) -> bool:
    if isinstance(value, dict):
        return forbidden in value or any(
            _contains_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, forbidden) for item in value)
    return False


def test_unauthenticated_employee_list_is_disabled_without_token(
    fresh_db, monkeypatch
):
    monkeypatch.delenv("FASTSME_API_TOKEN", raising=False)
    client, _api = _client()

    response = client.get("/api/v1/employees", params={"limit": 1})

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "api_access_disabled",
            "message": (
                "API reads are disabled until FASTSME_API_TOKEN is configured."
            ),
            "details": {},
        }
    }


def test_unauthenticated_employee_detail_is_disabled_without_token(
    fresh_db, monkeypatch
):
    employee_id = _employee(fresh_db)
    monkeypatch.delenv("FASTSME_API_TOKEN", raising=False)
    client, _api = _client()

    response = client.get(f"/api/v1/employees/{employee_id}")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_access_disabled"


def test_employee_reads_require_valid_token_and_redact_password_hash(
    fresh_db, monkeypatch
):
    employee_id = _employee(fresh_db)
    monkeypatch.setenv("FASTSME_API_TOKEN", "test-api-token")
    client, api = _client()

    missing = client.get("/api/v1/employees", params={"limit": 1})
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "invalid_token"
    assert missing.headers["www-authenticate"] == "Bearer"

    wrong = client.get(
        "/api/v1/employees",
        params={"limit": 1},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_token"
    assert wrong.headers["www-authenticate"] == "Bearer"

    headers = {"Authorization": "Bearer test-api-token"}
    listed = client.get(
        "/api/v1/employees", params={"limit": 1}, headers=headers
    )
    detail = client.get(f"/api/v1/employees/{employee_id}", headers=headers)

    assert listed.status_code == 200
    assert detail.status_code == 200
    assert set(listed.json()) == {"data", "meta"}
    assert listed.json()["meta"] == {"total": 1, "limit": 1, "offset": 0}
    assert not _contains_key(listed.json(), "password_hash")
    assert not _contains_key(detail.json(), "password_hash")

    schema = api.openapi()
    employee_schema = schema["components"]["schemas"]["EmployeesResource"]
    assert "password_hash" not in employee_schema["properties"]


def test_unauthenticated_post_keeps_existing_write_token_behaviour(
    fresh_db, monkeypatch
):
    payload = {
        "employee_id": 1,
        "leave_type": "Annual Leave",
        "from_date": "2026-10-08",
        "to_date": "2026-10-08",
        "days": 1,
        "status": "Pending",
        "reason": "Test",
        "applied_on": "2026-10-08",
    }
    monkeypatch.delenv("FASTSME_API_TOKEN", raising=False)
    client, _api = _client()

    disabled = client.post("/api/v1/leave", json=payload)
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "writes_disabled"

    monkeypatch.setenv("FASTSME_API_TOKEN", "test-api-token")
    invalid = client.post(
        "/api/v1/leave",
        json=payload,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_token"
    assert invalid.headers["www-authenticate"] == "Bearer"
