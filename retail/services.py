from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from orders.datatypes import BuyerInput
from orders.models import Order, OrderLine
from products.models import Product
from retail.models import (
    RetailCheckoutSession,
    RetailProductOffer,
)
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_LINES,
    MAX_RETAIL_ORDER_TOTAL,
    MIN_RETAIL_LINE_QUANTITY,
    RETAIL_PAYMENT_WINDOW,
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
    product_id: int
    quantity: int


@dataclass(frozen=True, slots=True)
class ResolvedRetailOrderLine:
    """Validated retail line with its server-side price snapshot."""

    product: Product
    quantity: int
    unit_price: Decimal

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

    Retail policy resolves products and prices before persistence.

    The channel-agnostic Order owns the durable buyer snapshot, order lines,
    currency and fulfillment lifecycle. RetailCheckoutSession owns only the
    short-lived checkout lifetime.

    Inventory reservation and payment are deliberately handled by later
    workflow slices.
    """

    _validate_buyer_destination(buyer)
    _validate_lines(lines)

    resolved_lines = _resolve_retail_lines(lines=lines)
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

    OrderLine.objects.bulk_create(
        [
            OrderLine(
                order=order,
                product=line.product,
                quantity=line.quantity,
                unit=OrderLine.Unit.STOCK_UNIT,
                quantity_in_units=line.quantity,
                unit_price_snapshot=line.unit_price,
            )
            for line in resolved_lines
        ]
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

    product_ids: set[int] = set()

    for line in lines:
        if not (
            MIN_RETAIL_LINE_QUANTITY
            <= line.quantity
            <= MAX_RETAIL_LINE_QUANTITY
        ):
            raise InvalidRetailOrder(
                "invalid retail line quantity"
            )

        if line.product_id in product_ids:
            raise InvalidRetailOrder(
                "duplicate retail product lines are not allowed"
            )

        product_ids.add(line.product_id)


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
    product = _get_product(line.product_id)
    offer = _get_retail_product_offer(product)

    assert offer.price is not None

    return ResolvedRetailOrderLine(
        product=product,
        quantity=line.quantity,
        unit_price=offer.price,
    )


def _calculate_order_total(
    *,
    lines: list[ResolvedRetailOrderLine],
) -> Decimal:
    return sum(
        (line.line_total for line in lines),
        start=Decimal("0.00"),
    )


def _get_product(product_id: int) -> Product:
    try:
        return Product.objects.get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise InvalidRetailOrder(
            "product does not exist"
        ) from exc


def _get_retail_product_offer(
    product: Product,
) -> RetailProductOffer:
    try:
        offer = product.retail_offer
    except RetailProductOffer.DoesNotExist as exc:
        raise InvalidRetailOrder(
            "product has no retail offer"
        ) from exc

    if not is_retail_product_sellable(offer):
        raise InvalidRetailOrder(
            "product is not enabled for retail"
        )

    assert offer.price is not None

    return offer
