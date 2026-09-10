"""Live provider adapters used by the integrations service."""
from __future__ import annotations

from . import base

ADAPTERS = {
    "slack": base.slack_test,
    "github": base.github_test,
    "greenhouse": base.greenhouse_test,
    "bamboohr": base.bamboohr_test,
    "checkr": base.checkr_test,
    "teams": base.teams_test,
}


def adapter(provider: str):
    """Return the live adapter for *provider*, if this build has one."""
    return ADAPTERS.get(provider)

