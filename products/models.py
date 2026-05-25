"""
Product domain model.

Product is the stable operational object used by orders and inventory.

Stable identity:
    id
    sku
    weight_per_box

Editable catalog data:
    internal_number
    manufacturer
    brand
    name
    active
    vegan

ProductProfile stores optional future catalog data without touching the
operational product identity.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Iterable

from django.db import models

from products.catalog import (
    MAX_IMAGE_URL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_SKU_LENGTH,
    MAX_WEIGHT_PER_BOX,
    MIN_WEIGHT_PER_BOX,
    make_sku,
    normalize_optional_text,
    normalize_required_text,
    validate_internal_number,
    validate_weight_per_box,
)
from products.errors import InvalidProductData


IMMUTABLE_PRODUCT_IDENTITY_FIELDS = frozenset(
    {
        "weight_per_box",
        "sku",
    }
)


class Product(models.Model):
    """Sellable product.

    SKU is generated when the product is created and then kept stable.

    internal_number, manufacturer, brand and name are editable catalog data.
    weight_per_box is immutable because order conversions and inventory stock
    depend on it historically.
    """

    internal_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="Informal internal product number used with customers.",
    )

    manufacturer = models.CharField(
        max_length=MAX_NAME_LENGTH,
        blank=True,
        help_text="Manufacturer or producer, e.g. Fazer, Cloetta, BUBS.",
    )

    brand = models.CharField(
        max_length=MAX_NAME_LENGTH,
        help_text="Brand or product line.",
    )

    name = models.CharField(
        max_length=MAX_NAME_LENGTH,
        help_text="Swedish/internal MVP product name.",
    )

    weight_per_box = models.PositiveIntegerField(
        help_text="Stored in grams.",
    )

    sku = models.CharField(
        max_length=MAX_SKU_LENGTH,
        unique=True,
        editable=False,
    )

    active = models.BooleanField(default=True)
    vegan = models.BooleanField(default=False)

    class Meta:
        ordering = [
            "internal_number",
            "brand",
            "name",
            "weight_per_box",
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(internal_number__isnull=True)
                    | models.Q(internal_number__gte=1)
                ),
                name="product_internal_number_positive_or_null",
            ),
            models.CheckConstraint(
                condition=models.Q(weight_per_box__gte=MIN_WEIGHT_PER_BOX),
                name="product_weight_per_box_at_least_min",
            ),
            models.CheckConstraint(
                condition=models.Q(weight_per_box__lte=MAX_WEIGHT_PER_BOX),
                name="product_weight_per_box_at_most_max",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        """Normalize fields, validate identity and protect immutable data."""

        update_fields = _normalize_update_fields(kwargs.get("update_fields"))
        is_create = self.pk is None

        self._normalize_catalog_fields(update_fields=update_fields)
        self._validate_identity_fields(update_fields=update_fields)

        if is_create:
            self._assign_initial_sku()
            update_fields = _add_update_field(update_fields, "sku")
        else:
            self._protect_immutable_identity(update_fields=update_fields)

        if update_fields is not None:
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)

    def _normalize_catalog_fields(
        self,
        *,
        update_fields: set[str] | None,
    ) -> None:
        if _should_handle(update_fields, "internal_number"):
            validate_internal_number(self.internal_number)

        if _should_handle(update_fields, "manufacturer"):
            self.manufacturer = normalize_optional_text(
                self.manufacturer,
                field_name="manufacturer",
            )

        if _should_handle(update_fields, "brand"):
            self.brand = normalize_required_text(
                self.brand,
                field_name="brand",
            )

        if _should_handle(update_fields, "name"):
            self.name = normalize_required_text(
                self.name,
                field_name="name",
            )

    def _validate_identity_fields(
        self,
        *,
        update_fields: set[str] | None,
    ) -> None:
        if _should_handle(update_fields, "weight_per_box"):
            validate_weight_per_box(self.weight_per_box)

    def _assign_initial_sku(self) -> None:
        self.sku = make_sku(
            internal_number=self.internal_number,
            brand=self.brand,
            name=self.name,
            weight_per_box=self.weight_per_box,
        )

    def _protect_immutable_identity(
        self,
        *,
        update_fields: set[str] | None,
    ) -> None:
        if not _touches_any(update_fields, IMMUTABLE_PRODUCT_IDENTITY_FIELDS):
            return

        self._raise_if_immutable_identity_changed()

    def _raise_if_immutable_identity_changed(self) -> None:
        persisted = (
            type(self).objects
            .only("weight_per_box", "sku")
            .get(pk=self.pk)
        )

        if self.weight_per_box != persisted.weight_per_box:
            raise InvalidProductData(
                "weight_per_box cannot be changed after product creation"
            )

        if self.sku != persisted.sku:
            raise InvalidProductData(
                "sku cannot be changed after product creation"
            )

    def display_name(self, *, language: str = "sv") -> str:
        """Return display name.

        MVP uses the Swedish/internal product name. The language argument keeps
        the call site future-compatible with product translations.
        """

        return self.name

    def grams_to_boxes(self, *, grams: int) -> int:
        """Convert grams into whole boxes for this product."""

        if grams <= 0:
            raise InvalidProductData("grams must be positive")

        return (grams + self.weight_per_box - 1) // self.weight_per_box

    def kg_to_boxes(self, *, kg: Decimal) -> int:
        """Convert kilograms into whole boxes for this product."""

        if kg <= 0:
            raise InvalidProductData("kg must be positive")

        grams = (kg * Decimal("1000")).to_integral_value(
            rounding=ROUND_CEILING
        )

        return self.grams_to_boxes(grams=int(grams))

    def boxes_to_grams(self, *, boxes: int) -> int:
        """Convert whole boxes into grams for this product."""

        if boxes <= 0:
            raise InvalidProductData("boxes must be positive")

        return boxes * self.weight_per_box

    def boxes_to_kg(self, *, boxes: int) -> Decimal:
        """Convert whole boxes into kilograms."""

        grams = self.boxes_to_grams(boxes=boxes)
        return Decimal(grams) / Decimal("1000")

    def __str__(self) -> str:
        return self.sku


class ProductProfile(models.Model):
    """Optional editable catalog information for a product.

    This is separate from Product because description, ingredients and image are
    presentation/catalog data, not inventory/order identity.
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    description = models.TextField(blank=True)
    ingredients = models.TextField(blank=True)

    image_url = models.URLField(
        max_length=MAX_IMAGE_URL_LENGTH,
        blank=True,
        help_text="External image URL. Prefer this over uploads for MVP/Railway.",
    )

    class Meta:
        ordering = ["product__brand", "product__name"]

    def __str__(self) -> str:
        return self.product.sku


def _normalize_update_fields(
    update_fields: Iterable[str] | None,
) -> set[str] | None:
    if update_fields is None:
        return None

    return set(update_fields)


def _should_handle(
    update_fields: set[str] | None,
    field_name: str,
) -> bool:
    return update_fields is None or field_name in update_fields


def _touches_any(
    update_fields: set[str] | None,
    field_names: frozenset[str],
) -> bool:
    if update_fields is None:
        return True

    return bool(update_fields & field_names)


def _add_update_field(
    update_fields: set[str] | None,
    field_name: str,
) -> set[str] | None:
    if update_fields is None:
        return None

    update_fields.add(field_name)
    return update_fields
