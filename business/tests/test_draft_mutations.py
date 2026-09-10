from __future__ import annotations

import pytest

from business.models import BusinessOfferSelection
from business.services import (
    remove_draft_line,
    remove_product_from_draft_order,
    set_draft_line_quantity,
    set_draft_product_quantity,
)
from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
)
from pricing.models import PriceAmount


def _create_line(
    *,
    order: Order,
    product,
    quantity: int,
) -> OrderLine:
    return OrderLine.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit=OrderLine.Unit.STOCK_UNIT,
        quantity_in_units=quantity,
    )


def _explicit_standard_offer(
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
def test_set_draft_product_quantity_updates_product_line(
    customer,
    apple,
    stocked_inventory,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=1,
    )

    updated = set_draft_product_quantity(
        order=order,
        product=apple,
        quantity=5,
    )

    line.refresh_from_db()

    assert updated.pk == order.pk
    assert line.quantity == 5
    assert line.quantity_in_units == 5


@pytest.mark.django_db
def test_set_draft_product_quantity_preserves_other_products(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    apple_line = _create_line(
        order=order,
        product=apple,
        quantity=1,
    )
    banana_line = _create_line(
        order=order,
        product=banana,
        quantity=7,
    )

    set_draft_product_quantity(
        order=order,
        product=apple,
        quantity=5,
    )

    apple_line.refresh_from_db()
    banana_line.refresh_from_db()

    assert apple_line.quantity_in_units == 5
    assert banana_line.quantity_in_units == 7


@pytest.mark.django_db
@pytest.mark.parametrize(
    "quantity",
    [
        0,
        -1,
    ],
)
def test_set_draft_product_quantity_rejects_non_positive_quantity(
    customer,
    apple,
    quantity,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="quantity must be positive",
    ):
        set_draft_product_quantity(
            order=order,
            product=apple,
            quantity=quantity,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_product_quantity_rejects_quantity_above_business_availability(
    customer,
    apple,
    stocked_inventory,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="only 150 units are currently available",
    ):
        set_draft_product_quantity(
            order=order,
            product=apple,
            quantity=151,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_product_quantity_rejects_quantity_above_order_limit(
    customer,
    apple,
    monkeypatch,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    monkeypatch.setattr(
        "business.services.orderable_quantity_by_product_id",
        lambda: {
            apple.id: (
                MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                + 100
            ),
        },
    )

    with pytest.raises(
        InvalidOrderOperation,
        match=(
            "maximum quantity per product is "
            f"{MAX_QUANTITY_PER_PRODUCT_PER_ORDER}"
        ),
    ):
        set_draft_product_quantity(
            order=order,
            product=apple,
            quantity=(
                MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                + 1
            ),
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_product_quantity_rejects_product_not_in_draft(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    apple_line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="product is not part of the draft order",
    ):
        set_draft_product_quantity(
            order=order,
            product=banana,
            quantity=5,
        )

    apple_line.refresh_from_db()

    assert apple_line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_product_quantity_rejects_non_business_order(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="requires a business order",
    ):
        set_draft_product_quantity(
            order=order,
            product=apple,
            quantity=5,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_set_draft_product_quantity_rejects_non_draft_order(
    customer,
    apple,
    stocked_inventory,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="Only draft orders can be edited",
    ):
        set_draft_product_quantity(
            order=order,
            product=apple,
            quantity=5,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 3


@pytest.mark.django_db
def test_remove_product_from_draft_order_removes_product_line(
    customer,
    apple,
    banana,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    apple_line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )
    banana_line = _create_line(
        order=order,
        product=banana,
        quantity=7,
    )

    updated = remove_product_from_draft_order(
        order=order,
        product=apple,
    )

    assert updated.pk == order.pk
    assert not OrderLine.objects.filter(
        pk=apple_line.pk,
    ).exists()

    banana_line.refresh_from_db()

    assert banana_line.quantity_in_units == 7


@pytest.mark.django_db
def test_remove_product_from_draft_order_allows_empty_draft(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    remove_product_from_draft_order(
        order=order,
        product=apple,
    )

    assert not OrderLine.objects.filter(
        pk=line.pk,
    ).exists()
    assert order.lines.count() == 0
    assert Order.objects.filter(
        pk=order.pk,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_remove_product_from_draft_order_rejects_product_not_in_draft(
    customer,
    apple,
    banana,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    apple_line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="product is not part of the draft order",
    ):
        remove_product_from_draft_order(
            order=order,
            product=banana,
        )

    assert OrderLine.objects.filter(
        pk=apple_line.pk,
    ).exists()


@pytest.mark.django_db
def test_remove_product_from_draft_order_rejects_non_business_order(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.RETAIL,
        customer=customer,
        status=Order.Status.DRAFT,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="requires a business order",
    ):
        remove_product_from_draft_order(
            order=order,
            product=apple,
        )

    assert OrderLine.objects.filter(
        pk=line.pk,
    ).exists()


@pytest.mark.django_db
def test_remove_product_from_draft_order_rejects_non_draft_order(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.PLACED,
    )
    line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="Only draft orders can be edited",
    ):
        remove_product_from_draft_order(
            order=order,
            product=apple,
        )

    assert OrderLine.objects.filter(
        pk=line.pk,
    ).exists()


@pytest.mark.django_db
def test_set_draft_line_quantity_updates_only_selected_line(
    customer,
    apple,
    monkeypatch,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    first_line = _create_line(
        order=order,
        product=apple,
        quantity=2,
    )
    second_line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    BusinessOfferSelection.objects.create(
        order_line=first_line,
        commercial_price=None,
    )
    BusinessOfferSelection.objects.create(
        order_line=second_line,
        commercial_price=None,
    )

    catalog_product = _explicit_standard_offer(
        product=apple,
        available_units=20,
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    updated = set_draft_line_quantity(
        order=order,
        order_line_id=second_line.id,
        quantity=7,
    )

    first_line.refresh_from_db()
    second_line.refresh_from_db()

    assert updated.pk == order.pk
    assert first_line.quantity_in_units == 2
    assert second_line.quantity_in_units == 7


@pytest.mark.django_db
def test_remove_draft_line_removes_only_selected_same_product_line(
    customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    first_line = _create_line(
        order=order,
        product=apple,
        quantity=2,
    )
    second_line = _create_line(
        order=order,
        product=apple,
        quantity=3,
    )

    BusinessOfferSelection.objects.create(
        order_line=first_line,
        commercial_price=None,
    )
    BusinessOfferSelection.objects.create(
        order_line=second_line,
        commercial_price=None,
    )

    updated = remove_draft_line(
        order=order,
        order_line_id=second_line.id,
    )

    assert updated.pk == order.pk

    assert OrderLine.objects.filter(
        pk=first_line.pk,
    ).exists()

    assert not OrderLine.objects.filter(
        pk=second_line.pk,
    ).exists()


@pytest.mark.django_db
def test_set_draft_line_quantity_rejects_line_from_other_order(
    customer,
    other_customer,
    apple,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    other_order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=other_customer,
        status=Order.Status.DRAFT,
    )

    other_line = _create_line(
        order=other_order,
        product=apple,
        quantity=3,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="order line does not belong to this draft order",
    ):
        set_draft_line_quantity(
            order=order,
            order_line_id=other_line.id,
            quantity=5,
        )


@pytest.mark.django_db
def test_set_explicit_offer_quantity_rejects_above_offer_availability(
    customer,
    apple,
    monkeypatch,
):
    order = Order.objects.create(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    )

    line = _create_line(
        order=order,
        product=apple,
        quantity=2,
    )

    BusinessOfferSelection.objects.create(
        order_line=line,
        commercial_price=None,
    )

    catalog_product = _explicit_standard_offer(
        product=apple,
        available_units=4,
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="only 4 units are currently available for this offer",
    ):
        set_draft_line_quantity(
            order=order,
            order_line_id=line.id,
            quantity=5,
        )

    line.refresh_from_db()

    assert line.quantity_in_units == 2
