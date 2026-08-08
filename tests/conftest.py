"""Test fixtures — every test runs against a throwaway migrated database."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env so the opt-in live-model test can reach the API. It does not
# override variables the fixtures set.
load_dotenv(ROOT / ".env")


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """A migrated, empty database isolated per test."""
    monkeypatch.setenv("FASTHR_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("FASTSME_AUTH_DB", str(tmp_path / "accounts.sqlite"))
    monkeypatch.setenv("FASTHR_UPLOAD_DIR", str(tmp_path / "uploads"))

    import db
    importlib.reload(db)
    db.migrate()

    import talent
    importlib.reload(talent)
    from web import cv_extract, llm
    importlib.reload(cv_extract)
    llm.reset()  # drop any client cached by an earlier test
    return db
