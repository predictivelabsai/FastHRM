#!/usr/bin/env python3
"""Capture the user-guide screenshots from a running FastHRM cockpit.

Drives a headless Chromium through every feature page and saves one screenshot
each. These feed the landscape user guide (docs/fasthrm_user_guide_<date>.md →
PDF + PPTX) and the README walkthrough GIF.

Usage (server must be running):
    DEMO_BASE_URL=http://localhost:5010 .venv/bin/python scripts/capture_guide_screenshots.py

Env: FASTHR_ADMIN_EMAIL / FASTHR_ADMIN_PASSWORD (defaults match the demo).
"""
from __future__ import annotations

import argparse
import os
import sys

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1500, "height": 940}

# (filename, kind, target) — kind drives the interaction.
SHOTS = [
    ("00-login.png",        "login",     "/login"),
    ("01-dashboard.png",    "goto",      "/"),
    ("02-employees.png",    "goto",      "/employees"),
    ("03-employee.png",     "first_row", "/employees"),
    ("04-departments.png",  "goto",      "/departments"),
    ("05-leave.png",        "goto",      "/leave"),
    ("06-attendance.png",   "goto",      "/attendance"),
    ("07-payroll.png",      "goto",      "/payroll"),
    ("08-payslip.png",      "first_row", "/payroll"),
    ("09-requisitions.png", "goto",      "/talent/jobs"),
    ("10-pipeline.png",     "goto",      "/talent/jobs/1"),
    ("11-candidates.png",   "goto",      "/talent/candidates"),
    ("12-candidate.png",    "parsed",    "/talent/candidates"),
    ("13-upload.png",       "upload",    "/talent/candidates"),
    ("14-offers.png",       "goto",      "/talent/offers"),
    ("15-analytics.png",    "goto",      "/talent/analytics"),
    ("16-goals.png",        "goto",      "/performance/goals"),
    ("17-alignment.png",    "goto",      "/performance/alignment"),
    ("18-feedback.png",     "goto",      "/performance/feedback"),
    ("19-reviews.png",      "goto",      "/performance/reviews"),
    ("20-signals.png",      "goto",      "/performance/signals"),
    ("21-onboarding.png",   "goto",      "/lifecycle/onboarding"),
    ("22-changes.png",      "goto",      "/lifecycle/changes"),
    ("23-separations.png",  "goto",      "/lifecycle/separations"),
    ("24-cases.png",        "goto",      "/lifecycle/cases"),
    ("25-org.png",          "goto",      "/lifecycle/org"),
    ("26-integrations.png", "goto",      "/settings/integrations"),
    ("27-roles.png",        "goto",      "/settings/roles"),
    ("28-prompts.png",      "goto",      "/talent/prompts"),
    ("29-ai.png",           "chat",      "Which department is biggest?"),
    ("30-developers.png",   "goto",      "/developers"),
]


def _settle(page, extra=1100):
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(extra)


def capture(base_url: str, out_dir: str, only: set[str] | None = None):
    email = os.getenv("FASTHR_ADMIN_EMAIL", "admin@fasthr.example")
    password = os.getenv("FASTHR_ADMIN_PASSWORD", "FastHR2026$")
    os.makedirs(out_dir, exist_ok=True)
    shots = [s for s in SHOTS if not only or s[0] in only]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        login_shot = next((s for s in shots if s[1] == "login"), None)
        if login_shot:
            # tighter viewport: the sign-in card is small, and at full cockpit
            # width it disappears into a field of background colour
            page.set_viewport_size({"width": 900, "height": 620})
            page.goto(f"{base_url}/login")
            _settle(page)
            page.screenshot(path=os.path.join(out_dir, login_shot[0]))
            page.set_viewport_size(VIEWPORT)
            print(f"  ✓ {login_shot[0]}")

        page.goto(f"{base_url}/login")
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        for fname, kind, target in shots:
            if kind == "login":
                continue
            dest = os.path.join(out_dir, fname)
            try:
                if kind == "goto":
                    page.goto(f"{base_url}{target}")
                    _settle(page)
                elif kind == "first_row":
                    # open the first detail link in the table
                    page.goto(f"{base_url}{target}")
                    _settle(page, 500)
                    page.click("table.tbl tbody tr:first-child a")
                    _settle(page)
                elif kind == "parsed":
                    # the candidate whose profile came from a real CV parse
                    page.goto(f"{base_url}{target}")
                    _settle(page, 500)
                    # the CV-parse column shows an "ok" pill on extracted profiles
                    row = page.locator("table.tbl tbody tr").filter(
                        has=page.locator("span.pill.ok")).first
                    if row.count():
                        row.locator("a").first.click()
                    else:
                        page.click("table.tbl tbody tr:first-child a")
                    _settle(page)
                elif kind == "upload":
                    page.goto(f"{base_url}{target}")
                    _settle(page, 500)
                    page.locator(".drop-zone").scroll_into_view_if_needed()
                    page.wait_for_timeout(700)
                elif kind == "chat":
                    page.goto(f"{base_url}/")
                    _settle(page, 600)
                    page.fill("#chat-input", target)
                    page.press("#chat-input", "Enter")
                    page.wait_for_timeout(7000)  # let the answer stream in
                page.screenshot(path=dest)
                print(f"  ✓ {fname}")
            except Exception as e:  # keep going; report the miss
                print(f"  ✗ {fname}: {e}", file=sys.stderr)
        browser.close()
    print(f"✓ Saved screenshots to {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("DEMO_BASE_URL", "http://localhost:5010"))
    ap.add_argument("--out", default="screenshots")
    ap.add_argument("--only", default="", help="comma-separated filenames to (re)capture")
    a = ap.parse_args()
    only = {s.strip() for s in a.only.split(",") if s.strip()} or None
    capture(a.base_url.rstrip("/"), a.out, only)
