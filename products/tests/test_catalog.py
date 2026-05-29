from __future__ import annotations

import pytest

from products.catalog import (
    MAX_NAME_LENGTH,
    MAX_WEIGHT_PER_UNIT,
    MIN_WEIGHT_PER_UNIT,
    make_sku,
    normalize_optional_text,
    normalize_required_text,
    slugify_sku_part,
    validate_internal_number,
    validate_weight_per_unit,
)
from products.errors import InvalidProductData


def test_normalize_required_text_strips_and_collapses_whitespace():
    assert normalize_required_text("  Grill   Chips  ", field_name="name") == "Grill Chips"


def test_normalize_required_text_rejects_empty_text():
    with pytest.raises(InvalidProductData, match="name must not be empty"):
        normalize_required_text("   ", field_name="name")


def test_normalize_required_text_rejects_too_long_text():
    value = "x" * (MAX_NAME_LENGTH + 1)

    with pytest.raises(InvalidProductData, match=f"name must be at most {MAX_NAME_LENGTH}"):
        normalize_required_text(value, field_name="name")


def test_normalize_optional_text_allows_empty_text():
    assert normalize_optional_text("   ", field_name="manufacturer") == ""


def test_normalize_optional_text_strips_and_collapses_whitespace():
    assert (
        normalize_optional_text("  Fazer   Sweden  ", field_name="manufacturer")
        == "Fazer Sweden"
    )


def test_slugify_sku_part_uppercases_and_uses_underscores():
    assert slugify_sku_part("Grill Chips!") == "GRILL_CHIPS"


def test_make_sku_uses_internal_number_when_present():
    assert (
        make_sku(
            internal_number=23,
            brand="OLW",
            name="Grill Chips",
            weight_per_unit=275,
        )
        == "SS-023"
    )


def test_make_sku_uses_brand_name_and_weight_without_internal_number():
    assert (
        make_sku(
            brand="OLW",
            name="Grill Chips",
            weight_per_unit=275,
        )
        == "OLW-GRILL_CHIPS-275"
    )


@pytest.mark.parametrize("weight", [MIN_WEIGHT_PER_UNIT, MAX_WEIGHT_PER_UNIT])
def test_validate_weight_per_unit_accepts_boundaries(weight):
    validate_weight_per_unit(weight)


@pytest.mark.parametrize("weight", [MIN_WEIGHT_PER_UNIT - 1, MAX_WEIGHT_PER_UNIT + 1])
def test_validate_weight_per_unit_rejects_out_of_range_values(weight):
    with pytest.raises(InvalidProductData):
        validate_weight_per_unit(weight)


@pytest.mark.parametrize("internal_number", [None, 1, 23])
def test_validate_internal_number_accepts_positive_or_none(internal_number):
    validate_internal_number(internal_number)


@pytest.mark.parametrize("internal_number", [0, -1])
def test_validate_internal_number_rejects_zero_or_negative(internal_number):
    with pytest.raises(InvalidProductData, match="internal_number must be positive"):
        validate_internal_number(internal_number)
