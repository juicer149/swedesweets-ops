from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from retail.models import RetailOrder
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    RETAIL_PAYMENT_WINDOW,
)
from retail.services import (
    AnonymousBuyerInput,
    InvalidRetailOrder,
    RetailOrderLineInput,
    create_pending_retail_order,
)
from retail.tests.factories import (
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_create_pending_retail_order():
    retail_postal_area_factory()

    product = retail_product_factory()

    retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    before = timezone.now()

    order = create_pending_retail_order(
        buyer=AnonymousBuyerInput(**retail_buyer_data()),
        lines=[
            RetailOrderLineInput(
                product_id=product.pk,
                quantity=2,
            ),
        ],
    )

    after = timezone.now()

    assert order.status == RetailOrder.Status.PENDING_PAYMENT

    assert order.first_name == "Marie"
    assert order.last_name == "Dupont"
    assert order.email == "marie@example.com"
    assert order.phone_number == "+33612345678"
    assert order.country == "FR"
    assert order.postal_code == "74000"
    assert order.city == "Annecy"
    assert order.address_line == "10 Rue de Test"

    line = order.lines.get()

    assert line.product == product
    assert line.quantity == 2
    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")

    assert order.total == Decimal("25.00")

    assert before + RETAIL_PAYMENT_WINDOW <= order.expires_at
    assert order.expires_at <= after + RETAIL_PAYMENT_WINDOW


@pytest.mark.django_db
def test_existing_order_keeps_original_price_after_product_offer_changes():
    retail_postal_area_factory()

    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    order = create_pending_retail_order(
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

    line = order.lines.get()

    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")
    assert order.total == Decimal("25.00")


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
