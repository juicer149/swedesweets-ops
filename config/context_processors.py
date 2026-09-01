from __future__ import annotations

from accounts.navigation import build_home_href
from ops_portal.navigation import build_staff_primary_nav_items
from accounts.roles import AccountRole
from business_portal.navigation import (
    build_business_primary_nav_items,
)


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

    if account_role == AccountRole.BUSINESS_CUSTOMER:
        primary_nav_items = build_business_primary_nav_items(
            role_spec=role_spec,
        )
    else:
        primary_nav_items = build_staff_primary_nav_items(
            account_role=account_role,
            role_spec=role_spec,
        )

    return {
        "primary_nav_items": primary_nav_items,
        "site_home_href": build_home_href(
            account_role=account_role,
            role_spec=role_spec,
        ),
    }
