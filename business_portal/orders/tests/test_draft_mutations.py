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
from inventory.tests.factories import (
    batch_factory,
)
from orders.models import (
    Order,
    OrderLine,
)
from orders.tests.conftest import TODAY
from products.tests.factories import (
    product_factory,
)


def _create_draft_line(
    *,
    customer,
    product,
    quantity: int,
) -> OrderLine:
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    return OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
    )


@pytest.mark.django_db
def test_customer_can_set_draft_line_quantity(
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
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=1,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        {
            "quantity": "5",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:current_order"
    )

    line.refresh_from_db()

    assert line.quantity == 5
    assert line.quantity_in_units == 5


@pytest.mark.django_db
def test_set_draft_line_quantity_returns_json_success(
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

    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=1,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        {
            "quantity": "5",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    assert response.json() == {
        "ok": True,
        "message": "Quantity updated.",
        "quantity": 5,
    }

    line.refresh_from_db()

    assert line.quantity == 5
    assert line.quantity_in_units == 5


@pytest.mark.django_db
def test_set_draft_line_quantity_rejects_invalid_quantity(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        {
            "quantity": "not-a-number",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:current_order"
    )

    line.refresh_from_db()

    assert line.quantity_in_units == 3

    stored_messages = [
        str(message)
        for message in get_messages(
            response.wsgi_request
        )
    ]

    assert stored_messages == [
        "Quantity must be a whole number."
    ]


@pytest.mark.django_db
def test_set_draft_line_quantity_returns_json_error_for_invalid_quantity(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )

    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        {
            "quantity": "not-a-number",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 400

    assert response.json() == {
        "ok": False,
        "message": "Quantity must be a whole number.",
    }

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_line_quantity_shows_business_validation_error(
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
        quantity=10,
    )
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        {
            "quantity": "11",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:current_order"
    )

    line.refresh_from_db()

    assert line.quantity_in_units == 3

    stored_messages = [
        str(message)
        for message in get_messages(
            response.wsgi_request
        )
    ]

    assert stored_messages == [
        "only 10 units are currently available"
    ]


@pytest.mark.django_db
def test_set_draft_line_quantity_returns_json_business_validation_error(
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
        quantity=10,
    )

    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        ),
        {
            "quantity": "11",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 400

    assert response.json() == {
        "ok": False,
        "message": "only 10 units are currently available",
    }

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_line_quantity_cannot_mutate_another_customer_draft(
    client,
):
    customer = customer_factory()
    other_customer = customer_factory(
        name="Other Customer",
        email="other@example.com",
    )
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )

    other_line = _create_draft_line(
        customer=other_customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": other_line.id,
            },
        ),
        {
            "quantity": "5",
        },
    )

    assert response.status_code == 404

    other_line.refresh_from_db()

    assert other_line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_line_quantity_returns_404_for_unknown_line(
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
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": 999999,
            },
        ),
        {
            "quantity": "5",
        },
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_set_draft_line_quantity_get_is_not_allowed(
    client,
):
    customer = customer_factory()
    product = product_factory()
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=1,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.get(
        reverse(
            "business_portal:set_draft_line_quantity",
            kwargs={
                "order_line_id": line.id,
            },
        )
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_customer_can_remove_draft_line(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:remove_draft_line",
            kwargs={
                "order_line_id": line.id,
            },
        )
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:current_order"
    )

    assert not OrderLine.objects.filter(
        pk=line.pk,
    ).exists()


@pytest.mark.django_db
def test_remove_draft_line_allows_empty_draft(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=3,
    )

    order = line.order

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:remove_draft_line",
            kwargs={
                "order_line_id": line.id,
            },
        )
    )

    assert response.status_code == 302

    assert not OrderLine.objects.filter(
        pk=line.pk,
    ).exists()

    assert Order.objects.filter(
        pk=order.pk,
        status=Order.Status.DRAFT,
    ).exists()

    assert not OrderLine.objects.filter(
        order=order,
    ).exists()


@pytest.mark.django_db
def test_remove_draft_line_cannot_mutate_another_customer_draft(
    client,
):
    customer = customer_factory()
    other_customer = customer_factory(
        name="Other Customer",
        email="other@example.com",
    )
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )

    other_line = _create_draft_line(
        customer=other_customer,
        product=product,
        quantity=3,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "business_portal:remove_draft_line",
            kwargs={
                "order_line_id": other_line.id,
            },
        )
    )

    assert response.status_code == 404

    assert OrderLine.objects.filter(
        pk=other_line.pk,
    ).exists()


@pytest.mark.django_db
def test_remove_draft_line_returns_404_for_unknown_line(
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
            "business_portal:remove_draft_line",
            kwargs={
                "order_line_id": 999999,
            },
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_remove_draft_line_get_is_not_allowed(
    client,
):
    customer = customer_factory()
    product = product_factory()
    line = _create_draft_line(
        customer=customer,
        product=product,
        quantity=1,
    )

    user = customer_user_factory(
        customer=customer,
    )
    client.force_login(
        user
    )

    response = client.get(
        reverse(
            "business_portal:remove_draft_line",
            kwargs={
                "order_line_id": line.id,
            },
        )
    )

    assert response.status_code == 405
