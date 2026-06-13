from __future__ import annotations

from accounts.roles import Capability, RoleSpec
from customers.models import Customer


CAPABILITIES = frozenset(
    {
        Capability.VIEW_CUSTOMERS,
        Capability.CREATE_CUSTOMERS,
        Capability.EDIT_CUSTOMERS,
    }
)


VIEW_CAPABILITIES = {
    "customers:index": Capability.VIEW_CUSTOMERS,
    "customers:detail": Capability.VIEW_CUSTOMERS,
    "customers:create": Capability.CREATE_CUSTOMERS,
    "customers:edit": Capability.EDIT_CUSTOMERS,
}


def can_create_customer(*, role_spec: RoleSpec) -> bool:
    return role_spec.allows(Capability.CREATE_CUSTOMERS)


def can_edit_customer(
    *,
    customer: Customer,
    role_spec: RoleSpec,
) -> bool:
    return role_spec.allows(Capability.EDIT_CUSTOMERS)
