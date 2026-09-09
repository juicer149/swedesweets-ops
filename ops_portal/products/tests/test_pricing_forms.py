from __future__ import annotations

from decimal import Decimal

import pytest

from ops_portal.products.pricing_forms import (
    PRICING_STATUS_ACTIVE,
    PRICING_STATUS_INACTIVE,
    ProductPricingForm,
    build_product_pricing_initial_data,
)
from pricing.models import CommercialPrice, PriceAmount
from pricing.tests.factories import (
    commercial_price_factory,
    price_amount_factory,
    pricing_product_factory,
)


def valid_pricing_form_data(
    **overrides,
) -> dict[str, str]:
    data = {
        "business_eur": "",
        "business_sek": "",
        "business_status": PRICING_STATUS_INACTIVE,
        "retail_eur": "",
        "retail_sek": "",
        "retail_status": PRICING_STATUS_INACTIVE,
    }
    data.update(overrides)

    return data


def test_product_pricing_form_accepts_empty_pricing():
    form = ProductPricingForm(
        data=valid_pricing_form_data(),
    )

    assert form.is_valid(), form.errors

    assert form.cleaned_data["business_eur"] is None
    assert form.cleaned_data["business_sek"] is None
    assert (
        form.cleaned_data["business_status"]
        == PRICING_STATUS_INACTIVE
    )
    assert form.business_enabled is False

    assert form.cleaned_data["retail_eur"] is None
    assert form.cleaned_data["retail_sek"] is None
    assert (
        form.cleaned_data["retail_status"]
        == PRICING_STATUS_INACTIVE
    )
    assert form.retail_enabled is False


def test_product_pricing_form_accepts_disabled_configured_pricing():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            business_eur="7.50",
            business_status=PRICING_STATUS_INACTIVE,
        )
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["business_eur"]
        == Decimal("7.50")
    )
    assert form.business_enabled is False


def test_product_pricing_form_accepts_enabled_business_pricing():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            business_eur="7.50",
            business_status=PRICING_STATUS_ACTIVE,
        )
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["business_eur"]
        == Decimal("7.50")
    )
    assert (
        form.cleaned_data["business_status"]
        == PRICING_STATUS_ACTIVE
    )
    assert form.business_enabled is True


def test_product_pricing_form_accepts_enabled_retail_pricing():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            retail_sek="99.00",
            retail_status=PRICING_STATUS_ACTIVE,
        )
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["retail_sek"]
        == Decimal("99.00")
    )
    assert (
        form.cleaned_data["retail_status"]
        == PRICING_STATUS_ACTIVE
    )
    assert form.retail_enabled is True


def test_product_pricing_form_accepts_multiple_currencies():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            business_eur="7.00",
            business_sek="79.00",
            business_status=PRICING_STATUS_ACTIVE,
            retail_eur="9.00",
            retail_sek="99.00",
            retail_status=PRICING_STATUS_ACTIVE,
        )
    )

    assert form.is_valid(), form.errors

    assert (
        form.cleaned_data["business_eur"]
        == Decimal("7.00")
    )
    assert (
        form.cleaned_data["business_sek"]
        == Decimal("79.00")
    )
    assert (
        form.cleaned_data["retail_eur"]
        == Decimal("9.00")
    )
    assert (
        form.cleaned_data["retail_sek"]
        == Decimal("99.00")
    )

    assert form.business_enabled is True
    assert form.retail_enabled is True


def test_product_pricing_form_rejects_active_business_without_amount():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            business_status=PRICING_STATUS_ACTIVE,
        )
    )

    assert not form.is_valid()
    assert "business_status" in form.errors


def test_product_pricing_form_rejects_active_retail_without_amount():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            retail_status=PRICING_STATUS_ACTIVE,
        )
    )

    assert not form.is_valid()
    assert "retail_status" in form.errors


def test_product_pricing_form_rejects_invalid_business_status():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            business_status="archived",
        )
    )

    assert not form.is_valid()
    assert "business_status" in form.errors


def test_product_pricing_form_rejects_invalid_retail_status():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            retail_status="archived",
        )
    )

    assert not form.is_valid()
    assert "retail_status" in form.errors


def test_product_pricing_form_exposes_service_values():
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            business_eur="7.00",
            business_sek="79.00",
            business_status=PRICING_STATUS_ACTIVE,
            retail_eur="9.00",
            retail_status=PRICING_STATUS_INACTIVE,
        )
    )

    assert form.is_valid(), form.errors

    assert form.pricing_values() == {
        "business_eur": Decimal("7.00"),
        "business_sek": Decimal("79.00"),
        "business_enabled": True,
        "retail_eur": Decimal("9.00"),
        "retail_sek": None,
        "retail_enabled": False,
    }


@pytest.mark.parametrize(
    "field_name",
    [
        "business_eur",
        "business_sek",
        "retail_eur",
        "retail_sek",
    ],
)
def test_product_pricing_form_rejects_zero_price(
    field_name,
):
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            **{
                field_name: "0.00",
            }
        )
    )

    assert not form.is_valid()
    assert field_name in form.errors


@pytest.mark.parametrize(
    "field_name",
    [
        "business_eur",
        "business_sek",
        "retail_eur",
        "retail_sek",
    ],
)
def test_product_pricing_form_rejects_more_than_two_decimal_places(
    field_name,
):
    form = ProductPricingForm(
        data=valid_pricing_form_data(
            **{
                field_name: "9.999",
            }
        )
    )

    assert not form.is_valid()
    assert field_name in form.errors


def test_product_pricing_form_uses_radio_chip_status_widgets():
    form = ProductPricingForm()

    business_widget = form.fields[
        "business_status"
    ].widget
    retail_widget = form.fields[
        "retail_status"
    ].widget

    assert isinstance(
        business_widget,
        type(retail_widget),
    )
    assert (
        business_widget.attrs["class"]
        == "radio-chip-group"
    )
    assert (
        retail_widget.attrs["class"]
        == "radio-chip-group"
    )


@pytest.mark.django_db
def test_build_product_pricing_initial_data_without_pricing():
    initial = build_product_pricing_initial_data(
        business_price=None,
        retail_price=None,
    )

    assert initial == {
        "business_eur": None,
        "business_sek": None,
        "business_status": PRICING_STATUS_INACTIVE,
        "retail_eur": None,
        "retail_sek": None,
        "retail_status": PRICING_STATUS_INACTIVE,
    }


@pytest.mark.django_db
def test_build_product_pricing_initial_data_from_existing_prices():
    product = pricing_product_factory()

    business_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("7.00"),
    )
    price_amount_factory(
        commercial_price=business_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("79.00"),
    )

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=False,
    )
    price_amount_factory(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )

    initial = build_product_pricing_initial_data(
        business_price=business_price,
        retail_price=retail_price,
    )

    assert initial == {
        "business_eur": Decimal("7.00"),
        "business_sek": Decimal("79.00"),
        "business_status": PRICING_STATUS_ACTIVE,
        "retail_eur": Decimal("9.00"),
        "retail_sek": None,
        "retail_status": PRICING_STATUS_INACTIVE,
    }
