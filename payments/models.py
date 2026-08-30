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

    Provider identifiers belong here because they identify this specific
    external payment attempt, not the order as a whole.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Provider(models.TextChoices):
        SUMUP = "sumup", "SumUp"

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

    provider = models.CharField(
        max_length=32,
        choices=Provider.choices,
        default=Provider.SUMUP,
    )

    provider_payment_id = models.CharField(
        max_length=255,
        blank=True,
    )

    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
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
            models.Index(
                fields=[
                    "provider",
                    "provider_payment_id",
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
            models.UniqueConstraint(
                fields=[
                    "provider",
                    "provider_payment_id",
                ],
                condition=~Q(
                    provider_payment_id="",
                ),
                name="unique_provider_payment_id",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Payment attempt {self.pk or 'new'} "
            f"for order {self.order_id}"
        )
