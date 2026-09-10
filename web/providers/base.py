"""Small, synchronous live checks for providers with cheap auth probes."""
from __future__ import annotations

import re
from typing import Any

import httpx

TIMEOUT = 10.0


def _failure(method: str, url: str, exc: Exception) -> tuple[bool, str]:
    called = f"{method} {url}"
    if isinstance(exc, httpx.TimeoutException):
        return False, f"{called} timed out after {int(TIMEOUT)} seconds."
    if isinstance(exc, httpx.RequestError):
        return False, f"{called} failed: provider could not be reached."
    return False, f"{called} failed: {type(exc).__name__}."


def _status(method: str, url: str, response: httpx.Response) -> tuple[bool, str]:
    called = f"{method} {url}"
    if 200 <= response.status_code < 300:
        return True, f"{called} returned HTTP {response.status_code}; authenticated read succeeded."
    if response.status_code in (401, 403):
        return False, f"{called} returned HTTP {response.status_code}; credentials were rejected."
    return False, f"{called} returned HTTP {response.status_code}; provider did not accept the request."


def _meta_label(meta: dict[str, Any]) -> str:
    return meta.get("label", "Provider")


def slack_test(meta, key, secret, account_ref):
    url = "https://slack.com/api/auth.test"
    if not key.startswith("xoxb-"):
        return False, f"POST {url} was not called: Slack bot tokens must start with xoxb-."
    try:
        response = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
    except Exception as exc:  # httpx normalizes network failures into RequestError subclasses
        return _failure("POST", url, exc)
    ok, note = _status("POST", url, response)
    if ok:
        try:
            body = response.json()
        except ValueError:
            return False, f"POST {url} returned HTTP {response.status_code}; Slack returned invalid JSON."
        if not body.get("ok"):
            return False, f"POST {url} returned HTTP {response.status_code}; Slack rejected the token."
    return ok, note


def github_test(meta, key, secret, account_ref):
    url = "https://api.github.com/user"
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/vnd.github+json"},
                             timeout=TIMEOUT)
    except Exception as exc:
        return _failure("GET", url, exc)
    return _status("GET", url, response)


def greenhouse_test(meta, key, secret, account_ref):
    url = "https://harvest.greenhouse.io/v1/jobs?per_page=1"
    try:
        response = httpx.get(url, auth=(key, ""), timeout=TIMEOUT)
    except Exception as exc:
        return _failure("GET", url, exc)
    return _status("GET", url, response)


def _bamboo_url(account_ref: str) -> str | None:
    subdomain = account_ref.strip().lower()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", subdomain):
        return None
    return f"https://{subdomain}.bamboohr.com/api/gateway.php/{subdomain}/v1/employees/directory"


def bamboohr_test(meta, key, secret, account_ref):
    url = _bamboo_url(account_ref)
    if not url:
        return False, "GET BambooHR employee directory was not called: a valid BambooHR subdomain is required."
    try:
        response = httpx.get(url, auth=(key, "x"), timeout=TIMEOUT)
    except Exception as exc:
        return _failure("GET", url, exc)
    return _status("GET", url, response)


def bamboohr_directory(key: str, account_ref: str):
    """Fetch the directory once and return its JSON and employee count."""
    url = _bamboo_url(account_ref)
    if not url:
        return False, "GET BambooHR employee directory was not called: a valid BambooHR subdomain is required.", None, 0
    try:
        response = httpx.get(url, auth=(key, "x"), timeout=TIMEOUT)
    except Exception as exc:
        ok, note = _failure("GET", url, exc)
        return ok, note, None, 0
    ok, note = _status("GET", url, response)
    if not ok:
        return ok, note, None, 0
    try:
        payload = response.json()
    except ValueError:
        return False, f"GET {url} returned HTTP {response.status_code}; BambooHR returned invalid JSON.", None, 0
    employees = payload.get("employees", payload) if isinstance(payload, dict) else payload
    count = len(employees) if isinstance(employees, list) else 0
    return True, f"GET {url} returned HTTP {response.status_code}; fetched {count} employees.", payload, count


def checkr_test(meta, key, secret, account_ref):
    url = "https://api.checkr.com/v1/candidates?limit=1"
    try:
        response = httpx.get(url, auth=(key, ""), timeout=TIMEOUT)
    except Exception as exc:
        return _failure("GET", url, exc)
    return _status("GET", url, response)


def teams_test(meta, key, secret, account_ref):
    url = key
    if not url.lower().startswith(("https://", "http://")):
        return False, "POST Teams webhook was not called: the webhook URL must start with http:// or https://."
    try:
        response = httpx.post(url, content="FastHR integration connection test.",
                              headers={"Content-Type": "text/plain"}, timeout=TIMEOUT)
    except Exception as exc:
        return _failure("POST", url, exc)
    return _status("POST", url, response)


__all__ = ["bamboohr_directory", "bamboohr_test", "checkr_test", "github_test",
           "greenhouse_test", "slack_test", "teams_test"]
