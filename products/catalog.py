from __future__ import annotations

from products.errors import InvalidProductData

MAX_NAME_LENGTH = 160
MAX_SKU_LENGTH = 180
MAX_IMAGE_URL_LENGTH = 500

MIN_WEIGHT_PER_UNIT = 1
MAX_WEIGHT_PER_UNIT = 50_000

SKU_PREFIX = "SS"
SKU_INTERNAL_NUMBER_WIDTH = 3


def normalize_required_text(
    value: str,
    *,
    field_name: str,
    max_length: int = MAX_NAME_LENGTH,
) -> str:
    value = " ".join(value.strip().split())

    if not value:
        raise InvalidProductData(f"{field_name} must not be empty")

    if len(value) > max_length:
        raise InvalidProductData(
            f"{field_name} must be at most {max_length} characters"
        )

    return value


def normalize_optional_text(
    value: str,
    *,
    field_name: str,
    max_length: int = MAX_NAME_LENGTH,
) -> str:
    value = " ".join(value.strip().split())

    if len(value) > max_length:
        raise InvalidProductData(
            f"{field_name} must be at most {max_length} characters"
        )

    return value


def slugify_sku_part(value: str) -> str:
    value = normalize_required_text(value, field_name="sku part")

    characters: list[str] = []
    previous_was_separator = False

    for character in value.casefold().upper():
        if character.isalnum():
            characters.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            characters.append("_")
            previous_was_separator = True

    return "".join(characters).strip("_")


def validate_weight_per_unit(weight_per_unit: int) -> None:
    if weight_per_unit < MIN_WEIGHT_PER_UNIT:
        raise InvalidProductData(
            f"weight_per_unit must be at least {MIN_WEIGHT_PER_UNIT}"
        )

    if weight_per_unit > MAX_WEIGHT_PER_UNIT:
        raise InvalidProductData(
            f"weight_per_unit must be at most {MAX_WEIGHT_PER_UNIT}"
        )


def validate_internal_number(internal_number: int | None) -> None:
    if internal_number is None:
        return

    if internal_number <= 0:
        raise InvalidProductData("internal_number must be positive")


def make_sku(
    *,
    brand: str,
    name: str,
    weight_per_unit: int,
    internal_number: int | None = None,
) -> str:
    validate_weight_per_unit(weight_per_unit)
    validate_internal_number(internal_number)

    if internal_number is not None:
        return f"{SKU_PREFIX}-{internal_number:0{SKU_INTERNAL_NUMBER_WIDTH}d}"

    return f"{slugify_sku_part(brand)}-{slugify_sku_part(name)}-{weight_per_unit}"
