from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from inventory.selectors import available_boxes_by_product_id
from orders.models import Order
from products.models import Product


@dataclass(frozen=True)
class ProductChoiceContext:
    queryset: Any
    available_boxes_by_product_id: dict[int, int]


def build_product_choice_context(*, order: Order | None = None) -> ProductChoiceContext:
    available_boxes = available_boxes_by_product_id()

    if order is not None:
        for line in order.lines.all():
            available_boxes[line.product_id] = (
                available_boxes.get(line.product_id, 0)
                + line.quantity_in_boxes
            )

    orderable_product_ids = {
        product_id
        for product_id, boxes in available_boxes.items()
        if boxes > 0
    }

    existing_product_ids = set()

    if order is not None:
        existing_product_ids = set(
            order.lines.values_list("product_id", flat=True)
        )

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
                "weight_per_box",
            )
        )

    return ProductChoiceContext(
        queryset=queryset,
        available_boxes_by_product_id=available_boxes,
    )
