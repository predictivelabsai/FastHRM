"""Build identity — what version is this, and where did it come from.

Resolution order, most to least trustworthy:

1. Coolify's ``SOURCE_COMMIT`` runtime value.
2. ``FASTHR_COMMIT`` / ``FASTHR_BUILD_DATE`` values stamped by a manual deploy.
3. ``git`` in the working tree, for local development.
4. Nothing — reported as "unknown", never guessed.

The version number itself comes from the VERSION file, which is also what
scripts/build_user_guide.sh stamps into the guide footer, so the docs and the
running app always agree.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"


@lru_cache(maxsize=1)
def version() -> str:
    try:
        return VERSION_FILE.read_text().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                             timeout=3, check=False)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@lru_cache(maxsize=1)
def commit() -> str:
    return (os.getenv("SOURCE_COMMIT") or os.getenv("FASTHR_COMMIT")
            or _git("rev-parse", "--short", "HEAD") or "")[:12]


@lru_cache(maxsize=1)
def branch() -> str:
    return (os.getenv("COOLIFY_BRANCH") or os.getenv("FASTHR_BRANCH")
            or _git("rev-parse", "--abbrev-ref", "HEAD") or "")


@lru_cache(maxsize=1)
def build_date() -> str:
    # A webhook deployment may leave an older manual stamp in the environment.
    # Do not pair that date with Coolify's newer authoritative source commit.
    source_commit = os.getenv("SOURCE_COMMIT")
    stamped_commit = os.getenv("FASTHR_COMMIT")
    if source_commit and stamped_commit and source_commit[:12] != stamped_commit[:12]:
        return ""
    return (os.getenv("FASTHR_BUILD_DATE")
            or _git("log", "-1", "--format=%cd", "--date=short") or "")


@lru_cache(maxsize=1)
def dirty() -> bool:
    """True when the working tree has uncommitted changes — dev builds only."""
    if os.getenv("SOURCE_COMMIT") or os.getenv("FASTHR_COMMIT"):
        return False  # a stamped image is by definition a clean build
    return bool(_git("status", "--porcelain"))


def label() -> str:
    """Short form for the top bar: ``v0.3.0 · 4ee9ebe``."""
    parts = [f"v{version()}"]
    if commit():
        parts.append(commit() + ("+" if dirty() else ""))
    return " · ".join(parts)


def detail() -> str:
    """Long form for the tooltip and the About page."""
    bits = [f"FastHRM v{version()}"]
    if commit():
        bits.append(f"commit {commit()}{' (uncommitted changes)' if dirty() else ''}")
    if branch():
        bits.append(f"branch {branch()}")
    if build_date():
        bits.append(f"built {build_date()}")
    if not commit():
        bits.append("build provenance unknown — no FASTHR_COMMIT stamped and no git available")
    return " · ".join(bits)


def info() -> dict:
    return {"version": version(), "commit": commit(), "branch": branch(),
            "build_date": build_date(), "dirty": dirty(), "label": label(),
            "detail": detail()}
