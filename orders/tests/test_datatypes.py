from __future__ import annotations

from decimal import Decimal

import pytest

from orders.datatypes import OrderLineInput, BuyerInput
from orders.errors import InvalidOrderOperation
from products.units import OrderUnit


@pytest.mark.django_db
def test_order_line_input_accepts_product_id_or_product(apple):
    by_id = OrderLineInput.units(
        product_id=apple.id,
        quantity=10,
    )

    by_product = OrderLineInput.units(
        product=apple,
        quantity=10,
    )

    assert by_id.resolve_product_id() == apple.id
    assert by_product.resolve_product_id() == apple.id


@pytest.mark.django_db
def test_order_line_input_accepts_matching_product_and_product_id(apple):
    line = OrderLineInput.units(
        product=apple,
        product_id=apple.id,
        quantity=10,
    )

    assert line.resolve_product_id() == apple.id


@pytest.mark.django_db
def test_order_line_input_rejects_conflicting_product_and_product_id(
    apple,
    banana,
):
    line = OrderLineInput.units(
        product=apple,
        product_id=banana.id,
        quantity=10,
    )

    with pytest.raises(InvalidOrderOperation, match="different products"):
        line.resolve_product_id()


def test_order_line_input_rejects_missing_product_reference():
    line = OrderLineInput.units(
        quantity=10,
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
    assert line.unit == OrderUnit.KG 
    assert line.resolve_product_id() == apple.id


@pytest.mark.django_db
def test_order_line_input_factories_normalize_quantity_and_unit(apple):
    units = OrderLineInput.units(
        product=apple,
        quantity=10,
    )
    stock_units = OrderLineInput.stock_units(
        product=apple,
        quantity=11,
    )
    kg = OrderLineInput.kg(
        product=apple,
        kg=25.0,
    )
    grams = OrderLineInput.grams(
        product=apple,
        grams=25000,
    )

    assert units.quantity == Decimal("10")
    assert units.unit == OrderUnit.STOCK

    assert stock_units.quantity == Decimal("11")
    assert stock_units.unit == OrderUnit.STOCK

    assert kg.quantity == Decimal("25.0")
    assert kg.unit == OrderUnit.KG

    assert grams.quantity == Decimal("25000")
    assert grams.unit == OrderUnit.GRAMS


def test_buyer_input_represents_buyer_without_customer_model():
    buyer = BuyerInput(
        name="Marie Dupont",
        email="marie@example.fr",
        phone_number="+33612345678",
        country="FR",
        city="Annecy",
        address_line="10 Rue du Lac",
    )

    assert buyer.name == "Marie Dupont"
    assert buyer.email == "marie@example.fr"
    assert buyer.phone_number == "+33612345678"
    assert buyer.country == "FR"
    assert buyer.city == "Annecy"
    assert buyer.address_line == "10 Rue du Lac"
    assert buyer.postal_code == ""
