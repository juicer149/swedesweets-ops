"""
Inventory application services.

These functions coordinate inventory use-cases. They may call model methods,
perform database queries, and define transaction boundaries. They should not
contain presentation/UI logic.

public API:
    create_batch(
        *,
        product: Product,
        boxes: int,
        best_before: date,
        location: str,
        batch_id: str | None = None,
        today: date | None = None,
        allow_non_future_best_before: bool = False,
    ) -> InventoryBatch
        -> Create a new physical inventory batch.

    update_batch(
        *,
        batch: InventoryBatch,
        boxes: int,
        best_before: date,
        location: str,
    ) -> InventoryBatch
        -> Correct editable physical batch fields.

    reserved_boxes_for_batch(
        *,
        batch: InventoryBatch,
    ) -> int
        -> Return boxes reserved from this batch by placed orders.

    plan_batch_picks(
        *,
        product: Product,
        boxes: int,
        reserved_boxes_by_batch_id: dict[int, int],
    ) -> list[BatchPick]
        -> Plan FEFO picks for a product quantity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
import unicodedata

from django.db import IntegrityError, transaction
from django.db.models import Sum

from inventory.errors import InsufficientStockError, InvalidStockOperation
from inventory.models import InventoryBatch, normalize_batch_id
from orders.models import Allocation, Order
from products.models import Product


BATCH_ID_SEQUENCE_WIDTH = 3
BATCH_ID_GENERATION_ATTEMPTS = 3
BATCH_ID_MISSING_PRODUCT_CODE = "PX"
BATCH_ID_TEXT_PART_LENGTH = 3


@dataclass(frozen=True)
class BatchPick:
    """Planned pick from one physical batch.

    This is not a database object. It is a planning result used by order services
    to create Allocation rows.
    """

    batch: InventoryBatch
    boxes: int


@dataclass(frozen=True)
class BatchPickPlan:
    """Result of trying to build a complete FEFO pick plan."""

    picks: list[BatchPick]
    available_boxes: int
    missing_boxes: int

    @property
    def is_complete(self) -> bool:
        return self.missing_boxes == 0


# ==============================================================================
# public
# ==============================================================================


@transaction.atomic
def create_batch(
    *,
    product: Product,
    boxes: int,
    best_before: date,
    location: str,
    batch_id: str | None = None,
    today: date | None = None,
    allow_non_future_best_before: bool = False,
) -> InventoryBatch:
    """Create a new physical inventory batch.

    A new batch must start with positive physical stock. Later corrections may
    use InventoryBatch.adjust_boxes(), but creating an empty batch is not a
    meaningful stock-receiving event for this MVP.

    If batch_id is provided, it is treated as a manual or external lot code.
    If batch_id is omitted, a product-based id is generated.

    Generated format:
        P004-TUT-SOU-001

    The prefix is based on product internal number, brand and name. The trailing
    number is a sequence per product prefix.

    allow_non_future_best_before exists for trusted import/seed data only.
    Normal app flows should leave it as False.
    """

    today = today or date.today()

    if boxes <= 0:
        raise InvalidStockOperation("boxes must be positive")

    if best_before <= today and not allow_non_future_best_before:
        raise InvalidStockOperation("best_before date must be in the future")

    if batch_id:
        normalized_batch_id = normalize_batch_id(batch_id)

        try:
            return _create_batch_with_id(
                batch_id=normalized_batch_id,
                product=product,
                boxes=boxes,
                best_before=best_before,
                location=location,
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
                boxes=boxes,
                best_before=best_before,
                location=location,
            )
        except IntegrityError:
            continue

    raise InvalidStockOperation("Could not generate a unique batch id")


@transaction.atomic
def update_batch(
    *,
    batch: InventoryBatch,
    boxes: int,
    best_before: date,
    location: str,
) -> InventoryBatch:
    """Correct editable fields for a physical inventory batch.

    Product and batch_id are intentionally immutable in this MVP. They identify
    what was received. Changing them later would weaken traceability.

    Boxes may not be corrected below the number of boxes currently reserved from
    this batch by placed orders.
    """

    batch = (
        InventoryBatch.objects
        .select_for_update()
        .select_related("product")
        .get(pk=batch.pk)
    )

    if batch.status == InventoryBatch.Status.CLOSED:
        raise InvalidStockOperation(f"Batch {batch.batch_id} is closed")

    reserved_boxes = reserved_boxes_for_batch(batch=batch)

    if boxes < reserved_boxes:
        raise InvalidStockOperation(
            f"Cannot set batch {batch.batch_id} to {boxes} boxes; "
            f"{reserved_boxes} boxes are reserved."
        )

    batch.adjust_boxes(boxes=boxes)

    batch.best_before = best_before
    batch.location = location
    batch.save(update_fields=["best_before", "location"])

    return batch


@transaction.atomic
def close_batch(*, batch: InventoryBatch) -> InventoryBatch:
    """Close a batch so it is no longer orderable.

    A batch with active reservations cannot be closed, because placed orders
    still depend on it.
    """

    batch = (
        InventoryBatch.objects
        .select_for_update()
        .select_related("product")
        .get(pk=batch.pk)
    )

    reserved_boxes = reserved_boxes_for_batch(batch=batch)

    if reserved_boxes > 0:
        raise InvalidStockOperation(
            f"Cannot close batch {batch.batch_id}; "
            f"{reserved_boxes} boxes are reserved."
        )

    batch.close()
    return batch


def reserved_boxes_for_batch(*, batch: InventoryBatch) -> int:
    """Return boxes reserved from this batch by placed orders."""

    result = (
        Allocation.objects
        .filter(
            batch=batch,
            status=Allocation.Status.RESERVED,
            order__status=Order.Status.PLACED,
        )
        .aggregate(total=Sum("boxes"))
    )

    return result["total"] or 0


def plan_batch_picks(
    *,
    product: Product,
    boxes: int,
    reserved_boxes_by_batch_id: dict[int, int],
) -> list[BatchPick]:
    """Plan which batches should be used for a product quantity.

    Uses FEFO:
        first-expired, first-out

    The caller provides reserved_boxes_by_batch_id because reservations are owned
    by the order/allocation workflow. This keeps inventory independent from
    orders while still allowing it to make correct batch-level plans.

    This function mutates reserved_boxes_by_batch_id deliberately. When an order
    has multiple lines, later lines must see reservations planned by earlier
    lines.

    Important:
        Candidate batches are locked with select_for_update(). In the real order
        workflow, call this inside transaction.atomic() together with Allocation
        creation, otherwise the lock is not protecting the whole workflow.
    """

    if boxes <= 0:
        raise InvalidStockOperation("boxes must be positive")

    plan = _build_batch_pick_plan(
        batches=_list_candidate_batches_for_picking(product=product),
        requested_boxes=boxes,
        reserved_boxes_by_batch_id=reserved_boxes_by_batch_id,
    )

    if not plan.is_complete:
        raise InsufficientStockError(
            product_name=product.display_name,
            requested_boxes=boxes,
            available_boxes=plan.available_boxes,
            missing_boxes=plan.missing_boxes,
        )

    return plan.picks


# ==============================================================================
# private/helpers
# ==============================================================================


def _create_batch_with_id(
    *,
    batch_id: str,
    product: Product,
    boxes: int,
    best_before: date,
    location: str,
) -> InventoryBatch:
    return InventoryBatch.objects.create(
        batch_id=batch_id,
        product=product,
        boxes=boxes,
        best_before=best_before,
        location=location,
    )


def _generate_batch_id(*, product: Product) -> str:
    """Generate the next local batch id for a product.

    Format:
        P004-TUT-SOU-001

    This is private because batch-id generation is an implementation detail of
    create_batch(), not a separate application use-case.
    """

    prefix = _batch_id_prefix(product)

    latest_batch = (
        InventoryBatch.objects
        .filter(batch_id__startswith=f"{prefix}-")
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

    characters = [
        character
        for character in ascii_value.upper()
        if character.isalnum()
    ]

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
    """Return locked active batches for product in FEFO order."""

    return list(
        InventoryBatch.objects
        .select_for_update()
        .filter(
            product=product,
            status=InventoryBatch.Status.ACTIVE,
            boxes__gt=0,
        )
        .order_by("best_before", "batch_id")
    )


def _build_batch_pick_plan(
    *,
    batches: Iterable[InventoryBatch],
    requested_boxes: int,
    reserved_boxes_by_batch_id: dict[int, int],
) -> BatchPickPlan:
    """Build a FEFO pick plan from candidate batches.

    This is pure planning except for one deliberate side effect:
    reserved_boxes_by_batch_id is mutated so subsequent order lines see boxes
    already planned by earlier lines.
    """

    remaining_boxes = requested_boxes
    available_boxes = 0
    picks: list[BatchPick] = []

    for batch in batches:
        if remaining_boxes == 0:
            break

        allocatable_boxes = _allocatable_boxes(
            batch=batch,
            reserved_boxes_by_batch_id=reserved_boxes_by_batch_id,
        )

        if allocatable_boxes <= 0:
            continue

        available_boxes += allocatable_boxes
        boxes_to_pick = min(allocatable_boxes, remaining_boxes)

        picks.append(
            BatchPick(
                batch=batch,
                boxes=boxes_to_pick,
            )
        )

        _reserve_planned_boxes(
            batch=batch,
            boxes=boxes_to_pick,
            reserved_boxes_by_batch_id=reserved_boxes_by_batch_id,
        )

        remaining_boxes -= boxes_to_pick

    return BatchPickPlan(
        picks=picks,
        available_boxes=available_boxes,
        missing_boxes=remaining_boxes,
    )


def _allocatable_boxes(
    *,
    batch: InventoryBatch,
    reserved_boxes_by_batch_id: dict[int, int],
) -> int:
    already_reserved = reserved_boxes_by_batch_id.get(batch.id, 0)
    return batch.boxes - already_reserved


def _reserve_planned_boxes(
    *,
    batch: InventoryBatch,
    boxes: int,
    reserved_boxes_by_batch_id: dict[int, int],
) -> None:
    already_reserved = reserved_boxes_by_batch_id.get(batch.id, 0)
    reserved_boxes_by_batch_id[batch.id] = already_reserved + boxes
