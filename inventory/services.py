"""
Inventory application services.

These functions coordinate inventory use-cases. They may call model methods,
perform database queries, and define transaction boundaries. They should not
contain presentation/UI logic.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.errors import InsufficientStockError, InvalidStockOperation
from inventory.expiry import orderable_best_before_cutoff
from inventory.models import InventoryBatch, normalize_batch_id
from orders.models import Allocation, Order
from products.models import Product

BATCH_ID_SEQUENCE_WIDTH = 3
BATCH_ID_GENERATION_ATTEMPTS = 3
BATCH_ID_MISSING_PRODUCT_CODE = "PX"
BATCH_ID_TEXT_PART_LENGTH = 3


@dataclass(frozen=True)
class BatchPick:
    """Planned pick from one physical batch."""

    batch: InventoryBatch
    quantity: int


@dataclass(frozen=True)
class BatchPickPlan:
    """Result of trying to build a complete FEFO pick plan."""

    picks: list[BatchPick]
    available_quantity: int
    missing_quantity: int

    @property
    def is_complete(self) -> bool:
        return self.missing_quantity == 0


@transaction.atomic
def create_batch(
    *,
    product: Product,
    quantity: int,
    best_before: date,
    location: str,
    batch_id: str | None = None,
    today: date | None = None,
    allow_non_future_best_before: bool = False,
    user=None,
) -> InventoryBatch:
    """Create a new physical inventory batch.

    A new batch must start with positive physical stock. If batch_id is omitted,
    a product-based id is generated.
    """

    today = today or date.today()

    if quantity <= 0:
        raise InvalidStockOperation("quantity must be positive")

    if best_before <= today and not allow_non_future_best_before:
        raise InvalidStockOperation("best_before date must be in the future")

    if batch_id:
        normalized_batch_id = normalize_batch_id(batch_id)

        try:
            return _create_batch_with_id(
                batch_id=normalized_batch_id,
                product=product,
                quantity=quantity,
                best_before=best_before,
                location=location,
                user=user,
            )
        except IntegrityError as exc:
            raise InvalidStockOperation(
                f"Batch {normalized_batch_id} already exists"
            ) from exc

    for _ in range(BATCH_ID_GENERATION_ATTEMPTS):
        generated_batch_id = _generate_batch_id(product=product)

        try:
            return _create_batch_with_id(
                batch_id=generated_batch_id,
                product=product,
                quantity=quantity,
                best_before=best_before,
                location=location,
                user=user,
            )
        except IntegrityError:
            continue

    raise InvalidStockOperation("Could not generate a unique batch id")


@transaction.atomic
def update_batch(
    *,
    batch: InventoryBatch,
    quantity: int,
    best_before: date,
    location: str,
    user=None,
) -> InventoryBatch:
    """Correct editable fields for a physical inventory batch.

    Product and batch_id are intentionally immutable in this MVP. Quantity may
    not be corrected below the number currently reserved from this batch.
    """

    batch = (
        InventoryBatch.objects.select_for_update()
        .select_related("product")
        .get(pk=batch.pk)
    )

    if batch.status == InventoryBatch.Status.CLOSED:
        raise InvalidStockOperation(f"Batch {batch.batch_id} is closed")

    reserved_quantity = reserved_quantity_for_batch(batch=batch)

    if quantity < reserved_quantity:
        raise InvalidStockOperation(
            f"Cannot set batch {batch.batch_id} to {quantity} units; "
            f"{reserved_quantity} units are reserved."
        )

    batch.adjust_quantity(quantity=quantity)

    batch.best_before = best_before
    batch.location = location
    batch.save(update_fields=["best_before", "location", "updated_at"])
    batch.mark_as_edited(user=user)

    return batch


@transaction.atomic
def close_batch(
    *,
    batch: InventoryBatch,
    user=None,
) -> InventoryBatch:
    """Close a batch so it is no longer orderable."""

    batch = (
        InventoryBatch.objects.select_for_update()
        .select_related("product")
        .get(pk=batch.pk)
    )

    reserved_quantity = reserved_quantity_for_batch(batch=batch)

    if reserved_quantity > 0:
        raise InvalidStockOperation(
            f"Cannot close batch {batch.batch_id}; "
            f"{reserved_quantity} units are reserved."
        )

    batch.close(user=user)
    return batch


def reserved_quantity_for_batch(*, batch: InventoryBatch) -> int:
    """Return quantity reserved from this batch by placed orders."""

    result = Allocation.objects.filter(
        batch=batch,
        status=Allocation.Status.RESERVED,
        order__status=Order.Status.PLACED,
    ).aggregate(total=Sum("quantity"))

    return result["total"] or 0


def plan_batch_picks(
    *,
    product: Product,
    quantity: int,
    reserved_quantity_by_batch_id: dict[int, int] | None = None,
) -> list[BatchPick]:
    """Plan which batches should be used for a product quantity.

    Uses FEFO: first-expired, first-out.
    """

    if reserved_quantity_by_batch_id is None:
        reserved_quantity_by_batch_id = {}

    if quantity <= 0:
        raise InvalidStockOperation("quantity must be positive")

    plan = _build_batch_pick_plan(
        batches=_list_candidate_batches_for_picking(product=product),
        requested_quantity=quantity,
        reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
    )

    if not plan.is_complete:
        raise InsufficientStockError(
            product_name=product.display_name,
            requested_quantity=quantity,
            available_quantity=plan.available_quantity,
            missing_quantity=plan.missing_quantity,
        )

    return plan.picks


def _create_batch_with_id(
    *,
    batch_id: str,
    product: Product,
    quantity: int,
    best_before: date,
    location: str,
    user=None,
) -> InventoryBatch:
    batch = InventoryBatch.objects.create(
        batch_id=batch_id,
        product=product,
        quantity=quantity,
        best_before=best_before,
        location=location,
    )
    batch.mark_as_created(user=user)

    return batch


def _generate_batch_id(*, product: Product) -> str:
    """Generate the next local batch id for a product.

    Format:
        P004-TUT-SOU-001
    """

    prefix = _batch_id_prefix(product)

    latest_batch = (
        InventoryBatch.objects.filter(batch_id__startswith=f"{prefix}-")
        .order_by("-batch_id")
        .first()
    )

    if latest_batch is None:
        next_number = 1
    else:
        last_number = int(latest_batch.batch_id.rsplit("-", 1)[1])
        next_number = last_number + 1

    return f"{prefix}-{next_number:0{BATCH_ID_SEQUENCE_WIDTH}d}"


def _batch_id_prefix(product: Product) -> str:
    product_code = _batch_product_code(product)

    return (
        f"{product_code}-"
        f"{_batch_text_part(product.brand)}-"
        f"{_batch_text_part(product.name)}"
    )


def _batch_product_code(product: Product) -> str:
    if product.internal_number:
        return f"P{product.internal_number:03d}"

    return BATCH_ID_MISSING_PRODUCT_CODE


def _batch_text_part(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")

    characters = [character for character in ascii_value.upper() if character.isalnum()]

    if not characters:
        return "XXX"

    return "".join(characters[:BATCH_ID_TEXT_PART_LENGTH]).ljust(
        BATCH_ID_TEXT_PART_LENGTH,
        "X",
    )


def _list_candidate_batches_for_picking(
    *,
    product: Product,
) -> list[InventoryBatch]:
    """Return locked orderable active batches for product in FEFO order."""

    cutoff_date = orderable_best_before_cutoff(today=timezone.localdate())

    return list(
        InventoryBatch.objects.select_for_update()
        .filter(
            product=product,
            status=InventoryBatch.Status.ACTIVE,
            quantity__gt=0,
            best_before__gt=cutoff_date,
        )
        .order_by("best_before", "batch_id")
    )


def _build_batch_pick_plan(
    *,
    batches: Iterable[InventoryBatch],
    requested_quantity: int,
    reserved_quantity_by_batch_id: dict[int, int],
) -> BatchPickPlan:
    """Build a FEFO pick plan from candidate batches.

    This is pure planning except for one deliberate side effect:
    reserved_quantity_by_batch_id is mutated so subsequent order lines see
    quantity already planned by earlier lines.
    """

    remaining_quantity = requested_quantity
    available_quantity = 0
    picks: list[BatchPick] = []

    for batch in batches:
        if remaining_quantity == 0:
            break

        allocatable_quantity = _allocatable_quantity(
            batch=batch,
            reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
        )

        if allocatable_quantity <= 0:
            continue

        available_quantity += allocatable_quantity
        quantity_to_pick = min(allocatable_quantity, remaining_quantity)

        picks.append(
            BatchPick(
                batch=batch,
                quantity=quantity_to_pick,
            )
        )

        _reserve_planned_quantity(
            batch=batch,
            quantity=quantity_to_pick,
            reserved_quantity_by_batch_id=reserved_quantity_by_batch_id,
        )

        remaining_quantity -= quantity_to_pick

    return BatchPickPlan(
        picks=picks,
        available_quantity=available_quantity,
        missing_quantity=remaining_quantity,
    )


def _allocatable_quantity(
    *,
    batch: InventoryBatch,
    reserved_quantity_by_batch_id: dict[int, int],
) -> int:
    already_reserved = reserved_quantity_by_batch_id.get(batch.id, 0)
    return batch.quantity - already_reserved


def _reserve_planned_quantity(
    *,
    batch: InventoryBatch,
    quantity: int,
    reserved_quantity_by_batch_id: dict[int, int],
) -> None:
    already_reserved = reserved_quantity_by_batch_id.get(batch.id, 0)
    reserved_quantity_by_batch_id[batch.id] = already_reserved + quantity
