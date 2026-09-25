from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from business.datatypes import BusinessOfferLineInput
from business.drafts import resolve_business_offer_lines
from business.tests.conftest import TODAY
from business.tests.factories import (
    standard_business_offer_factory,
)
from inventory.services import create_batch
from orders.errors import InvalidOrderOperation
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)
from products.units import OrderUnit


def _priced_batch_offer(
    *,
    product,
    batch,
    price: str = "8.50",
) -> CommercialPrice:
    offer = CommercialPrice.objects.create(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    PriceAmount.objects.create(
        commercial_price=offer,
        currency=PriceAmount.Currency.EUR,
        price=Decimal(price),
    )

    return offer


@pytest.mark.django_db
def test_resolve_business_offer_lines_resolves_unpriced_standard_offer(
    apple,
):
    offer = standard_business_offer_factory(
        product=apple,
    )

    resolved = resolve_business_offer_lines(
        lines=[
            BusinessOfferLineInput(
                commercial_offer_id=offer.pk,
                quantity=2,
                unit=OrderUnit.STOCK,
            ),
        ],
    )

    assert len(resolved) == 1

    line = resolved[0]

    assert line.product == apple
    assert line.commercial_offer == offer
    assert line.quantity_in_units == 2
    assert line.unit_price_snapshot is None


@pytest.mark.django_db
def test_resolve_business_offer_lines_snapshots_batch_offer_price(
    apple,
):
    batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=10,
        best_before=TODAY + timedelta(days=30),
        location="Shelf A1",
        today=TODAY,
    )
    offer = _priced_batch_offer(
        product=apple,
        batch=batch,
        price="8.50",
    )

    resolved = resolve_business_offer_lines(
        lines=[
            BusinessOfferLineInput(
                commercial_offer_id=offer.pk,
                quantity=3,
                unit=OrderUnit.STOCK,
            ),
        ],
    )

    line = resolved[0]

    assert line.product == apple
    assert line.commercial_offer == offer
    assert line.quantity_in_units == 3
    assert line.unit_price_snapshot == Decimal("8.50")


@pytest.mark.django_db
def test_resolve_business_offer_lines_keeps_distinct_offers_for_same_product(
    apple,
):
    standard_offer = standard_business_offer_factory(
        product=apple,
    )
    batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=10,
        best_before=TODAY + timedelta(days=30),
        location="Shelf A1",
        today=TODAY,
    )
    batch_offer = _priced_batch_offer(
        product=apple,
        batch=batch,
    )

    resolved = resolve_business_offer_lines(
        lines=[
            BusinessOfferLineInput(
                commercial_offer_id=standard_offer.pk,
                quantity=5,
                unit=OrderUnit.STOCK,
            ),
            BusinessOfferLineInput(
                commercial_offer_id=batch_offer.pk,
                quantity=3,
                unit=OrderUnit.STOCK,
            ),
        ],
    )

    assert [
        (
            line.commercial_offer.pk,
            line.quantity_in_units,
        )
        for line in resolved
    ] == [
        (
            standard_offer.pk,
            5,
        ),
        (
            batch_offer.pk,
            3,
        ),
    ]


@pytest.mark.django_db
def test_resolve_business_offer_lines_merges_duplicate_offer_inputs(
    apple,
):
    offer = standard_business_offer_factory(
        product=apple,
    )

    resolved = resolve_business_offer_lines(
        lines=[
            BusinessOfferLineInput(
                commercial_offer_id=offer.pk,
                quantity=2,
                unit=OrderUnit.STOCK,
            ),
            BusinessOfferLineInput(
                commercial_offer_id=offer.pk,
                quantity=3,
                unit=OrderUnit.STOCK,
            ),
        ],
    )

    assert len(resolved) == 1
    assert resolved[0].commercial_offer == offer
    assert resolved[0].quantity_in_units == 5


@pytest.mark.django_db
def test_resolve_business_offer_lines_rejects_non_business_offer(
    apple,
):
    offer = CommercialPrice.objects.create(
        product=apple,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="business channel",
    ):
        resolve_business_offer_lines(
            lines=[
                BusinessOfferLineInput(
                    commercial_offer_id=offer.pk,
                    quantity=1,
                    unit=OrderUnit.STOCK,
                ),
            ],
        )


@pytest.mark.django_db
def test_resolve_business_offer_lines_rejects_disabled_offer(
    apple,
):
    offer = CommercialPrice.objects.create(
        product=apple,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="not currently available",
    ):
        resolve_business_offer_lines(
            lines=[
                BusinessOfferLineInput(
                    commercial_offer_id=offer.pk,
                    quantity=1,
                    unit=OrderUnit.STOCK,
                ),
            ],
        )


@pytest.mark.django_db
def test_resolve_business_offer_lines_rejects_unpriced_batch_offer(
    apple,
):
    batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=10,
        best_before=TODAY + timedelta(days=30),
        location="Shelf A1",
        today=TODAY,
    )
    offer = CommercialPrice.objects.create(
        product=apple,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
        reason=CommercialPrice.Reason.PROMOTION,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="requires an EUR price",
    ):
        resolve_business_offer_lines(
            lines=[
                BusinessOfferLineInput(
                    commercial_offer_id=offer.pk,
                    quantity=1,
                    unit=OrderUnit.STOCK,
                ),
            ],
        )


@pytest.mark.django_db
def test_resolve_business_offer_lines_rejects_missing_offer():
    with pytest.raises(
        InvalidOrderOperation,
        match="does not exist",
    ):
        resolve_business_offer_lines(
            lines=[
                BusinessOfferLineInput(
                    commercial_offer_id=999_999,
                    quantity=1,
                    unit=OrderUnit.STOCK,
                ),
            ],
        )
