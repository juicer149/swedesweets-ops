from __future__ import annotations

from collections import defaultdict

from django.db.models import Prefetch

from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import list_commercial_prices
from products.models import Product, ProductTranslation
from retail.selectors import list_batches_for_retail_price


def list_retail_catalog_products() -> tuple[CatalogProduct, ...]:
    """Return the retail catalog as shared product/offer contracts.

    Unlike business ordering, retail has no unpriced standard offer: a
    product only appears here backed by an enabled, EUR-priced
    CommercialPrice with currently sellable stock. This mirrors the same
    requirement `retail/services.py` enforces server-side at checkout time
    (`_get_retail_price_and_amount`), so what the catalog shows and what
    checkout will accept never drift apart.

    Available units per offer come from `list_batches_for_retail_price`,
    which already applies retail's pool-exclusion rule (a product-wide
    price excludes batches that have their own enabled batch-specific
    price) - not from raw product-level stock.
    """

    commercial_prices = tuple(
        list_commercial_prices(
            channels=[
                CommercialPrice.Channel.RETAIL,
            ],
            enabled_only=True,
        )
    )

    if not commercial_prices:
        return ()

    offers_by_product_id: dict[int, list[CatalogOffer]] = defaultdict(list)
    total_available_units_by_product_id: dict[int, int] = defaultdict(int)

    for commercial_price in commercial_prices:
        amount = _find_amount(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )

        if amount is None:
            continue

        available_units = _available_units(
            commercial_price=commercial_price,
            currency=amount.currency,
        )

        if available_units <= 0:
            continue

        offer = CatalogOffer(
            kind=(
                CatalogOfferKind.BATCH
                if commercial_price.batch_id is not None
                else CatalogOfferKind.STANDARD
            ),
            commercial_price_id=commercial_price.pk,
            batch_id=commercial_price.batch_id,
            reason=(
                commercial_price.reason
                or None
            ),
            price=amount.price,
            currency=amount.currency,
            available_units=available_units,
        )

        offers_by_product_id[
            commercial_price.product_id
        ].append(offer)

        total_available_units_by_product_id[
            commercial_price.product_id
        ] += available_units

    if not offers_by_product_id:
        return ()

    products = _list_catalog_products(
        product_ids=offers_by_product_id.keys(),
    )

    catalog_products = [
        CatalogProduct(
            product=product,
            available_units=(
                total_available_units_by_product_id.get(
                    product.id,
                    0,
                )
            ),
            offers=tuple(
                offers_by_product_id.get(
                    product.id,
                    (),
                )
            ),
        )
        for product in products
        if offers_by_product_id.get(product.id)
    ]

    return tuple(catalog_products)


def get_retail_catalog_product(
    *,
    product_id: int,
) -> CatalogProduct | None:
    """Return one currently orderable product from the retail catalog.

    Reuses the same catalog construction as the list view so product detail
    cannot drift from catalog offer and stock semantics.
    """

    for catalog_product in list_retail_catalog_products():
        if catalog_product.product.id == product_id:
            return catalog_product

    return None


def _available_units(
    *,
    commercial_price: CommercialPrice,
    currency: str,
) -> int:
    batches = list_batches_for_retail_price(
        commercial_price=commercial_price,
        currency=currency,
    )

    return sum(
        batch.quantity
        for batch in batches
    )


def _find_amount(
    *,
    commercial_price: CommercialPrice,
    currency: str,
) -> PriceAmount | None:
    for amount in commercial_price.amounts.all():
        if amount.currency == currency:
            return amount

    return None


def _list_catalog_products(
    *,
    product_ids,
):
    # Deliberately mirrors business/selectors.py's private catalog query -
    # active products, profile + translations prefetched, stable sort. Kept
    # as a small local duplication rather than extracting a shared helper,
    # since doing so would touch business/selectors.py (existing code) for
    # a query that is currently only two lines. Worth revisiting under the
    # Rule of Three if a third caller needs the same shape.
    return (
        Product.objects
        .filter(
            active=True,
            id__in=product_ids,
        )
        .select_related(
            "profile",
        )
        .prefetch_related(
            Prefetch(
                "translations",
                queryset=(
                    ProductTranslation.objects.all()
                ),
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
