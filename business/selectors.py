from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch

from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from inventory.selectors import (
    orderable_quantity_by_batch_pk,
    orderable_quantity_by_product_id,
)
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)
from pricing.selectors import (
    list_commercial_prices,
)
from products.models import (
    Product,
    ProductTranslation,
)


@dataclass(frozen=True, slots=True)
class BusinessCatalogEntry:
    """Legacy product-level business catalog entry.

    Retained while the business portal migrates to the shared catalog
    contracts.
    """

    product: Product
    available_units: int


def list_business_catalog_products(
) -> tuple[CatalogProduct, ...]:
    """Return the business catalog as shared product/offer contracts.

    Business policy currently allows ordinary product ordering without a
    configured price.

    Enabled batch-specific BUSINESS prices with an EUR amount become explicit
    offers and their physical stock is removed from the ordinary standard
    pool, so the same units are not represented by two selectable offers.
    """

    available_units_by_product_id = (
        orderable_quantity_by_product_id()
    )

    candidate_product_ids = {
        product_id
        for product_id, available_units
        in available_units_by_product_id.items()
        if available_units > 0
    }

    if not candidate_product_ids:
        return ()

    products = tuple(
        _list_catalog_products(
            product_ids=candidate_product_ids,
        )
    )

    if not products:
        return ()

    commercial_prices = tuple(
        list_commercial_prices(
            channels=[
                CommercialPrice.Channel.BUSINESS,
            ],
            enabled_only=True,
        ).filter(
            product_id__in=candidate_product_ids,
        )
    )

    product_price_by_product_id: dict[
        int,
        tuple[CommercialPrice, PriceAmount],
    ] = {}

    batch_price_candidates: list[
        tuple[CommercialPrice, PriceAmount]
    ] = []

    for commercial_price in commercial_prices:
        amount = _find_amount(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )

        if amount is None:
            continue

        if commercial_price.batch_id is None:
            product_price_by_product_id[
                commercial_price.product_id
            ] = (
                commercial_price,
                amount,
            )
            continue

        batch_price_candidates.append(
            (
                commercial_price,
                amount,
            )
        )

    available_units_by_batch_pk = (
        orderable_quantity_by_batch_pk(
            batch_pks=(
                commercial_price.batch_id
                for commercial_price, _
                in batch_price_candidates
                if commercial_price.batch_id is not None
            ),
        )
    )

    batch_offers_by_product_id: dict[
        int,
        list[CatalogOffer],
    ] = defaultdict(list)

    batch_offer_units_by_product_id: dict[
        int,
        int,
    ] = defaultdict(int)

    for commercial_price, amount in batch_price_candidates:
        batch_id = commercial_price.batch_id

        if batch_id is None:
            continue

        available_units = (
            available_units_by_batch_pk.get(
                batch_id,
                0,
            )
        )

        if available_units <= 0:
            continue

        offer = CatalogOffer(
            kind=CatalogOfferKind.BATCH,
            commercial_price_id=commercial_price.pk,
            batch_id=batch_id,
            reason=(
                commercial_price.reason
                or None
            ),
            price=amount.price,
            currency=amount.currency,
            available_units=available_units,
        )

        batch_offers_by_product_id[
            commercial_price.product_id
        ].append(
            offer
        )

        batch_offer_units_by_product_id[
            commercial_price.product_id
        ] += available_units

    catalog_products: list[CatalogProduct] = []

    for product in products:
        total_available_units = (
            available_units_by_product_id.get(
                product.id,
                0,
            )
        )

        batch_offers = tuple(
            batch_offers_by_product_id.get(
                product.id,
                (),
            )
        )

        batch_offer_units = (
            batch_offer_units_by_product_id.get(
                product.id,
                0,
            )
        )

        standard_available_units = max(
            total_available_units
            - batch_offer_units,
            0,
        )

        offers: list[CatalogOffer] = []

        if standard_available_units > 0:
            offers.append(
                _build_standard_offer(
                    product=product,
                    available_units=(
                        standard_available_units
                    ),
                    product_price=(
                        product_price_by_product_id.get(
                            product.id
                        )
                    ),
                )
            )

        offers.extend(
            batch_offers
        )

        if not offers:
            continue

        catalog_products.append(
            CatalogProduct(
                product=product,
                available_units=(
                    total_available_units
                ),
                offers=tuple(
                    offers
                ),
            )
        )

    return tuple(
        catalog_products
    )


def list_business_catalog_entries(
) -> tuple[BusinessCatalogEntry, ...]:
    """Return active products with positive ordinary business stock.

    This legacy selector remains available while business catalog presentation
    migrates to `list_business_catalog_products`.
    """

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

    products = _list_catalog_products(
        product_ids=orderable_product_ids,
    )

    return tuple(
        BusinessCatalogEntry(
            product=product,
            available_units=(
                available_units_by_product_id[
                    product.id
                ]
            ),
        )
        for product in products
    )


def get_business_catalog_entry(
    *,
    product_id: int,
) -> BusinessCatalogEntry | None:
    """Return one currently orderable business catalog entry."""

    available_units_by_product_id = (
        orderable_quantity_by_product_id()
    )

    available_units = (
        available_units_by_product_id.get(
            product_id,
            0,
        )
    )

    if available_units <= 0:
        return None

    product = (
        _list_catalog_products(
            product_ids={
                product_id,
            },
        )
        .first()
    )

    if product is None:
        return None

    return BusinessCatalogEntry(
        product=product,
        available_units=available_units,
    )


def _list_catalog_products(
    *,
    product_ids,
):
    return (
        Product.objects
        .filter(
            active=True,
            id__in=product_ids,
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


def _build_standard_offer(
    *,
    product: Product,
    available_units: int,
    product_price: (
        tuple[
            CommercialPrice,
            PriceAmount,
        ]
        | None
    ),
) -> CatalogOffer:
    if product_price is None:
        return CatalogOffer(
            kind=CatalogOfferKind.STANDARD,
            commercial_price_id=None,
            batch_id=None,
            reason=None,
            price=None,
            currency=PriceAmount.Currency.EUR,
            available_units=available_units,
        )

    commercial_price, amount = (
        product_price
    )

    return CatalogOffer(
        kind=CatalogOfferKind.STANDARD,
        commercial_price_id=(
            commercial_price.pk
        ),
        batch_id=None,
        reason=None,
        price=amount.price,
        currency=amount.currency,
        available_units=available_units,
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
