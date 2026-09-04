from __future__ import annotations

import uuid
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


class RetailProductOffer(models.Model):
    """General retail offer for one product SKU.

    The offer owns commercial eligibility and price for the ordinary retail
    product pool.

    Physical batches with an enabled RetailBatchOffer form separate commercial
    offers and are excluded from this offer's stock pool.
    """

    product = models.OneToOneField(
        "products.Product",
        on_delete=models.PROTECT,
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
                name="retail_product_offer_price_positive_or_null",
            ),
            models.CheckConstraint(
                condition=Q(enabled=False) | Q(price__isnull=False),
                name="retail_product_offer_enabled_requires_price",
            ),
        ]

    def __str__(self) -> str:
        state = "enabled" if self.enabled else "disabled"
        return f"{self.product}: retail {state}"


class RetailBatchOffer(models.Model):
    """Retail offer for one exact physical inventory batch.

    A batch offer is a separate commercial offer, not an override of a product
    offer. Its stock pool consists only of the configured physical batch.
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


class RetailCart(models.Model):
    """Mutable retail purchase intent before an Order exists.

    A cart is deliberately weaker than an order:
    it owns only the selected retail offers and quantities.

    Buyer data, price snapshots, stock reservations and payment state belong
    to later checkout/order stages.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Retail cart {self.pk}"


class RetailCartLine(models.Model):
    """One selected retail offer in a mutable cart.

    Exactly one of product_offer and batch_offer must be present.

    Price is intentionally not snapshotted here. The selected offer is
    re-resolved when the cart is converted into an order.
    """

    cart = models.ForeignKey(
        RetailCart,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    product_offer = models.ForeignKey(
        RetailProductOffer,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart_lines",
    )

    batch_offer = models.ForeignKey(
        RetailBatchOffer,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart_lines",
    )

    quantity = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        product_offer__isnull=False,
                        batch_offer__isnull=True,
                    )
                    | Q(
                        product_offer__isnull=True,
                        batch_offer__isnull=False,
                    )
                ),
                name="retail_cart_line_exactly_one_offer",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="retail_cart_line_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=["cart", "product_offer"],
                condition=Q(product_offer__isnull=False),
                name="unique_retail_product_offer_per_cart",
            ),
            models.UniqueConstraint(
                fields=["cart", "batch_offer"],
                condition=Q(batch_offer__isnull=False),
                name="unique_retail_batch_offer_per_cart",
            ),
        ]

    def __str__(self) -> str:
        if self.product_offer_id is not None:
            offer = f"product offer {self.product_offer_id}"
        else:
            offer = f"batch offer {self.batch_offer_id}"

        return f"Cart {self.cart_id}: {self.quantity} × {offer}"


class RetailCheckoutSession(models.Model):
    """Short-lived ownership of a retail checkout.

    The related Order owns buyer snapshot, order lines, commercial price
    snapshots and fulfillment lifecycle.

    This model owns only checkout-specific state that should not become part of
    the channel-agnostic order model.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="retail_checkout",
    )

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"Retail checkout {self.pk}"


class RetailOfferSelection(models.Model):
    """Retail commercial origin for one generic order line.

    OrderLine owns durable product, quantity and price snapshot.

    RetailOfferSelection owns only the retail-specific information needed to
    determine which stock pool may satisfy that line.

    Exactly one of product_offer and batch_offer must be present.
    """

    order_line = models.OneToOneField(
        "orders.OrderLine",
        on_delete=models.CASCADE,
        related_name="retail_offer_selection",
    )

    product_offer = models.ForeignKey(
        RetailProductOffer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_line_selections",
    )

    batch_offer = models.ForeignKey(
        RetailBatchOffer,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="order_line_selections",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        product_offer__isnull=False,
                        batch_offer__isnull=True,
                    )
                    | Q(
                        product_offer__isnull=True,
                        batch_offer__isnull=False,
                    )
                ),
                name="retail_offer_selection_exactly_one_offer",
            ),
        ]

    def __str__(self) -> str:
        if self.product_offer_id is not None:
            return (
                f"Order line {self.order_line_id} "
                f"-> product offer {self.product_offer_id}"
            )

        return (
            f"Order line {self.order_line_id} "
            f"-> batch offer {self.batch_offer_id}"
        )
