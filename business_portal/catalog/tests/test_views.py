from __future__ import annotations

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.tests.factories import (
    customer_user_factory,
)
from customers.tests.factories import (
    customer_factory,
)
from inventory.tests.conftest import TODAY
from inventory.tests.factories import (
    batch_factory,
)
from orders.models import Order
from products.tests.factories import (
    product_factory,
)


@pytest.mark.django_db
def test_customer_can_add_catalog_product_to_draft(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )
    batch_factory(
        product=product,
        today=TODAY,
        quantity=100,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:catalog_add_product",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )

    order = Order.objects.get(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    line = order.lines.get()

    assert line.product == product
    assert line.quantity_in_units == 1


@pytest.mark.django_db
def test_customer_adding_same_catalog_product_increments_quantity(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )
    batch_factory(
        product=product,
        today=TODAY,
        quantity=100,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    url = reverse(
        "business_portal:catalog_add_product",
        kwargs={
            "product_id": product.id,
        },
    )

    first_response = client.post(url)
    second_response = client.post(url)

    assert first_response.status_code == 302
    assert second_response.status_code == 302

    order = Order.objects.get(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    assert order.lines.count() == 1

    line = order.lines.get()

    assert line.product == product
    assert line.quantity_in_units == 2


@pytest.mark.django_db
def test_catalog_add_product_get_is_not_allowed(
    client,
):
    customer = customer_factory()
    product = product_factory()

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.get(
        reverse(
            "business_portal:catalog_add_product",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_catalog_add_product_returns_404_for_unknown_product(
    client,
):
    customer = customer_factory()

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:catalog_add_product",
            kwargs={
                "product_id": 999999,
            },
        )
    )

    assert response.status_code == 404

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_shows_success_message(
    client,
):
    customer = customer_factory()
    product = product_factory(
        brand="Generic",
        name="Apple",
        weight_per_unit=5000,
    )
    batch_factory(
        product=product,
        today=TODAY,
        quantity=100,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:catalog_add_product",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    messages = [
        str(message)
        for message in get_messages(
            response.wsgi_request
        )
    ]

    assert messages == [
        "Generic — Apple added to your order."
    ]


@pytest.mark.django_db
def test_catalog_add_product_shows_error_when_product_is_not_in_business_catalog(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )

    product.active = False
    product.save(
        update_fields=[
            "active",
            "updated_at",
        ],
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:catalog_add_product",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )

    messages = [
        str(message)
        for message in get_messages(
            response.wsgi_request
        )
    ]

    assert messages == [
        "product is not available in the business catalog"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()
