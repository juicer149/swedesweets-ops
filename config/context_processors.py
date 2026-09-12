from __future__ import annotations

from accounts.navigation import (
    build_home_href,
)
from accounts.roles import (
    AccountRole,
    Capability,
)
from business_portal.navigation import (
    build_business_primary_nav_items,
)
from business_portal.orders.navbar_viewmodels import (
    build_business_navbar_cart,
)
from business_portal.selectors import (
    get_portal_customer_for_user,
)
from ops_portal.navigation import (
    build_staff_primary_nav_items,
)
from orders.selectors import (
    get_active_draft_order_for_customer,
)


def navigation(request):
    account_role = getattr(
        request,
        "account_role",
        None,
    )
    role_spec = getattr(
        request,
        "role_spec",
        None,
    )

    if (
        account_role is None
        or role_spec is None
    ):
        return {
            "primary_nav_items": (),
            "site_home_href": build_home_href(
                account_role=None,
                role_spec=None,
            ),
            "navbar_cart": None,
        }

    navbar_cart = None

    if (
        account_role
        == AccountRole.BUSINESS_CUSTOMER
    ):
        primary_nav_items = (
            build_business_primary_nav_items(
                role_spec=role_spec,
            )
        )

        if role_spec.allows(
            Capability.PLACE_BUSINESS_ORDERS
        ):
            customer = (
                get_portal_customer_for_user(
                    user=request.user,
                )
            )

            draft_order = (
                get_active_draft_order_for_customer(
                    customer=customer,
                )
            )

            navbar_cart = (
                build_business_navbar_cart(
                    draft_order=draft_order,
                    language_code=getattr(
                        request,
                        "LANGUAGE_CODE",
                        None,
                    ),
                )
            )
    else:
        primary_nav_items = (
            build_staff_primary_nav_items(
                account_role=account_role,
                role_spec=role_spec,
            )
        )

    return {
        "primary_nav_items": primary_nav_items,
        "site_home_href": build_home_href(
            account_role=account_role,
            role_spec=role_spec,
        ),
        "navbar_cart": navbar_cart,
    }
