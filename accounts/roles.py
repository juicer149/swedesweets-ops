"""
Account roles and capabilities.

This module answers:

    What can this account role do?

It also owns stable role metadata such as labels and sort ranks. It should not
know about Django User objects, StaffAccount rows or CustomerMembership rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from django.utils.translation import gettext_lazy as _


class Capability(StrEnum):
    VIEW_STAFF_OPS = "can_view_staff_ops"
    VIEW_CUSTOMER_PORTAL = "can_view_customer_portal"

    MANAGE_ACCOUNTS = "can_manage_accounts"
    VIEW_OWN_ACCOUNT = "can_view_own_account"
    EDIT_OWN_ACCOUNT = "can_edit_own_account"

    # Orders
    VIEW_ORDERS = "can_view_orders"
    CREATE_ORDERS = "can_create_orders"
    EDIT_ORDERS = "can_edit_orders"
    CANCEL_ORDERS = "can_cancel_orders"
    PACK_ORDERS = "can_pack_orders"
    DELIVER_ORDERS = "can_deliver_orders"

    # Inventory
    VIEW_INVENTORY = "can_view_inventory"
    CREATE_BATCHES = "can_create_batches"
    EDIT_BATCHES = "can_edit_batches"
    CLOSE_BATCHES = "can_close_batches"
    VIEW_INVENTORY_RISKS = "can_view_inventory_risks"

    # Ops products
    VIEW_OPS_PRODUCTS = "can_view_ops_products"
    CREATE_PRODUCTS = "can_create_products"
    EDIT_PRODUCTS = "can_edit_products"

    # Customers
    VIEW_CUSTOMERS = "can_view_customers"
    CREATE_CUSTOMERS = "can_create_customers"
    EDIT_CUSTOMERS = "can_edit_customers"

    # Customer portal
    PLACE_CUSTOMER_ORDERS = "can_place_customer_orders"
    VIEW_OWN_ORDERS = "can_view_own_orders"


class StaffAccessLevel(StrEnum):
    RESTRICTED = "restricted"
    FULL = "full"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.RESTRICTED.value, _("Restricted")),
            (cls.FULL.value, _("Full")),
        ]


class AccountRole(StrEnum):
    OWNER = "owner"
    FULL_STAFF = "full_staff"
    RESTRICTED_STAFF = "restricted_staff"
    CUSTOMER = "customer"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RoleSpec:
    capabilities: frozenset[Capability]

    def allows(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def allows_any(self, capabilities: frozenset[Capability]) -> bool:
        return bool(self.capabilities & capabilities)

    def allows_all(self, capabilities: frozenset[Capability]) -> bool:
        return capabilities <= self.capabilities


STAFF_CAPABILITIES = frozenset(
    {
        Capability.VIEW_STAFF_OPS,
        Capability.MANAGE_ACCOUNTS,
        Capability.VIEW_OWN_ACCOUNT,

        Capability.VIEW_ORDERS,
        Capability.CREATE_ORDERS,
        Capability.EDIT_ORDERS,
        Capability.CANCEL_ORDERS,
        Capability.PACK_ORDERS,
        Capability.DELIVER_ORDERS,

        Capability.VIEW_INVENTORY,
        Capability.CREATE_BATCHES,
        Capability.EDIT_BATCHES,
        Capability.CLOSE_BATCHES,
        Capability.VIEW_INVENTORY_RISKS,

        Capability.VIEW_OPS_PRODUCTS,
        Capability.CREATE_PRODUCTS,
        Capability.EDIT_PRODUCTS,

        Capability.VIEW_CUSTOMERS,
        Capability.CREATE_CUSTOMERS,
        Capability.EDIT_CUSTOMERS,
    }
)

RESTRICTED_STAFF_CAPABILITIES = frozenset(
    {
        Capability.VIEW_STAFF_OPS,
        Capability.VIEW_OWN_ACCOUNT,
        Capability.EDIT_OWN_ACCOUNT,

        Capability.VIEW_ORDERS,
        Capability.PACK_ORDERS,
        Capability.DELIVER_ORDERS,

        Capability.VIEW_INVENTORY,
        Capability.CREATE_BATCHES,

        Capability.VIEW_OPS_PRODUCTS,
        Capability.VIEW_CUSTOMERS,
    }
)

CUSTOMER_CAPABILITIES = frozenset(
    {
        Capability.VIEW_CUSTOMER_PORTAL,
        Capability.VIEW_OWN_ACCOUNT,
        Capability.EDIT_OWN_ACCOUNT,
        Capability.PLACE_CUSTOMER_ORDERS,
        Capability.VIEW_OWN_ORDERS,
    }
)


OWNER_SPEC = RoleSpec(
    capabilities=STAFF_CAPABILITIES,
)

FULL_STAFF_SPEC = RoleSpec(
    capabilities=STAFF_CAPABILITIES,
)

RESTRICTED_STAFF_SPEC = RoleSpec(
    capabilities=RESTRICTED_STAFF_CAPABILITIES,
)

CUSTOMER_SPEC = RoleSpec(
    capabilities=CUSTOMER_CAPABILITIES,
)

UNKNOWN_SPEC = RoleSpec(
    capabilities=frozenset(),
)


ROLE_SPECS: dict[AccountRole, RoleSpec] = {
    AccountRole.OWNER: OWNER_SPEC,
    AccountRole.FULL_STAFF: FULL_STAFF_SPEC,
    AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_SPEC,
    AccountRole.CUSTOMER: CUSTOMER_SPEC,
    AccountRole.UNKNOWN: UNKNOWN_SPEC,
}


ROLE_LABELS: dict[AccountRole, str] = {
    AccountRole.OWNER: _("Owner"),
    AccountRole.FULL_STAFF: _("Full staff"),
    AccountRole.RESTRICTED_STAFF: _("Restricted staff"),
    AccountRole.CUSTOMER: _("Customer"),
    AccountRole.UNKNOWN: _("Unlinked"),
}


ROLE_RANKS: dict[AccountRole, int] = {
    AccountRole.OWNER: 0,
    AccountRole.FULL_STAFF: 1,
    AccountRole.RESTRICTED_STAFF: 2,
    AccountRole.CUSTOMER: 3,
    AccountRole.UNKNOWN: 4,
}


STAFF_ACCESS_LEVEL_LABELS: dict[StaffAccessLevel, str] = {
    StaffAccessLevel.RESTRICTED: _("Restricted access"),
    StaffAccessLevel.FULL: _("Full access"),
}


def get_role_spec(role: AccountRole) -> RoleSpec:
    return ROLE_SPECS[role]


def get_role_label(role: AccountRole) -> str:
    return ROLE_LABELS.get(role, _("Unknown"))


def get_role_rank(role: AccountRole) -> int:
    return ROLE_RANKS.get(role, 99)


def get_staff_access_level_label(access_level: StaffAccessLevel | str) -> str:
    try:
        normalized_access_level = StaffAccessLevel(access_level)
    except ValueError:
        return _("Unknown access")

    return STAFF_ACCESS_LEVEL_LABELS.get(
        normalized_access_level,
        _("Unknown access"),
    )
