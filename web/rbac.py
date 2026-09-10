"""Granular, module-level role permissions."""
from __future__ import annotations

import db
from web.layout import NAV_ITEMS


MODULES = tuple(
    (key, label)
    for _section, items in NAV_ITEMS
    for key, label, _icon, _href in items
)


def permissions_for(role_names: set[str] | list[str] | tuple[str, ...]) -> dict[str, dict[str, bool]]:
    """Return the union of configured permissions for the supplied roles."""
    names = {str(name).strip().lower() for name in role_names if str(name).strip()}
    if not names:
        return {}
    marks = ",".join("?" for _ in names)
    rows = db.rows(
        f"SELECT module_key, can_view, can_edit FROM role_permissions "
        f"WHERE lower(role_name) IN ({marks})", tuple(names))
    result: dict[str, dict[str, bool]] = {}
    for row in rows:
        current = result.setdefault(row["module_key"], {"view": False, "edit": False})
        current["view"] = current["view"] or bool(row["can_view"])
        current["edit"] = current["edit"] or bool(row["can_edit"])
    return result


def can(user_roles: set[str] | list[str] | tuple[str, ...], module_key: str,
        action: str = "view") -> bool:
    """Check access, leaving modules without a configured row unchanged."""
    roles = {str(role).strip().lower() for role in user_roles}
    if "admin" in roles:
        return True
    configured = permissions_for(roles)
    if module_key not in configured:
        return True
    return bool(configured[module_key].get("edit" if action == "edit" else "view"))
