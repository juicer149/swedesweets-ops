from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.tests.factories import (
    customer_user_factory,
)
from business.models import BusinessOfferSelection
from customers.tests.factories import (
    customer_factory,
)
from inventory.tests.conftest import TODAY
from inventory.tests.factories import (
    batch_factory,
)
from orders.models import Order
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)
from products.tests.factories import (
    product_factory,
)


def _business_price(
    *,
    product,
    batch=None,
    price: str = "8.50",
    enabled: bool = True,
    reason: str = "",
) -> CommercialPrice:
    commercial_price = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=enabled,
        reason=reason,
    )

    PriceAmount.objects.create(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal(price),
    )

    return commercial_price


def _stored_messages(
    response,
) -> list[str]:
    return [
        str(message)
        for message in get_messages(
            response.wsgi_request
        )
    ]


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
    assert line.unit_price_snapshot is None

    selection = line.business_offer_selection

    assert isinstance(
        selection,
        BusinessOfferSelection,
    )
    assert selection.commercial_price_id is None


@pytest.mark.django_db
def test_catalog_add_product_defaults_missing_quantity_to_one(
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
        ),
        {
            "commercial_price_id": "",
        },
    )

    assert response.status_code == 302

    order = Order.objects.get(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    line = order.lines.get()

    assert line.quantity_in_units == 1


@pytest.mark.django_db
def test_catalog_add_product_accepts_explicit_quantity(
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
        ),
        {
            "commercial_price_id": "",
            "quantity": "4",
        },
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
    assert line.quantity_in_units == 4
    assert line.unit_price_snapshot is None
    assert (
        line.business_offer_selection.commercial_price_id
        is None
    )


@pytest.mark.django_db
def test_catalog_add_product_accepts_explicit_quantity_for_batch_offer(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )

    batch = batch_factory(
        product=product,
        today=TODAY,
        quantity=100,
    )

    commercial_price = _business_price(
        product=product,
        batch=batch,
        price="7.50",
        reason=CommercialPrice.Reason.SHORT_DATED,
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
        ),
        {
            "commercial_price_id": str(
                commercial_price.pk
            ),
            "quantity": "3",
        },
    )

    assert response.status_code == 302

    order = Order.objects.get(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    line = order.lines.get()

    assert line.product == product
    assert line.quantity_in_units == 3
    assert line.unit_price_snapshot == Decimal("7.50")
    assert (
        line.business_offer_selection.commercial_price
        == commercial_price
    )


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

    first_response = client.post(
        url,
        {
            "commercial_price_id": "",
            "quantity": "2",
        },
    )
    second_response = client.post(
        url,
        {
            "commercial_price_id": "",
            "quantity": "3",
        },
    )

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
    assert line.quantity_in_units == 5
    assert (
        line.business_offer_selection.commercial_price_id
        is None
    )


@pytest.mark.django_db
def test_catalog_add_product_rejects_empty_quantity(
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
        ),
        {
            "commercial_price_id": "",
            "quantity": "",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )

    assert _stored_messages(
        response
    ) == [
        "quantity is required"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "quantity",
        "expected_message",
    ),
    [
        (
            "abc",
            "invalid quantity",
        ),
        (
            "1.5",
            "invalid quantity",
        ),
        (
            "0",
            "quantity must be greater than zero",
        ),
        (
            "-1",
            "quantity must be greater than zero",
        ),
    ],
)
def test_catalog_add_product_rejects_invalid_quantity(
    client,
    quantity,
    expected_message,
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
        ),
        {
            "commercial_price_id": "",
            "quantity": quantity,
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )

    assert _stored_messages(
        response
    ) == [
        expected_message
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_returns_json_error_for_empty_quantity(
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
        ),
        {
            "commercial_price_id": "",
            "quantity": "",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "message": "quantity is required",
    }

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_returns_json_error_for_invalid_quantity(
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
        ),
        {
            "commercial_price_id": "",
            "quantity": "abc",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "message": "invalid quantity",
    }

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_accepts_explicit_standard_selection(
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
        ),
        {
            "commercial_price_id": "",
        },
    )

    assert response.status_code == 302

    order = Order.objects.get(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    line = order.lines.get()

    assert line.product == product
    assert line.quantity_in_units == 1
    assert line.unit_price_snapshot is None
    assert (
        line.business_offer_selection.commercial_price_id
        is None
    )


@pytest.mark.django_db
def test_catalog_add_product_accepts_business_batch_offer(
    client,
):
    customer = customer_factory()
    product = product_factory(
        name="Apple",
        weight_per_unit=5000,
    )

    batch = batch_factory(
        product=product,
        today=TODAY,
        quantity=10,
    )

    commercial_price = _business_price(
        product=product,
        batch=batch,
        price="7.50",
        reason=CommercialPrice.Reason.SHORT_DATED,
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
        ),
        {
            "commercial_price_id": str(
                commercial_price.pk
            ),
        },
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
    assert line.unit_price_snapshot == Decimal("7.50")
    assert (
        line.business_offer_selection.commercial_price
        == commercial_price
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "commercial_price_id",
    [
        "abc",
        "0",
        "-1",
    ],
)
def test_catalog_add_product_rejects_invalid_offer_id(
    client,
    commercial_price_id,
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
        ),
        {
            "commercial_price_id": commercial_price_id,
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )

    assert _stored_messages(
        response
    ) == [
        "invalid business offer"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_rejects_unknown_offer_id(
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
        ),
        {
            "commercial_price_id": "999999",
        },
    )

    assert response.status_code == 302

    assert _stored_messages(
        response
    ) == [
        "business offer is not currently available"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_rejects_retail_price(
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

    retail_price = CommercialPrice.objects.create(
        product=product,
        batch=None,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )

    PriceAmount.objects.create(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("12.50"),
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
        ),
        {
            "commercial_price_id": str(
                retail_price.pk
            ),
        },
    )

    assert response.status_code == 302

    assert _stored_messages(
        response
    ) == [
        "business offer is not currently available"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_rejects_disabled_business_price(
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

    disabled_price = _business_price(
        product=product,
        enabled=False,
        price="12.50",
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
        ),
        {
            "commercial_price_id": str(
                disabled_price.pk
            ),
        },
    )

    assert response.status_code == 302

    assert _stored_messages(
        response
    ) == [
        "business offer is not currently available"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_catalog_add_product_returns_json_success(
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
        quantity=10,
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
        ),
        {
            "commercial_price_id": "",
            "quantity": "3",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    assert response.json() == {
        "ok": True,
        "message": "Generic — Apple added to your order.",
    }

    order = Order.objects.get(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    assert order.lines.get().quantity_in_units == 3


@pytest.mark.django_db
def test_catalog_add_product_returns_json_error_for_invalid_offer(
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
        ),
        {
            "commercial_price_id": "abc",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 400

    assert response.json() == {
        "ok": False,
        "message": "invalid business offer",
    }

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


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
        ),
        {
            "commercial_price_id": "",
            "quantity": "2",
        },
    )

    assert _stored_messages(
        response
    ) == [
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
        ),
        {
            "commercial_price_id": "",
            "quantity": "2",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )

    assert _stored_messages(
        response
    ) == [
        "product is not available in the business catalog"
    ]

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()
