from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from customers.models import Customer
from orders.datatypes import (
    BuyerInput,
    OrderLineInput,
)
from orders.drafts import (
    OrderDraft,
    ResolvedOrderLine,
)
from orders.errors import InvalidOrderOperation
from orders.models import Order
from pricing.models import CommercialPrice
from products.models import Product
from products.units import (
    normalize_order_unit,
    quantity_to_units,
)


def buyer_from_customer(
    *,
    customer: Customer,
) -> BuyerInput:
    """Adapt a persisted business customer to the shared buyer contract."""

    return BuyerInput(
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        country=customer.country,
        city=customer.city,
        address_line=customer.address_line,
        postal_code="",
    )


def resolve_standard_business_offer(
    *,
    product: Product,
) -> CommercialPrice:
    """Return the product's persistent standard BUSINESS offer.

    Missing standard identity is a catalog/configuration invariant violation.

    A disabled standard offer is different: the identity exists, but the
    product is intentionally unavailable in the business channel.
    """

    offer = (
        CommercialPrice.objects
        .filter(
            product=product,
            channel=CommercialPrice.Channel.BUSINESS,
            batch__isnull=True,
        )
        .first()
    )

    if offer is None:
        raise RuntimeError(
            "business ordering invariant violated: "
            "missing standard BUSINESS offer for "
            f"{product.display_name}"
        )

    if not offer.enabled:
        raise InvalidOrderOperation(
            "product is not available for business ordering"
        )

    return offer


def build_business_order_draft(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
) -> OrderDraft:
    """Resolve business input into a channel-agnostic order draft."""

    resolved_lines = resolve_business_order_lines(
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


def resolve_business_order_lines(
    *,
    lines: Iterable[OrderLineInput],
) -> tuple[ResolvedOrderLine, ...]:
    """Resolve business quantities to physical stock units.

    Duplicate product lines are merged after quantity conversion.

    Each resolved line carries the product's persistent standard BUSINESS offer
    as its commercial selection. Ordinary product ordering is therefore an
    explicit commercial choice rather than an offer-less special case.
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
            str(line_input.unit),
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
    """Resolve standard BUSINESS offers for several products in one query.

    Every requested product must have a persistent standard BUSINESS offer.
    Disabled offers are present identities but are not orderable.
    """

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
            "business ordering invariant violated: "
            "missing standard BUSINESS offer for "
            + ", ".join(missing_product_names)
        )

    disabled_product_names = sorted(
        products_by_id[product_id].display_name
        for product_id, offer in offers_by_product_id.items()
        if not offer.enabled
    )

    if disabled_product_names:
        raise InvalidOrderOperation(
            "product is not available for business ordering: "
            + ", ".join(disabled_product_names)
        )

    return offers_by_product_id
