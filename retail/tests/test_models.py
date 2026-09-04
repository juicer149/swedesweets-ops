from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.models import Order, OrderLine
from pricing.models import CommercialPrice, PriceAmount
from retail.models import (
    RetailCart,
    RetailCartLine,
    RetailCheckoutSession,
    RetailOfferSelection,
)
from retail.rules import RETAIL_CHECKOUT_WINDOW
from retail.tests.factories import (
    retail_batch_price_factory,
    retail_postal_area_factory,
    retail_product_price_factory,
)


@pytest.mark.django_db
def test_retail_postal_area_normalizes_values():
    area = retail_postal_area_factory(
        country_code=" fr ",
        postal_code=" 74000 ",
        city="  La   Roche-sur-Foron  ",
    )

    assert area.country_code == "FR"
    assert area.postal_code == "74000"
    assert area.city == "La Roche-sur-Foron"


@pytest.mark.django_db
def test_retail_postal_area_combination_must_be_unique():
    retail_postal_area_factory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_postal_area_factory()


@pytest.mark.django_db
def test_retail_cart_can_be_created_empty():
    cart = RetailCart.objects.create()

    assert cart.pk.version == 4
    assert cart.lines.count() == 0


@pytest.mark.django_db
def test_retail_cart_line_references_commercial_price():
    cart = RetailCart.objects.create()
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    line = RetailCartLine.objects.create(
        cart=cart,
        commercial_price=commercial_price,
        quantity=2,
    )

    assert line.commercial_price == commercial_price
    assert line.quantity == 2


@pytest.mark.django_db
def test_retail_cart_line_requires_commercial_price():
    cart = RetailCart.objects.create()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                quantity=1,
            )


@pytest.mark.django_db
@pytest.mark.parametrize("quantity", [0, -1])
def test_retail_cart_line_quantity_must_be_positive(quantity):
    cart = RetailCart.objects.create()
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                commercial_price=commercial_price,
                quantity=quantity,
            )


@pytest.mark.django_db
def test_same_commercial_price_can_appear_only_once_per_cart():
    cart = RetailCart.objects.create()
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    RetailCartLine.objects.create(
        cart=cart,
        commercial_price=commercial_price,
        quantity=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                commercial_price=commercial_price,
                quantity=2,
            )


@pytest.mark.django_db
def test_same_product_can_have_product_and_batch_price_in_same_cart():
    product_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    product = product_price.product

    from retail.tests.factories import retail_inventory_batch_factory

    batch = retail_inventory_batch_factory(
        product=product,
        batch_id="SAME-PRODUCT",
    )
    batch_price = retail_batch_price_factory(
        batch=batch,
        enabled=True,
        price=Decimal("4.90"),
    )

    cart = RetailCart.objects.create()

    first = RetailCartLine.objects.create(
        cart=cart,
        commercial_price=product_price,
        quantity=1,
    )
    second = RetailCartLine.objects.create(
        cart=cart,
        commercial_price=batch_price,
        quantity=2,
    )

    assert first.commercial_price.product == second.commercial_price.product
    assert first.commercial_price_id != second.commercial_price_id


@pytest.mark.django_db
def test_retail_checkout_session_owns_retail_order():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    checkout = RetailCheckoutSession.objects.create(
        order=order,
        expires_at=timezone.now() + RETAIL_CHECKOUT_WINDOW,
    )

    assert checkout.order == order
    assert order.retail_checkout == checkout
    assert checkout.pk.version == 4


@pytest.mark.django_db
def test_order_can_have_only_one_retail_checkout_session():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    RetailCheckoutSession.objects.create(
        order=order,
        expires_at=timezone.now() + RETAIL_CHECKOUT_WINDOW,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCheckoutSession.objects.create(
                order=order,
                expires_at=timezone.now() + RETAIL_CHECKOUT_WINDOW,
            )


@pytest.mark.django_db
def test_retail_offer_selection_references_commercial_price():
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=commercial_price.product,
        quantity=2,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=2,
        unit_price_snapshot=Decimal("12.50"),
    )

    selection = RetailOfferSelection.objects.create(
        order_line=line,
        commercial_price=commercial_price,
    )

    assert selection.order_line == line
    assert selection.commercial_price == commercial_price
    assert line.retail_offer_selection == selection


@pytest.mark.django_db
def test_retail_offer_selection_requires_commercial_price():
    commercial_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=commercial_price.product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailOfferSelection.objects.create(
                order_line=line,
            )
