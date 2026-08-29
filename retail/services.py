from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from orders.datatypes import BuyerInput
from orders.models import Order, OrderLine
from products.models import Product
from retail.models import (
    RetailBatchOffer,
    RetailCheckoutSession,
    RetailOfferSelection,
    RetailProductOffer,
)
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_LINES,
    MAX_RETAIL_ORDER_TOTAL,
    MIN_RETAIL_LINE_QUANTITY,
    RETAIL_PAYMENT_WINDOW,
    is_retail_batch_sellable,
    is_retail_product_sellable,
    is_supported_retail_destination,
)


class InvalidRetailOrder(ValueError):
    """Raised when a retail checkout violates a business invariant."""


@dataclass(frozen=True, slots=True)
class AnonymousBuyerInput:
    first_name: str
    last_name: str
    email: str
    phone_number: str
    country: str
    postal_code: str
    city: str
    address_line: str


@dataclass(frozen=True, slots=True)
class RetailOrderLineInput:
    quantity: int
    product_offer_id: int | None = None
    batch_offer_id: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedRetailOrderLine:
    """Validated retail line with commercial origin resolved server-side."""

    product: Product
    quantity: int
    unit_price: Decimal
    product_offer: RetailProductOffer | None = None
    batch_offer: RetailBatchOffer | None = None

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


def buyer_from_anonymous_retail_input(
    *,
    buyer: AnonymousBuyerInput,
) -> BuyerInput:
    """Adapt anonymous retail input to the channel-agnostic buyer contract."""

    first_name = " ".join(buyer.first_name.strip().split())
    last_name = " ".join(buyer.last_name.strip().split())

    return BuyerInput(
        name=" ".join(part for part in (first_name, last_name) if part),
        email=buyer.email.strip(),
        phone_number=buyer.phone_number.strip(),
        country=buyer.country.strip().upper(),
        postal_code=buyer.postal_code.strip(),
        city=" ".join(buyer.city.strip().split()),
        address_line=" ".join(buyer.address_line.strip().split()),
    )


@transaction.atomic
def create_pending_retail_order(
    *,
    buyer: AnonymousBuyerInput,
    lines: list[RetailOrderLineInput],
) -> RetailCheckoutSession:
    """Start an anonymous retail checkout.

    Every retail line references exactly one commercial offer.

    The offer is resolved server-side into product and price. The generic
    OrderLine stores the durable product, quantity and price snapshot, while
    RetailOfferSelection preserves the retail-specific stock-pool identity.

    Inventory reservation and payment are handled by later workflow slices.
    """

    _validate_buyer_destination(buyer)
    _validate_lines(lines)

    resolved_lines = _resolve_retail_lines(lines=lines)
    _validate_unique_products(lines=resolved_lines)

    total = _calculate_order_total(lines=resolved_lines)

    if total > MAX_RETAIL_ORDER_TOTAL:
        raise InvalidRetailOrder(
            "order total exceeds maximum allowed amount"
        )

    order = Order(
        channel=Order.Channel.RETAIL,
        currency=Order.Currency.EUR,
        customer=None,
        status=Order.Status.DRAFT,
    )
    order.snapshot_buyer(
        buyer=buyer_from_anonymous_retail_input(buyer=buyer),
    )
    order.save()

    for resolved_line in resolved_lines:
        order_line = OrderLine.objects.create(
            order=order,
            product=resolved_line.product,
            quantity=resolved_line.quantity,
            unit=OrderLine.Unit.STOCK_UNIT,
            quantity_in_units=resolved_line.quantity,
            unit_price_snapshot=resolved_line.unit_price,
        )

        RetailOfferSelection.objects.create(
            order_line=order_line,
            product_offer=resolved_line.product_offer,
            batch_offer=resolved_line.batch_offer,
        )

    return RetailCheckoutSession.objects.create(
        order=order,
        expires_at=timezone.now() + RETAIL_PAYMENT_WINDOW,
    )


def _validate_buyer_destination(
    buyer: AnonymousBuyerInput,
) -> None:
    if not is_supported_retail_destination(
        country_code=buyer.country,
        postal_code=buyer.postal_code,
        city=buyer.city,
    ):
        raise InvalidRetailOrder(
            "unsupported retail destination"
        )


def _validate_lines(
    lines: list[RetailOrderLineInput],
) -> None:
    if not lines:
        raise InvalidRetailOrder(
            "order must contain at least one line"
        )

    if len(lines) > MAX_RETAIL_ORDER_LINES:
        raise InvalidRetailOrder(
            "order contains too many lines"
        )

    for line in lines:
        if not (
            MIN_RETAIL_LINE_QUANTITY
            <= line.quantity
            <= MAX_RETAIL_LINE_QUANTITY
        ):
            raise InvalidRetailOrder(
                "invalid retail line quantity"
            )

        has_product_offer = line.product_offer_id is not None
        has_batch_offer = line.batch_offer_id is not None

        if has_product_offer == has_batch_offer:
            raise InvalidRetailOrder(
                "retail line must reference exactly one offer"
            )


def _resolve_retail_lines(
    *,
    lines: list[RetailOrderLineInput],
) -> list[ResolvedRetailOrderLine]:
    return [
        _resolve_retail_line(line=line)
        for line in lines
    ]


def _resolve_retail_line(
    *,
    line: RetailOrderLineInput,
) -> ResolvedRetailOrderLine:
    if line.product_offer_id is not None:
        offer = _get_retail_product_offer(
            offer_id=line.product_offer_id,
        )

        assert offer.price is not None

        return ResolvedRetailOrderLine(
            product=offer.product,
            quantity=line.quantity,
            unit_price=offer.price,
            product_offer=offer,
        )

    assert line.batch_offer_id is not None

    offer = _get_retail_batch_offer(
        offer_id=line.batch_offer_id,
    )

    assert offer.price is not None

    return ResolvedRetailOrderLine(
        product=offer.batch.product,
        quantity=line.quantity,
        unit_price=offer.price,
        batch_offer=offer,
    )


def _validate_unique_products(
    *,
    lines: list[ResolvedRetailOrderLine],
) -> None:
    """Protect the current generic OrderLine product uniqueness invariant.

    Retail may later need multiple lines for the same product when different
    commercial offers are bought together. The current shared OrderLine schema
    cannot represent that yet, so reject it explicitly rather than leaking a
    database IntegrityError.
    """

    product_ids: set[int] = set()

    for line in lines:
        if line.product.pk in product_ids:
            raise InvalidRetailOrder(
                "duplicate retail product lines are not allowed"
            )

        product_ids.add(line.product.pk)


def _calculate_order_total(
    *,
    lines: list[ResolvedRetailOrderLine],
) -> Decimal:
    return sum(
        (line.line_total for line in lines),
        start=Decimal("0.00"),
    )


def _get_retail_product_offer(
    *,
    offer_id: int,
) -> RetailProductOffer:
    try:
        offer = (
            RetailProductOffer.objects
            .select_related("product")
            .get(pk=offer_id)
        )
    except RetailProductOffer.DoesNotExist as exc:
        raise InvalidRetailOrder(
            "product retail offer does not exist"
        ) from exc

    if not is_retail_product_sellable(offer):
        raise InvalidRetailOrder(
            "product is not enabled for retail"
        )

    assert offer.price is not None

    return offer


def _get_retail_batch_offer(
    *,
    offer_id: int,
) -> RetailBatchOffer:
    try:
        offer = (
            RetailBatchOffer.objects
            .select_related("batch__product")
            .get(pk=offer_id)
        )
    except RetailBatchOffer.DoesNotExist as exc:
        raise InvalidRetailOrder(
            "batch retail offer does not exist"
        ) from exc

    if not is_retail_batch_sellable(offer):
        raise InvalidRetailOrder(
            "batch is not enabled for retail"
        )

    assert offer.price is not None

    return offer
