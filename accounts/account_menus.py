"""
Identity menus for the shared navbar account slot.

The account slot has one presentation component, but its contents depend on
the current application zone:

    public storefront
        anonymous       -> no menu; navbar renders Login
        business custom -> Orders, My account, Store info, Logout
        staff           -> My account, Ops dashboard, Logout

    business portal
        business custom -> Orders, My account, Store info, Logout

    operations portal
        staff           -> My account, Public site, Logout

Logout is not represented as an AccountMenuItem because it is a POST action.
The shared account_menu.html template renders it separately with CSRF
protection.

This module owns identity/context navigation. Primary application navigation
remains owned by storefront, business_portal and ops_portal respectively.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from accounts.roles import AccountRole, Capability, RoleSpec


@dataclass(frozen=True, slots=True)
class AccountMenuItem:
    label: str
    route_name: str
    icon: str = ""

    @property
    def href(self) -> str:
        return reverse(self.route_name)


@dataclass(frozen=True, slots=True)
class AccountMenu:
    label: str
    items: tuple[AccountMenuItem, ...]


MY_ACCOUNT_MENU_ITEM = AccountMenuItem(
    label=_("My account"),
    route_name="accounts:me",
    icon="users",
)

BUSINESS_ORDERS_MENU_ITEM = AccountMenuItem(
    label=_("Orders"),
    route_name="business_portal:orders",
    icon="box",
)

BUSINESS_STORE_INFO_MENU_ITEM = AccountMenuItem(
    label=_("Store info"),
    route_name="business_portal:profile",
    icon="users",
)

OPS_DASHBOARD_MENU_ITEM = AccountMenuItem(
    label=_("Ops dashboard"),
    route_name="ops_dashboard",
    icon="inventory",
)

PUBLIC_SITE_MENU_ITEM = AccountMenuItem(
    label=_("Public site"),
    route_name="storefront:product_list",
    icon="lollipop",
)


def build_storefront_account_menu(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> AccountMenu | None:
    """Build the account menu shown while browsing the public storefront."""

    if role_spec.allows(Capability.VIEW_STAFF_OPS):
        return AccountMenu(
            label=_("Account"),
            items=(
                MY_ACCOUNT_MENU_ITEM,
                OPS_DASHBOARD_MENU_ITEM,
            ),
        )

    if account_role == AccountRole.BUSINESS_CUSTOMER:
        return build_business_account_menu()

    return None


def build_business_account_menu() -> AccountMenu:
    """Build identity navigation for an authenticated business customer."""

    return AccountMenu(
        label=_("Account"),
        items=(
            BUSINESS_ORDERS_MENU_ITEM,
            MY_ACCOUNT_MENU_ITEM,
            BUSINESS_STORE_INFO_MENU_ITEM,
        ),
    )


def build_ops_account_menu() -> AccountMenu:
    """Build identity/context navigation for staff inside the ops portal."""

    return AccountMenu(
        label=_("Account"),
        items=(
            MY_ACCOUNT_MENU_ITEM,
            PUBLIC_SITE_MENU_ITEM,
        ),
    )
