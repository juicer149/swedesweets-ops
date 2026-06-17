from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from inventory.selectors import orderable_quantity_by_product_id
from orders.models import Order
from products.models import Product


@dataclass(frozen=True)
class ProductChoiceContext:
    queryset: Any
    available_units_by_product_id: dict[int, int]


def build_product_choice_context(*, order: Order | None = None) -> ProductChoiceContext:
    available_units = orderable_quantity_by_product_id()
    existing_product_ids = set()

    if order is not None:
        existing_product_ids = set(
            order.lines.values_list("product_id", flat=True)
        )

    if order is not None and order.status != Order.Status.DRAFT:
        for line in order.lines.all():
            available_units[line.product_id] = (
                available_units.get(line.product_id, 0)
                + line.quantity_in_units
            )

    orderable_product_ids = {
        product_id
        for product_id, quantity in available_units.items()
        if quantity > 0
    }

    allowed_product_ids = orderable_product_ids | existing_product_ids

    if not allowed_product_ids:
        queryset = Product.objects.none()
    else:
        queryset = (
            Product.objects
            .filter(
                Q(active=True)
                | Q(id__in=existing_product_ids),
                id__in=allowed_product_ids,
            )
            .order_by(
                "internal_number",
                "brand",
                "name",
                "weight_per_unit",
            )
        )

    return ProductChoiceContext(
        queryset=queryset,
        available_units_by_product_id=available_units,
    )
