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
import shutil
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
    ("31-platform-operations.png",     "goto", "/talent/platform?section=operations"),
    ("32-platform-communications.png", "goto", "/talent/platform?section=communications"),
    ("33-platform-scheduling.png",     "goto", "/talent/platform?section=scheduling"),
    ("34-platform-marketing.png",      "goto", "/talent/platform?section=marketing"),
    ("35-platform-analytics.png",      "goto", "/talent/platform?section=analytics"),
    ("36-platform-enterprise.png",     "goto", "/talent/platform?section=enterprise"),
    ("37-workflow.png",                "goto", "/talent/jobs/2/workflow"),
    ("38-careers.png",                 "goto", "/careers"),
    ("39-public-job.png",              "goto", "/jobs/product-designer"),
    ("40-products.png",                "goto", "/features"),
]

# A concise cross-product tour for the README and public landing page. Keeping
# this manifest beside SHOTS makes the generated GIF deterministic and prevents
# guide-only screens from making the public walkthrough too long.
DEMO_FRAMES = [
    ("01-dashboard.png", "01-dashboard.png"),
    ("02-employees.png", "02-employees.png"),
    ("05-leave.png", "03-leave.png"),
    ("07-payroll.png", "04-payroll.png"),
    ("38-careers.png", "05-careers.png"),
    ("39-public-job.png", "06-public-job.png"),
    ("09-requisitions.png", "07-requisitions.png"),
    ("37-workflow.png", "08-workflow.png"),
    ("31-platform-operations.png", "09-recruiting-operations.png"),
    ("32-platform-communications.png", "10-communications.png"),
    ("33-platform-scheduling.png", "11-scheduling.png"),
    ("34-platform-marketing.png", "12-marketing.png"),
    ("35-platform-analytics.png", "13-recruiting-analytics.png"),
    ("36-platform-enterprise.png", "14-enterprise.png"),
    ("12-candidate.png", "15-candidate.png"),
    ("14-offers.png", "16-offers.png"),
    ("16-goals.png", "17-goals.png"),
    ("21-onboarding.png", "18-onboarding.png"),
    ("29-ai.png", "19-ai-assistant.png"),
]
LEGACY_DEMO_FRAMES = [
    "hr-01-dashboard.png", "hr-02-employees.png", "hr-03-leave.png",
    "hr-04-payroll.png", "hr-05-requisitions.png", "hr-06-pipeline.png",
    "hr-07-candidate.png", "hr-08-upload.png", "hr-09-offers.png",
    "hr-10-goals.png", "hr-11-signals.png", "hr-12-onboarding.png",
    "hr-13-org.png", "hr-14-integrations.png", "hr-15-ai.png",
]


def _settle(page, extra=1100):
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(extra)


def _goto(page, url: str):
    """Navigate and fail loudly instead of committing an HTTP error screenshot."""
    response = page.goto(url)
    if response is not None and not response.ok:
        raise RuntimeError(f"{url} returned HTTP {response.status}")
    return response


def capture(base_url: str, out_dir: str, only: set[str] | None = None,
            demo_frames_dir: str = ""):
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
            _goto(page, f"{base_url}/login")
            _settle(page)
            page.screenshot(path=os.path.join(out_dir, login_shot[0]))
            page.set_viewport_size(VIEWPORT)
            print(f"  ✓ {login_shot[0]}")

        # The public login page now uses the shared account modal. Keep the
        # deterministic legacy demo account only for local guide capture; the
        # request context shares its signed session cookie with the page.
        response = page.request.post(
            f"{base_url}/login", form={"email": email, "password": password}
        )
        if not response.ok:
            raise RuntimeError(f"demo login failed with HTTP {response.status}")
        _goto(page, f"{base_url}/")
        page.wait_for_load_state("networkidle")

        for fname, kind, target in shots:
            if kind == "login":
                continue
            dest = os.path.join(out_dir, fname)
            try:
                if kind == "goto":
                    _goto(page, f"{base_url}{target}")
                    _settle(page)
                elif kind == "first_row":
                    # open the first detail link in the table
                    _goto(page, f"{base_url}{target}")
                    _settle(page, 500)
                    page.click("table.tbl tbody tr:first-child a")
                    _settle(page)
                elif kind == "parsed":
                    # the candidate whose profile came from a real CV parse
                    _goto(page, f"{base_url}{target}")
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
                    _goto(page, f"{base_url}{target}")
                    _settle(page, 500)
                    page.locator(".drop-zone").scroll_into_view_if_needed()
                    page.wait_for_timeout(700)
                elif kind == "chat":
                    _goto(page, f"{base_url}/")
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

    if demo_frames_dir:
        os.makedirs(demo_frames_dir, exist_ok=True)
        generated_names = [target for _, target in DEMO_FRAMES]
        for name in [*generated_names, *LEGACY_DEMO_FRAMES]:
            path = os.path.join(demo_frames_dir, name)
            if os.path.isfile(path):
                os.unlink(path)
        for source, target in DEMO_FRAMES:
            source_path = os.path.join(out_dir, source)
            if not os.path.exists(source_path):
                raise FileNotFoundError(f"Demo source screenshot missing: {source_path}")
            shutil.copy2(source_path, os.path.join(demo_frames_dir, target))
        print(f"✓ Published {len(DEMO_FRAMES)} demo frames to {demo_frames_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.getenv("DEMO_BASE_URL", "http://localhost:5010"))
    ap.add_argument("--out", default="screenshots")
    ap.add_argument("--only", default="", help="comma-separated filenames to (re)capture")
    ap.add_argument("--demo-frames", default="",
                    help="replace this directory with the curated README/landing GIF frames")
    a = ap.parse_args()
    only = {s.strip() for s in a.only.split(",") if s.strip()} or None
    capture(a.base_url.rstrip("/"), a.out, only, a.demo_frames)
