from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.models import Order, OrderLine
from retail.models import (
    RetailBatchOffer,
    RetailCart,
    RetailCartLine,
    RetailCheckoutSession,
    RetailOfferSelection,
    RetailProductOffer,
)
from retail.rules import RETAIL_CHECKOUT_WINDOW
from retail.tests.factories import (
    retail_batch_offer_factory,
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_retail_postal_area_normalizes_country_postal_code_and_city():
    area = retail_postal_area_factory(
        country_code=" fr ",
        postal_code=" 74000 ",
        city="  Annecy  ",
    )

    assert area.country_code == "FR"
    assert area.postal_code == "74000"
    assert area.city == "Annecy"


@pytest.mark.django_db
def test_retail_postal_area_collapses_city_whitespace():
    area = retail_postal_area_factory(
        city="La   Roche-sur-Foron",
    )

    assert area.city == "La Roche-sur-Foron"


@pytest.mark.django_db
def test_retail_postal_area_is_enabled_by_default():
    area = retail_postal_area_factory()

    assert area.enabled is True


@pytest.mark.django_db
def test_retail_postal_area_combination_must_be_unique():
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_postal_area_factory(
                country_code="FR",
                postal_code="74000",
                city="Annecy",
            )


@pytest.mark.django_db
def test_same_postal_code_can_represent_different_cities():
    first = retail_postal_area_factory(
        postal_code="74000",
        city="Annecy",
    )
    second = retail_postal_area_factory(
        postal_code="74000",
        city="Annecy Cedex",
    )

    assert first.pk != second.pk


@pytest.mark.django_db
def test_retail_product_offer_belongs_to_product():
    offer = retail_product_offer_factory()

    assert offer.product is not None


@pytest.mark.django_db
def test_retail_product_offer_is_disabled_by_default():
    offer = retail_product_offer_factory()

    assert offer.enabled is False


@pytest.mark.django_db
def test_disabled_retail_product_offer_may_have_no_price():
    offer = retail_product_offer_factory(
        enabled=False,
        price=None,
    )

    assert offer.price is None


@pytest.mark.django_db
def test_disabled_retail_product_offer_may_have_price():
    offer = retail_product_offer_factory(
        enabled=False,
        price=Decimal("12.50"),
    )

    assert offer.price == Decimal("12.50")


@pytest.mark.django_db
def test_product_can_have_only_one_retail_offer():
    offer = retail_product_offer_factory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailProductOffer.objects.create(
                product=offer.product,
                enabled=False,
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "price",
    [
        Decimal("0.00"),
        Decimal("-0.01"),
    ],
)
def test_retail_product_offer_price_must_be_positive_when_present(price):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_product_offer_factory(
                enabled=False,
                price=price,
            )


@pytest.mark.django_db
def test_enabled_retail_product_offer_requires_price():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_product_offer_factory(
                enabled=True,
                price=None,
            )


@pytest.mark.django_db
def test_enabled_retail_product_offer_accepts_positive_price():
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    assert offer.enabled is True
    assert offer.price == Decimal("12.50")


@pytest.mark.django_db
def test_retail_cart_can_be_created_empty():
    cart = RetailCart.objects.create()

    assert cart.pk is not None
    assert cart.lines.count() == 0


@pytest.mark.django_db
def test_retail_cart_uses_uuid_primary_key():
    cart = RetailCart.objects.create()

    assert cart.pk.version == 4


@pytest.mark.django_db
def test_retail_cart_line_can_reference_product_offer():
    cart = RetailCart.objects.create()
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    line = RetailCartLine.objects.create(
        cart=cart,
        product_offer=offer,
        quantity=2,
    )

    assert line.cart == cart
    assert line.product_offer == offer
    assert line.batch_offer is None
    assert line.quantity == 2


@pytest.mark.django_db
def test_retail_cart_line_can_reference_batch_offer():
    cart = RetailCart.objects.create()
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    line = RetailCartLine.objects.create(
        cart=cart,
        batch_offer=offer,
        quantity=2,
    )

    assert line.cart == cart
    assert line.product_offer is None
    assert line.batch_offer == offer
    assert line.quantity == 2


@pytest.mark.django_db
def test_retail_cart_line_requires_an_offer():
    cart = RetailCart.objects.create()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                quantity=1,
            )


@pytest.mark.django_db
def test_retail_cart_line_rejects_two_offers():
    cart = RetailCart.objects.create()
    product_offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    batch_offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                product_offer=product_offer,
                batch_offer=batch_offer,
                quantity=1,
            )


@pytest.mark.django_db
@pytest.mark.parametrize("quantity", [0, -1])
def test_retail_cart_line_quantity_must_be_positive(quantity: int):
    cart = RetailCart.objects.create()
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                product_offer=offer,
                quantity=quantity,
            )


@pytest.mark.django_db
def test_product_offer_can_appear_only_once_per_cart():
    cart = RetailCart.objects.create()
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    RetailCartLine.objects.create(
        cart=cart,
        product_offer=offer,
        quantity=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                product_offer=offer,
                quantity=2,
            )


@pytest.mark.django_db
def test_batch_offer_can_appear_only_once_per_cart():
    cart = RetailCart.objects.create()
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    RetailCartLine.objects.create(
        cart=cart,
        batch_offer=offer,
        quantity=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailCartLine.objects.create(
                cart=cart,
                batch_offer=offer,
                quantity=2,
            )


@pytest.mark.django_db
def test_same_offer_can_appear_in_different_carts():
    first_cart = RetailCart.objects.create()
    second_cart = RetailCart.objects.create()
    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    first_line = RetailCartLine.objects.create(
        cart=first_cart,
        product_offer=offer,
        quantity=1,
    )
    second_line = RetailCartLine.objects.create(
        cart=second_cart,
        product_offer=offer,
        quantity=2,
    )

    assert first_line.pk != second_line.pk


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


@pytest.mark.django_db
def test_retail_checkout_session_uses_uuid_primary_key():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    checkout = RetailCheckoutSession.objects.create(
        order=order,
        expires_at=timezone.now() + RETAIL_CHECKOUT_WINDOW,
    )

    assert checkout.pk is not None
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
def test_retail_checkout_session_tracks_expiry():
    before = timezone.now()

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    checkout = RetailCheckoutSession.objects.create(
        order=order,
        expires_at=before + RETAIL_CHECKOUT_WINDOW,
    )

    assert checkout.expires_at == before + RETAIL_CHECKOUT_WINDOW


@pytest.mark.django_db
def test_deleting_order_deletes_retail_checkout_session():
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )

    checkout = RetailCheckoutSession.objects.create(
        order=order,
        expires_at=timezone.now() + RETAIL_CHECKOUT_WINDOW,
    )

    checkout_id = checkout.pk

    order.delete()

    assert not RetailCheckoutSession.objects.filter(pk=checkout_id).exists()


@pytest.mark.django_db
def test_retail_offer_selection_can_reference_product_offer():
    product = retail_product_factory()
    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=2,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=2,
        unit_price_snapshot=Decimal("12.50"),
    )

    selection = RetailOfferSelection.objects.create(
        order_line=line,
        product_offer=offer,
    )

    assert selection.order_line == line
    assert selection.product_offer == offer
    assert selection.batch_offer is None
    assert line.retail_offer_selection == selection


@pytest.mark.django_db
def test_retail_offer_selection_can_reference_batch_offer():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )
    product = offer.batch.product

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=2,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=2,
        unit_price_snapshot=Decimal("4.90"),
    )

    selection = RetailOfferSelection.objects.create(
        order_line=line,
        batch_offer=offer,
    )

    assert selection.order_line == line
    assert selection.product_offer is None
    assert selection.batch_offer == offer


@pytest.mark.django_db
def test_retail_offer_selection_requires_an_offer():
    product = retail_product_factory()

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailOfferSelection.objects.create(
                order_line=line,
            )


@pytest.mark.django_db
def test_retail_offer_selection_rejects_two_offers():
    product_offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    batch_offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=None,
    )
    line = OrderLine.objects.create(
        order=order,
        product=product_offer.product,
        quantity=1,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailOfferSelection.objects.create(
                order_line=line,
                product_offer=product_offer,
                batch_offer=batch_offer,
            )


@pytest.mark.django_db
def test_retail_batch_offer_belongs_to_inventory_batch():
    offer = retail_batch_offer_factory()

    assert offer.batch is not None


@pytest.mark.django_db
def test_retail_batch_offer_is_disabled_by_default():
    offer = retail_batch_offer_factory()

    assert offer.enabled is False


@pytest.mark.django_db
def test_disabled_retail_batch_offer_may_have_no_price():
    offer = retail_batch_offer_factory(
        enabled=False,
        price=None,
    )

    assert offer.price is None


@pytest.mark.django_db
def test_disabled_retail_batch_offer_may_have_price():
    offer = retail_batch_offer_factory(
        enabled=False,
        price=Decimal("4.90"),
    )

    assert offer.price == Decimal("4.90")


@pytest.mark.django_db
def test_inventory_batch_can_have_only_one_retail_offer():
    offer = retail_batch_offer_factory()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            RetailBatchOffer.objects.create(
                batch=offer.batch,
                enabled=False,
            )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "price",
    [
        Decimal("0.00"),
        Decimal("-0.01"),
    ],
)
def test_retail_batch_offer_price_must_be_positive_when_present(price):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_batch_offer_factory(
                enabled=False,
                price=price,
            )


@pytest.mark.django_db
def test_enabled_retail_batch_offer_requires_price():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_batch_offer_factory(
                enabled=True,
                price=None,
            )


@pytest.mark.django_db
def test_enabled_retail_batch_offer_accepts_positive_price():
    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    assert offer.enabled is True
    assert offer.price == Decimal("4.90")
