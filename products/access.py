from __future__ import annotations

from accounts.roles import Capability, RoleSpec
from products.models import Product

CAPABILITIES = frozenset(
    {
        Capability.VIEW_OPS_PRODUCTS,
        Capability.CREATE_PRODUCTS,
        Capability.EDIT_PRODUCTS,
    }
)


VIEW_CAPABILITIES = {
    "products:index": Capability.VIEW_OPS_PRODUCTS,
    "products:detail": Capability.VIEW_OPS_PRODUCTS,
    "products:create": Capability.CREATE_PRODUCTS,
    "products:edit": Capability.EDIT_PRODUCTS,
}


def can_create_product(*, role_spec: RoleSpec) -> bool:
    return role_spec.allows(Capability.CREATE_PRODUCTS)


def can_edit_product(
    *,
    product: Product,
    role_spec: RoleSpec,
) -> bool:
    return role_spec.allows(Capability.EDIT_PRODUCTS)
