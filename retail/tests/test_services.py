from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.errors import (
    InsufficientStockError,
    InvalidStockOperation,
)
from inventory.services import (
    create_batch,
    update_batch,
)
from orders.models import Allocation, Order, OrderLine
from payments.models import PaymentAttempt
from retail.models import (
    RetailCheckoutSession,
    RetailOfferSelection,
    RetailOrder,
    RetailOrderLine,
)
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_TOTAL,
    RETAIL_CHECKOUT_WINDOW,
    RETAIL_PAYMENT_RESERVATION_WINDOW,
)
from retail.services import (
    AnonymousBuyerInput,
    InvalidRetailOrder,
    RetailOrderLineInput,
    buyer_from_anonymous_retail_input,
    create_pending_retail_order,
    start_retail_payment,
)
from retail.tests.factories import (
    retail_batch_offer_factory,
    retail_buyer_data,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_create_pending_retail_order_from_product_offer():
    retail_postal_area_factory()

    product = retail_product_factory()
    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    before = timezone.now()

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    after = timezone.now()

    assert isinstance(
        checkout,
        RetailCheckoutSession,
    )

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

    selection = line.retail_offer_selection

    assert selection.product_offer == offer
    assert selection.batch_offer is None

    assert order.total == Decimal("25.00")

    assert (
        before + RETAIL_CHECKOUT_WINDOW
        <= checkout.expires_at
    )
    assert (
        checkout.expires_at
        <= after + RETAIL_CHECKOUT_WINDOW
    )


@pytest.mark.django_db
def test_create_pending_retail_order_from_batch_offer():
    retail_postal_area_factory()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                batch_offer_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    line = checkout.order.lines.get()
    selection = line.retail_offer_selection

    assert line.product == offer.batch.product
    assert line.unit_price_snapshot == Decimal("4.90")
    assert line.line_total == Decimal("9.80")

    assert selection.product_offer is None
    assert selection.batch_offer == offer


@pytest.mark.django_db
def test_pending_retail_checkout_does_not_create_legacy_retail_order():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=1,
            ),
        ],
    )

    assert RetailOrder.objects.count() == 0
    assert RetailOrderLine.objects.count() == 0

    assert Order.objects.count() == 1
    assert OrderLine.objects.count() == 1
    assert RetailCheckoutSession.objects.count() == 1
    assert RetailOfferSelection.objects.count() == 1


@pytest.mark.django_db
def test_existing_order_keeps_original_price_after_product_offer_changes():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    offer.price = Decimal("20.00")
    offer.save(
        update_fields=["price"],
    )

    line = checkout.order.lines.get()

    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")
    assert checkout.order.total == Decimal("25.00")


@pytest.mark.django_db
def test_existing_order_keeps_original_price_after_batch_offer_changes():
    retail_postal_area_factory()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                batch_offer_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    offer.price = Decimal("2.90")
    offer.save(
        update_fields=["price"],
    )

    line = checkout.order.lines.get()

    assert line.unit_price_snapshot == Decimal("4.90")
    assert line.line_total == Decimal("9.80")


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
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[],
        )


@pytest.mark.django_db
def test_retail_line_requires_exactly_one_offer():
    retail_postal_area_factory()

    with pytest.raises(
        InvalidRetailOrder,
        match="exactly one offer",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_retail_line_rejects_product_and_batch_offer_together():
    retail_postal_area_factory()

    product_offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    batch_offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="exactly one offer",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    quantity=1,
                    product_offer_id=product_offer.pk,
                    batch_offer_id=batch_offer.pk,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_requires_supported_destination():
    offer = retail_product_offer_factory(
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
                    product_offer_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_missing_product_offer():
    retail_postal_area_factory()

    with pytest.raises(
        InvalidRetailOrder,
        match="does not exist",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    product_offer_id=999_999,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_disabled_product_offer():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=False,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    product_offer_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_disabled_batch_offer():
    retail_postal_area_factory()

    offer = retail_batch_offer_factory(
        enabled=False,
        price=Decimal("4.90"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    batch_offer_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_inactive_product():
    retail_postal_area_factory()

    product = retail_product_factory()
    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    product.active = False
    product.save(
        update_fields=["active"],
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    product_offer_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_quantity_above_retail_limit():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="quantity",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    product_offer_id=offer.pk,
                    quantity=MAX_RETAIL_LINE_QUANTITY + 1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_duplicate_product_lines():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="duplicate",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    product_offer_id=offer.pk,
                    quantity=1,
                ),
                RetailOrderLineInput(
                    product_offer_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_retail_order_total_limit_rolls_back_checkout():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=MAX_RETAIL_ORDER_TOTAL + Decimal("1.00"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="maximum",
    ):
        create_pending_retail_order(
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
            lines=[
                RetailOrderLineInput(
                    product_offer_id=offer.pk,
                    quantity=1,
                ),
            ],
        )

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert RetailCheckoutSession.objects.count() == 0
    assert RetailOfferSelection.objects.count() == 0


@pytest.mark.django_db
def test_start_retail_payment_reserves_product_offer_stock():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    batch = create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=4,
            ),
        ],
    )

    before = timezone.now()

    start_retail_payment(
        checkout=checkout,
    )

    after = timezone.now()

    allocation = checkout.order.allocations.get()

    assert allocation.batch == batch
    assert allocation.quantity == 4
    assert allocation.status == Allocation.Status.RESERVED
    assert allocation.reserved_until is not None

    assert (
        before + RETAIL_PAYMENT_RESERVATION_WINDOW
        <= allocation.reserved_until
    )
    assert (
        allocation.reserved_until
        <= after + RETAIL_PAYMENT_RESERVATION_WINDOW
    )

    checkout.order.refresh_from_db()

    assert checkout.order.status == Order.Status.DRAFT


@pytest.mark.django_db
def test_product_offer_cannot_use_stock_owned_by_batch_offer():
    retail_postal_area_factory()

    product_offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    product = product_offer.product

    create_batch(
        batch_id="A-001",
        product=product,
        quantity=3,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    special_batch = create_batch(
        batch_id="B-001",
        product=product,
        quantity=100,
        best_before=timezone.localdate() + timedelta(days=30),
        location="Shelf B1",
    )

    retail_batch_offer_factory(
        batch=special_batch,
        enabled=True,
        price=Decimal("4.90"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=product_offer.pk,
                quantity=4,
            ),
        ],
    )

    with pytest.raises(
        InsufficientStockError,
    ) as error:
        start_retail_payment(
            checkout=checkout,
        )

    assert error.value.requested_quantity == 4
    assert error.value.available_quantity == 3
    assert error.value.missing_quantity == 1

    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_batch_offer_cannot_use_other_batches_of_same_product():
    retail_postal_area_factory()

    product = retail_product_factory()

    create_batch(
        batch_id="A-001",
        product=product,
        quantity=100,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    special_batch = create_batch(
        batch_id="B-001",
        product=product,
        quantity=3,
        best_before=timezone.localdate() + timedelta(days=30),
        location="Shelf B1",
    )

    batch_offer = retail_batch_offer_factory(
        batch=special_batch,
        enabled=True,
        price=Decimal("4.90"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                batch_offer_id=batch_offer.pk,
                quantity=4,
            ),
        ],
    )

    with pytest.raises(
        InsufficientStockError,
    ) as error:
        start_retail_payment(
            checkout=checkout,
        )

    assert error.value.requested_quantity == 4
    assert error.value.available_quantity == 3
    assert error.value.missing_quantity == 1

    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_second_checkout_cannot_reserve_stock_held_by_first_checkout():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=3,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    first_checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=3,
            ),
        ],
    )

    second_checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=1,
            ),
        ],
    )

    start_retail_payment(
        checkout=first_checkout,
    )

    with pytest.raises(
        InsufficientStockError,
    ) as error:
        start_retail_payment(
            checkout=second_checkout,
        )

    assert error.value.requested_quantity == 1
    assert error.value.available_quantity == 0
    assert error.value.missing_quantity == 1

    assert (
        first_checkout.order.allocations
        .filter(status=Allocation.Status.RESERVED)
        .count()
        == 1
    )
    assert second_checkout.order.allocations.count() == 0


@pytest.mark.django_db
def test_expired_payment_reservation_does_not_block_new_checkout():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=3,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    first_checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=3,
            ),
        ],
    )

    start_retail_payment(
        checkout=first_checkout,
    )

    first_checkout.order.allocations.update(
        reserved_until=(
            timezone.now() - timedelta(seconds=1)
        ),
    )

    second_checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=3,
            ),
        ],
    )

    start_retail_payment(
        checkout=second_checkout,
    )

    allocation = (
        second_checkout.order.allocations.get()
    )

    assert allocation.quantity == 3
    assert allocation.status == Allocation.Status.RESERVED


@pytest.mark.django_db
def test_expired_checkout_cannot_start_retail_payment():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=1,
            ),
        ],
    )

    RetailCheckoutSession.objects.filter(
        pk=checkout.pk,
    ).update(
        expires_at=(
            timezone.now() - timedelta(seconds=1)
        ),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="expired",
    ):
        start_retail_payment(
            checkout=checkout,
        )

    assert Allocation.objects.count() == 0


@pytest.mark.django_db
def test_product_offer_payment_reservation_uses_fefo():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    later_batch = create_batch(
        batch_id="A-002",
        product=offer.product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A2",
    )

    earlier_batch = create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=3,
        best_before=timezone.localdate() + timedelta(days=30),
        location="Shelf A1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=5,
            ),
        ],
    )

    start_retail_payment(
        checkout=checkout,
    )

    allocations = list(
        checkout.order.allocations
        .select_related("batch")
        .order_by(
            "batch__best_before",
            "batch__batch_id",
        )
    )

    assert [
        (
            allocation.batch.batch_id,
            allocation.quantity,
        )
        for allocation in allocations
    ] == [
        (earlier_batch.batch_id, 3),
        (later_batch.batch_id, 2),
    ]


@pytest.mark.django_db
def test_starting_payment_again_preserves_existing_temporary_hold():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=10,
        best_before=(
            timezone.localdate()
            + timedelta(days=60)
        ),
        location="Shelf A1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=4,
            ),
        ],
    )

    first_attempt = start_retail_payment(
        checkout=checkout,
    )

    first_allocation = (
        checkout.order.allocations.get()
    )
    original_reserved_until = (
        first_allocation.reserved_until
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="already has a pending payment attempt",
    ):
        start_retail_payment(
            checkout=checkout,
        )

    first_attempt.refresh_from_db()
    first_allocation.refresh_from_db()

    assert (
        first_attempt.status
        == PaymentAttempt.Status.PENDING
    )

    assert (
        PaymentAttempt.objects
        .filter(order=checkout.order)
        .count()
        == 1
    )

    assert (
        first_allocation.status
        == Allocation.Status.RESERVED
    )
    assert (
        first_allocation.reserved_until
        == original_reserved_until
    )


@pytest.mark.django_db
def test_retail_payment_reservation_prevents_inventory_reduction_below_hold():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    batch = create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=4,
            ),
        ],
    )

    start_retail_payment(
        checkout=checkout,
    )

    with pytest.raises(
        InvalidStockOperation,
        match="reserved",
    ):
        update_batch(
            batch=batch,
            quantity=3,
            best_before=batch.best_before,
            location=batch.location,
        )


@pytest.mark.django_db
def test_start_retail_payment_rolls_back_all_lines_when_one_line_lacks_stock():
    retail_postal_area_factory()

    first_product = retail_product_factory(
        name="Product A",
    )
    second_product = retail_product_factory(
        name="Product B",
    )

    first_offer = retail_product_offer_factory(
        product=first_product,
        enabled=True,
        price=Decimal("12.50"),
    )
    second_offer = retail_product_offer_factory(
        product=second_product,
        enabled=True,
        price=Decimal("8.50"),
    )

    create_batch(
        batch_id="A-001",
        product=first_product,
        quantity=10,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A1",
    )

    create_batch(
        batch_id="B-001",
        product=second_product,
        quantity=1,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf B1",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=first_offer.pk,
                quantity=4,
            ),
            RetailOrderLineInput(
                product_offer_id=second_offer.pk,
                quantity=2,
            ),
        ],
    )

    with pytest.raises(
        InsufficientStockError,
    ):
        start_retail_payment(
            checkout=checkout,
        )

    assert checkout.order.allocations.count() == 0

@pytest.mark.django_db
def test_product_offer_reservation_can_span_multiple_eligible_batches():
    retail_postal_area_factory()

    offer = retail_product_offer_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    earlier_batch = create_batch(
        batch_id="A-001",
        product=offer.product,
        quantity=3,
        best_before=timezone.localdate() + timedelta(days=30),
        location="Shelf A1",
    )

    later_batch = create_batch(
        batch_id="A-002",
        product=offer.product,
        quantity=5,
        best_before=timezone.localdate() + timedelta(days=60),
        location="Shelf A2",
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                product_offer_id=offer.pk,
                quantity=6,
            ),
        ],
    )

    start_retail_payment(
        checkout=checkout,
    )

    allocations = list(
        checkout.order.allocations
        .select_related("batch")
        .order_by(
            "batch__best_before",
            "batch__batch_id",
        )
    )

    assert [
        (
            allocation.batch.batch_id,
            allocation.quantity,
        )
        for allocation in allocations
    ] == [
        (earlier_batch.batch_id, 3),
        (later_batch.batch_id, 3),
    ]
