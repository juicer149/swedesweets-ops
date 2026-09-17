from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from customers.tests.factories import (
    customer_factory,
)
from accounts.tests.factories import (
    customer_user_factory,
)
from pricing.models import CommercialPrice, PriceAmount
from products.tests.factories import product_factory
from retail.models import RetailCart
from retail.tests.factories import (
    retail_inventory_batch_factory,
    retail_product_price_factory,
)


def _stored_messages(response) -> list[str]:
    return [
        str(message)
        for message in get_messages(
            response.wsgi_request
        )
    ]


# ---------------------------------------------------------------------------
# product_list / product_detail - anonymous access + AUTH_EXEMPT regression
# ---------------------------------------------------------------------------
#
# These views must be reachable without login. A missing entry in
# storefront.access.AUTH_EXEMPT_VIEWS would show up here as a 302 redirect
# to login rather than 200, since these tests never call client.force_login.


@pytest.mark.django_db
def test_product_list_is_reachable_by_anonymous_visitors(client):
    response = client.get(
        reverse("storefront:product_list")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_product_detail_is_reachable_by_anonymous_visitors(client):
    product = product_factory(
        name="Apple",
    )
    retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )
    retail_inventory_batch_factory(
        product=product,
        quantity=10,
    )

    response = client.get(
        reverse(
            "storefront:product_detail",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_product_detail_returns_404_for_unknown_product(client):
    response = client.get(
        reverse(
            "storefront:product_detail",
            kwargs={
                "product_id": 999999,
            },
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_product_detail_returns_404_for_product_without_retail_price(
    client,
):
    product = product_factory(
        name="Business Only",
    )

    business_price = CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    PriceAmount.objects.create(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )

    response = client.get(
        reverse(
            "storefront:product_detail",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# storefront sales-channel boundary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_business_customer_is_redirected_from_retail_catalog(
    client,
):
    customer = customer_factory()
    user = customer_user_factory(
        customer=customer,
    )

    client.force_login(
        user
    )

    response = client.get(
        reverse("storefront:product_list")
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog"
    )


@pytest.mark.django_db
def test_business_customer_is_redirected_from_retail_product_detail(
    client,
):
    customer = customer_factory()
    user = customer_user_factory(
        customer=customer,
    )
    product = product_factory(
        name="Apple",
    )

    client.force_login(
        user
    )

    response = client.get(
        reverse(
            "storefront:product_detail",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:catalog_product",
        kwargs={
            "product_id": product.id,
        },
    )


@pytest.mark.django_db
def test_business_customer_cannot_mutate_retail_cart(
    client,
):
    customer = customer_factory()
    user = customer_user_factory(
        customer=customer,
    )
    product = product_factory(
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    client.force_login(
        user
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
            "quantity": "1",
        },
    )

    assert response.status_code == 403
    assert not RetailCart.objects.exists()
    assert "retail_cart" not in response.cookies


# ---------------------------------------------------------------------------
# add_to_cart - success + cart cookie lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_add_to_cart_creates_cart_and_sets_cookie_for_new_visitor(client):
    product = product_factory(
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "storefront:product_list"
    )

    assert "retail_cart" in response.cookies

    cart = RetailCart.objects.get()
    line = cart.lines.get()

    assert line.commercial_price == offer
    assert line.quantity == 1


@pytest.mark.django_db
def test_add_to_cart_reuses_existing_cart_across_requests(client):
    product = product_factory(
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    url = reverse(
        "storefront:add_to_cart",
        kwargs={
            "product_id": product.id,
        },
    )

    first_response = client.post(
        url,
        {
            "commercial_price_id": str(
                offer.pk
            ),
            "quantity": "2",
        },
    )
    second_response = client.post(
        url,
        {
            "commercial_price_id": str(
                offer.pk
            ),
            "quantity": "3",
        },
    )

    assert first_response.status_code == 302
    assert second_response.status_code == 302

    # The client's cookie jar carries the signed cart cookie between
    # requests, the same way a browser would - so this is one cart, one
    # merged line, not two.
    assert RetailCart.objects.count() == 1

    cart = RetailCart.objects.get()
    line = cart.lines.get()

    assert line.quantity == 5


@pytest.mark.django_db
def test_add_to_cart_shows_success_message(client):
    product = product_factory(
        brand="Generic",
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
        },
    )

    assert _stored_messages(response) == [
        "Generic — Apple added to your cart."
    ]


@pytest.mark.django_db
def test_add_to_cart_returns_json_success(client):
    product = product_factory(
        brand="Generic",
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
            "quantity": "3",
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "message": "Generic — Apple added to your cart.",
    }


# ---------------------------------------------------------------------------
# add_to_cart - validation errors
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_add_to_cart_requires_commercial_price_id(client):
    product = product_factory(
        name="Apple",
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": "",
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        "an offer must be selected"
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "commercial_price_id",
    [
        "abc",
        "0",
        "-1",
    ],
)
def test_add_to_cart_rejects_invalid_offer_id(
    client,
    commercial_price_id,
):
    product = product_factory(
        name="Apple",
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": commercial_price_id,
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        "invalid retail offer"
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_rejects_unknown_offer_id(client):
    product = product_factory(
        name="Apple",
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": "999999",
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        "retail commercial price does not exist"
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_rejects_business_price(client):
    product = product_factory(
        name="Apple",
    )

    business_price = CommercialPrice.objects.create(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    PriceAmount.objects.create(
        commercial_price=business_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("9.00"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                business_price.pk
            ),
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        "commercial price does not belong to retail"
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_rejects_disabled_price(client):
    product = product_factory(
        name="Apple",
    )
    disabled_offer = retail_product_price_factory(
        product=product,
        enabled=False,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                disabled_offer.pk
            ),
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        "commercial price is not enabled for retail"
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_defaults_missing_quantity_to_one(client):
    product = product_factory(
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
        },
    )

    assert response.status_code == 302

    line = RetailCart.objects.get().lines.get()

    assert line.quantity == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "quantity",
        "expected_message",
    ),
    [
        (
            "",
            "quantity is required",
        ),
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
def test_add_to_cart_rejects_invalid_quantity(
    client,
    quantity,
    expected_message,
):
    product = product_factory(
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
            "quantity": quantity,
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        expected_message
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_rejects_quantity_above_line_maximum(client):
    product = product_factory(
        name="Apple",
    )
    offer = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        ),
        {
            "commercial_price_id": str(
                offer.pk
            ),
            "quantity": "21",
        },
    )

    assert response.status_code == 302
    assert _stored_messages(response) == [
        "invalid retail cart line quantity"
    ]
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_returns_json_error_for_invalid_offer(client):
    product = product_factory(
        name="Apple",
    )

    response = client.post(
        reverse(
            "storefront:add_to_cart",
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
        "message": "invalid retail offer",
    }
    assert not RetailCart.objects.exists()


@pytest.mark.django_db
def test_add_to_cart_get_is_not_allowed(client):
    product = product_factory(
        name="Apple",
    )

    response = client.get(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": product.id,
            },
        )
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_add_to_cart_returns_404_for_unknown_product(client):
    response = client.post(
        reverse(
            "storefront:add_to_cart",
            kwargs={
                "product_id": 999999,
            },
        )
    )

    assert response.status_code == 404
    assert not RetailCart.objects.exists()
