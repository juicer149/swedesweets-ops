from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import InventoryBatch
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_TOTAL,
    MIN_RETAIL_LINE_QUANTITY,
    is_retail_batch_sellable,
    is_retail_product_sellable,
    is_supported_retail_destination,
    is_valid_retail_line_quantity,
    is_valid_retail_order_total,
)
from retail.tests.factories import (
    retail_batch_offer_factory,
    retail_postal_area_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_known_enabled_destination_is_supported():
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )

    assert is_supported_retail_destination(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("country_code", "postal_code", "city"),
    [
        ("SE", "74000", "Annecy"),
        ("FR", "75001", "Annecy"),
        ("FR", "74000", "Paris"),
    ],
)
def test_destination_requires_matching_country_postal_code_and_city(
    country_code: str,
    postal_code: str,
    city: str,
):
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )

    assert not is_supported_retail_destination(
        country_code=country_code,
        postal_code=postal_code,
        city=city,
    )


@pytest.mark.django_db
def test_disabled_destination_is_not_supported():
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
        enabled=False,
    )

    assert not is_supported_retail_destination(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )


@pytest.mark.django_db
def test_destination_matching_ignores_country_and_city_case():
    retail_postal_area_factory()

    assert is_supported_retail_destination(
        country_code="fr",
        postal_code="74000",
        city="annecy",
    )


@pytest.mark.django_db
def test_destination_matching_ignores_surrounding_whitespace():
    retail_postal_area_factory()

    assert is_supported_retail_destination(
        country_code=" FR ",
        postal_code=" 74000 ",
        city=" Annecy ",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("country_code", "postal_code", "city"),
    [
        ("", "74000", "Annecy"),
        ("FR", "", "Annecy"),
        ("FR", "74000", ""),
        (" ", "74000", "Annecy"),
        ("FR", " ", "Annecy"),
        ("FR", "74000", " "),
    ],
)
def test_blank_destination_component_is_rejected(
    country_code: str,
    postal_code: str,
    city: str,
):
    retail_postal_area_factory()

    assert not is_supported_retail_destination(
        country_code=country_code,
        postal_code=postal_code,
        city=city,
    )


@pytest.mark.django_db
def test_enabled_product_offer_with_price_is_sellable():
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    assert is_retail_product_sellable(offer)


@pytest.mark.django_db
def test_disabled_product_offer_is_not_sellable():
    offer = retail_product_offer_factory(
        enabled=False,
        price=Decimal("12.50"),
    )

    assert not is_retail_product_sellable(offer)


@pytest.mark.django_db
def test_inactive_product_offer_is_not_sellable():
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    offer.product.active = False
    offer.product.save(update_fields=["active"])

    assert not is_retail_product_sellable(offer)


@pytest.mark.django_db
def test_enabled_batch_offer_with_active_stock_and_future_best_before_is_sellable():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    assert is_retail_batch_sellable(offer)


@pytest.mark.django_db
def test_disabled_batch_offer_is_not_sellable():
    offer = retail_batch_offer_factory(
        enabled=False,
        price=Decimal("4.90"),
    )

    assert not is_retail_batch_sellable(offer)


@pytest.mark.django_db
def test_batch_offer_for_inactive_product_is_not_sellable():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    offer.batch.product.active = False
    offer.batch.product.save(update_fields=["active"])

    assert not is_retail_batch_sellable(offer)


@pytest.mark.django_db
def test_depleted_batch_offer_is_not_sellable():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    offer.batch.adjust_quantity(quantity=0)

    assert offer.batch.status == InventoryBatch.Status.DEPLETED
    assert not is_retail_batch_sellable(offer)


@pytest.mark.django_db
def test_closed_batch_offer_is_not_sellable():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    offer.batch.close()

    assert offer.batch.status == InventoryBatch.Status.CLOSED
    assert not is_retail_batch_sellable(offer)


@pytest.mark.django_db
def test_expired_batch_offer_is_not_sellable():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    offer.batch.best_before = today - timedelta(days=1)
    offer.batch.save(update_fields=["best_before", "updated_at"])

    assert not is_retail_batch_sellable(
        offer,
        today=today,
    )


@pytest.mark.django_db
def test_batch_with_best_before_today_is_not_sellable():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    offer.batch.best_before = today
    offer.batch.save(update_fields=["best_before", "updated_at"])

    assert not is_retail_batch_sellable(
        offer,
        today=today,
    )


@pytest.mark.django_db
def test_future_batch_is_sellable_even_when_close_to_expiry():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    offer.batch.best_before = today + timedelta(days=1)
    offer.batch.save(update_fields=["best_before", "updated_at"])

    assert is_retail_batch_sellable(
        offer,
        today=today,
    )


@pytest.mark.parametrize(
    "quantity",
    [
        MIN_RETAIL_LINE_QUANTITY,
        MAX_RETAIL_LINE_QUANTITY,
    ],
)
def test_retail_line_quantity_accepts_boundaries(quantity: int):
    assert is_valid_retail_line_quantity(quantity)


@pytest.mark.parametrize(
    "quantity",
    [
        MIN_RETAIL_LINE_QUANTITY - 1,
        MAX_RETAIL_LINE_QUANTITY + 1,
    ],
)
def test_retail_line_quantity_rejects_values_outside_boundaries(
    quantity: int,
):
    assert not is_valid_retail_line_quantity(quantity)


@pytest.mark.parametrize(
    "total",
    [
        Decimal("0.01"),
        MAX_RETAIL_ORDER_TOTAL,
    ],
)
def test_retail_order_total_accepts_valid_boundaries(total: Decimal):
    assert is_valid_retail_order_total(total)


@pytest.mark.parametrize(
    "total",
    [
        Decimal("0.00"),
        Decimal("-0.01"),
        MAX_RETAIL_ORDER_TOTAL + Decimal("0.01"),
    ],
)
def test_retail_order_total_rejects_invalid_values(total: Decimal):
    assert not is_valid_retail_order_total(total)
