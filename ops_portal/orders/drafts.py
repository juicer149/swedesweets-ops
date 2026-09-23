from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from customers.models import Customer
from orders.datatypes import BuyerInput, OrderLineInput
from orders.drafts import OrderDraft, ResolvedOrderLine
from orders.errors import InvalidOrderOperation
from orders.models import Order
from pricing.models import CommercialPrice
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

    Ops orders are BUSINESS-channel orders. Every resolved line therefore
    carries the product's persistent standard BUSINESS offer.
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
    """Resolve ops-portal quantities and commercial identities.

    Duplicate product lines are merged after quantity conversion.

    Ops orders use the BUSINESS channel, so an ordinary product line uses
    the product's persistent standard BUSINESS offer. Missing offer identity
    is a configuration invariant violation; a disabled offer makes the
    product unavailable for business ordering.
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
            product = products_by_id[
                product_id
            ]
        except KeyError as exc:
            raise InvalidOrderOperation(
                f"Product {product_id} does not exist"
            ) from exc

        unit = normalize_order_unit(
            str(line_input.unit)
        )

        quantity_in_units = quantity_to_units(
            product=product,
            quantity=line_input.quantity,
            unit=unit,
        )

        if quantity_in_units <= 0:
            raise InvalidOrderOperation(
                "order line quantity must be positive"
            )

        quantity_by_product_id[
            product_id
        ] += quantity_in_units

    standard_offers_by_product_id = (
        _standard_business_offers_by_product_id(
            products=(
                products_by_id[product_id]
                for product_id in quantity_by_product_id
            ),
        )
    )

    return tuple(
        ResolvedOrderLine(
            product=products_by_id[
                product_id
            ],
            quantity_in_units=quantity,
            commercial_offer=standard_offers_by_product_id[
                product_id
            ],
        )
        for product_id, quantity
        in quantity_by_product_id.items()
    )


def _standard_business_offers_by_product_id(
    *,
    products: Iterable[Product],
) -> dict[int, CommercialPrice]:
    """Resolve persistent standard BUSINESS offers for ops order lines."""

    products_by_id = {
        product.id: product
        for product in products
    }

    if not products_by_id:
        return {}

    offers_by_product_id = {
        offer.product_id: offer
        for offer in (
            CommercialPrice.objects
            .filter(
                product_id__in=products_by_id,
                channel=CommercialPrice.Channel.BUSINESS,
                batch__isnull=True,
            )
        )
    }

    missing_product_names = sorted(
        products_by_id[product_id].display_name
        for product_id in (
            products_by_id.keys()
            - offers_by_product_id.keys()
        )
    )

    if missing_product_names:
        raise RuntimeError(
            "ops ordering invariant violated: "
            "missing standard BUSINESS offer for "
            + ", ".join(missing_product_names)
        )

    disabled_product_names = sorted(
        products_by_id[product_id].display_name
        for product_id, offer
        in offers_by_product_id.items()
        if not offer.enabled
    )

    if disabled_product_names:
        raise InvalidOrderOperation(
            "product is not available for business ordering: "
            + ", ".join(disabled_product_names)
        )

    return offers_by_product_id
