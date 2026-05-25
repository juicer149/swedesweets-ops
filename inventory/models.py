"""
Inventory domain model.

class InventoryBatch
fields:
    batch_id, product(FK), boxes, best_before, location, status

public API:
    .is_available
        -> True when batch is ACTIVE and has boxes > 0.

    .save(*args, **kwargs)
        -> Normalize fields and protect local invariants before saving.

    .adjust_boxes(boxes: int)
        -> Absolute inventory correction: current boxes = boxes.

    .pick(boxes: int)
        -> Order fulfillment: current boxes -= boxes.

    .close()
        -> Move batch lifecycle status to CLOSED.
"""
from __future__ import annotations

from django.db import models

from inventory.errors import (
    InvalidBatchStatusTransition,
    InvalidStockOperation,
)


def normalize_batch_id(value: str) -> str:
    value = value.strip().upper()

    if not value:
        raise InvalidStockOperation("batch id must not be empty")

    return value


def normalize_location(value: str) -> str:
    value = " ".join(value.strip().split())

    if not value:
        raise InvalidStockOperation("location must not be empty")

    return value


class InventoryBatch(models.Model):
    """Physical stock.

    InventoryBatch owns physical boxes and physical lifecycle.

    Reservation ownership belongs to orders.Allocation. This model should know
    how physical stock changes, but it should not know how orders reserve stock
    or how allocations are stored.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEPLETED = "depleted", "Depleted"
        CLOSED = "closed", "Closed"

    ALLOWED_STATUS_TRANSITIONS = {
        Status.ACTIVE: {Status.DEPLETED, Status.CLOSED},
        Status.DEPLETED: {Status.ACTIVE, Status.CLOSED},
        Status.CLOSED: set(),
    }

    batch_id = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="batches",
    )
    boxes = models.PositiveIntegerField()
    best_before = models.DateField()
    location = models.CharField(max_length=120)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["best_before", "batch_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(boxes__gte=0),
                name="inventorybatch_boxes_gte_0",
            ),
        ]

    @property
    def is_available(self) -> bool:
        return self.status == self.Status.ACTIVE and self.boxes > 0

    @staticmethod
    def _validate_positive_boxes(boxes: int) -> None:
        if boxes <= 0:
            raise InvalidStockOperation("boxes must be positive")

    @staticmethod
    def _validate_non_negative_boxes(boxes: int) -> None:
        if boxes < 0:
            raise InvalidStockOperation("boxes must be non-negative")

    def _transition_to(self, new_status: str) -> None:
        """Move batch to a new lifecycle status if the transition is allowed.

        This method is private on purpose. Public methods should describe the
        business event that caused the transition: pick(), adjust_boxes(),
        close(), return_boxes() later, etc.
        """

        old_status = self.status

        if old_status == new_status:
            return

        allowed_targets = self.ALLOWED_STATUS_TRANSITIONS[old_status]

        if new_status not in allowed_targets:
            raise InvalidBatchStatusTransition(
                f"Cannot transition batch {self.batch_id} "
                f"from {old_status!r} to {new_status!r}"
            )

        self.status = new_status

    def _sync_status_from_boxes(self) -> None:
        """Synchronize lifecycle status from physical box count.

        For normal stock states:

            boxes > 0   -> ACTIVE
            boxes == 0  -> DEPLETED

        CLOSED is terminal in this MVP and is not reopened implicitly. If a closed
        batch should ever be reused, that should become an explicit business
        operation, not a side effect of changing boxes.
        """

        if self.status == self.Status.CLOSED:
            return

        next_status = (
            self.Status.ACTIVE
            if self.boxes > 0
            else self.Status.DEPLETED
        )

        self._transition_to(next_status)

    def _protect_status_transition(self) -> None:
        if self.pk is None:
            return

        persisted_status = (
            type(self).objects
            .only("status")
            .get(pk=self.pk)
            .status
        )

        if persisted_status == self.status:
            return

        allowed_targets = self.ALLOWED_STATUS_TRANSITIONS[persisted_status]

        if self.status not in allowed_targets:
            raise InvalidBatchStatusTransition(
                f"Cannot transition batch {self.batch_id} "
                f"from {persisted_status!r} to {self.status!r}"
            )

    def save(self, *args, **kwargs) -> None:
        """Normalize fields and protect local invariants before saving.

        This method respects update_fields. If a caller saves only boxes/status,
        it does not accidentally add unrelated fields like batch_id or location
        to the database UPDATE.

        boxes and status are coupled, so when stock state is saved, status may be
        added to update_fields after synchronization.
        """

        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)

        should_save_all_fields = update_fields is None
        should_handle_batch_id = should_save_all_fields or "batch_id" in update_fields
        should_handle_location = should_save_all_fields or "location" in update_fields
        should_handle_stock_state = (
            should_save_all_fields
            or "boxes" in update_fields
            or "status" in update_fields
        )

        if should_handle_batch_id:
            self.batch_id = normalize_batch_id(self.batch_id)

        if should_handle_location:
            self.location = normalize_location(self.location)

        if should_handle_stock_state:
            self._validate_non_negative_boxes(self.boxes)
            self._sync_status_from_boxes()
            self._protect_status_transition()

            if update_fields is not None:
                update_fields.add("status")

        if update_fields is not None:
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)

    def adjust_boxes(self, *, boxes: int) -> None:
        """Set physical box count after inventory correction.

        This is an absolute edit:

            current boxes = boxes

        Use this when the system's recorded number should be corrected to match
        reality, for example after manual inventory counting.

        This method may reactivate a DEPLETED batch if the corrected physical
        count is greater than zero. It may not reopen CLOSED batches.
        """

        if self.status == self.Status.CLOSED:
            raise InvalidStockOperation(f"Batch {self.batch_id} is closed")

        self._validate_non_negative_boxes(boxes)

        self.boxes = boxes
        self._sync_status_from_boxes()

        self.save(update_fields=["boxes", "status"])

    def _remove_boxes(self, *, boxes: int) -> None:
        """Decrease physical boxes in memory.

        This method contains the shared mechanics for reducing stock:

            validate input
            ensure enough boxes exist
            subtract boxes
            synchronize status

        It deliberately does not save. Public domain methods such as pick() should
        call this method and then decide what should be persisted.

        The method is private because "remove boxes" is not a complete business
        reason by itself. A caller should usually say why stock is being removed:
        picked for an order, damaged, expired, wasted, or corrected.
        """

        self._validate_positive_boxes(boxes)

        if boxes > self.boxes:
            raise InvalidStockOperation(
                f"Cannot remove {boxes} boxes from batch {self.batch_id}; "
                f"only {self.boxes} available"
            )

        self.boxes -= boxes
        self._sync_status_from_boxes()

    def pick(self, *, boxes: int) -> None:
        """Remove boxes because they were picked for order fulfillment.

        This updates physical stock only.

        Reservation logic belongs to orders.Allocation. The order layer should
        ensure that a pick corresponds to valid reserved allocations.
        """

        if not self.is_available:
            raise InvalidStockOperation(f"Batch {self.batch_id} is not available")

        self._remove_boxes(boxes=boxes)
        self.save(update_fields=["boxes", "status"])

    def close(self) -> None:
        """Close this batch.

        Closing removes the batch from normal stock operations. It does not change
        the physical box count. CLOSED is terminal for this MVP.
        """

        self._transition_to(self.Status.CLOSED)
        self.save(update_fields=["status"])

    def __str__(self) -> str:
        return f"{self.batch_id} - {self.product} ({self.boxes} boxes)"
