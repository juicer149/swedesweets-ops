"""
Product domain model.

Product is the stable operational object used by orders and inventory.

Stable identity:
    id
    sku
    weight_per_unit
    stock_unit

Editable catalog data:
    internal_number
    manufacturer
    brand
    name
    active
    vegan

ProductProfile stores optional catalog data without touching the operational
product identity.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Iterable

from django.db import models

from products.catalog import (
    MAX_IMAGE_URL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_SKU_LENGTH,
    MAX_WEIGHT_PER_UNIT,
    MIN_WEIGHT_PER_UNIT,
    make_sku,
    normalize_optional_text,
    normalize_required_text,
    validate_internal_number,
    validate_weight_per_unit,
)
from products.errors import InvalidProductData


IMMUTABLE_PRODUCT_IDENTITY_FIELDS = frozenset(
    {
        "weight_per_unit",
        "stock_unit",
        "sku",
    }
)


class Product(models.Model):
    """Sellable product.

    SKU is generated when the product is created and then kept stable.

    internal_number, manufacturer, brand and name are editable catalog data.
    weight_per_unit and stock_unit are immutable because order conversions,
    inventory stock and historical labels depend on them.
    """

    class StockUnit(models.TextChoices):
        BOX = "box", "Box"
        PIECE = "piece", "Piece"
        BAG = "bag", "Bag"
        CASE = "case", "Case"

    STOCK_UNIT_PLURALS = {
        StockUnit.BOX.value: "boxes",
        StockUnit.PIECE.value: "pieces",
        StockUnit.BAG.value: "bags",
        StockUnit.CASE.value: "cases",
    }

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

    weight_per_unit = models.PositiveIntegerField(
        help_text="Weight in grams for one physical stock unit.",
    )

    stock_unit = models.CharField(
        max_length=20,
        choices=StockUnit.choices,
        default=StockUnit.BOX,
        help_text="Physical inventory unit used for this product.",
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
            "weight_per_unit",
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
                condition=models.Q(weight_per_unit__gte=MIN_WEIGHT_PER_UNIT),
                name="product_weight_per_unit_at_least_min",
            ),
            models.CheckConstraint(
                condition=models.Q(weight_per_unit__lte=MAX_WEIGHT_PER_UNIT),
                name="product_weight_per_unit_at_most_max",
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
        if _should_handle(update_fields, "weight_per_unit"):
            validate_weight_per_unit(self.weight_per_unit)

        if _should_handle(update_fields, "stock_unit"):
            self._validate_stock_unit()

    def _validate_stock_unit(self) -> None:
        valid_units = {choice.value for choice in self.StockUnit}

        if self.stock_unit not in valid_units:
            raise InvalidProductData(f"Unsupported stock unit: {self.stock_unit}")

    def _assign_initial_sku(self) -> None:
        self.sku = make_sku(
            internal_number=self.internal_number,
            brand=self.brand,
            name=self.name,
            weight_per_unit=self.weight_per_unit,
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
            .only("weight_per_unit", "stock_unit", "sku")
            .get(pk=self.pk)
        )

        if self.weight_per_unit != persisted.weight_per_unit:
            raise InvalidProductData(
                "weight_per_unit cannot be changed after product creation"
            )

        if self.stock_unit != persisted.stock_unit:
            raise InvalidProductData(
                "stock_unit cannot be changed after product creation"
            )

        if self.sku != persisted.sku:
            raise InvalidProductData(
                "sku cannot be changed after product creation"
            )

    @property
    def display_name(self, *, language: str = "sv") -> str:
        """Human-readable product name for cards, selects and links."""
        parts = [self.brand, self.name]
        return " — ".join(str(part) for part in parts if part)

    @property
    def code_label(self) -> str:
        """Short code label for internal use and compact displays."""
        if self.internal_number:
            return f"#{self.internal_number}"
        return self.sku

    @property
    def stock_unit_singular(self) -> str:
        return self.stock_unit

    @property
    def stock_unit_plural(self) -> str:
        return self.STOCK_UNIT_PLURALS[self.stock_unit]

    @property
    def weight_label(self) -> str:
        return f"{self.weight_per_unit} g"

    @property
    def unit_weight_label(self) -> str:
        return f"{self.weight_per_unit} g / {self.stock_unit_singular}"

    @property
    def catalog_label(self) -> str:
        """Full operational label for searchable selects."""
        return (
            f"{self.code_label} · "
            f"{self.display_name} · "
            f"{self.unit_weight_label}"
        )

    @property
    def catalog_sort_key(self) -> tuple[int, str, str, int, str]:
        return (
            self.internal_number or 999_999,
            self.brand.casefold(),
            self.name.casefold(),
            self.weight_per_unit,
            self.sku,
        )

    def stock_quantity_label(self, quantity: int) -> str:
        if quantity < 0:
            raise InvalidProductData("quantity must be non-negative")

        unit = (
            self.stock_unit_singular
            if quantity == 1
            else self.stock_unit_plural
        )
        return f"{quantity} {unit}"

    def grams_to_units(self, *, grams: int) -> int:
        """Convert grams into whole stock units for this product."""

        if grams <= 0:
            raise InvalidProductData("grams must be positive")

        return (grams + self.weight_per_unit - 1) // self.weight_per_unit

    def kg_to_units(self, *, kg: Decimal) -> int:
        """Convert kilograms into whole stock units for this product."""

        if kg <= 0:
            raise InvalidProductData("kg must be positive")

        grams = (kg * Decimal("1000")).to_integral_value(
            rounding=ROUND_CEILING
        )

        return self.grams_to_units(grams=int(grams))

    def units_to_grams(self, *, units: int) -> int:
        """Convert whole stock units into grams for this product."""

        if units <= 0:
            raise InvalidProductData("units must be positive")

        return units * self.weight_per_unit

    def units_to_kg(self, *, units: int) -> Decimal:
        """Convert whole stock units into kilograms."""

        grams = self.units_to_grams(units=units)
        return Decimal(grams) / Decimal("1000")

    def __str__(self) -> str:
        return self.display_name


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
