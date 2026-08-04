#!/usr/bin/env python3
"""Run this repository's deployment through the sibling FastDevOps control plane."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = Path(os.getenv("FASTDEVOPS_DIR", ROOT.parent / "FastDevOps")).resolve()
if not (CONTROL / "cli.py").is_file():
    raise SystemExit("FastDevOps not found; set FASTDEVOPS_DIR to its checkout")
sys.path.insert(0, str(CONTROL))
from cli import catalog, load_local_env, main  # noqa: E402

for key, value in load_local_env(ROOT / ".env").items():
    if key in {"COOLIFY_API_TOKEN", "COOLIFY_BASE_URL"}:
        os.environ.setdefault(key, value)


def _stamp_build_identity() -> None:
    """Record the commit being shipped so the running app can name itself.

    Coolify builds from the repository without passing Docker build arguments,
    so the Dockerfile's ARGs stay empty and a deployed container has no git
    history to fall back on — /about and /healthz would only ever report
    "unknown". FastDevOps syncs environment variables from this repo's .env, so
    stamping them there is what carries the commit through to the container.

    .env is gitignored and local, so this never leaves the machine deploying.
    """
    import re
    import subprocess

    def git(*args: str) -> str:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                             timeout=5, check=False)
        return out.stdout.strip() if out.returncode == 0 else ""

    stamp = {"FASTHR_COMMIT": git("rev-parse", "--short", "HEAD"),
             "FASTHR_BRANCH": git("rev-parse", "--abbrev-ref", "HEAD"),
             "FASTHR_BUILD_DATE": git("log", "-1", "--format=%cd", "--date=short")}
    if not stamp["FASTHR_COMMIT"]:
        print("warning: no git commit available; the deploy will report an unknown build")
        return
    if git("status", "--porcelain"):
        print(f"warning: working tree is dirty — {stamp['FASTHR_COMMIT']} will not match "
              f"exactly what is deployed")

    env_path = ROOT / ".env"
    text = env_path.read_text() if env_path.exists() else ""
    for key, value in stamp.items():
        line = f"{key}={value}"
        if re.search(rf"(?m)^{key}=", text):
            text = re.sub(rf"(?m)^{key}=.*$", line, text)
        else:
            text = text.rstrip("\n") + f"\n{line}\n"
    env_path.write_text(text)
    print(f"stamped build identity: {stamp['FASTHR_COMMIT']} on {stamp['FASTHR_BRANCH']} "
          f"({stamp['FASTHR_BUILD_DATE']})")
service = next((name for name, spec in catalog().items() if spec.get("local_dir") == ROOT.name), None)
if not service:
    raise SystemExit(f"{ROOT.name} is not declared in FastDevOps")
if len(sys.argv) < 2:
    raise SystemExit("usage: coolify.py validate|doctor|status|provision|env|deploy [options]")
command, *options = sys.argv[1:]
if command in {"env", "deploy"}:
    _stamp_build_identity()
sys.argv = [sys.argv[0], command, *([] if command == "validate" else [service]), *options]
main()
