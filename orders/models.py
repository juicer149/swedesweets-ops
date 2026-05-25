"""
Order domain model.

Order owns the order lifecycle.

OrderLine owns the product quantity requested by the order. For operational
simplicity, services normalize input quantities to boxes and store one order line
per product per order.

Allocation owns batch-level reservations for placed orders.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from orders.errors import (
    InvalidAllocationStatusTransition,
    InvalidOrderStatusTransition,
)


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PLACED = "placed", "Placed"
        PACKED = "packed", "Packed"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class CancelReason(models.TextChoices):
        CUSTOMER_REQUEST = "customer_request", "Customer request"
        ORDER_ENTRY_ERROR = "order_entry_error", "Order entry error"
        DUPLICATE_ORDER = "duplicate_order", "Duplicate order"
        OUT_OF_STOCK = "out_of_stock", "Out of stock"
        OTHER = "other", "Other"

    ALLOWED_TRANSITIONS = {
        Status.DRAFT: {Status.PLACED, Status.CANCELLED},
        Status.PLACED: {Status.PACKED, Status.CANCELLED},
        Status.PACKED: {Status.DELIVERED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    edited_at = models.DateTimeField(null=True, blank=True)

    placed_at = models.DateTimeField(null=True, blank=True)
    packed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders_edited",
    )
    placed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders_placed",
    )
    packed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders_packed",
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders_delivered",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders_cancelled",
    )

    cancel_reason = models.CharField(
        max_length=40,
        blank=True,
        choices=CancelReason.choices,
    )
    cancel_note = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["edited_at"]),
            models.Index(fields=["placed_at"]),
            models.Index(fields=["packed_at"]),
            models.Index(fields=["delivered_at"]),
            models.Index(fields=["cancelled_at"]),
        ]

    @property
    def can_be_edited(self) -> bool:
        return self.status == self.Status.PLACED

    @property
    def can_be_cancelled(self) -> bool:
        return self.status in {
            self.Status.DRAFT,
            self.Status.PLACED,
        }

    def _transition_to(self, target: str) -> None:
        if self.status == target:
            return

        allowed_targets = self.ALLOWED_TRANSITIONS[self.status]

        if target not in allowed_targets:
            raise InvalidOrderStatusTransition(
                f"Cannot transition order {self.pk} "
                f"from {self.status!r} to {target!r}"
            )

        self.status = target

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

    def mark_as_placed(self, *, user=None) -> None:
        self._transition_to(self.Status.PLACED)
        self.placed_at = timezone.now()
        self.placed_by = user
        self.save(
            update_fields=[
                "status",
                "placed_at",
                "placed_by",
                "updated_at",
            ]
        )

    def mark_as_packed(self, *, user=None) -> None:
        self._transition_to(self.Status.PACKED)
        self.packed_at = timezone.now()
        self.packed_by = user
        self.save(
            update_fields=[
                "status",
                "packed_at",
                "packed_by",
                "updated_at",
            ]
        )

    def mark_as_delivered(self, *, user=None) -> None:
        self._transition_to(self.Status.DELIVERED)
        self.delivered_at = timezone.now()
        self.delivered_by = user
        self.save(
            update_fields=[
                "status",
                "delivered_at",
                "delivered_by",
                "updated_at",
            ]
        )

    def cancel(
        self,
        *,
        user=None,
        reason: str = "",
        note: str = "",
    ) -> None:
        self._transition_to(self.Status.CANCELLED)
        self.cancelled_at = timezone.now()
        self.cancelled_by = user
        self.cancel_reason = reason
        self.cancel_note = note.strip()
        self.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancelled_by",
                "cancel_reason",
                "cancel_note",
                "updated_at",
            ]
        )

    def __str__(self) -> str:
        return f"Order {self.pk}"


class OrderLine(models.Model):
    class Unit(models.TextChoices):
        BOXES = "boxes", "Boxes"
        KG = "kg", "Kg"
        GRAMS = "grams", "Grams"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, choices=Unit.choices)
    quantity_in_boxes = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="unique_product_per_order",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="orderline_quantity_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_in_boxes__gt=0),
                name="orderline_quantity_in_boxes_gt_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product.sku}: {self.quantity} {self.unit}"


class Allocation(models.Model):
    """Batch-level reservation.

    RESERVED:
        Stock is reserved for a placed order.

    CONSUMED:
        Order was packed and physical stock was reduced.

    CANCELLED:
        Reservation was released.
    """

    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        CONSUMED = "consumed", "Consumed"
        CANCELLED = "cancelled", "Cancelled"

    ALLOWED_TRANSITIONS = {
        Status.RESERVED: {
            Status.CONSUMED,
            Status.CANCELLED,
        },
        Status.CONSUMED: set(),
        Status.CANCELLED: set(),
    }

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    order_line = models.ForeignKey(
        OrderLine,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    batch = models.ForeignKey(
        "inventory.InventoryBatch",
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    boxes = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RESERVED,
    )

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["order", "status"]),
            models.Index(fields=["batch", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(boxes__gt=0),
                name="allocation_boxes_gt_0",
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
        return f"{self.order_id} -> {self.batch_id}: {self.boxes}"
