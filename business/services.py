from __future__ import annotations

from collections.abc import Iterable

from django.db import IntegrityError, transaction

from business.drafts import (
    build_business_order_draft,
    buyer_from_customer,
    resolve_business_order_lines,
)
from business.models import BusinessOfferSelection
from business.policies import (
    prepare_business_order_for_placement,
)
from business.selectors import (
    list_business_catalog_products,
)
from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from customers.models import Customer
from inventory.selectors import (
    orderable_quantity_by_product_id,
)
from orders.datatypes import OrderLineInput
from orders.drafts import ResolvedOrderLine
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
    is_unusually_large_order_line,
)
from orders.services import (
    add_draft_order_line as add_shared_draft_order_line,
    create_draft_order as create_shared_draft_order,
    discard_draft_order as discard_shared_draft_order,
    place_order as place_shared_order,
    remove_draft_order_line as remove_shared_draft_order_line,
    replace_draft_order_lines as replace_shared_draft_order_lines,
    set_draft_order_line_quantity as set_shared_draft_order_line_quantity,
    update_placed_order as update_shared_placed_order,
)
from products.models import Product
from reservations.policies import (
    clear_order_reservations_before_line_replacement,
    require_order_without_reservations_before_discard,
)


@transaction.atomic
def create_draft_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
) -> Order:
    """Create an ordinary unpriced business order in DRAFT status."""

    draft = build_business_order_draft(
        customer=customer,
        lines=lines,
    )

    return create_shared_draft_order(
        draft=draft,
    )


@transaction.atomic
def add_catalog_offer_to_draft_order(
    *,
    customer: Customer,
    product: Product,
    commercial_price_id: int | None,
    quantity: int = 1,
    user=None,
) -> Order:
    """Add one channel-approved catalog selection to a business draft.

    CommercialPrice identity distinguishes offers for the same product.

    `commercial_price_id=None` is valid only when the current business catalog
    exposes an explicit standard selection without a CommercialPrice.
    """

    if quantity <= 0:
        raise InvalidOrderOperation(
            "quantity must be positive"
        )

    catalog_product = _get_catalog_product(
        product=product,
    )

    offer = _get_catalog_offer(
        catalog_product=catalog_product,
        commercial_price_id=commercial_price_id,
    )

    order = get_or_create_customer_draft_order(
        customer=customer,
    )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    existing_line = _find_line_for_offer(
        order=order,
        product=product,
        commercial_price_id=commercial_price_id,
    )

    existing_offer_quantity = (
        existing_line.quantity_in_units
        if existing_line is not None
        else 0
    )

    requested_offer_quantity = (
        existing_offer_quantity
        + quantity
    )

    if requested_offer_quantity > offer.available_units:
        raise InvalidOrderOperation(
            f"only {offer.available_units} units "
            "are currently available for this offer"
        )

    current_product_quantity = sum(
        line.quantity_in_units
        for line in (
            order.lines
            .filter(product=product)
            .only("quantity_in_units")
        )
    )

    requested_product_quantity = (
        current_product_quantity
        + quantity
    )

    if is_unusually_large_order_line(
        quantity=requested_product_quantity,
    ):
        raise InvalidOrderOperation(
            f"maximum quantity per product is "
            f"{MAX_QUANTITY_PER_PRODUCT_PER_ORDER}"
        )

    if existing_line is not None:
        set_shared_draft_order_line_quantity(
            order=order,
            order_line_id=existing_line.id,
            quantity_in_units=requested_offer_quantity,
            user=user,
        )

        return order

    order_line = add_shared_draft_order_line(
        order=order,
        line=ResolvedOrderLine(
            product=product,
            quantity_in_units=quantity,
            unit_price_snapshot=offer.price,
        ),
        user=user,
    )

    BusinessOfferSelection.objects.create(
        order_line=order_line,
        commercial_price_id=offer.commercial_price_id,
    )

    return order


@transaction.atomic
def add_product_to_draft_order(
    *,
    customer: Customer,
    product: Product,
    quantity: int = 1,
    user=None,
) -> Order:
    """Add ordinary unpriced units of one product to a business draft.

    This legacy product-level mutation remains available while portal callers
    migrate to explicit catalog-offer selection.

    Legacy lines intentionally have no BusinessOfferSelection.
    """

    if quantity <= 0:
        raise InvalidOrderOperation(
            "quantity must be positive"
        )

    if not product.active:
        raise InvalidOrderOperation(
            "product is not available for business ordering"
        )

    order = get_or_create_customer_draft_order(
        customer=customer,
    )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    existing_line = (
        order.lines
        .select_related("product")
        .filter(
            product=product,
            business_offer_selection__isnull=True,
        )
        .first()
    )

    existing_quantity = (
        existing_line.quantity_in_units
        if existing_line is not None
        else 0
    )

    requested_quantity = (
        existing_quantity
        + quantity
    )

    if is_unusually_large_order_line(
        quantity=requested_quantity,
    ):
        raise InvalidOrderOperation(
            f"maximum quantity per product is "
            f"{MAX_QUANTITY_PER_PRODUCT_PER_ORDER}"
        )

    available_units = (
        orderable_quantity_by_product_id()
        .get(
            product.id,
            0,
        )
    )

    if requested_quantity > available_units:
        raise InvalidOrderOperation(
            f"only {available_units} units are currently available"
        )

    if existing_line is not None:
        return set_shared_draft_order_line_quantity(
            order=order,
            order_line_id=existing_line.id,
            quantity_in_units=requested_quantity,
            user=user,
        )

    add_shared_draft_order_line(
        order=order,
        line=ResolvedOrderLine(
            product=product,
            quantity_in_units=quantity,
        ),
        user=user,
    )

    return order


@transaction.atomic
def set_draft_line_quantity(
    *,
    order: Order,
    order_line_id: int,
    quantity: int,
    user=None,
) -> Order:
    """Set quantity for one durable business draft line.

    Legacy lines without BusinessOfferSelection use ordinary product
    availability.

    Explicit catalog selections use the currently available quantity of that
    exact offer.
    """

    if quantity <= 0:
        raise InvalidOrderOperation(
            "quantity must be positive"
        )

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "requires a business order"
        )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=order.pk)
    )

    line = (
        order.lines
        .select_related(
            "product",
            "business_offer_selection__commercial_price",
        )
        .filter(
            pk=order_line_id,
        )
        .first()
    )

    if line is None:
        raise InvalidOrderOperation(
            "order line does not belong to this draft order"
        )

    product_total_without_line = sum(
        sibling.quantity_in_units
        for sibling in (
            order.lines
            .filter(product=line.product)
            .exclude(pk=line.pk)
            .only("quantity_in_units")
        )
    )

    requested_product_quantity = (
        product_total_without_line
        + quantity
    )

    if is_unusually_large_order_line(
        quantity=requested_product_quantity,
    ):
        raise InvalidOrderOperation(
            f"maximum quantity per product is "
            f"{MAX_QUANTITY_PER_PRODUCT_PER_ORDER}"
        )

    try:
        selection = line.business_offer_selection
    except BusinessOfferSelection.DoesNotExist:
        available_units = (
            orderable_quantity_by_product_id()
            .get(
                line.product_id,
                0,
            )
        )

        if quantity > available_units:
            raise InvalidOrderOperation(
                f"only {available_units} units "
                "are currently available"
            )
    else:
        offer = _get_explicit_offer_for_order_line(
            line=line,
            selection=selection,
        )

        if quantity > offer.available_units:
            raise InvalidOrderOperation(
                f"only {offer.available_units} units "
                "are currently available for this offer"
            )

    return set_shared_draft_order_line_quantity(
        order=order,
        order_line_id=line.id,
        quantity_in_units=quantity,
        user=user,
    )


@transaction.atomic
def remove_draft_line(
    *,
    order: Order,
    order_line_id: int,
    user=None,
) -> Order:
    """Remove one durable business draft line."""

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "requires a business order"
        )

    return remove_shared_draft_order_line(
        order=order,
        order_line_id=order_line_id,
        user=user,
    )


@transaction.atomic
def set_draft_product_quantity(
    *,
    order: Order,
    product: Product,
    quantity: int,
    user=None,
) -> Order:
    """Set quantity on one legacy product-only business draft line."""

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "requires a business order"
        )

    line = (
        order.lines
        .filter(
            product=product,
            business_offer_selection__isnull=True,
        )
        .first()
    )

    if line is None:
        raise InvalidOrderOperation(
            "product is not part of the draft order"
        )

    return set_draft_line_quantity(
        order=order,
        order_line_id=line.id,
        quantity=quantity,
        user=user,
    )


@transaction.atomic
def remove_product_from_draft_order(
    *,
    order: Order,
    product: Product,
    user=None,
) -> Order:
    """Remove one legacy product-only business draft line."""

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "requires a business order"
        )

    line = (
        order.lines
        .filter(
            product=product,
            business_offer_selection__isnull=True,
        )
        .first()
    )

    if line is None:
        raise InvalidOrderOperation(
            "product is not part of the draft order"
        )

    return remove_draft_line(
        order=order,
        order_line_id=line.id,
        user=user,
    )


@transaction.atomic
def create_order(
    *,
    customer: Customer,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Create and immediately place an ordinary business order."""

    order = create_draft_order(
        customer=customer,
        lines=lines,
    )

    return place_order(
        order=order,
        user=user,
    )


@transaction.atomic
def get_or_create_customer_draft_order(
    *,
    customer: Customer,
) -> Order:
    """Return the customer's active business draft, creating one if needed."""

    draft = (
        Order.objects
        .select_for_update()
        .filter(
            channel=Order.Channel.BUSINESS,
            customer=customer,
            status=Order.Status.DRAFT,
        )
        .order_by(
            "created_at",
            "id",
        )
        .first()
    )

    if draft is not None:
        return draft

    order = Order(
        channel=Order.Channel.BUSINESS,
        currency=Order.Currency.EUR,
        customer=customer,
    )

    order.snapshot_buyer(
        buyer=buyer_from_customer(
            customer=customer,
        ),
    )

    try:
        with transaction.atomic():
            order.save()
    except IntegrityError:
        return (
            Order.objects
            .select_for_update()
            .get(
                channel=Order.Channel.BUSINESS,
                customer=customer,
                status=Order.Status.DRAFT,
            )
        )

    return order


def replace_draft_order_lines(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace ordinary product-only lines of a business draft.

    This API intentionally remains a legacy ordinary-order path. Catalog
    offer-aware editing uses line-specific mutations instead.
    """

    resolved_lines = resolve_business_order_lines(
        lines=lines,
    )

    return replace_shared_draft_order_lines(
        order=order,
        lines=resolved_lines,
        user=user,
    )


def discard_draft_order(
    *,
    order: Order,
) -> None:
    """Discard a business draft that owns no reservations."""

    discard_shared_draft_order(
        order=order,
        preparation=(
            require_order_without_reservations_before_discard
        ),
    )


def place_order(
    *,
    order: Order,
    user=None,
) -> Order:
    """Place a business draft order."""

    return place_shared_order(
        order=order,
        preparation=prepare_business_order_for_placement,
        user=user,
    )


def update_placed_order(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Replace ordinary lines and rebuild a business reservation.

    Offer-aware placed-order editing requires a separate explicit use-case;
    this legacy API must not silently reinterpret commercial selections.
    """

    resolved_lines = resolve_business_order_lines(
        lines=lines,
    )

    return update_shared_placed_order(
        order=order,
        lines=resolved_lines,
        before_replacement=(
            clear_order_reservations_before_line_replacement
        ),
        preparation=prepare_business_order_for_placement,
        user=user,
    )


def _get_catalog_product(
    *,
    product: Product,
) -> CatalogProduct:
    for catalog_product in (
        list_business_catalog_products()
    ):
        if catalog_product.product.id == product.id:
            return catalog_product

    raise InvalidOrderOperation(
        "product is not available in the business catalog"
    )


def _get_catalog_offer(
    *,
    catalog_product: CatalogProduct,
    commercial_price_id: int | None,
) -> CatalogOffer:
    for offer in catalog_product.offers:
        if (
            offer.commercial_price_id
            == commercial_price_id
        ):
            return offer

    raise InvalidOrderOperation(
        "business offer is not currently available"
    )


def _find_line_for_offer(
    *,
    order: Order,
    product: Product,
    commercial_price_id: int | None,
) -> OrderLine | None:
    lines = (
        order.lines
        .filter(
            product=product,
        )
        .select_related(
            "business_offer_selection",
        )
        .order_by("id")
    )

    for line in lines:
        try:
            selection = line.business_offer_selection
        except BusinessOfferSelection.DoesNotExist:
            continue

        if (
            selection.commercial_price_id
            == commercial_price_id
        ):
            return line

    return None


def _get_explicit_offer_for_order_line(
    *,
    line: OrderLine,
    selection: BusinessOfferSelection,
) -> CatalogOffer:
    catalog_product = _get_catalog_product(
        product=line.product,
    )

    if selection.commercial_price_id is None:
        return _get_standard_offer(
            catalog_product=catalog_product,
        )

    return _get_catalog_offer(
        catalog_product=catalog_product,
        commercial_price_id=(
            selection.commercial_price_id
        ),
    )


def _get_standard_offer(
    *,
    catalog_product: CatalogProduct,
) -> CatalogOffer:
    for offer in catalog_product.offers:
        if offer.kind == CatalogOfferKind.STANDARD:
            return offer

    raise InvalidOrderOperation(
        "standard business offer is not currently available"
    )
