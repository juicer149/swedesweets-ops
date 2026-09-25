from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Q, QuerySet

from business.selectors import list_business_catalog_products
from orders.models import Order
from pricing.models import CommercialPrice, PriceAmount
from pricing.selectors import list_commercial_prices


@dataclass(frozen=True, slots=True)
class BusinessOfferChoiceContext:
    """Selectable BUSINESS offers and their order-adjusted availability."""

    queryset: QuerySet[CommercialPrice]
    available_units_by_offer_id: dict[int, int]


def build_business_offer_choice_context(
    *,
    order: Order | None = None,
) -> BusinessOfferChoiceContext:
    """Build offer choices for BUSINESS order creation or editing.

    New choices come from the current BUSINESS catalog.

    When editing a placed order, each still-commercially-valid existing
    offer gets the order's own quantity added back because current catalog
    availability already subtracts that reservation.
    """

    available_units_by_offer_id: dict[int, int] = {}
    selectable_offer_ids: set[int] = set()

    for catalog_product in list_business_catalog_products():
        for offer in catalog_product.offers:
            selectable_offer_ids.add(
                offer.commercial_price_id
            )
            available_units_by_offer_id[
                offer.commercial_price_id
            ] = offer.available_units

    if (
        order is not None
        and order.status != Order.Status.DRAFT
    ):
        existing_quantity_by_offer_id: dict[int, int] = (
            defaultdict(int)
        )

        for (
            offer_id,
            quantity,
        ) in order.lines.values_list(
            "commercial_offer_id",
            "quantity_in_units",
        ):
            existing_quantity_by_offer_id[
                offer_id
            ] += quantity

        eligible_existing_offer_ids = (
            _commercially_eligible_business_offer_ids(
                offer_ids=set(
                    existing_quantity_by_offer_id
                ),
            )
        )

        for offer_id in eligible_existing_offer_ids:
            selectable_offer_ids.add(
                offer_id
            )
            available_units_by_offer_id[
                offer_id
            ] = (
                available_units_by_offer_id.get(
                    offer_id,
                    0,
                )
                + existing_quantity_by_offer_id[
                    offer_id
                ]
            )

    if not selectable_offer_ids:
        queryset = CommercialPrice.objects.none()
    else:
        queryset = (
            list_commercial_prices(
                channels=[
                    CommercialPrice.Channel.BUSINESS,
                ],
                enabled_only=True,
            )
            .filter(
                pk__in=selectable_offer_ids,
            )
            .order_by(
                "product__internal_number",
                "product__brand",
                "product__name",
                "product_id",
                "batch_id",
                "id",
            )
        )

    return BusinessOfferChoiceContext(
        queryset=queryset,
        available_units_by_offer_id=(
            available_units_by_offer_id
        ),
    )


def _commercially_eligible_business_offer_ids(
    *,
    offer_ids: set[int],
) -> set[int]:
    """Return existing offers that remain valid BUSINESS selections.

    Physical availability is deliberately not checked here. An existing
    placed-order reservation may itself be the reason current free
    availability is zero.
    """

    if not offer_ids:
        return set()

    return set(
        CommercialPrice.objects
        .filter(
            pk__in=offer_ids,
            channel=CommercialPrice.Channel.BUSINESS,
            enabled=True,
            product__active=True,
        )
        .filter(
            Q(batch__isnull=True)
            | Q(
                amounts__currency=(
                    PriceAmount.Currency.EUR
                )
            )
        )
        .values_list(
            "pk",
            flat=True,
        )
        .distinct()
    )
