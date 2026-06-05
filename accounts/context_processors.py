from __future__ import annotations

from accounts.navigation import build_primary_nav_items


def navigation(request):
    role_spec = getattr(request, "role_spec", None)

    if role_spec is None:
        return {
            "primary_nav_items": (),
        }

    return {
        "primary_nav_items": build_primary_nav_items(role_spec=role_spec),
    }
