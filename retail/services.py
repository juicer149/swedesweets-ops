from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from products.models import Product
from retail.models import RetailOrder, RetailOrderLine, RetailPrice
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_LINES,
    MAX_RETAIL_ORDER_TOTAL,
    MIN_RETAIL_LINE_QUANTITY,
    RETAIL_PAYMENT_WINDOW,
    is_supported_retail_destination,
)


class InvalidRetailOrder(ValueError):
    """Raised when a retail order violates a business invariant."""


@dataclass(frozen=True)
class AnonymousBuyerInput:
    first_name: str
    last_name: str
    email: str
    phone_number: str
    country: str
    postal_code: str
    city: str
    address_line: str


@dataclass(frozen=True)
class RetailOrderLineInput:
    product_id: int
    quantity: int


@transaction.atomic
def create_pending_retail_order(
    *,
    buyer: AnonymousBuyerInput,
    lines: list[RetailOrderLineInput],
) -> RetailOrder:
    _validate_buyer_destination(buyer)
    _validate_lines(lines)

    order = RetailOrder.objects.create(
        first_name=buyer.first_name.strip(),
        last_name=buyer.last_name.strip(),
        email=buyer.email.strip(),
        phone_number=buyer.phone_number.strip(),
        country=buyer.country.strip().upper(),
        postal_code=buyer.postal_code.strip(),
        city=" ".join(buyer.city.strip().split()),
        address_line=" ".join(buyer.address_line.strip().split()),
        expires_at=timezone.now() + RETAIL_PAYMENT_WINDOW,
    )

    total = Decimal("0.00")

    for line_input in lines:
        product = _get_product(line_input.product_id)
        price = _get_retail_price(product)

        line_total = price.amount * line_input.quantity

        RetailOrderLine.objects.create(
            order=order,
            product=product,
            quantity=line_input.quantity,
            unit_price_snapshot=price.amount,
            line_total=line_total,
        )

        total += line_total

    if total > MAX_RETAIL_ORDER_TOTAL:
        raise InvalidRetailOrder("order total exceeds maximum allowed amount")

    order.total = total
    order.save(update_fields=["total", "updated_at"])

    return order


def _validate_buyer_destination(buyer: AnonymousBuyerInput) -> None:
    if not is_supported_retail_destination(
        country_code=buyer.country,
        postal_code=buyer.postal_code,
        city=buyer.city,
    ):
        raise InvalidRetailOrder("unsupported retail destination")


def _validate_lines(lines: list[RetailOrderLineInput]) -> None:
    if not lines:
        raise InvalidRetailOrder("order must contain at least one line")

    if len(lines) > MAX_RETAIL_ORDER_LINES:
        raise InvalidRetailOrder("order contains too many lines")

    for line in lines:
        if not (
            MIN_RETAIL_LINE_QUANTITY
            <= line.quantity
            <= MAX_RETAIL_LINE_QUANTITY
        ):
            raise InvalidRetailOrder("invalid retail line quantity")


def _get_product(product_id: int) -> Product:
    try:
        return Product.objects.get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise InvalidRetailOrder("product does not exist") from exc


def _get_retail_price(product: Product) -> RetailPrice:
    try:
        return product.retail_price
    except RetailPrice.DoesNotExist as exc:
        raise InvalidRetailOrder("product has no retail price") from exc
