from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from business.models import BusinessOfferSelection
from business.selectors import list_business_catalog_products
from business.services import add_catalog_offer_to_draft_order
from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from customers.models import Customer
from orders.errors import InvalidOrderOperation
from orders.models import Order, OrderLine
from products.models import Product


class RepeatOrderSkipReason(StrEnum):
    PRODUCT_UNAVAILABLE = "product_unavailable"
    OFFER_UNAVAILABLE = "offer_unavailable"
    QUANTITY_UNAVAILABLE = "quantity_unavailable"
    COULD_NOT_ADD = "could_not_add"


@dataclass(frozen=True, slots=True)
class RepeatOrderSkippedLine:
    product: Product
    quantity: int
    reason: RepeatOrderSkipReason


@dataclass(frozen=True, slots=True)
class RepeatOrderResult:
    draft_order: Order | None
    added_count: int
    skipped: tuple[RepeatOrderSkippedLine, ...]

    @property
    def has_added_lines(self) -> bool:
        return self.added_count > 0


def repeat_order_into_draft(
    *,
    customer: Customer,
    source_order: Order,
    user=None,
) -> RepeatOrderResult:
    """Copy currently valid selections from one historical order into a draft.

    Each source line is treated independently. A line that can no longer be
    ordered is skipped without rolling back lines that were successfully added.

    Standard and legacy lines use today's standard business offer. Explicit
    non-standard offers retain their CommercialPrice identity and are skipped
    if that offer no longer exists.
    """

    _require_repeatable_order(
        customer=customer,
        source_order=source_order,
    )

    catalog_by_product_id = {
        catalog_product.product.id: catalog_product
        for catalog_product in list_business_catalog_products()
    }

    source_lines = tuple(
        source_order.lines
        .select_related(
            "product",
            "business_offer_selection__commercial_price",
        )
        .order_by("id")
    )

    draft_order: Order | None = None
    added_count = 0
    skipped: list[RepeatOrderSkippedLine] = []

    for line in source_lines:
        catalog_product = catalog_by_product_id.get(
            line.product_id
        )

        if catalog_product is None:
            skipped.append(
                _skipped(
                    line=line,
                    reason=(
                        RepeatOrderSkipReason.PRODUCT_UNAVAILABLE
                    ),
                )
            )
            continue

        offer = _resolve_repeat_offer(
            line=line,
            catalog_product=catalog_product,
        )

        if offer is None:
            skipped.append(
                _skipped(
                    line=line,
                    reason=(
                        RepeatOrderSkipReason.OFFER_UNAVAILABLE
                    ),
                )
            )
            continue

        quantity = line.quantity_in_units

        if quantity > offer.available_units:
            skipped.append(
                _skipped(
                    line=line,
                    reason=(
                        RepeatOrderSkipReason.QUANTITY_UNAVAILABLE
                    ),
                )
            )
            continue

        try:
            draft_order = add_catalog_offer_to_draft_order(
                customer=customer,
                product=line.product,
                commercial_price_id=(
                    offer.commercial_price_id
                ),
                quantity=quantity,
                user=user,
            )
        except InvalidOrderOperation:
            skipped.append(
                _skipped(
                    line=line,
                    reason=RepeatOrderSkipReason.COULD_NOT_ADD,
                )
            )
            continue

        added_count += 1

    return RepeatOrderResult(
        draft_order=draft_order,
        added_count=added_count,
        skipped=tuple(skipped),
    )


def _require_repeatable_order(
    *,
    customer: Customer,
    source_order: Order,
) -> None:
    if (
        source_order.channel
        != Order.Channel.BUSINESS
    ):
        raise InvalidOrderOperation(
            "order is not a business order"
        )

    if source_order.customer_id != customer.id:
        raise InvalidOrderOperation(
            "order does not belong to the current customer"
        )

    if source_order.status == Order.Status.DRAFT:
        raise InvalidOrderOperation(
            "draft orders cannot be repeated"
        )


def _resolve_repeat_offer(
    *,
    line: OrderLine,
    catalog_product: CatalogProduct,
) -> CatalogOffer | None:
    try:
        selection = line.business_offer_selection
    except BusinessOfferSelection.DoesNotExist:
        return _standard_offer(
            catalog_product
        )

    if selection.commercial_price_id is None:
        return _standard_offer(
            catalog_product
        )

    for offer in catalog_product.offers:
        if (
            offer.commercial_price_id
            == selection.commercial_price_id
        ):
            return offer

    return None


def _standard_offer(
    catalog_product: CatalogProduct,
) -> CatalogOffer | None:
    for offer in catalog_product.offers:
        if offer.kind == CatalogOfferKind.STANDARD:
            return offer

    return None


def _skipped(
    *,
    line: OrderLine,
    reason: RepeatOrderSkipReason,
) -> RepeatOrderSkippedLine:
    return RepeatOrderSkippedLine(
        product=line.product,
        quantity=line.quantity_in_units,
        reason=reason,
    )
