from __future__ import annotations

from decimal import Decimal

import pytest

from orders.datatypes import OrderLineInput
from orders.errors import InvalidOrderOperation


@pytest.mark.django_db
def test_order_line_input_accepts_product_id_or_product(apple):
    by_id = OrderLineInput.boxes(
        product_id=apple.id,
        boxes=10,
    )

    by_product = OrderLineInput.boxes(
        product=apple,
        boxes=10,
    )

    assert by_id.resolve_product_id() == apple.id
    assert by_product.resolve_product_id() == apple.id


@pytest.mark.django_db
def test_order_line_input_accepts_matching_product_and_product_id(apple):
    line = OrderLineInput.boxes(
        product=apple,
        product_id=apple.id,
        boxes=10,
    )

    assert line.resolve_product_id() == apple.id


@pytest.mark.django_db
def test_order_line_input_rejects_conflicting_product_and_product_id(
    apple,
    banana,
):
    line = OrderLineInput.boxes(
        product=apple,
        product_id=banana.id,
        boxes=10,
    )

    with pytest.raises(InvalidOrderOperation, match="different products"):
        line.resolve_product_id()


def test_order_line_input_rejects_missing_product_reference():
    line = OrderLineInput.boxes(
        boxes=10,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="product_id or product is required",
    ):
        line.resolve_product_id()


@pytest.mark.django_db
def test_order_line_input_normalizes_quantity_and_unit(apple):
    line = OrderLineInput(
        product=apple,
        quantity=25.0,
        unit=" KG ",
    )

    assert line.quantity == Decimal("25.0")
    assert line.unit == "kg"
    assert line.resolve_product_id() == apple.id


@pytest.mark.django_db
def test_order_line_input_factories_normalize_quantity_and_unit(apple):
    boxes = OrderLineInput.boxes(
        product=apple,
        boxes=10,
    )
    kg = OrderLineInput.kg(
        product=apple,
        kg=25.0,
    )
    grams = OrderLineInput.grams(
        product=apple,
        grams=25000,
    )

    assert boxes.quantity == Decimal("10")
    assert boxes.unit == "boxes"

    assert kg.quantity == Decimal("25.0")
    assert kg.unit == "kg"

    assert grams.quantity == Decimal("25000")
    assert grams.unit == "grams"
