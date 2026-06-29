from __future__ import annotations

import pytest

from customers.errors import InvalidCustomerData
from customers.services import create_customer, update_customer


@pytest.mark.django_db
def test_create_customer_creates_and_normalizes_customer():
    customer = create_customer(
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
def test_create_customer_rejects_duplicate_normalized_email(customer):
    with pytest.raises(
        InvalidCustomerData,
        match="Customer with email orders@example.fr already exists",
    ):
        create_customer(
            name="Duplicate Customer",
            email="  orders@example.fr  ",
            phone_number="+33 1 22 33 44 55",
            country="FR",
            city="Paris",
            address_line="1 Rue Example",
        )


@pytest.mark.django_db
def test_create_customer_rejects_invalid_country():
    with pytest.raises(InvalidCustomerData, match="unsupported customer country"):
        create_customer(
            name="Nordic Corner Shop",
            email="orders@example.se",
            phone_number="+46 123 456",
            country="SE",
            city="Stockholm",
            address_line="Example Street 1",
        )


@pytest.mark.django_db
def test_update_customer_updates_editable_fields(customer):
    updated = update_customer(
        customer=customer,
        name="  Updated   Shop  ",
        email="  UPDATED@EXAMPLE.CH ",
        phone_number="+41 44-123 45 67",
        country="CH",
        city="  Zürich  ",
        address_line="  Bahnhofstrasse   1  ",
    )

    updated.refresh_from_db()

    assert updated.name == "Updated Shop"
    assert updated.email == "updated@example.ch"
    assert updated.phone_number == "+41441234567"
    assert updated.country == "CH"
    assert updated.city == "Zürich"
    assert updated.address_line == "Bahnhofstrasse 1"


@pytest.mark.django_db
def test_update_customer_allows_keeping_same_email(customer):
    updated = update_customer(
        customer=customer,
        name="Nordic Corner Shop Updated",
        email=" ORDERS@EXAMPLE.FR ",
        phone_number="+33 6 12 34 56 78",
        country="FR",
        city="Chamonix-Mont-Blanc",
        address_line="123 Rue du Mont Blanc",
    )

    assert updated.email == "orders@example.fr"
    assert updated.name == "Nordic Corner Shop Updated"


@pytest.mark.django_db
def test_update_customer_rejects_email_used_by_another_customer(
    customer, other_customer
):
    with pytest.raises(
        InvalidCustomerData,
        match="Customer with email orders@example.ch already exists",
    ):
        update_customer(
            customer=customer,
            name="Nordic Corner Shop",
            email=" ORDERS@EXAMPLE.CH ",
            phone_number="+33 6 12 34 56 78",
            country="FR",
            city="Chamonix-Mont-Blanc",
            address_line="123 Rue du Mont Blanc",
        )
