from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch

from inventory.selectors import orderable_quantity_by_product_id
from products.models import Product, ProductTranslation


@dataclass(frozen=True, slots=True)
class BusinessCatalogEntry:
    """One product currently orderable through the business channel."""

    product: Product
    available_units: int


def list_business_catalog_entries(
) -> tuple[BusinessCatalogEntry, ...]:
    """Return active products with positive ordinary business stock."""

    available_units_by_product_id = (
        orderable_quantity_by_product_id()
    )

    orderable_product_ids = {
        product_id
        for product_id, quantity
        in available_units_by_product_id.items()
        if quantity > 0
    }

    if not orderable_product_ids:
        return ()

    products = (
        Product.objects
        .filter(
            active=True,
            id__in=orderable_product_ids,
        )
        .prefetch_related(
            Prefetch(
                "translations",
                queryset=ProductTranslation.objects.all(),
                to_attr="prefetched_translations",
            )
        )
        .order_by(
            "internal_number",
            "brand",
            "name",
            "weight_per_unit",
            "sku",
        )
    )

    return tuple(
        BusinessCatalogEntry(
            product=product,
            available_units=(
                available_units_by_product_id[product.id]
            ),
        )
        for product in products
    )
