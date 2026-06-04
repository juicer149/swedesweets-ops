from __future__ import annotations

from django.core.exceptions import PermissionDenied

from accounts.errors import InvalidAccountIdentity
from accounts.roles import (
    AccountRole,
    StaffAccessLevel,
    get_role_spec,
)


def resolve_account_role(user) -> AccountRole:
    if not user.is_authenticated:
        return AccountRole.UNKNOWN

    if user.is_superuser:
        return AccountRole.OWNER

    has_staff_account = hasattr(user, "staff_account")
    has_customer_membership = user.customer_memberships.exists()

    if has_staff_account and has_customer_membership:
        raise InvalidAccountIdentity(
            "A user cannot be linked to both staff and customer profiles."
        )

    if has_staff_account:
        access_level = user.staff_account.access_level

        if access_level == StaffAccessLevel.FULL:
            return AccountRole.FULL_STAFF

        if access_level == StaffAccessLevel.RESTRICTED:
            return AccountRole.RESTRICTED_STAFF

        raise InvalidAccountIdentity(
            f"Unknown staff access level: {access_level!r}"
        )

    if has_customer_membership:
        return AccountRole.CUSTOMER

    return AccountRole.UNKNOWN


def resolve_role_spec(user):
    return get_role_spec(resolve_account_role(user))


def require_capability(request, capability: str) -> None:
    role_spec = getattr(request, "role_spec", None)

    if role_spec is None:
        role_spec = resolve_role_spec(request.user)

    if not getattr(role_spec, capability):
        raise PermissionDenied("You do not have permission to access this page.")


def require_can_view_staff_ops(request) -> None:
    require_capability(request, "can_view_staff_ops")


def require_can_view_customer_portal(request) -> None:
    require_capability(request, "can_view_customer_portal")


def require_can_manage_accounts(request) -> None:
    require_capability(request, "can_manage_accounts")


def require_can_view_orders(request) -> None:
    require_capability(request, "can_view_orders")


def require_can_create_orders(request) -> None:
    require_capability(request, "can_create_orders")


def require_can_edit_orders(request) -> None:
    require_capability(request, "can_edit_orders")


def require_can_cancel_orders(request) -> None:
    require_capability(request, "can_cancel_orders")


def require_can_pack_orders(request) -> None:
    require_capability(request, "can_pack_orders")


def require_can_deliver_orders(request) -> None:
    require_capability(request, "can_deliver_orders")


def require_can_view_inventory(request) -> None:
    require_capability(request, "can_view_inventory")


def require_can_create_batches(request) -> None:
    require_capability(request, "can_create_batches")


def require_can_edit_batches(request) -> None:
    require_capability(request, "can_edit_batches")


def require_can_close_batches(request) -> None:
    require_capability(request, "can_close_batches")


def require_can_view_inventory_risks(request) -> None:
    require_capability(request, "can_view_inventory_risks")


def require_can_view_ops_products(request) -> None:
    require_capability(request, "can_view_ops_products")


def require_can_create_products(request) -> None:
    require_capability(request, "can_create_products")


def require_can_edit_products(request) -> None:
    require_capability(request, "can_edit_products")


def require_can_view_customers(request) -> None:
    require_capability(request, "can_view_customers")


def require_can_create_customers(request) -> None:
    require_capability(request, "can_create_customers")


def require_can_edit_customers(request) -> None:
    require_capability(request, "can_edit_customers")


def require_can_place_customer_orders(request) -> None:
    require_capability(request, "can_place_customer_orders")


def require_can_view_own_orders(request) -> None:
    require_capability(request, "can_view_own_orders")
