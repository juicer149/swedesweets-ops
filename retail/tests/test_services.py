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
from pricing.models import CommercialPrice, PriceAmount
from retail.models import (
    RetailCart,
    RetailCartLine,
    RetailCheckoutSession,
    RetailOfferSelection,
)
from retail.rules import (
    MAX_RETAIL_LINE_QUANTITY,
    MAX_RETAIL_ORDER_TOTAL,
    MIN_RETAIL_LINE_QUANTITY,
    RETAIL_CHECKOUT_WINDOW,
    RETAIL_PAYMENT_RESERVATION_WINDOW,
)
from retail.services import (
    AnonymousBuyerInput,
    InvalidRetailCart,
    InvalidRetailOrder,
    RetailOrderLineInput,
    add_retail_cart_line,
    buyer_from_anonymous_retail_input,
    clear_retail_cart,
    create_pending_retail_order,
    create_retail_cart,
    create_retail_checkout_from_cart,
    remove_retail_cart_line,
    start_retail_payment,
    update_retail_cart_line_quantity,
)
from retail.tests.factories import (
    retail_batch_price_factory,
    retail_buyer_data,
    retail_inventory_batch_factory,
    retail_postal_area_factory,
    retail_product_factory,
    retail_product_price_factory,
)


@pytest.mark.django_db
def test_create_retail_cart_creates_empty_cart():
    cart = create_retail_cart()

    assert isinstance(cart, RetailCart)
    assert cart.lines.count() == 0


@pytest.mark.django_db
def test_add_product_price_to_retail_cart():
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    line = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    assert line.cart == cart
    assert line.commercial_price == offer
    assert line.commercial_price.product == offer.product
    assert line.commercial_price.channel == CommercialPrice.Channel.RETAIL
    assert (
        line.commercial_price.amounts.get(
            currency=PriceAmount.Currency.EUR,
        ).price
        == Decimal("12.50")
    )
    assert line.quantity == 2


@pytest.mark.django_db
def test_add_batch_price_to_retail_cart():
    cart = create_retail_cart()
    offer = retail_batch_price_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    line = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    assert line.cart == cart
    assert line.commercial_price == offer
    assert line.commercial_price.batch == offer.batch
    assert line.commercial_price.channel == CommercialPrice.Channel.RETAIL
    assert (
        line.commercial_price.amounts.get(
            currency=PriceAmount.Currency.EUR,
        ).price
        == Decimal("4.90")
    )
    assert line.quantity == 2


@pytest.mark.django_db
def test_adding_same_commercial_price_again_increments_existing_cart_line():
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    first = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )
    second = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=3,
    )

    first.refresh_from_db()

    assert second.pk == first.pk
    assert first.quantity == 5
    assert cart.lines.count() == 1


@pytest.mark.django_db
def test_adding_same_commercial_price_rejects_quantity_above_retail_limit():
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    line = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=MAX_RETAIL_LINE_QUANTITY,
    )

    with pytest.raises(
        InvalidRetailCart,
        match="quantity",
    ):
        add_retail_cart_line(
            cart=cart,
            commercial_price_id=offer.pk,
            quantity=1,
        )

    line.refresh_from_db()
    assert line.quantity == MAX_RETAIL_LINE_QUANTITY






@pytest.mark.django_db
@pytest.mark.parametrize(
    "quantity",
    [
        MIN_RETAIL_LINE_QUANTITY - 1,
        MAX_RETAIL_LINE_QUANTITY + 1,
    ],
)
def test_add_retail_cart_line_rejects_invalid_quantity(quantity: int):
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailCart,
        match="quantity",
    ):
        add_retail_cart_line(
            cart=cart,
            commercial_price_id=offer.pk,
            quantity=quantity,
        )


@pytest.mark.django_db
def test_add_retail_cart_line_rejects_missing_offer():
    cart = create_retail_cart()

    with pytest.raises(
        InvalidRetailOrder,
        match="does not exist",
    ):
        add_retail_cart_line(
            cart=cart,
            commercial_price_id=999_999,
            quantity=1,
        )


@pytest.mark.django_db
def test_add_retail_cart_line_rejects_disabled_offer():
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=False,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        add_retail_cart_line(
            cart=cart,
            commercial_price_id=offer.pk,
            quantity=1,
        )


@pytest.mark.django_db
def test_update_retail_cart_line_quantity():
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    line = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    updated = update_retail_cart_line_quantity(
        cart=cart,
        line=line,
        quantity=5,
    )

    assert updated.quantity == 5


@pytest.mark.django_db
def test_update_retail_cart_line_rejects_line_from_other_cart():
    first_cart = create_retail_cart()
    second_cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    line = add_retail_cart_line(
        cart=first_cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    with pytest.raises(
        InvalidRetailCart,
        match="does not belong",
    ):
        update_retail_cart_line_quantity(
            cart=second_cart,
            line=line,
            quantity=3,
        )

    line.refresh_from_db()
    assert line.quantity == 2


@pytest.mark.django_db
def test_remove_retail_cart_line():
    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    line = add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    remove_retail_cart_line(
        cart=cart,
        line=line,
    )

    assert not RetailCartLine.objects.filter(pk=line.pk).exists()


@pytest.mark.django_db
def test_remove_retail_cart_line_rejects_line_from_other_cart():
    first_cart = create_retail_cart()
    second_cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    line = add_retail_cart_line(
        cart=first_cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    with pytest.raises(
        InvalidRetailCart,
        match="does not belong",
    ):
        remove_retail_cart_line(
            cart=second_cart,
            line=line,
        )

    assert RetailCartLine.objects.filter(pk=line.pk).exists()


@pytest.mark.django_db
def test_clear_retail_cart_removes_all_lines():
    cart = create_retail_cart()
    first_offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    second_offer = retail_batch_price_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    add_retail_cart_line(
        cart=cart,
        commercial_price_id=first_offer.pk,
        quantity=1,
    )
    add_retail_cart_line(
        cart=cart,
        commercial_price_id=second_offer.pk,
        quantity=2,
    )

    returned_cart = clear_retail_cart(
        cart=cart,
    )

    assert returned_cart.pk == cart.pk
    assert cart.lines.count() == 0


@pytest.mark.django_db
def test_create_retail_checkout_from_cart_converts_and_consumes_cart():
    retail_postal_area_factory()

    cart = create_retail_cart()
    cart_id = cart.pk

    product = retail_product_factory(
        name="Product Offer Product",
    )
    product_price = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )

    batch_product = retail_product_factory(
        name="Batch Offer Product",
    )
    batch = retail_inventory_batch_factory(
        product=batch_product,
        batch_id="CART-BATCH-001",
    )
    batch_price = retail_batch_price_factory(
        batch=batch,
        enabled=True,
        price=Decimal("4.90"),
    )

    add_retail_cart_line(
        cart=cart,
        commercial_price_id=product_price.pk,
        quantity=2,
    )
    add_retail_cart_line(
        cart=cart,
        commercial_price_id=batch_price.pk,
        quantity=3,
    )

    checkout = create_retail_checkout_from_cart(
        cart=cart,
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
    )

    order = checkout.order
    lines = list(
        order.lines
        .select_related(
            "retail_offer_selection",
        )
        .order_by("id")
    )

    assert order.channel == Order.Channel.RETAIL
    assert order.status == Order.Status.DRAFT
    assert order.buyer_name == "Marie Dupont"
    assert len(lines) == 2

    assert lines[0].product == product
    assert lines[0].quantity_in_units == 2
    assert lines[0].unit_price_snapshot == Decimal("12.50")
    assert (
        lines[0].retail_offer_selection.commercial_price
        == product_price
    )
    assert (
        lines[0].retail_offer_selection.commercial_price.batch_id
        is None
    )

    assert lines[1].product == batch_product
    assert lines[1].quantity_in_units == 3
    assert lines[1].unit_price_snapshot == Decimal("4.90")
    assert (
        lines[1].retail_offer_selection.commercial_price
        == batch_price
    )

    assert not RetailCart.objects.filter(
        pk=cart_id,
    ).exists()
    assert order.allocations.count() == 0


@pytest.mark.django_db
def test_create_retail_checkout_from_cart_allows_two_prices_for_same_product():
    retail_postal_area_factory()

    cart = create_retail_cart()
    product = retail_product_factory()

    product_price = retail_product_price_factory(
        product=product,
        enabled=True,
        price=Decimal("12.50"),
    )
    batch = retail_inventory_batch_factory(
        product=product,
        batch_id="CART-BATCH-SAME-PRODUCT",
    )
    batch_price = retail_batch_price_factory(
        batch=batch,
        enabled=True,
        price=Decimal("4.90"),
    )

    add_retail_cart_line(
        cart=cart,
        commercial_price_id=product_price.pk,
        quantity=1,
    )
    add_retail_cart_line(
        cart=cart,
        commercial_price_id=batch_price.pk,
        quantity=1,
    )

    checkout = create_retail_checkout_from_cart(
        cart=cart,
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
    )

    lines = list(
        checkout.order.lines
        .select_related("retail_offer_selection__commercial_price")
        .order_by("id")
    )

    assert len(lines) == 2
    assert lines[0].product == product
    assert lines[1].product == product
    assert (
        lines[0].retail_offer_selection.commercial_price
        == product_price
    )
    assert (
        lines[1].retail_offer_selection.commercial_price
        == batch_price
    )
    assert lines[0].unit_price_snapshot == Decimal("12.50")
    assert lines[1].unit_price_snapshot == Decimal("4.90")


@pytest.mark.django_db
def test_create_retail_checkout_from_cart_reprices_at_conversion():
    retail_postal_area_factory()

    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    amount = offer.amounts.get(
        currency=PriceAmount.Currency.EUR,
    )
    amount.price = Decimal("14.25")
    amount.save(
        update_fields=[
            "price",
            "updated_at",
        ],
    )

    checkout = create_retail_checkout_from_cart(
        cart=cart,
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
    )

    line = checkout.order.lines.get()

    assert line.unit_price_snapshot == Decimal("14.25")


@pytest.mark.django_db
def test_create_retail_checkout_from_cart_rejects_empty_cart():
    retail_postal_area_factory()
    cart = create_retail_cart()

    with pytest.raises(
        InvalidRetailCart,
        match="empty",
    ):
        create_retail_checkout_from_cart(
            cart=cart,
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
        )

    assert RetailCart.objects.filter(
        pk=cart.pk,
    ).exists()
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_create_retail_checkout_from_cart_preserves_cart_on_validation_failure():
    retail_postal_area_factory()

    cart = create_retail_cart()
    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    add_retail_cart_line(
        cart=cart,
        commercial_price_id=offer.pk,
        quantity=2,
    )

    offer.enabled = False
    offer.save(
        update_fields=[
            "enabled",
            "updated_at",
        ],
    )

    with pytest.raises(
        InvalidRetailOrder,
        match="not enabled",
    ):
        create_retail_checkout_from_cart(
            cart=cart,
            buyer=AnonymousBuyerInput(
                **retail_buyer_data()
            ),
        )

    assert RetailCart.objects.filter(
        pk=cart.pk,
    ).exists()
    assert RetailCartLine.objects.filter(
        cart=cart,
        commercial_price=offer,
        quantity=2,
    ).exists()
    assert Order.objects.count() == 0
    assert RetailCheckoutSession.objects.count() == 0


@pytest.mark.django_db
def test_create_pending_retail_order_from_product_price():
    retail_postal_area_factory()

    product = retail_product_factory()
    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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

    assert selection.commercial_price == offer

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
def test_create_pending_retail_order_from_batch_price():
    retail_postal_area_factory()

    offer = retail_batch_price_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                commercial_price_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    line = checkout.order.lines.get()
    selection = line.retail_offer_selection

    assert line.product == offer.batch.product
    assert line.unit_price_snapshot == Decimal("4.90")
    assert line.line_total == Decimal("9.80")

    assert selection.commercial_price == offer


@pytest.mark.django_db
def test_existing_order_keeps_original_price_after_product_price_changes():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                commercial_price_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    amount = offer.amounts.get(
        currency=PriceAmount.Currency.EUR,
    )
    amount.price = Decimal("20.00")
    amount.save(
        update_fields=["price", "updated_at"],
    )

    line = checkout.order.lines.get()

    assert line.unit_price_snapshot == Decimal("12.50")
    assert line.line_total == Decimal("25.00")
    assert checkout.order.total == Decimal("25.00")


@pytest.mark.django_db
def test_existing_order_keeps_original_price_after_batch_price_changes():
    retail_postal_area_factory()

    offer = retail_batch_price_factory(
        enabled=True,
        price=Decimal("4.90"),
    )

    checkout = create_pending_retail_order(
        buyer=AnonymousBuyerInput(
            **retail_buyer_data()
        ),
        lines=[
            RetailOrderLineInput(
                commercial_price_id=offer.pk,
                quantity=2,
            ),
        ],
    )

    amount = offer.amounts.get(
        currency=PriceAmount.Currency.EUR,
    )
    amount.price = Decimal("2.90")
    amount.save(
        update_fields=["price", "updated_at"],
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
def test_pending_retail_order_requires_supported_destination():
    offer = retail_product_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_missing_commercial_price():
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
                    commercial_price_id=999_999,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_disabled_product_price():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_disabled_batch_price():
    retail_postal_area_factory()

    offer = retail_batch_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_inactive_product():
    retail_postal_area_factory()

    product = retail_product_factory()
    offer = retail_product_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_quantity_above_retail_limit():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=MAX_RETAIL_LINE_QUANTITY + 1,
                ),
            ],
        )


@pytest.mark.django_db
def test_pending_retail_order_rejects_duplicate_commercial_price_lines():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
                RetailOrderLineInput(
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
            ],
        )


@pytest.mark.django_db
def test_retail_order_total_limit_rolls_back_checkout():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                    commercial_price_id=offer.pk,
                    quantity=1,
                ),
            ],
        )

    assert Order.objects.count() == 0
    assert OrderLine.objects.count() == 0
    assert RetailCheckoutSession.objects.count() == 0
    assert RetailOfferSelection.objects.count() == 0


@pytest.mark.django_db
def test_start_retail_payment_reserves_product_price_stock():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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
def test_product_price_cannot_use_stock_owned_by_batch_price():
    retail_postal_area_factory()

    product_price = retail_product_price_factory(
        enabled=True,
        price=Decimal("12.50"),
    )
    product = product_price.product

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

    retail_batch_price_factory(
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
                commercial_price_id=product_price.pk,
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
def test_batch_price_cannot_use_other_batches_of_same_product():
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

    batch_price = retail_batch_price_factory(
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
                commercial_price_id=batch_price.pk,
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

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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
                commercial_price_id=offer.pk,
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

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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
                commercial_price_id=offer.pk,
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

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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
def test_product_price_payment_reservation_uses_fefo():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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

    first_offer = retail_product_price_factory(
        product=first_product,
        enabled=True,
        price=Decimal("12.50"),
    )
    second_offer = retail_product_price_factory(
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
                commercial_price_id=first_offer.pk,
                quantity=4,
            ),
            RetailOrderLineInput(
                commercial_price_id=second_offer.pk,
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
def test_product_price_reservation_can_span_multiple_eligible_batches():
    retail_postal_area_factory()

    offer = retail_product_price_factory(
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
                commercial_price_id=offer.pk,
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
