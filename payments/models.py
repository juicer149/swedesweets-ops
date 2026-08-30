from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q


class PaymentAttempt(models.Model):
    """One attempt to pay for an order.

    PaymentAttempt owns payment lifecycle state.

    Order owns the commercial purchase and its price snapshots.
    PaymentAttempt snapshots the amount and currency that this specific
    payment attempt was created for.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment_attempts",
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-id",
        ]
        indexes = [
            models.Index(
                fields=[
                    "order",
                    "status",
                ],
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    amount__gt=Decimal("0.00"),
                ),
                name="payment_attempt_amount_positive",
            ),
            models.UniqueConstraint(
                fields=[
                    "order",
                ],
                condition=Q(
                    status="pending",
                ),
                name="one_pending_payment_attempt_per_order",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Payment attempt {self.pk or 'new'} "
            f"for order {self.order_id}"
        )
