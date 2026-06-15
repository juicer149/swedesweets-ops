from __future__ import annotations

from accounts.navigation import build_home_href, build_primary_nav_items


def navigation(request):
    account_role = getattr(request, "account_role", None)
    role_spec = getattr(request, "role_spec", None)

    if account_role is None or role_spec is None:
        return {
            "primary_nav_items": (),
            "site_home_href": build_home_href(
                account_role=None,
                role_spec=None,
            ),
        }

    return {
        "primary_nav_items": build_primary_nav_items(
            account_role=account_role,
            role_spec=role_spec,
        ),
        "site_home_href": build_home_href(
            account_role=account_role,
            role_spec=role_spec,
        ),
    }
