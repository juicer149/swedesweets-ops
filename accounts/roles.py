from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StaffAccessLevel(StrEnum):
    RESTRICTED = "restricted"
    FULL = "full"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.RESTRICTED, "Restricted"),
            (cls.FULL, "Full"),
        ]


class AccountRole(StrEnum):
    OWNER = "owner"
    FULL_STAFF = "full_staff"
    RESTRICTED_STAFF = "restricted_staff"
    CUSTOMER = "customer"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RoleSpec:
    can_view_staff_ops: bool = False
    can_view_customer_portal: bool = False

    can_manage_accounts: bool = False

    can_view_orders: bool = False
    can_create_orders: bool = False
    can_edit_orders: bool = False
    can_cancel_orders: bool = False
    can_pack_orders: bool = False
    can_deliver_orders: bool = False

    can_view_inventory: bool = False
    can_create_batches: bool = False
    can_edit_batches: bool = False
    can_close_batches: bool = False
    can_view_inventory_risks: bool = False

    can_view_ops_products: bool = False
    can_create_products: bool = False
    can_edit_products: bool = False

    can_view_customers: bool = False
    can_create_customers: bool = False
    can_edit_customers: bool = False

    can_place_customer_orders: bool = False
    can_view_own_orders: bool = False


OWNER_SPEC = RoleSpec(
    can_view_staff_ops=True,
    can_manage_accounts=True,
    can_view_orders=True,
    can_create_orders=True,
    can_edit_orders=True,
    can_cancel_orders=True,
    can_pack_orders=True,
    can_deliver_orders=True,
    can_view_inventory=True,
    can_create_batches=True,
    can_edit_batches=True,
    can_close_batches=True,
    can_view_inventory_risks=True,
    can_view_ops_products=True,
    can_create_products=True,
    can_edit_products=True,
    can_view_customers=True,
    can_create_customers=True,
    can_edit_customers=True,
)

FULL_STAFF_SPEC = RoleSpec(
    can_view_staff_ops=True,
    can_manage_accounts=True,
    can_view_orders=True,
    can_create_orders=True,
    can_edit_orders=True,
    can_cancel_orders=True,
    can_pack_orders=True,
    can_deliver_orders=True,
    can_view_inventory=True,
    can_create_batches=True,
    can_edit_batches=True,
    can_close_batches=True,
    can_view_inventory_risks=True,
    can_view_ops_products=True,
    can_create_products=True,
    can_edit_products=True,
    can_view_customers=True,
    can_create_customers=True,
    can_edit_customers=True,
)

RESTRICTED_STAFF_SPEC = RoleSpec(
    can_view_staff_ops=True,
    can_view_orders=True,
    can_pack_orders=True,
    can_deliver_orders=True,
    can_view_inventory=True,
    can_create_batches=True,
    can_view_ops_products=True,
    can_view_customers=True,
)

CUSTOMER_SPEC = RoleSpec(
    can_view_customer_portal=True,
    can_place_customer_orders=True,
    can_view_own_orders=True,
)

UNKNOWN_SPEC = RoleSpec()


ROLE_SPECS: dict[AccountRole, RoleSpec] = {
    AccountRole.OWNER: OWNER_SPEC,
    AccountRole.FULL_STAFF: FULL_STAFF_SPEC,
    AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_SPEC,
    AccountRole.CUSTOMER: CUSTOMER_SPEC,
    AccountRole.UNKNOWN: UNKNOWN_SPEC,
}


def get_role_spec(role: AccountRole) -> RoleSpec:
    return ROLE_SPECS[role]
