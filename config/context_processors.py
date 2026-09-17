from __future__ import annotations

from django.urls import reverse

from accounts.account_menus import (
    build_business_account_menu,
    build_ops_account_menu,
    build_storefront_account_menu,
)
from accounts.navigation import build_home_href
from accounts.roles import AccountRole, Capability
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
from storefront.navigation import (
    build_public_primary_nav_items,
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
            "site_home_href": reverse("index"),
            "navbar_cart": None,
            "account_menu": None,
        }

    if _uses_shared_site_chrome(request):
        return _build_site_navigation(
            request=request,
            account_role=account_role,
            role_spec=role_spec,
        )

    return _build_portal_navigation(
        request=request,
        account_role=account_role,
        role_spec=role_spec,
    )


def _build_site_navigation(
    *,
    request,
    account_role: AccountRole,
    role_spec,
) -> dict:
    if (
        account_role
        == AccountRole.BUSINESS_CUSTOMER
    ):
        primary_nav_items = (
            build_business_primary_nav_items()
        )

        account_menu = (
            build_business_account_menu()
        )
    else:
        primary_nav_items = (
            build_public_primary_nav_items()
        )

        account_menu = (
            build_storefront_account_menu(
                account_role=account_role,
                role_spec=role_spec,
            )
        )

    return {
        "primary_nav_items": primary_nav_items,
        "site_home_href": reverse("index"),
        "navbar_cart": None,
        "account_menu": account_menu,
    }


def _build_portal_navigation(
    *,
    request,
    account_role: AccountRole,
    role_spec,
) -> dict:
    navbar_cart = None

    if (
        account_role
        == AccountRole.BUSINESS_CUSTOMER
    ):
        primary_nav_items = (
            build_business_primary_nav_items()
        )

        account_menu = (
            build_business_account_menu()
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

        account_menu = (
            build_ops_account_menu()
            if role_spec.allows(
                Capability.VIEW_STAFF_OPS
            )
            else None
        )

    return {
        "primary_nav_items": primary_nav_items,
        "site_home_href": build_home_href(
            account_role=account_role,
            role_spec=role_spec,
        ),
        "navbar_cart": navbar_cart,
        "account_menu": account_menu,
    }


def _uses_shared_site_chrome(
    request,
) -> bool:
    resolver_match = getattr(
        request,
        "resolver_match",
        None,
    )

    if resolver_match is None:
        return False

    return resolver_match.namespace in {
        "storefront",
        "public_site",
    }
