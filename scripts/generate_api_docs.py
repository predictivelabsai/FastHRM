#!/usr/bin/env python3
"""Regenerate the committed FastHRM OpenAPI compatibility document."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.api import api  # noqa: E402
from web.api_core import write_swagger  # noqa: E402



if __name__ == "__main__":
    destination = ROOT / "swagger.json"
    write_swagger(api, destination)
    print(f"Generated {destination} from {len(api.routes)} API routes")
