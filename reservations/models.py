"""Reservation persistence.

Allocation owns batch-level stock reservations for orders.

Dependency direction: reservations -> orders, inventory.
An Allocation cannot exist without its order, order line, and inventory batch;
an Order can exist without any Allocation.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from reservations.errors import InvalidAllocationStatusTransition


class Allocation(models.Model):
    """Batch-level stock reservation.

    RESERVED:
        Stock is claimed by an order.

        ``reserved_until=None`` represents a reservation without automatic
        expiry, used by the normal placed-order workflow.

        A future ``reserved_until`` represents a temporary reservation, such
        as stock held while a retail payment attempt is in progress.

        Once ``reserved_until`` has passed, the reservation no longer reduces
        availability even if cleanup has not yet changed its status.

    CONSUMED:
        The order was packed and physical stock was reduced.

    CANCELLED:
        The reservation was explicitly released.
    """

    class Status(models.TextChoices):
        RESERVED = "reserved", _("Reserved")
        CONSUMED = "consumed", _("Consumed")
        CANCELLED = "cancelled", _("Cancelled")

    ALLOWED_TRANSITIONS = {
        Status.RESERVED: {
            Status.CONSUMED,
            Status.CANCELLED,
        },
        Status.CONSUMED: set(),
        Status.CANCELLED: set(),
    }

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    order_line = models.ForeignKey(
        "orders.OrderLine",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    batch = models.ForeignKey(
        "inventory.InventoryBatch",
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RESERVED,
    )
    reserved_until = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        # Physical table is kept from when Allocation lived in `orders`.
        db_table = "orders_allocation"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["order", "status"]),
            models.Index(fields=["batch", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="allocation_quantity_gt_0",
            ),
        ]

    def _transition_to(self, target: str) -> None:
        if self.status == target:
            return

        allowed_targets = self.ALLOWED_TRANSITIONS[self.status]

        if target not in allowed_targets:
            raise InvalidAllocationStatusTransition(
                f"Cannot transition allocation {self.pk} "
                f"from {self.status!r} to {target!r}"
            )

        self.status = target
        self.save(update_fields=["status"])

    def consume(self) -> None:
        self._transition_to(self.Status.CONSUMED)

    def cancel(self) -> None:
        self._transition_to(self.Status.CANCELLED)

    def __str__(self) -> str:
        return f"{self.order_id} -> {self.batch_id}: {self.quantity}"
