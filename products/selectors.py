from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Max, QuerySet, Sum

from common.table_tools import normalize_sort
from orders.models import Order, OrderLine
from products.models import Product


PRODUCT_FILTER_ALL = ""
PRODUCT_FILTER_ACTIVE = "active"
PRODUCT_FILTER_INACTIVE = "inactive"

DEFAULT_PRODUCT_SORT = "number"

PRODUCT_SORTS: dict[str, tuple[str, ...]] = {
    "number": ("internal_number", "brand", "name", "weight_per_box", "sku"),
    "-number": ("-internal_number", "brand", "name", "weight_per_box", "sku"),
    "product": ("name", "brand", "weight_per_box", "sku"),
    "-product": ("-name", "brand", "weight_per_box", "sku"),
    "brand": ("brand", "name", "weight_per_box", "sku"),
    "-brand": ("-brand", "name", "weight_per_box", "sku"),
    "manufacturer": ("manufacturer", "brand", "name", "sku"),
    "-manufacturer": ("-manufacturer", "brand", "name", "sku"),
    "sku": ("sku",),
    "-sku": ("-sku",),
    "weight": ("weight_per_box", "brand", "name", "sku"),
    "-weight": ("-weight_per_box", "brand", "name", "sku"),
    "status": ("active", "brand", "name", "weight_per_box"),
    "-status": ("-active", "brand", "name", "weight_per_box"),
    "vegan": ("-vegan", "brand", "name", "sku"),
    "-vegan": ("vegan", "brand", "name", "sku"),
}


@dataclass(frozen=True)
class ProductDeliveredDemandSummary:
    delivered_order_count: int
    delivered_boxes: int
    average_boxes_per_delivered_order: Decimal
    last_delivered_at: datetime | None

    @classmethod
    def empty(cls) -> ProductDeliveredDemandSummary:
        return cls(
            delivered_order_count=0,
            delivered_boxes=0,
            average_boxes_per_delivered_order=Decimal("0.0"),
            last_delivered_at=None,
        )


def get_product_by_sku(*, sku: str) -> Product:
    return Product.objects.get(sku=sku.strip().upper())


def list_products(
    *,
    status: str | None = None,
    sort: str | None = None,
) -> QuerySet[Product]:
    normalized_sort = normalize_sort(
        sort,
        allowed_sorts=PRODUCT_SORTS,
        default_sort=DEFAULT_PRODUCT_SORT,
    )

    products = Product.objects.select_related("profile")

    if status == PRODUCT_FILTER_ACTIVE:
        products = products.filter(active=True)

    if status == PRODUCT_FILTER_INACTIVE:
        products = products.filter(active=False)

    return products.order_by(*PRODUCT_SORTS[normalized_sort])


def get_product_delivered_demand_summary(
    *,
    product: Product,
) -> ProductDeliveredDemandSummary:
    stats = (
        OrderLine.objects
        .filter(
            product=product,
            order__status=Order.Status.DELIVERED,
        )
        .aggregate(
            delivered_order_count=Count("order_id", distinct=True),
            delivered_boxes=Sum("quantity_in_boxes"),
            last_delivered_at=Max("order__delivered_at"),
        )
    )

    delivered_order_count = stats["delivered_order_count"] or 0
    delivered_boxes = stats["delivered_boxes"] or 0

    if delivered_order_count == 0:
        average = Decimal("0.0")
    else:
        average = (
            Decimal(delivered_boxes) / Decimal(delivered_order_count)
        ).quantize(Decimal("0.1"))

    return ProductDeliveredDemandSummary(
        delivered_order_count=delivered_order_count,
        delivered_boxes=delivered_boxes,
        average_boxes_per_delivered_order=average,
        last_delivered_at=stats["last_delivered_at"],
    )
