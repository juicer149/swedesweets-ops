from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.tests.factories import batch_factory
from ops_portal.inventory.pricing_forms import (
    BatchPricingForm,
    PRICING_STATUS_ACTIVE,
    PRICING_STATUS_INACTIVE,
    build_batch_pricing_initial_data,
)
from pricing.models import CommercialPrice, PriceAmount
from pricing.services import (
    create_commercial_price,
    set_commercial_price_enabled,
    set_commercial_price_reason,
    set_price_amount,
)
from products.tests.factories import product_factory


TODAY = timezone.localdate()


@pytest.mark.django_db
def test_batch_pricing_form_accepts_empty_pricing():
    form = BatchPricingForm(
        data={
            "reason": "",
            "business_eur": "",
            "business_sek": "",
            "business_status": PRICING_STATUS_INACTIVE,
            "retail_eur": "",
            "retail_sek": "",
            "retail_status": PRICING_STATUS_INACTIVE,
        }
    )

    assert form.is_valid(), form.errors

    assert form.pricing_values() == {
        "reason": "",
        "business_eur": None,
        "business_sek": None,
        "business_enabled": False,
        "retail_eur": None,
        "retail_sek": None,
        "retail_enabled": False,
    }


@pytest.mark.django_db
def test_batch_pricing_form_accepts_disabled_configured_pricing():
    form = BatchPricingForm(
        data={
            "reason": CommercialPrice.Reason.SHORT_DATED,
            "business_eur": "4.50",
            "business_sek": "",
            "business_status": PRICING_STATUS_INACTIVE,
            "retail_eur": "",
            "retail_sek": "",
            "retail_status": PRICING_STATUS_INACTIVE,
        }
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data["business_eur"] == Decimal("4.50")
    assert form.business_enabled is False


@pytest.mark.django_db
def test_batch_pricing_form_rejects_active_business_without_amount():
    form = BatchPricingForm(
        data={
            "reason": CommercialPrice.Reason.SHORT_DATED,
            "business_eur": "",
            "business_sek": "",
            "business_status": PRICING_STATUS_ACTIVE,
            "retail_eur": "",
            "retail_sek": "",
            "retail_status": PRICING_STATUS_INACTIVE,
        }
    )

    assert not form.is_valid()
    assert "business_status" in form.errors


@pytest.mark.django_db
def test_batch_pricing_form_rejects_active_retail_without_amount():
    form = BatchPricingForm(
        data={
            "reason": CommercialPrice.Reason.SHORT_DATED,
            "business_eur": "",
            "business_sek": "",
            "business_status": PRICING_STATUS_INACTIVE,
            "retail_eur": "",
            "retail_sek": "",
            "retail_status": PRICING_STATUS_ACTIVE,
        }
    )

    assert not form.is_valid()
    assert "retail_status" in form.errors


@pytest.mark.django_db
def test_batch_pricing_form_requires_reason_when_amount_is_configured():
    form = BatchPricingForm(
        data={
            "reason": "",
            "business_eur": "4.50",
            "business_sek": "",
            "business_status": PRICING_STATUS_INACTIVE,
            "retail_eur": "",
            "retail_sek": "",
            "retail_status": PRICING_STATUS_INACTIVE,
        }
    )

    assert not form.is_valid()
    assert "reason" in form.errors


@pytest.mark.django_db
def test_batch_pricing_form_parses_currency_amounts():
    form = BatchPricingForm(
        data={
            "reason": CommercialPrice.Reason.PROMOTION,
            "business_eur": "4.50",
            "business_sek": "49.90",
            "business_status": PRICING_STATUS_ACTIVE,
            "retail_eur": "5.25",
            "retail_sek": "57.00",
            "retail_status": PRICING_STATUS_ACTIVE,
        }
    )

    assert form.is_valid(), form.errors

    assert form.pricing_values() == {
        "reason": CommercialPrice.Reason.PROMOTION,
        "business_eur": Decimal("4.50"),
        "business_sek": Decimal("49.90"),
        "business_enabled": True,
        "retail_eur": Decimal("5.25"),
        "retail_sek": Decimal("57.00"),
        "retail_enabled": True,
    }


@pytest.mark.django_db
def test_build_batch_pricing_initial_data_from_existing_prices():
    product = product_factory()
    batch = batch_factory(
        product=product,
        today=TODAY,
    )

    business_price = create_commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )
    set_price_amount(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("4.50"),
    )
    business_price = set_commercial_price_enabled(
        commercial_price=business_price,
        enabled=True,
    )

    retail_price = create_commercial_price(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )
    set_price_amount(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("59.00"),
    )
    retail_price = set_commercial_price_reason(
        commercial_price=retail_price,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    initial = build_batch_pricing_initial_data(
        business_price=business_price,
        retail_price=retail_price,
    )

    assert initial == {
        "reason": CommercialPrice.Reason.SHORT_DATED,
        "business_eur": Decimal("4.50"),
        "business_sek": None,
        "business_status": PRICING_STATUS_ACTIVE,
        "retail_eur": None,
        "retail_sek": Decimal("59.00"),
        "retail_status": PRICING_STATUS_INACTIVE,
    }
