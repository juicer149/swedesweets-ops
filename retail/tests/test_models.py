from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from retail.models import RetailOrder, RetailOrderLine, RetailPrice
from retail.rules import RETAIL_PAYMENT_WINDOW
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
)


@pytest.mark.django_db
def test_retail_postal_area_normalizes_country_postal_code_and_city():
    area = retail_postal_area_factory(
        country_code=" fr ",
        postal_code=" 74000 ",
        city="  Annecy  ",
    )

    assert area.country_code == "FR"
    assert area.postal_code == "74000"
    assert area.city == "Annecy"


@pytest.mark.django_db
def test_retail_postal_area_collapses_city_whitespace():
    area = retail_postal_area_factory(
        city="La   Roche-sur-Foron",
    )

    assert area.city == "La Roche-sur-Foron"


@pytest.mark.django_db
def test_retail_postal_area_is_enabled_by_default():
    area = retail_postal_area_factory()

    assert area.enabled is True


@pytest.mark.django_db
def test_retail_postal_area_combination_must_be_unique():
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_postal_area_factory(
                country_code="FR",
                postal_code="74000",
                city="Annecy",
            )


@pytest.mark.django_db
def test_same_postal_code_can_represent_different_cities():
    first = retail_postal_area_factory(
        postal_code="74000",
        city="Annecy",
    )
    second = retail_postal_area_factory(
        postal_code="74000",
        city="Annecy Cedex",
    )

    assert first.pk != second.pk


@pytest.mark.django_db
def test_retail_price_belongs_to_product():
    product = retail_product_factory()

    price = RetailPrice.objects.create(
        product=product,
        amount=Decimal("12.50"),
        currency="EUR",
    )

    assert price.product == product
    assert price.amount == Decimal("12.50")
    assert price.currency == "EUR"


@pytest.mark.django_db
def test_retail_price_must_be_positive():
    product = retail_product_factory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailPrice.objects.create(
                product=product,
                amount=Decimal("0.00"),
                currency="EUR",
            )


@pytest.mark.django_db
def test_product_has_only_one_current_retail_price():
    product = retail_product_factory()

    RetailPrice.objects.create(
        product=product,
        amount=Decimal("12.50"),
        currency="EUR",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailPrice.objects.create(
                product=product,
                amount=Decimal("15.00"),
                currency="EUR",
            )


@pytest.mark.django_db
def test_retail_order_starts_pending_payment():
    buyer = retail_buyer_data()

    order = RetailOrder.objects.create(
        **buyer,
        expires_at=timezone.now() + RETAIL_PAYMENT_WINDOW,
    )

    assert order.status == RetailOrder.Status.PENDING_PAYMENT


@pytest.mark.django_db
def test_retail_order_snapshots_buyer_information():
    buyer = retail_buyer_data()

    order = RetailOrder.objects.create(
        **buyer,
        expires_at=timezone.now() + RETAIL_PAYMENT_WINDOW,
    )

    assert order.first_name == "Marie"
    assert order.last_name == "Dupont"
    assert order.email == "marie@example.com"
    assert order.phone_number == "+33612345678"
    assert order.country == "FR"
    assert order.postal_code == "74000"
    assert order.city == "Annecy"
    assert order.address_line == "10 Rue de Test"


@pytest.mark.django_db
def test_retail_order_line_belongs_to_order_and_product():
    product = retail_product_factory()

    order = RetailOrder.objects.create(
        **retail_buyer_data(),
        expires_at=timezone.now() + RETAIL_PAYMENT_WINDOW,
    )

    line = RetailOrderLine.objects.create(
        order=order,
        product=product,
        quantity=2,
        unit_price_snapshot=Decimal("12.50"),
        line_total=Decimal("25.00"),
    )

    assert line.order == order
    assert line.product == product
    assert line.quantity == 2
    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")


@pytest.mark.django_db
@pytest.mark.parametrize("quantity", [0, -1])
def test_retail_order_line_quantity_must_be_positive(quantity):
    product = retail_product_factory()

    order = RetailOrder.objects.create(
        **retail_buyer_data(),
        expires_at=timezone.now() + RETAIL_PAYMENT_WINDOW,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailOrderLine.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price_snapshot=Decimal("12.50"),
                line_total=Decimal("0.00"),
            )
