"""
Inventory application services.

These functions coordinate inventory use-cases. They may call model methods,
perform database queries, and define transaction boundaries. They should not
contain presentation/UI logic.
"""

from __future__ import annotations

import unicodedata
from datetime import date

from django.db import IntegrityError, transaction

from inventory.errors import InvalidStockOperation
from inventory.models import InventoryBatch, normalize_batch_id
from products.models import Product
from reservations.selectors import (
    active_reserved_quantity_for_batch_pk,
)

BATCH_ID_SEQUENCE_WIDTH = 3
BATCH_ID_GENERATION_ATTEMPTS = 3
BATCH_ID_MISSING_PRODUCT_CODE = "PX"
BATCH_ID_TEXT_PART_LENGTH = 3


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
        raise InvalidStockOperation(
            "best_before date must be in the future"
        )

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
        generated_batch_id = _generate_batch_id(
            product=product,
        )

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

    raise InvalidStockOperation(
        "Could not generate a unique batch id"
    )


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
        InventoryBatch.objects
        .select_for_update()
        .select_related("product")
        .get(pk=batch.pk)
    )

    if batch.status == InventoryBatch.Status.CLOSED:
        raise InvalidStockOperation(
            f"Batch {batch.batch_id} is closed"
        )

    reserved_quantity = (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
    )

    if quantity < reserved_quantity:
        raise InvalidStockOperation(
            f"Cannot set batch {batch.batch_id} to {quantity} units; "
            f"{reserved_quantity} units are reserved."
        )

    batch.adjust_quantity(
        quantity=quantity,
    )

    batch.best_before = best_before
    batch.location = location
    batch.save(
        update_fields=[
            "best_before",
            "location",
            "updated_at",
        ]
    )
    batch.mark_as_edited(
        user=user,
    )

    return batch


@transaction.atomic
def close_batch(
    *,
    batch: InventoryBatch,
    user=None,
) -> InventoryBatch:
    """Close a batch so it is no longer orderable."""

    batch = (
        InventoryBatch.objects
        .select_for_update()
        .select_related("product")
        .get(pk=batch.pk)
    )

    reserved_quantity = (
        active_reserved_quantity_for_batch_pk(
            batch_pk=batch.pk,
        )
    )

    if reserved_quantity > 0:
        raise InvalidStockOperation(
            f"Cannot close batch {batch.batch_id}; "
            f"{reserved_quantity} units are reserved."
        )

    batch.close(
        user=user,
    )

    return batch


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
    batch.mark_as_created(
        user=user,
    )

    return batch


def _generate_batch_id(
    *,
    product: Product,
) -> str:
    """Generate the next local batch id for a product.

    Format:
        P004-TUT-SOU-001
    """

    prefix = _batch_id_prefix(
        product,
    )

    latest_batch = (
        InventoryBatch.objects
        .filter(
            batch_id__startswith=f"{prefix}-",
        )
        .order_by("-batch_id")
        .first()
    )

    if latest_batch is None:
        next_number = 1
    else:
        last_number = int(
            latest_batch.batch_id.rsplit("-", 1)[1]
        )
        next_number = last_number + 1

    return (
        f"{prefix}-"
        f"{next_number:0{BATCH_ID_SEQUENCE_WIDTH}d}"
    )


def _batch_id_prefix(
    product: Product,
) -> str:
    product_code = _batch_product_code(
        product,
    )

    return (
        f"{product_code}-"
        f"{_batch_text_part(product.brand)}-"
        f"{_batch_text_part(product.name)}"
    )


def _batch_product_code(
    product: Product,
) -> str:
    if product.internal_number:
        return f"P{product.internal_number:03d}"

    return BATCH_ID_MISSING_PRODUCT_CODE


def _batch_text_part(
    value: str,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )
    ascii_value = (
        normalized
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    characters = [
        character
        for character in ascii_value.upper()
        if character.isalnum()
    ]

    if not characters:
        return "XXX"

    return "".join(
        characters[:BATCH_ID_TEXT_PART_LENGTH]
    ).ljust(
        BATCH_ID_TEXT_PART_LENGTH,
        "X",
    )
