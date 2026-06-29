"""
Inventory domain model.

class InventoryBatch
fields:
    batch_id, product(FK), quantity, best_before, location, status

public API:
    .is_available
        -> True when batch is ACTIVE and has quantity > 0.

    .save(*args, **kwargs)
        -> Normalize fields and protect local invariants before saving.

    .adjust_quantity(quantity: int)
        -> Absolute inventory correction: current quantity = quantity.

    .pick(quantity: int)
        -> Order fulfillment: current quantity -= quantity.

    .close(user=None)
        -> Move batch lifecycle status to CLOSED.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

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

    InventoryBatch owns physical stock quantity and physical lifecycle.

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
    quantity = models.PositiveIntegerField()
    best_before = models.DateField()
    location = models.CharField(max_length=120)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    edited_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_batches_created",
    )
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_batches_edited",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_batches_closed",
    )

    class Meta:
        ordering = ["best_before", "batch_id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["edited_at"]),
            models.Index(fields=["closed_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="inventorybatch_quantity_gte_0",
            ),
        ]

    @property
    def is_available(self) -> bool:
        return self.status == self.Status.ACTIVE and self.quantity > 0

    @staticmethod
    def _validate_positive_quantity(quantity: int) -> None:
        if quantity <= 0:
            raise InvalidStockOperation("quantity must be positive")

    @staticmethod
    def _validate_non_negative_quantity(quantity: int) -> None:
        if quantity < 0:
            raise InvalidStockOperation("quantity must be non-negative")

    def _transition_to(self, new_status: str) -> None:
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

    def _sync_status_from_quantity(self) -> None:
        """Synchronize lifecycle status from physical stock quantity.

        For normal stock states:

            quantity > 0   -> ACTIVE
            quantity == 0  -> DEPLETED

        CLOSED is terminal in this MVP and is not reopened implicitly.
        """

        if self.status == self.Status.CLOSED:
            return

        next_status = self.Status.ACTIVE if self.quantity > 0 else self.Status.DEPLETED

        self._transition_to(next_status)

    def _protect_status_transition(self) -> None:
        if self.pk is None:
            return

        persisted_status = type(self).objects.only("status").get(pk=self.pk).status

        if persisted_status == self.status:
            return

        allowed_targets = self.ALLOWED_STATUS_TRANSITIONS[persisted_status]

        if self.status not in allowed_targets:
            raise InvalidBatchStatusTransition(
                f"Cannot transition batch {self.batch_id} "
                f"from {persisted_status!r} to {self.status!r}"
            )

    def save(self, *args, **kwargs) -> None:
        """Normalize fields and protect local invariants before saving."""

        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)

        should_save_all_fields = update_fields is None
        should_handle_batch_id = should_save_all_fields or "batch_id" in update_fields
        should_handle_location = should_save_all_fields or "location" in update_fields
        should_handle_stock_state = (
            should_save_all_fields
            or "quantity" in update_fields
            or "status" in update_fields
        )

        if should_handle_batch_id:
            self.batch_id = normalize_batch_id(self.batch_id)

        if should_handle_location:
            self.location = normalize_location(self.location)

        if should_handle_stock_state:
            self._validate_non_negative_quantity(self.quantity)
            self._sync_status_from_quantity()
            self._protect_status_transition()

            if update_fields is not None:
                update_fields.add("status")

        if update_fields is not None:
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)

    def mark_as_created(self, *, user=None) -> None:
        self.created_by = user
        self.save(
            update_fields=[
                "created_by",
                "updated_at",
            ]
        )

    def mark_as_edited(self, *, user=None) -> None:
        self.edited_at = timezone.now()
        self.edited_by = user
        self.save(
            update_fields=[
                "edited_at",
                "edited_by",
                "updated_at",
            ]
        )

    def adjust_quantity(self, *, quantity: int) -> None:
        """Set physical stock count after inventory correction."""

        if self.status == self.Status.CLOSED:
            raise InvalidStockOperation(f"Batch {self.batch_id} is closed")

        self._validate_non_negative_quantity(quantity)

        self.quantity = quantity
        self._sync_status_from_quantity()

        self.save(update_fields=["quantity", "status", "updated_at"])

    def _remove_quantity(self, *, quantity: int) -> None:
        """Decrease physical stock quantity in memory.

        This method deliberately does not save. Public domain methods such as
        pick() should call this method and then decide what should be persisted.
        """

        self._validate_positive_quantity(quantity)

        if quantity > self.quantity:
            raise InvalidStockOperation(
                f"Cannot remove {quantity} units from batch {self.batch_id}; "
                f"only {self.quantity} available"
            )

        self.quantity -= quantity
        self._sync_status_from_quantity()

    def pick(self, *, quantity: int) -> None:
        """Remove stock because it was picked for order fulfillment."""

        if not self.is_available:
            raise InvalidStockOperation(f"Batch {self.batch_id} is not available")

        self._remove_quantity(quantity=quantity)
        self.save(update_fields=["quantity", "status", "updated_at"])

    def close(self, *, user=None) -> None:
        """Close this batch.

        Closing removes the batch from normal stock operations. It does not change
        the physical quantity. CLOSED is terminal for this MVP.
        """

        self._transition_to(self.Status.CLOSED)
        self.closed_at = timezone.now()
        self.closed_by = user
        self.save(
            update_fields=[
                "status",
                "closed_at",
                "closed_by",
                "updated_at",
            ]
        )

    def __str__(self) -> str:
        return (
            f"{self.batch_id} - {self.product} "
            f"({self.product.stock_quantity_label(self.quantity)})"
        )
