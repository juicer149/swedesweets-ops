from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from orders.models import Order, OrderLine
from retail.models import (
    RetailCheckoutSession,
    RetailOrder,
    RetailOrderLine,
)
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_TOTAL,
    RETAIL_PAYMENT_WINDOW,
)
from retail.services import (
    AnonymousBuyerInput,
    InvalidRetailOrder,
    RetailOrderLineInput,
    buyer_from_anonymous_retail_input,
    create_pending_retail_order,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_create_pending_retail_order_creates_checkout_with_common_order():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    before = timezone.now()

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(**retail_buyer_data()),
        lines=[
            RetailOrderLineInput(
                product_id=product.pk,
                quantity=2,
            ),
        ],
    )

    after = timezone.now()

    assert isinstance(checkout, RetailCheckoutSession)

    order = checkout.order

    assert order.channel == Order.Channel.RETAIL
    assert order.currency == Order.Currency.EUR
    assert order.status == Order.Status.DRAFT
    assert order.customer is None

    assert order.buyer_name == "Marie Dupont"
    assert order.buyer_email == "marie@example.com"
    assert order.buyer_phone_number == "+33612345678"
    assert order.buyer_country == "FR"
    assert order.buyer_postal_code == "74000"
    assert order.buyer_city == "Annecy"
    assert order.buyer_address_line == "10 Rue de Test"

    line = order.lines.get()

    assert line.product == product
    assert line.quantity == Decimal("2.000")
    assert line.unit == OrderLine.Unit.STOCK_UNIT
    assert line.quantity_in_units == 2
    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")

    assert order.total == Decimal("25.00")

    assert before + RETAIL_PAYMENT_WINDOW <= checkout.expires_at
    assert checkout.expires_at <= after + RETAIL_PAYMENT_WINDOW


@pytest.mark.django_db
def test_pending_retail_checkout_does_not_create_legacy_retail_order():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    create_pending_retail_order(
        buyer=AnonymousBuyerInput(**retail_buyer_data()),
        lines=[
            RetailOrderLineInput(
                product_id=product.pk,
                quantity=1,
            ),
        ],
    )

    assert RetailOrder.objects.count() == 0
    assert RetailOrderLine.objects.count() == 0

    assert Order.objects.count() == 1
    assert OrderLine.objects.count() == 1
    assert RetailCheckoutSession.objects.count() == 1


@pytest.mark.django_db
def test_existing_order_keeps_original_price_after_product_offer_changes():
    retail_postal_area_factory()

    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(**retail_buyer_data()),
        lines=[
            RetailOrderLineInput(
                product_id=product.pk,
                quantity=2,
            ),
        ],
    )

    offer.price = Decimal("20.00")
    offer.save(update_fields=["price"])

    line = checkout.order.lines.get()

    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")
    assert checkout.order.total == Decimal("25.00")


@pytest.mark.django_db
def test_anonymous_retail_buyer_is_normalized_before_snapshot():
    buyer = AnonymousBuyerInput(
        first_name="  Marie  ",
        last_name="  Dupont  ",
        email="  marie@example.com  ",
        phone_number="  +33612345678  ",
        country=" fr ",
        postal_code=" 74000 ",
        city="  Annecy   Centre  ",
        address_line="  10   Rue de Test  ",
    )

    order_buyer = buyer_from_anonymous_retail_input(
        buyer=buyer,
    )

    assert order_buyer.name == "Marie Dupont"
    assert order_buyer.email == "marie@example.com"
    assert order_buyer.phone_number == "+33612345678"
    assert order_buyer.country == "FR"
    assert order_buyer.postal_code == "74000"
    assert order_buyer.city == "Annecy Centre"
    assert order_buyer.address_line == "10 Rue de Test"


@pytest.mark.django_db
def test_pending_retail_order_requires_at_least_one_line():
    retail_postal_area_factory()

    with pytest.raises(
        InvalidRetailOrder,
        match="at least one",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[],
        )


@pytest.mark.django_db
def test_pending_retail_order_requires_supported_destination():
    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    buyer = AnonymousBuyerInput(
        **retail_buyer_data(
            postal_code="75001",
            city="Paris",
        )
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="destination",
    ):
        create_pending_retail_order(
            buyer=buyer,
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                )
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_product_without_retail_offer():
    retail_postal_area_factory()

    product = retail_product_factory()

    with pytest.raises(
        InvalidRetailOrder,
        match="retail offer",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                )
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_disabled_product_offer():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=False,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                )
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_inactive_product():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    product.active = False
    product.save(update_fields=["active"])

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                )
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_quantity_above_retail_limit():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="quantity",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=MAX_RETAIL_LINE_QUANTITY + 1,
                )
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_duplicate_product_lines():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="duplicate",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                ),
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_retail_order_total_limit_rolls_back_checkout():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=MAX_RETAIL_ORDER_TOTAL + Decimal("1.00"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="maximum",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(**retail_buyer_data()),
            lines=[
                RetailOrderLineInput(
                    product_id=product.pk,
                    quantity=1,
                ),
            ],
        )

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert RetailCheckoutSession.objects.count() == 0
