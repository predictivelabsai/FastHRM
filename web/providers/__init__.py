"""Live provider adapters used by the integrations service."""
from __future__ import annotations

from . import base

ADAPTERS = {
    "slack": base.slack_test,
    "github": base.github_test,
    "greenhouse": base.greenhouse_test,
    "bamboohr": base.bamboohr_test,
    "personio": base.personio_test,
    "checkr": base.checkr_test,
    "deel": base.deel_test,
    "teams": base.teams_test,
}

DIRECTORY_ADAPTERS = {
    "bamboohr": "bamboohr_directory",
}


def adapter(provider: str):
    """Return the live adapter for *provider*, if this build has one."""
    return ADAPTERS.get(provider)


def directory_adapter(provider: str):
    """Return the live directory export adapter for *provider*, if available."""
    adapter_name = DIRECTORY_ADAPTERS.get(provider)
    return getattr(base, adapter_name) if adapter_name else None
