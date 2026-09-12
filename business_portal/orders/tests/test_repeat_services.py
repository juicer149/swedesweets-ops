from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from business.models import BusinessOfferSelection
from business.services import create_order
from business_portal.orders.repeat_services import (
    RepeatOrderSkipReason,
    repeat_order_into_draft,
)
from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from customers.tests.factories import customer_factory
from inventory.services import create_batch
from inventory.tests.conftest import TODAY
from inventory.tests.factories import batch_factory
from orders.datatypes import OrderLineInput
from orders.models import Order
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)
from products.tests.factories import product_factory


def _customer(
    *,
    email: str = "repeat@example.com",
):
    return customer_factory(
        email=email,
    )


def _product(
    *,
    name: str,
    internal_number: int,
):
    return product_factory(
        brand="Generic",
        name=name,
        weight_per_unit=5000,
        internal_number=internal_number,
    )


def _stock(
    *,
    product,
    quantity: int = 100,
):
    return batch_factory(
        product=product,
        today=TODAY,
        quantity=quantity,
        batch_id=f"TEST-{product.pk}",
    )


def _standard_catalog_product(
    *,
    product,
    available_units: int,
) -> CatalogProduct:
    return CatalogProduct(
        product=product,
        available_units=available_units,
        offers=(
            CatalogOffer(
                kind=CatalogOfferKind.STANDARD,
                commercial_price_id=None,
                batch_id=None,
                reason=None,
                price=None,
                currency=PriceAmount.Currency.EUR,
                available_units=available_units,
            ),
        ),
    )


@pytest.mark.django_db
def test_repeat_order_adds_standard_line_to_draft(
    monkeypatch,
):
    customer = _customer()
    apple = _product(
        name="Apple",
        internal_number=101,
    )
    _stock(
        product=apple,
    )

    source_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=2,
            ),
        ],
    )

    catalog_product = _standard_catalog_product(
        product=apple,
        available_units=98,
    )

    monkeypatch.setattr(
        "business_portal.orders.repeat_services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
    )

    assert result.added_count == 1
    assert result.skipped == ()
    assert result.draft_order is not None
    assert result.draft_order.status == Order.Status.DRAFT

    line = result.draft_order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 2
    assert (
        line.business_offer_selection.commercial_price_id
        is None
    )


@pytest.mark.django_db
def test_repeat_order_preserves_original_special_offer(
    monkeypatch,
):
    customer = _customer()
    apple = _product(
        name="Apple",
        internal_number=102,
    )

    batch = create_batch(
        batch_id="APPLE-SPECIAL",
        product=apple,
        quantity=20,
        best_before=TODAY + timedelta(days=30),
        location="Shelf A1",
        today=TODAY,
    )

    commercial_price = CommercialPrice.objects.create(
        product=apple,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )

    amount = PriceAmount.objects.create(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("8.50"),
    )

    source_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=2,
            ),
        ],
    )

    source_line = source_order.lines.get()

    BusinessOfferSelection.objects.create(
        order_line=source_line,
        commercial_price=commercial_price,
    )

    catalog_product = CatalogProduct(
        product=apple,
        available_units=18,
        offers=(
            CatalogOffer(
                kind=CatalogOfferKind.BATCH,
                commercial_price_id=commercial_price.id,
                batch_id=batch.id,
                reason=CommercialPrice.Reason.SHORT_DATED,
                price=amount.price,
                currency=PriceAmount.Currency.EUR,
                available_units=18,
            ),
        ),
    )

    monkeypatch.setattr(
        "business_portal.orders.repeat_services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
    )

    assert result.added_count == 1
    assert result.skipped == ()
    assert result.draft_order is not None

    repeated_line = result.draft_order.lines.get()

    assert repeated_line.product == apple
    assert repeated_line.quantity_in_units == 2
    assert (
        repeated_line.business_offer_selection.commercial_price_id
        == commercial_price.id
    )


@pytest.mark.django_db
def test_repeat_order_skips_product_not_in_catalog(
    monkeypatch,
):
    customer = _customer()
    apple = _product(
        name="Apple",
        internal_number=103,
    )
    _stock(
        product=apple,
    )

    source_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=2,
            ),
        ],
    )

    monkeypatch.setattr(
        "business_portal.orders.repeat_services.list_business_catalog_products",
        lambda: (),
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
    )

    assert result.added_count == 0
    assert result.draft_order is None
    assert len(result.skipped) == 1

    skipped = result.skipped[0]

    assert skipped.product == apple
    assert skipped.quantity == 2
    assert (
        skipped.reason
        == RepeatOrderSkipReason.PRODUCT_UNAVAILABLE
    )


@pytest.mark.django_db
def test_repeat_order_skips_special_offer_that_no_longer_exists(
    monkeypatch,
):
    customer = _customer()
    apple = _product(
        name="Apple",
        internal_number=104,
    )
    _stock(
        product=apple,
    )

    commercial_price = CommercialPrice.objects.create(
        product=apple,
        batch=None,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    source_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=2,
            ),
        ],
    )

    source_line = source_order.lines.get()

    BusinessOfferSelection.objects.create(
        order_line=source_line,
        commercial_price=commercial_price,
    )

    catalog_product = _standard_catalog_product(
        product=apple,
        available_units=98,
    )

    monkeypatch.setattr(
        "business_portal.orders.repeat_services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
    )

    assert result.added_count == 0
    assert result.draft_order is None
    assert len(result.skipped) == 1

    skipped = result.skipped[0]

    assert skipped.product == apple
    assert (
        skipped.reason
        == RepeatOrderSkipReason.OFFER_UNAVAILABLE
    )


@pytest.mark.django_db
def test_repeat_order_skips_line_when_original_quantity_is_unavailable(
    monkeypatch,
):
    customer = _customer()
    apple = _product(
        name="Apple",
        internal_number=105,
    )
    _stock(
        product=apple,
    )

    source_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=4,
            ),
        ],
    )

    catalog_product = _standard_catalog_product(
        product=apple,
        available_units=2,
    )

    monkeypatch.setattr(
        "business_portal.orders.repeat_services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
    )

    assert result.added_count == 0
    assert result.draft_order is None
    assert len(result.skipped) == 1

    skipped = result.skipped[0]

    assert skipped.product == apple
    assert skipped.quantity == 4
    assert (
        skipped.reason
        == RepeatOrderSkipReason.QUANTITY_UNAVAILABLE
    )


@pytest.mark.django_db
def test_repeat_order_keeps_successful_lines_when_another_line_is_skipped(
    monkeypatch,
):
    customer = _customer()

    apple = _product(
        name="Apple",
        internal_number=106,
    )
    banana = _product(
        name="Banana",
        internal_number=107,
    )

    _stock(
        product=apple,
    )
    _stock(
        product=banana,
    )

    source_order = create_order(
        customer=customer,
        lines=[
            OrderLineInput.units(
                product=apple,
                quantity=2,
            ),
            OrderLineInput.units(
                product=banana,
                quantity=3,
            ),
        ],
    )

    apple_catalog_product = _standard_catalog_product(
        product=apple,
        available_units=98,
    )

    monkeypatch.setattr(
        "business_portal.orders.repeat_services.list_business_catalog_products",
        lambda: (
            apple_catalog_product,
        ),
    )

    result = repeat_order_into_draft(
        customer=customer,
        source_order=source_order,
    )

    assert result.added_count == 1
    assert len(result.skipped) == 1

    skipped = result.skipped[0]

    assert skipped.product == banana
    assert (
        skipped.reason
        == RepeatOrderSkipReason.PRODUCT_UNAVAILABLE
    )

    assert result.draft_order is not None

    assert list(
        result.draft_order.lines.values_list(
            "product_id",
            "quantity_in_units",
        )
    ) == [
        (
            apple.id,
            2,
        ),
    ]
