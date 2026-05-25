from __future__ import annotations

import pytest

from customers.errors import InvalidCustomerData
from customers.models import (
    CUSTOMER_COUNTRY_LABELS,
    MAX_CUSTOMER_ADDRESS_LINE_LENGTH,
    MAX_CUSTOMER_CITY_LENGTH,
    MAX_CUSTOMER_NAME_LENGTH,
    MAX_CUSTOMER_PHONE_LENGTH,
    Customer,
    normalize_customer_address_line,
    normalize_customer_city,
    normalize_customer_country,
    normalize_customer_email,
    normalize_customer_name,
    normalize_customer_phone_number,
)


def test_normalize_customer_name_strips_and_collapses_whitespace():
    assert normalize_customer_name("  Nordic   Corner   Shop  ") == "Nordic Corner Shop"


def test_normalize_customer_name_rejects_empty_value():
    with pytest.raises(InvalidCustomerData, match="customer name must not be empty"):
        normalize_customer_name("   ")


def test_normalize_customer_name_rejects_too_long_value():
    value = "x" * (MAX_CUSTOMER_NAME_LENGTH + 1)

    with pytest.raises(InvalidCustomerData, match="customer name must be at most"):
        normalize_customer_name(value)


def test_normalize_customer_email_strips_and_lowercases():
    assert normalize_customer_email("  ORDERS@EXAMPLE.FR  ") == "orders@example.fr"


def test_normalize_customer_email_rejects_empty_value():
    with pytest.raises(InvalidCustomerData, match="customer email must not be empty"):
        normalize_customer_email("   ")


def test_normalize_customer_phone_number_removes_spaces_and_dashes():
    assert normalize_customer_phone_number("+33 6 12-34-56-78") == "+33612345678"


def test_normalize_customer_phone_number_rejects_empty_value():
    with pytest.raises(
        InvalidCustomerData,
        match="customer phone number must not be empty",
    ):
        normalize_customer_phone_number("  --  ")


def test_normalize_customer_phone_number_rejects_too_long_value():
    value = "1" * (MAX_CUSTOMER_PHONE_LENGTH + 1)

    with pytest.raises(
        InvalidCustomerData,
        match="customer phone number must be at most",
    ):
        normalize_customer_phone_number(value)


@pytest.mark.parametrize("country", ["FR", "fr", " CH ", "it"])
def test_normalize_customer_country_accepts_supported_country_codes(country):
    assert normalize_customer_country(country) in CUSTOMER_COUNTRY_LABELS


def test_normalize_customer_country_rejects_empty_value():
    with pytest.raises(InvalidCustomerData, match="customer country must not be empty"):
        normalize_customer_country("   ")


def test_normalize_customer_country_rejects_unsupported_country():
    with pytest.raises(InvalidCustomerData, match="unsupported customer country"):
        normalize_customer_country("SE")


def test_normalize_customer_city_strips_and_collapses_whitespace():
    assert normalize_customer_city("  Chamonix   Mont Blanc  ") == "Chamonix Mont Blanc"


def test_normalize_customer_city_rejects_empty_value():
    with pytest.raises(InvalidCustomerData, match="customer city must not be empty"):
        normalize_customer_city("   ")


def test_normalize_customer_city_rejects_too_long_value():
    value = "x" * (MAX_CUSTOMER_CITY_LENGTH + 1)

    with pytest.raises(InvalidCustomerData, match="customer city must be at most"):
        normalize_customer_city(value)


def test_normalize_customer_address_line_strips_and_collapses_whitespace():
    assert (
        normalize_customer_address_line("  123   Rue du Mont Blanc  ")
        == "123 Rue du Mont Blanc"
    )


def test_normalize_customer_address_line_rejects_empty_value():
    with pytest.raises(InvalidCustomerData, match="customer address must not be empty"):
        normalize_customer_address_line("   ")


def test_normalize_customer_address_line_rejects_too_long_value():
    value = "x" * (MAX_CUSTOMER_ADDRESS_LINE_LENGTH + 1)

    with pytest.raises(InvalidCustomerData, match="customer address must be at most"):
        normalize_customer_address_line(value)


@pytest.mark.django_db
def test_customer_save_normalizes_fields():
    customer = Customer.objects.create(
        name="  Nordic   Corner   Shop  ",
        email="  ORDERS@EXAMPLE.FR  ",
        phone_number="+33 6 12-34-56-78",
        country=" fr ",
        city="  Chamonix-Mont-Blanc  ",
        address_line="  123   Rue du Mont Blanc  ",
    )

    assert customer.name == "Nordic Corner Shop"
    assert customer.email == "orders@example.fr"
    assert customer.phone_number == "+33612345678"
    assert customer.country == "FR"
    assert customer.city == "Chamonix-Mont-Blanc"
    assert customer.address_line == "123 Rue du Mont Blanc"


@pytest.mark.django_db
def test_customer_country_name_returns_display_name(customer):
    assert customer.country_name == "France"


@pytest.mark.django_db
def test_customer_address_formats_address_for_display(customer):
    assert customer.address == "123 Rue du Mont Blanc, Chamonix-Mont-Blanc, France"


@pytest.mark.django_db
def test_customer_string_is_name(customer):
    assert str(customer) == "Nordic Corner Shop"
