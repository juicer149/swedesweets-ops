from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.tests.factories import customer_user_factory
from customers.tests.factories import customer_factory
from inventory.tests.conftest import TODAY
from inventory.tests.factories import batch_factory
from orders.datatypes import OrderLineInput
from orders.services import create_order
from products.tests.factories import product_factory


PROFILE_FORM_DATA = {
    "name": "Updated Store",
    "email": "updated@example.com",
    "phone_number": "+33 6 99 88 77 66",
    "country": "CH",
    "city": "Zürich",
    "address_line": "Bahnhofstrasse 1",
}


@pytest.mark.django_db
def test_customer_updates_only_own_store_profile(client):
    customer = customer_factory(
        name="Original Store",
        email="store@example.com",
        phone_number="+33 6 11 22 33 44",
        country="FR",
        city="Chamonix-Mont-Blanc",
        address_line="1 Old Street",
    )
    other_customer = customer_factory(
        name="Other Store",
        email="other@example.com",
        phone_number="+33 6 55 66 77 88",
        country="FR",
        city="Annecy",
        address_line="2 Other Street",
    )
    user = customer_user_factory(
        customer=customer,
        username="login@example.com",
    )
    client.force_login(user)

    response = client.post(
        reverse("customer_portal:profile"),
        PROFILE_FORM_DATA,
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("customer_portal:profile")

    customer.refresh_from_db()
    other_customer.refresh_from_db()

    assert customer.name == "Updated Store"
    assert customer.email == "updated@example.com"
    assert customer.phone_number == "+33699887766"
    assert customer.country == "CH"
    assert customer.city == "Zürich"
    assert customer.address_line == "Bahnhofstrasse 1"

    assert other_customer.name == "Other Store"
    assert other_customer.email == "other@example.com"
    assert other_customer.phone_number == "+33655667788"
    assert other_customer.country == "FR"
    assert other_customer.city == "Annecy"
    assert other_customer.address_line == "2 Other Street"


@pytest.mark.django_db
def test_profile_update_affects_future_orders_but_not_existing_snapshots(client):
    customer = customer_factory(
        name="Original Store",
        email="store@example.com",
        phone_number="+33 6 11 22 33 44",
        country="FR",
        city="Chamonix-Mont-Blanc",
        address_line="1 Old Street",
    )
    product = product_factory(name="Apple", weight_per_unit=5000)
    batch_factory(product=product, today=TODAY, quantity=100)

    user = customer_user_factory(
        customer=customer,
        username="login@example.com",
    )
    client.force_login(user)

    existing_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=product, quantity=1),
        ],
    )

    response = client.post(
        reverse("customer_portal:profile"),
        PROFILE_FORM_DATA,
    )

    assert response.status_code == 302

    existing_order.refresh_from_db()
    customer.refresh_from_db()

    assert existing_order.customer_name == "Original Store"
    assert existing_order.customer_email == "store@example.com"
    assert existing_order.customer_phone_number == "+33611223344"
    assert existing_order.customer_country == "FR"
    assert existing_order.customer_city == "Chamonix-Mont-Blanc"
    assert existing_order.customer_address_line == "1 Old Street"

    new_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(product=product, quantity=1),
        ],
    )

    assert new_order.customer_name == "Updated Store"
    assert new_order.customer_email == "updated@example.com"
    assert new_order.customer_phone_number == "+33699887766"
    assert new_order.customer_country == "CH"
    assert new_order.customer_city == "Zürich"
    assert new_order.customer_address_line == "Bahnhofstrasse 1"
