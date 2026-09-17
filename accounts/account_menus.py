"""
Identity menus for the shared site navbar's account slot.

The account slot is one position with three states:

    anonymous       -> no menu, the navbar renders a login button
    business custom -> orders, account, logout
    staff           -> ops dashboard, logout

Logout is not listed as an item: it is a POST form, rendered separately by
includes/account_menu.html.

This lives in accounts because the account slot is identity presentation,
not storefront or portal presentation - every zone that shows a signed-in
user fills the same slot.
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


BUSINESS_ORDERS_MENU_ITEM = AccountMenuItem(
    label=_("Orders"),
    route_name="business_portal:orders",
    icon="box",
)

BUSINESS_ACCOUNT_MENU_ITEM = AccountMenuItem(
    label=_("Account"),
    route_name="business_portal:profile",
    icon="users",
)

OPS_DASHBOARD_MENU_ITEM = AccountMenuItem(
    label=_("Ops dashboard"),
    route_name="ops_dashboard",
    icon="inventory",
)


def build_account_menu(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> AccountMenu | None:
    """Return the account menu for one identity, or None when anonymous.

    Staff is checked before business customer because the two roles are
    mutually exclusive by construction (accounts.permissions rejects a
    user linked to both), and staff browsing the public storefront should
    get their way back to ops.
    """

    if role_spec.allows(Capability.VIEW_STAFF_OPS):
        return AccountMenu(
            label=_("My account"),
            items=(
                OPS_DASHBOARD_MENU_ITEM,
            ),
        )

    if account_role == AccountRole.BUSINESS_CUSTOMER:
        return AccountMenu(
            label=_("My account"),
            items=(
                BUSINESS_ORDERS_MENU_ITEM,
                BUSINESS_ACCOUNT_MENU_ITEM,
            ),
        )

    return None
