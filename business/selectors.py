from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

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

    Gates, in order:

        Product.active            global product status
        offer.enabled             business channel availability
        available units > 0       reservation-adjusted stock
        business price policy     standard offer: price optional
                                  batch offer: EUR price required

    Every active catalog product must have a persistent product-level BUSINESS
    CommercialPrice. That row is the standard offer's durable identity.

    An enabled standard offer may be unpriced. Missing price therefore does
    not remove the standard offer; only its displayed price is absent.

    A disabled standard offer removes the standard selection from the
    business channel, but valid batch-specific BUSINESS offers may still make
    the product orderable.

    Enabled batch-specific BUSINESS offers with an EUR amount become explicit
    offers and their stock is removed from the standard pool, so the same
    units are not represented by two selectable offers. A batch offer that is
    not orderable (disabled or unpriced) leaves its batch in the standard
    pool.

    A missing standard BUSINESS offer is an invalid catalog configuration.
    Synthetic standard offers are no longer created.
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
        ).filter(
            product_id__in=candidate_product_ids,
        )
    )

    standard_offer_by_product_id: dict[
        int,
        CommercialPrice,
    ] = {}

    batch_price_candidates: list[
        tuple[CommercialPrice, PriceAmount]
    ] = []

    for commercial_price in commercial_prices:
        if commercial_price.batch_id is None:
            standard_offer_by_product_id[
                commercial_price.product_id
            ] = commercial_price
            continue

        if not commercial_price.enabled:
            continue

        amount = _find_amount(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )

        if amount is None:
            continue

        batch_price_candidates.append(
            (
                commercial_price,
                amount,
            )
        )

    missing_standard_offer_products = [
        product
        for product in products
        if product.id not in standard_offer_by_product_id
    ]

    if missing_standard_offer_products:
        missing_products = ", ".join(
            product.display_name
            for product in missing_standard_offer_products
        )

        raise RuntimeError(
            "business catalog invariant violated: "
            "missing standard BUSINESS offer for "
            f"{missing_products}"
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

        standard_offer = (
            standard_offer_by_product_id[
                product.id
            ]
        )

        offers: list[CatalogOffer] = []

        if (
            standard_available_units > 0
            and standard_offer.enabled
        ):
            offers.append(
                _build_standard_offer(
                    available_units=(
                        standard_available_units
                    ),
                    standard_offer=standard_offer,
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


def get_business_catalog_product(
    *,
    product_id: int,
) -> CatalogProduct | None:
    """Return one currently orderable product from the Business catalog.

    Reuse the same catalog construction as the list view so product detail
    cannot drift from catalog offer and stock semantics.
    """

    for catalog_product in list_business_catalog_products():
        if catalog_product.product.id == product_id:
            return catalog_product

    return None


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
    """Return one currently orderable legacy business catalog entry."""

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


def _build_standard_offer(
    *,
    available_units: int,
    standard_offer: CommercialPrice,
) -> CatalogOffer:
    amount = _find_amount(
        commercial_price=standard_offer,
        currency=PriceAmount.Currency.EUR,
    )

    return CatalogOffer(
        kind=CatalogOfferKind.STANDARD,
        commercial_price_id=standard_offer.pk,
        batch_id=None,
        reason=None,
        price=(
            amount.price
            if amount is not None
            else None
        ),
        currency=PriceAmount.Currency.EUR,
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
