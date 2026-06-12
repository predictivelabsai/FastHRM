"""Minimal CLI — wraps ``openhr.app.main`` so the ``openhr`` entry point works."""

from __future__ import annotations

from .app import main as _main


def main() -> int:
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
