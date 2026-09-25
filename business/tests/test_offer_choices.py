from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from business.offer_choices import (
    build_business_offer_choice_context,
)
from business.services import (
    add_catalog_offer_to_draft_order,
    place_order,
)
from business.tests.conftest import TODAY
from business.tests.factories import (
    standard_business_offer_factory,
)
from customers.tests.factories import customer_factory
from inventory.services import create_batch
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)


def _batch_offer(
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
def test_business_offer_choice_context_keeps_offer_pools_separate(
    apple,
):
    create_batch(
        batch_id="A-ORDINARY",
        product=apple,
        quantity=6,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )
    special_batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=4,
        best_before=TODAY + timedelta(days=30),
        location="Shelf A2",
        today=TODAY,
    )

    standard_offer = standard_business_offer_factory(
        product=apple,
    )
    special_offer = _batch_offer(
        product=apple,
        batch=special_batch,
    )

    context = build_business_offer_choice_context()

    assert set(
        context.queryset.values_list(
            "pk",
            flat=True,
        )
    ) == {
        standard_offer.pk,
        special_offer.pk,
    }

    assert context.available_units_by_offer_id == {
        standard_offer.pk: 6,
        special_offer.pk: 4,
    }


@pytest.mark.django_db
def test_business_offer_choice_context_adds_back_placed_order_quantity_per_offer(
    apple,
):
    customer = customer_factory()

    create_batch(
        batch_id="A-ORDINARY",
        product=apple,
        quantity=6,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )
    special_batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=4,
        best_before=TODAY + timedelta(days=30),
        location="Shelf A2",
        today=TODAY,
    )

    standard_offer = standard_business_offer_factory(
        product=apple,
    )
    special_offer = _batch_offer(
        product=apple,
        batch=special_batch,
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=standard_offer.pk,
        quantity=5,
    )
    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=special_offer.pk,
        quantity=3,
    )
    order = place_order(
        order=order,
    )

    context = build_business_offer_choice_context(
        order=order,
    )

    assert context.available_units_by_offer_id[
        standard_offer.pk
    ] == 6

    assert context.available_units_by_offer_id[
        special_offer.pk
    ] == 4


@pytest.mark.django_db
def test_business_offer_choice_context_restores_existing_offer_when_free_pool_is_zero(
    apple,
):
    customer = customer_factory()

    create_batch(
        batch_id="A-ONLY",
        product=apple,
        quantity=4,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    standard_offer = standard_business_offer_factory(
        product=apple,
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=standard_offer.pk,
        quantity=4,
    )
    order = place_order(
        order=order,
    )

    context = build_business_offer_choice_context(
        order=order,
    )

    assert standard_offer.pk in set(
        context.queryset.values_list(
            "pk",
            flat=True,
        )
    )
    assert context.available_units_by_offer_id[
        standard_offer.pk
    ] == 4


@pytest.mark.django_db
def test_business_offer_choice_context_does_not_restore_disabled_existing_offer(
    apple,
):
    customer = customer_factory()

    create_batch(
        batch_id="A-ONLY",
        product=apple,
        quantity=4,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    standard_offer = standard_business_offer_factory(
        product=apple,
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=standard_offer.pk,
        quantity=2,
    )
    order = place_order(
        order=order,
    )

    standard_offer.enabled = False
    standard_offer.save(
        update_fields=[
            "enabled",
        ]
    )

    context = build_business_offer_choice_context(
        order=order,
    )

    assert standard_offer.pk not in set(
        context.queryset.values_list(
            "pk",
            flat=True,
        )
    )
    assert (
        standard_offer.pk
        not in context.available_units_by_offer_id
    )
