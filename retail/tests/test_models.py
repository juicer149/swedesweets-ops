from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from retail.models import (
    RetailBatchOffer,
    RetailOrder,
    RetailOrderLine,
    RetailProductOffer,
)
from retail.rules import RETAIL_PAYMENT_WINDOW
from retail.tests.factories import (
    retail_batch_offer_factory,
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_offer_factory,
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
def test_retail_product_offer_belongs_to_product():
    offer = retail_product_offer_factory()

    assert offer.product is not None


@pytest.mark.django_db
def test_retail_product_offer_is_disabled_by_default():
    offer = retail_product_offer_factory()

    assert offer.enabled is False


@pytest.mark.django_db
def test_disabled_retail_product_offer_may_have_no_price():
    offer = retail_product_offer_factory(
        enabled=False,
        price=None,
    )

    assert offer.price is None


@pytest.mark.django_db
def test_disabled_retail_product_offer_may_have_price():
    offer = retail_product_offer_factory(
        enabled=False,
        price=Decimal("12.50"),
    )

    assert offer.price == Decimal("12.50")


@pytest.mark.django_db
def test_product_can_have_only_one_retail_offer():
    offer = retail_product_offer_factory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailProductOffer.objects.create(
                product=offer.product,
                enabled=False,
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "price",
    [
        Decimal("0.00"),
        Decimal("-0.01"),
    ],
)
def test_retail_product_offer_price_must_be_positive_when_present(price):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_product_offer_factory(
                enabled=False,
                price=price,
            )


@pytest.mark.django_db
def test_enabled_retail_product_offer_requires_price():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_product_offer_factory(
                enabled=True,
                price=None,
            )


@pytest.mark.django_db
def test_enabled_retail_product_offer_accepts_positive_price():
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    assert offer.enabled is True
    assert offer.price == Decimal("12.50")


@pytest.mark.django_db
def test_retail_order_starts_pending_payment():
    order = RetailOrder.objects.create(
        **retail_buyer_data(),
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


@pytest.mark.django_db
def test_retail_batch_offer_belongs_to_inventory_batch():
    offer = retail_batch_offer_factory()

    assert offer.batch is not None


@pytest.mark.django_db
def test_retail_batch_offer_is_disabled_by_default():
    offer = retail_batch_offer_factory()

    assert offer.enabled is False


@pytest.mark.django_db
def test_disabled_retail_batch_offer_may_have_no_price():
    offer = retail_batch_offer_factory(
        enabled=False,
        price=None,
    )

    assert offer.price is None


@pytest.mark.django_db
def test_disabled_retail_batch_offer_may_have_price():
    offer = retail_batch_offer_factory(
        enabled=False,
        price=Decimal("4.90"),
    )

    assert offer.price == Decimal("4.90")


@pytest.mark.django_db
def test_inventory_batch_can_have_only_one_retail_offer():
    offer = retail_batch_offer_factory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailBatchOffer.objects.create(
                batch=offer.batch,
                enabled=False,
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "price",
    [
        Decimal("0.00"),
        Decimal("-0.01"),
    ],
)
def test_retail_batch_offer_price_must_be_positive_when_present(price):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_batch_offer_factory(
                enabled=False,
                price=price,
            )


@pytest.mark.django_db
def test_enabled_retail_batch_offer_requires_price():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_batch_offer_factory(
                enabled=True,
                price=None,
            )


@pytest.mark.django_db
def test_enabled_retail_batch_offer_accepts_positive_price():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    assert offer.enabled is True
    assert offer.price == Decimal("4.90")
