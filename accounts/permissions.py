from __future__ import annotations

from django.core.exceptions import PermissionDenied

from accounts.errors import InvalidAccountIdentity
from accounts.roles import (
    AccountRole,
    Capability,
    StaffAccessLevel,
    get_role_spec,
)


def resolve_account_role(user) -> AccountRole:
    if not user.is_authenticated:
        return AccountRole.UNKNOWN

    if user.is_superuser:
        return AccountRole.OWNER

    has_staff_account = hasattr(user, "staff_account")
    has_customer_membership = hasattr(user, "customer_membership")

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


def require_capability(request, capability: Capability) -> None:
    role_spec = getattr(request, "role_spec", None)

    if role_spec is None:
        role_spec = resolve_role_spec(request.user)

    if not role_spec.allows(capability):
        raise PermissionDenied("You do not have permission to access this page.")
