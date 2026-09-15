from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from customers.models import Customer
from orders.datatypes import BuyerInput, OrderLineInput
from orders.drafts import OrderDraft, ResolvedOrderLine
from orders.errors import InvalidOrderOperation
from orders.models import Order
from products.models import Product
from products.units import normalize_order_unit, quantity_to_units


def buyer_from_customer(
    *,
    customer: Customer,
) -> BuyerInput:
    """Adapt a persisted customer to the shared buyer contract.

    Plain field mapping, no business rule - duplicated locally rather
    than imported from business.drafts so ops_portal has no dependency
    on the business app.
    """

    return BuyerInput(
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        country=customer.country,
        city=customer.city,
        address_line=customer.address_line,
        postal_code="",
    )


def build_ops_order_draft(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
) -> OrderDraft:
    """Resolve ops-portal input into a channel-agnostic order draft.

    Ops orders are always Business channel - matches the prior behavior
    of business.create_order, which this function replaces the draft-
    building half of.
    """

    resolved_lines = resolve_ops_order_lines(
        lines=lines,
    )

    if not resolved_lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    return OrderDraft(
        channel=Order.Channel.BUSINESS,
        currency=Order.Currency.EUR,
        customer=customer,
        buyer=buyer_from_customer(
            customer=customer,
        ),
        lines=resolved_lines,
    )


def resolve_ops_order_lines(
    *,
    lines: Iterable[OrderLineInput],
) -> tuple[ResolvedOrderLine, ...]:
    """Resolve ops-portal quantities to physical stock units.

    Duplicate product lines are merged after quantity conversion. Same
    shape as business.resolve_business_order_lines, kept as a local
    copy rather than imported - no catalog-offer or commercial-price
    logic involved on either side, just unit conversion, so there is no
    shared business behavior to depend on.
    """

    line_inputs = tuple(lines)

    if not line_inputs:
        return ()

    resolved_inputs = tuple(
        (
            line_input,
            line_input.resolve_product_id(),
        )
        for line_input in line_inputs
    )

    products_by_id = Product.objects.in_bulk(
        product_id
        for _, product_id in resolved_inputs
    )

    quantity_by_product_id: dict[int, int] = defaultdict(int)

    for line_input, product_id in resolved_inputs:
        try:
            product = products_by_id[product_id]
        except KeyError as exc:
            raise InvalidOrderOperation(
                f"Product {product_id} does not exist"
            ) from exc

        unit = normalize_order_unit(str(line_input.unit))

        quantity_in_units = quantity_to_units(
            product=product,
            quantity=line_input.quantity,
            unit=unit,
        )

        if quantity_in_units <= 0:
            raise InvalidOrderOperation(
                "order line quantity must be positive"
            )

        quantity_by_product_id[product_id] += quantity_in_units

    return tuple(
        ResolvedOrderLine(
            product=products_by_id[product_id],
            quantity_in_units=quantity,
        )
        for product_id, quantity in quantity_by_product_id.items()
    )
