from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from inventory.models import InventoryBatch
from inventory.services import plan_batch_picks
from orders.datatypes import BuyerInput
from orders.models import Allocation, Order, OrderLine
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
    RETAIL_CHECKOUT_WINDOW,
    RETAIL_PAYMENT_RESERVATION_WINDOW,
    is_retail_batch_sellable,
    is_retail_product_sellable,
    is_supported_retail_destination,
)
from retail.selectors import (
    get_batch_for_batch_offer,
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
    """Adapt anonymous retail input to the channel-agnostic buyer contract."""

    first_name = " ".join(
        buyer.first_name.strip().split()
    )
    last_name = " ".join(
        buyer.last_name.strip().split()
    )

    return BuyerInput(
        name=" ".join(
            part
            for part in (first_name, last_name)
            if part
        ),
        email=buyer.email.strip(),
        phone_number=buyer.phone_number.strip(),
        country=buyer.country.strip().upper(),
        postal_code=buyer.postal_code.strip(),
        city=" ".join(buyer.city.strip().split()),
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

    Every retail line references exactly one commercial offer.

    The offer is resolved server-side into product and price. The generic
    OrderLine stores the durable product, quantity and price snapshot, while
    RetailOfferSelection preserves the retail-specific stock-pool identity.

    Merely creating the checkout does not reserve physical inventory.
    """

    _validate_buyer_destination(buyer)
    _validate_lines(lines)

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
        expires_at=timezone.now() + RETAIL_CHECKOUT_WINDOW,
    )


@transaction.atomic
def start_retail_payment(
    *,
    checkout: RetailCheckoutSession,
) -> RetailCheckoutSession:
    """Create a temporary stock hold before external payment starts.

    The checkout and eligible inventory batches are locked only for this
    database transaction.

    No lock remains held while the buyer is at the payment provider.

    Existing temporary reservations for this draft are cancelled and replaced
    by a fresh reservation window. A failure anywhere in this transaction rolls
    back both the cancellations and any newly planned allocations.
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

    _cancel_existing_payment_reservations(
        order=order,
    )

    reserved_until = (
        now + RETAIL_PAYMENT_RESERVATION_WINDOW
    )

    reserved_quantity_by_batch_id: dict[int, int] = {}
    allocations: list[Allocation] = []

    for line in lines:
        selection = _get_offer_selection(
            line=line,
        )

        eligible_batches = _lock_eligible_batches(
            selection=selection,
        )

        _load_active_reservations(
            batches=eligible_batches,
            reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
            now=now,
        )

        picks = plan_batch_picks(
            product=line.product,
            quantity=line.quantity_in_units,
            batches=eligible_batches,
            reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
        )

        for pick in picks:
            allocations.append(
                Allocation(
                    order=order,
                    order_line=line,
                    batch=pick.batch,
                    quantity=pick.quantity,
                    reserved_until=reserved_until,
                )
            )

    Allocation.objects.bulk_create(
        allocations,
    )

    return checkout


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


def _lock_eligible_batches(
    *,
    selection: RetailOfferSelection,
) -> list[InventoryBatch]:
    """Resolve retail stock policy and lock exactly that eligible pool."""

    if selection.product_offer_id is not None:
        offer = selection.product_offer

        assert offer is not None

        return list(
            list_batches_for_product_offer(
                offer=offer,
            )
            .select_for_update()
        )

    if selection.batch_offer_id is not None:
        offer = selection.batch_offer

        assert offer is not None

        batch = get_batch_for_batch_offer(
            offer=offer,
        )

        if batch is None:
            return []

        return list(
            InventoryBatch.objects
            .select_for_update()
            .filter(pk=batch.pk)
            .order_by("best_before", "batch_id")
        )

    raise InvalidRetailOrder(
        f"retail offer selection {selection.pk} has no offer"
    )


def _load_active_reservations(
    *,
    batches: Iterable[InventoryBatch],
    reserved_quantity_by_batch_id: dict[int, int],
    now,
) -> None:
    """Load active reservations for newly encountered locked batches."""

    batch_ids = [
        batch.pk
        for batch in batches
        if batch.pk not in reserved_quantity_by_batch_id
    ]

    if not batch_ids:
        return

    rows = (
        Allocation.objects
        .filter(
            batch_id__in=batch_ids,
            status=Allocation.Status.RESERVED,
        )
        .filter(
            Q(reserved_until__isnull=True)
            | Q(reserved_until__gt=now)
        )
        .values("batch_id")
        .annotate(total=Sum("quantity"))
    )

    totals = {
        row["batch_id"]: row["total"] or 0
        for row in rows
    }

    for batch_id in batch_ids:
        reserved_quantity_by_batch_id[batch_id] = (
            totals.get(batch_id, 0)
        )


def _cancel_existing_payment_reservations(
    *,
    order: Order,
) -> None:
    """Cancel existing temporary payment holds for this draft.

    Only expiring reservations are replaced here. A non-expiring allocation is
    not considered a temporary payment hold and is therefore not silently
    cancelled.
    """

    allocations = list(
        order.allocations
        .select_for_update()
        .filter(
            status=Allocation.Status.RESERVED,
            reserved_until__isnull=False,
        )
        .order_by("id")
    )

    for allocation in allocations:
        allocation.cancel()


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
    """Protect the current generic OrderLine product uniqueness invariant."""

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
