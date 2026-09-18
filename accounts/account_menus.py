"""
Identity menus for shared navbar account slots.

The account slot is shared presentation. Its contents depend on both
identity and the current application zone.

Logout is deliberately not represented as an AccountMenuItem because it is
a POST action. includes/account_menu.html renders it separately with CSRF
protection.
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

BUSINESS_ACCOUNT_MENU_ITEM = AccountMenuItem(
    label=_("My account"),
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
    """Build the identity menu while browsing the public storefront."""

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
    """Build the identity menu inside the business sales channel.

    The business account area will become the single entry point for
    account identity, store information and order history. Until that
    account area is migrated, the existing profile route remains the
    stable destination.
    """

    return AccountMenu(
        label=_("Account"),
        items=(
            BUSINESS_ACCOUNT_MENU_ITEM,
        ),
    )


def build_ops_account_menu() -> AccountMenu:
    """Build identity/context navigation inside the operations portal."""

    return AccountMenu(
        label=_("Account"),
        items=(
            MY_ACCOUNT_MENU_ITEM,
            PUBLIC_SITE_MENU_ITEM,
        ),
    )
