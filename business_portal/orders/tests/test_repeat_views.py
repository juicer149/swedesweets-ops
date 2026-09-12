from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.tests.factories import (
    customer_user_factory,
)
from business.services import create_order
from customers.tests.factories import (
    customer_factory,
)
from inventory.tests.conftest import TODAY
from inventory.tests.factories import (
    batch_factory,
)
from orders.datatypes import OrderLineInput
from orders.models import Order
from products.tests.factories import (
    product_factory,
)


def _create_source_order(
    *,
    customer,
    product,
    quantity: int = 1,
):
    batch_factory(
        product=product,
        today=TODAY,
        quantity=100,
    )

    return create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=product,
                quantity=quantity,
            ),
        ],
    )


@pytest.mark.django_db
def test_repeat_order_endpoint_requires_post(
    client,
):
    customer = customer_factory(
        email="repeat-get@example.com",
    )

    user = customer_user_factory(
        customer=customer,
    )

    product = product_factory(
        name="Apple",
        internal_number=201,
    )

    order = _create_source_order(
        customer=customer,
        product=product,
    )

    client.force_login(
        user
    )

    response = client.get(
        reverse(
            "business_portal:repeat_order",
            kwargs={
                "order_id": order.id,
            },
        )
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_repeat_order_endpoint_rejects_other_customers_order(
    client,
):
    customer = customer_factory(
        email="repeat-owner@example.com",
    )

    other_customer = customer_factory(
        email="repeat-other@example.com",
    )

    user = customer_user_factory(
        customer=customer,
    )

    product = product_factory(
        name="Apple",
        internal_number=202,
    )

    order = _create_source_order(
        customer=other_customer,
        product=product,
    )

    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:repeat_order",
            kwargs={
                "order_id": order.id,
            },
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_repeat_order_endpoint_redirects_to_current_order_after_success(
    client,
):
    customer = customer_factory(
        email="repeat-success@example.com",
    )

    user = customer_user_factory(
        customer=customer,
    )

    product = product_factory(
        name="Apple",
        internal_number=203,
    )

    order = _create_source_order(
        customer=customer,
        product=product,
        quantity=2,
    )

    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:repeat_order",
            kwargs={
                "order_id": order.id,
            },
        )
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:current_order"
    )

    draft = Order.objects.get(
        customer=customer,
        channel=Order.Channel.BUSINESS,
        status=Order.Status.DRAFT,
    )

    line = draft.lines.get()

    assert line.product == product
    assert line.quantity_in_units == 2
