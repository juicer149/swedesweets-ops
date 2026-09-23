from __future__ import annotations

import pytest

from orders.datatypes import BuyerInput
from orders.drafts import OrderDraft, ResolvedOrderLine
from orders.errors import InvalidOrderOperation
from orders.models import Order
from orders.services import (
    add_draft_order_line,
    create_draft_order,
)
from pricing.models import CommercialPrice
from pricing.tests.factories import commercial_price_factory
from products.tests.factories import product_factory


def _buyer(customer):
    return BuyerInput(
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        country=customer.country,
        city=customer.city,
        address_line=customer.address_line,
    )


@pytest.mark.django_db
def test_explicit_offer_is_stored_on_the_order_line(
    customer,
    apple,
):
    order = Order.objects.create(
        customer=customer,
    )
    offer = commercial_price_factory(
        product=apple,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    order_line = add_draft_order_line(
        order=order,
        line=ResolvedOrderLine(
            product=apple,
            quantity_in_units=3,
            commercial_offer=offer,
        ),
    )

    order_line.refresh_from_db()

    assert order_line.commercial_offer == offer


@pytest.mark.django_db
def test_offer_for_another_product_is_rejected(
    customer,
    apple,
):
    order = Order.objects.create(
        customer=customer,
    )

    other_product = product_factory(
        name="Other",
        internal_number=99,
    )
    offer = commercial_price_factory(
        product=other_product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="belongs to product",
    ):
        add_draft_order_line(
            order=order,
            line=ResolvedOrderLine(
                product=apple,
                quantity_in_units=1,
                commercial_offer=offer,
            ),
        )

    assert not order.lines.exists()


@pytest.mark.django_db
def test_offer_from_another_channel_is_rejected(
    customer,
    apple,
):
    order = Order.objects.create(
        customer=customer,
    )

    retail_offer = commercial_price_factory(
        product=apple,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="is a retail offer",
    ):
        add_draft_order_line(
            order=order,
            line=ResolvedOrderLine(
                product=apple,
                quantity_in_units=1,
                commercial_offer=retail_offer,
            ),
        )

    assert not order.lines.exists()


@pytest.mark.django_db
def test_unsaved_offer_is_rejected(
    customer,
    apple,
):
    order = Order.objects.create(
        customer=customer,
    )

    unsaved_offer = CommercialPrice(
        product=apple,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="must be persisted",
    ):
        add_draft_order_line(
            order=order,
            line=ResolvedOrderLine(
                product=apple,
                quantity_in_units=1,
                commercial_offer=unsaved_offer,
            ),
        )

    assert not order.lines.exists()


@pytest.mark.django_db
def test_line_without_offer_is_rejected(
    customer,
    apple,
):
    """Runtime validation protects callers despite Python's non-enforced types."""

    order = Order.objects.create(
        customer=customer,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="commercial offer is required",
    ):
        add_draft_order_line(
            order=order,
            line=ResolvedOrderLine(
                product=apple,
                quantity_in_units=2,
                commercial_offer=None,  # type: ignore[arg-type]
            ),
        )

    assert not order.lines.exists()


@pytest.mark.django_db
def test_draft_creation_stores_offers_on_every_line(
    customer,
    apple,
    banana,
):
    apple_offer = commercial_price_factory(
        product=apple,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    banana_offer = commercial_price_factory(
        product=banana,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    order = create_draft_order(
        draft=OrderDraft(
            channel=Order.Channel.BUSINESS,
            currency=Order.Currency.EUR,
            customer=customer,
            buyer=_buyer(customer),
            lines=(
                ResolvedOrderLine(
                    product=apple,
                    quantity_in_units=2,
                    commercial_offer=apple_offer,
                ),
                ResolvedOrderLine(
                    product=banana,
                    quantity_in_units=1,
                    commercial_offer=banana_offer,
                ),
            ),
        ),
    )

    assert set(
        order.lines.values_list(
            "product_id",
            "commercial_offer_id",
        )
    ) == {
        (
            apple.id,
            apple_offer.pk,
        ),
        (
            banana.id,
            banana_offer.pk,
        ),
    }


@pytest.mark.django_db
def test_draft_creation_validates_every_line_before_persisting(
    customer,
    apple,
    banana,
):
    """A bad offer on the second line must not leave the first line behind."""

    apple_offer = commercial_price_factory(
        product=apple,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    unrelated_product = product_factory(
        name="Unrelated",
        internal_number=98,
    )
    wrong_offer = commercial_price_factory(
        product=unrelated_product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="belongs to product",
    ):
        create_draft_order(
            draft=OrderDraft(
                channel=Order.Channel.BUSINESS,
                currency=Order.Currency.EUR,
                customer=customer,
                buyer=_buyer(customer),
                lines=(
                    ResolvedOrderLine(
                        product=apple,
                        quantity_in_units=2,
                        commercial_offer=apple_offer,
                    ),
                    ResolvedOrderLine(
                        product=banana,
                        quantity_in_units=1,
                        commercial_offer=wrong_offer,
                    ),
                ),
            ),
        )

    assert not Order.objects.filter(
        customer=customer,
    ).exists()
