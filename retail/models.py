from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q


MAX_RETAIL_COUNTRY_CODE_LENGTH = 2
MAX_RETAIL_POSTAL_CODE_LENGTH = 10
MAX_RETAIL_CITY_LENGTH = 120


def normalize_country_code(value: str) -> str:
    return value.strip().upper()


def normalize_postal_code(value: str) -> str:
    return value.strip()


def normalize_city(value: str) -> str:
    return " ".join(value.strip().split())


class RetailPostalArea(models.Model):
    """A destination where retail orders may be delivered.

    Postal areas are reference data, expected to be populated from an
    authoritative external source.

    `enabled` is a local business override. It allows SwedeSweets to disable a
    destination without deleting the underlying postal reference data.
    """

    country_code = models.CharField(
        max_length=MAX_RETAIL_COUNTRY_CODE_LENGTH,
    )
    postal_code = models.CharField(
        max_length=MAX_RETAIL_POSTAL_CODE_LENGTH,
    )
    city = models.CharField(
        max_length=MAX_RETAIL_CITY_LENGTH,
    )

    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "country_code",
            "postal_code",
            "city",
        ]
        indexes = [
            models.Index(fields=["country_code", "postal_code"]),
            models.Index(fields=["enabled"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "country_code",
                    "postal_code",
                    "city",
                ],
                name="unique_retail_postal_area",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        self.country_code = normalize_country_code(self.country_code)
        self.postal_code = normalize_postal_code(self.postal_code)
        self.city = normalize_city(self.city)

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.postal_code} {self.city}, {self.country_code}"


class RetailPrice(models.Model):
    """Current default retail price for a product.

    Batch-specific clearance pricing belongs to RetailBatchOffer.
    """

    product = models.OneToOneField(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="retail_price",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    currency = models.CharField(
        max_length=3,
        default="EUR",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="retail_price_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product}: {self.amount} {self.currency}"


class RetailBatchOffer(models.Model):
    """Retail configuration for one physical inventory batch.

    The inventory batch owns physical truth: quantity, expiry and lifecycle.
    This model only describes whether that batch has deliberately been offered
    through the retail sales channel and at what price.

    `enabled` expresses operator intent. Actual sellability is derived from this
    configuration together with current inventory state.
    """

    batch = models.OneToOneField(
        "inventory.InventoryBatch",
        on_delete=models.CASCADE,
        related_name="retail_offer",
    )
    enabled = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["enabled"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gt=Decimal("0.00")),
                name="retail_batch_offer_price_positive_or_null",
            ),
            models.CheckConstraint(
                condition=Q(enabled=False) | Q(price__isnull=False),
                name="retail_batch_offer_enabled_requires_price",
            ),
        ]

    def __str__(self) -> str:
        state = "enabled" if self.enabled else "disabled"
        return f"{self.batch.batch_id}: retail {state}"


class RetailOrder(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone_number = models.CharField(max_length=40)

    country = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=10)
    city = models.CharField(max_length=120)
    address_line = models.CharField(max_length=255)

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Retail order #{self.pk or 'new'}"


class RetailOrderLine(models.Model):
    order = models.ForeignKey(
        RetailOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="retail_order_lines",
    )

    quantity = models.PositiveIntegerField()

    unit_price_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="retail_order_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price_snapshot__gt=Decimal("0.00")),
                name="retail_order_line_unit_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=Decimal("0.00")),
                name="retail_order_line_total_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product}"
