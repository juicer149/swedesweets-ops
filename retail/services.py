from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from inventory.errors import InsufficientStockError
from inventory.models import InventoryBatch
from orders.datatypes import BuyerInput
from orders.models import (
    Order,
    OrderLine,
)
from orders.services import (
    place_order as place_shared_order,
)
from payments.models import PaymentAttempt
from payments.services import (
    InvalidPaymentAttempt,
    cancel_pending_payment_attempts_for_order,
    create_payment_attempt,
    mark_payment_attempt_failed,
    mark_payment_attempt_succeeded,
)
from products.models import Product
from reservations.planning import (
    InsufficientReservationCapacity,
)
from reservations.policies import (
    make_order_reservations_permanent_before_placement,
)
from reservations.services import (
    cancel_temporary_reservations_for_order,
    reserve_order_line_from_pool,
)
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
    RETAIL_CHECKOUT_WINDOW,
    RETAIL_PAYMENT_RESERVATION_WINDOW,
    is_retail_batch_sellable,
    is_retail_product_sellable,
    is_supported_retail_destination,
)
from retail.selectors import (
    list_batches_for_batch_offer,
    list_batches_for_product_offer,
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
    """Adapt anonymous retail input to the shared buyer contract."""

    first_name = " ".join(
        buyer.first_name.strip().split()
    )
    last_name = " ".join(
        buyer.last_name.strip().split()
    )

    return BuyerInput(
        name=" ".join(
            part
            for part in (
                first_name,
                last_name,
            )
            if part
        ),
        email=buyer.email.strip(),
        phone_number=buyer.phone_number.strip(),
        country=buyer.country.strip().upper(),
        postal_code=buyer.postal_code.strip(),
        city=" ".join(
            buyer.city.strip().split()
        ),
        address_line=" ".join(
            buyer.address_line.strip().split()
        ),
    )


@transaction.atomic
def create_pending_retail_order(
    *,
    buyer: AnonymousBuyerInput,
    lines: list[RetailOrderLineInput],
) -> RetailCheckoutSession:
    """Start an anonymous retail checkout.

    Every line references exactly one commercial retail offer.

    The generic OrderLine stores product, quantity and price snapshot.
    RetailOfferSelection preserves the retail-specific offer identity.

    Creating a checkout does not reserve physical stock.
    """

    _validate_buyer_destination(
        buyer,
    )
    _validate_lines(
        lines,
    )

    resolved_lines = _resolve_retail_lines(
        lines=lines,
    )
    _validate_unique_products(
        lines=resolved_lines,
    )

    total = _calculate_order_total(
        lines=resolved_lines,
    )

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
        buyer=buyer_from_anonymous_retail_input(
            buyer=buyer,
        ),
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
        expires_at=(
            timezone.now()
            + RETAIL_CHECKOUT_WINDOW
        ),
    )


@transaction.atomic
def start_retail_payment(
    *,
    checkout: RetailCheckoutSession,
) -> PaymentAttempt:
    """Prepare one retail order for an external payment attempt.

    The checkout and order are locked while retail availability is
    re-evaluated.

    Existing temporary reservations and pending payment attempts are replaced
    atomically.

    The returned PaymentAttempt exists only after every order line has been
    successfully reserved.

    No payment-provider call happens while these database locks are held.
    """

    now = timezone.now()

    checkout = (
        RetailCheckoutSession.objects
        .select_for_update()
        .get(pk=checkout.pk)
    )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=checkout.order_id)
    )

    if checkout.expires_at <= now:
        raise InvalidRetailOrder(
            "retail checkout has expired"
        )

    if order.channel != Order.Channel.RETAIL:
        raise InvalidRetailOrder(
            "checkout does not belong to a retail order"
        )

    if order.status != Order.Status.DRAFT:
        raise InvalidRetailOrder(
            "only draft retail orders can start payment"
        )

    lines = list(
        order.lines
        .select_related(
            "product",
            "retail_offer_selection__product_offer__product",
            "retail_offer_selection__batch_offer__batch__product",
        )
        .order_by("id")
    )

    if not lines:
        raise InvalidRetailOrder(
            "retail checkout has no order lines"
        )

    cancel_temporary_reservations_for_order(
        order=order,
    )

    cancel_pending_payment_attempts_for_order(
        order=order,
    )

    reserved_until = (
        now
        + RETAIL_PAYMENT_RESERVATION_WINDOW
    )

    for line in lines:
        selection = _get_offer_selection(
            line=line,
        )

        batches = _eligible_batches_for_selection(
            selection=selection,
        )

        try:
            reserve_order_line_from_pool(
                order_line=line,
                batches=batches,
                quantity=line.quantity_in_units,
                reserved_until=reserved_until,
            )
        except InsufficientReservationCapacity as exc:
            raise InsufficientStockError(
                product_name=line.product.display_name,
                requested_quantity=exc.requested_quantity,
                available_quantity=exc.available_quantity,
                missing_quantity=exc.missing_quantity,
            ) from exc

    return create_payment_attempt(
        order=order,
    )


@transaction.atomic
def complete_retail_payment(
    *,
    attempt: PaymentAttempt,
) -> Order:
    """Finalize a successfully paid retail checkout.

    Temporary payment reservations become durable before the shared order
    moves from DRAFT to PLACED.

    The payment attempt is marked SUCCEEDED only after order placement
    succeeds inside the same database transaction.
    """

    attempt = (
        PaymentAttempt.objects
        .select_for_update()
        .select_related("order")
        .get(pk=attempt.pk)
    )

    if attempt.status != PaymentAttempt.Status.PENDING:
        raise InvalidPaymentAttempt(
            "only pending payment attempts can complete retail payment"
        )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=attempt.order_id)
    )

    if order.channel != Order.Channel.RETAIL:
        raise InvalidRetailOrder(
            "payment attempt does not belong to a retail order"
        )

    order = place_shared_order(
        order=order,
        preparation=(
            make_order_reservations_permanent_before_placement
        ),
    )

    mark_payment_attempt_succeeded(
        attempt=attempt,
    )

    return order


@transaction.atomic
def fail_retail_payment(
    *,
    attempt: PaymentAttempt,
) -> PaymentAttempt:
    """Finalize a failed retail payment attempt.

    Temporary payment reservations are released while the shared order remains
    in DRAFT so the buyer may retry checkout.

    Reservation release and payment state transition happen atomically.
    """

    attempt = (
        PaymentAttempt.objects
        .select_for_update()
        .select_related("order")
        .get(pk=attempt.pk)
    )

    if attempt.status != PaymentAttempt.Status.PENDING:
        raise InvalidPaymentAttempt(
            "only pending payment attempts can fail retail payment"
        )

    order = (
        Order.objects
        .select_for_update()
        .get(pk=attempt.order_id)
    )

    if order.channel != Order.Channel.RETAIL:
        raise InvalidRetailOrder(
            "payment attempt does not belong to a retail order"
        )

    if order.status != Order.Status.DRAFT:
        raise InvalidRetailOrder(
            "only draft retail orders can fail payment"
        )

    cancel_temporary_reservations_for_order(
        order=order,
    )

    return mark_payment_attempt_failed(
        attempt=attempt,
    )


def _get_offer_selection(
    *,
    line: OrderLine,
) -> RetailOfferSelection:
    try:
        return line.retail_offer_selection
    except RetailOfferSelection.DoesNotExist as exc:
        raise InvalidRetailOrder(
            f"order line {line.pk} has no retail offer selection"
        ) from exc


def _eligible_batches_for_selection(
    *,
    selection: RetailOfferSelection,
) -> QuerySet[InventoryBatch]:
    """Return the commercial stock pool selected by one retail offer."""

    if selection.product_offer_id is not None:
        offer = selection.product_offer

        assert offer is not None

        return list_batches_for_product_offer(
            offer=offer,
        )

    if selection.batch_offer_id is not None:
        offer = selection.batch_offer

        assert offer is not None

        return list_batches_for_batch_offer(
            offer=offer,
        )

    raise InvalidRetailOrder(
        f"retail offer selection {selection.pk} "
        "has no offer"
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

        has_product_offer = (
            line.product_offer_id is not None
        )
        has_batch_offer = (
            line.batch_offer_id is not None
        )

        if has_product_offer == has_batch_offer:
            raise InvalidRetailOrder(
                "retail line must reference exactly one offer"
            )


def _resolve_retail_lines(
    *,
    lines: list[RetailOrderLineInput],
) -> list[ResolvedRetailOrderLine]:
    return [
        _resolve_retail_line(
            line=line,
        )
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
    """Protect the current generic OrderLine product uniqueness constraint."""

    product_ids: set[int] = set()

    for line in lines:
        if line.product.pk in product_ids:
            raise InvalidRetailOrder(
                "duplicate retail product lines are not allowed"
            )

        product_ids.add(
            line.product.pk,
        )


def _calculate_order_total(
    *,
    lines: list[ResolvedRetailOrderLine],
) -> Decimal:
    return sum(
        (
            line.line_total
            for line in lines
        ),
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

    if not is_retail_product_sellable(
        offer,
    ):
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

    if not is_retail_batch_sellable(
        offer,
    ):
        raise InvalidRetailOrder(
            "batch is not enabled for retail"
        )

    assert offer.price is not None

    return offer
