from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from business.models import BusinessOfferSelection
from business.services import (
    add_catalog_offer_to_draft_order,
    add_product_to_draft_order,
)
from business.tests.conftest import TODAY
from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from inventory.services import create_batch
from orders.errors import InvalidOrderOperation
from orders.models import Order
from orders.order_limits import (
    MAX_QUANTITY_PER_PRODUCT_PER_ORDER,
)
from pricing.models import (
    CommercialPrice,
    PriceAmount,
)


def _catalog_product(
    *,
    product,
    offers: tuple[CatalogOffer, ...],
    available_units: int,
) -> CatalogProduct:
    return CatalogProduct(
        product=product,
        available_units=available_units,
        offers=offers,
    )


def _standard_offer(
    *,
    available_units: int,
    commercial_price_id: int | None = None,
    price: Decimal | None = None,
) -> CatalogOffer:
    return CatalogOffer(
        kind=CatalogOfferKind.STANDARD,
        commercial_price_id=commercial_price_id,
        batch_id=None,
        reason=None,
        price=price,
        currency=PriceAmount.Currency.EUR,
        available_units=available_units,
    )


def _batch_offer(
    *,
    commercial_price: CommercialPrice,
    available_units: int,
    price: Decimal,
) -> CatalogOffer:
    return CatalogOffer(
        kind=CatalogOfferKind.BATCH,
        commercial_price_id=commercial_price.pk,
        batch_id=commercial_price.batch_id,
        reason=commercial_price.reason or None,
        price=price,
        currency=PriceAmount.Currency.EUR,
        available_units=available_units,
    )


@pytest.mark.django_db
def test_add_product_to_draft_order_creates_draft_and_line(
    customer,
    apple,
    stocked_inventory,
):
    order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    assert order.channel == Order.Channel.BUSINESS
    assert order.status == Order.Status.DRAFT
    assert order.customer == customer

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 1


@pytest.mark.django_db
def test_add_product_to_draft_order_increments_existing_product(
    customer,
    apple,
    stocked_inventory,
):
    first_order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    second_order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    assert second_order.pk == first_order.pk
    assert second_order.lines.count() == 1

    line = second_order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 2


@pytest.mark.django_db
def test_add_product_to_draft_order_preserves_other_products(
    customer,
    apple,
    banana,
    stocked_inventory,
):
    order = add_product_to_draft_order(
        customer=customer,
        product=apple,
    )

    updated = add_product_to_draft_order(
        customer=customer,
        product=banana,
    )

    assert updated.pk == order.pk

    assert list(
        updated.lines
        .order_by("product_id")
        .values_list(
            "product_id",
            "quantity_in_units",
        )
    ) == [
        (
            apple.id,
            1,
        ),
        (
            banana.id,
            1,
        ),
    ]


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_inactive_product(
    customer,
    apple,
    stocked_inventory,
):
    apple.active = False
    apple.save(
        update_fields=[
            "active",
            "updated_at",
        ],
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="product is not available for business ordering",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_unavailable_product(
    customer,
    apple,
):
    with pytest.raises(
        InvalidOrderOperation,
        match="only 0 units are currently available",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_quantity_above_available_stock(
    customer,
    apple,
):
    create_batch(
        batch_id="A-001",
        product=apple,
        quantity=3,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="only 3 units are currently available",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
            quantity=4,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_quantity_above_order_limit(
    customer,
    apple,
    monkeypatch,
):
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
        match="maximum quantity per product",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
            quantity=(
                MAX_QUANTITY_PER_PRODUCT_PER_ORDER
                + 1
            ),
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_product_to_draft_order_rejects_non_positive_quantity(
    customer,
    apple,
):
    with pytest.raises(
        InvalidOrderOperation,
        match="quantity must be positive",
    ):
        add_product_to_draft_order(
            customer=customer,
            product=apple,
            quantity=0,
        )

    assert not Order.objects.filter(
        channel=Order.Channel.BUSINESS,
        customer=customer,
        status=Order.Status.DRAFT,
    ).exists()


@pytest.mark.django_db
def test_add_unpriced_standard_catalog_offer_creates_explicit_selection(
    customer,
    apple,
    monkeypatch,
):
    catalog_product = _catalog_product(
        product=apple,
        available_units=10,
        offers=(
            _standard_offer(
                available_units=10,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=None,
        quantity=2,
    )

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 2
    assert line.unit_price_snapshot is None

    selection = line.business_offer_selection

    assert isinstance(
        selection,
        BusinessOfferSelection,
    )
    assert selection.commercial_price_id is None


@pytest.mark.django_db
def test_add_priced_standard_catalog_offer_snapshots_price(
    customer,
    apple,
    monkeypatch,
):
    commercial_price = CommercialPrice.objects.create(
        product=apple,
        batch=None,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )

    amount = Decimal("12.50")

    catalog_product = _catalog_product(
        product=apple,
        available_units=10,
        offers=(
            _standard_offer(
                available_units=10,
                commercial_price_id=commercial_price.pk,
                price=amount,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=commercial_price.pk,
        quantity=2,
    )

    line = order.lines.get()

    assert line.unit_price_snapshot == amount
    assert (
        line.business_offer_selection.commercial_price
        == commercial_price
    )


@pytest.mark.django_db
def test_add_batch_catalog_offer_snapshots_price_and_selection(
    customer,
    apple,
    monkeypatch,
):
    batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=5,
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

    amount = Decimal("8.50")

    catalog_product = _catalog_product(
        product=apple,
        available_units=5,
        offers=(
            _batch_offer(
                commercial_price=commercial_price,
                available_units=5,
                price=amount,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=commercial_price.pk,
        quantity=3,
    )

    line = order.lines.get()

    assert line.product == apple
    assert line.quantity_in_units == 3
    assert line.unit_price_snapshot == amount
    assert (
        line.business_offer_selection.commercial_price
        == commercial_price
    )


@pytest.mark.django_db
def test_adding_same_catalog_offer_again_increments_existing_line(
    customer,
    apple,
    monkeypatch,
):
    catalog_product = _catalog_product(
        product=apple,
        available_units=10,
        offers=(
            _standard_offer(
                available_units=10,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    first_order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=None,
        quantity=2,
    )

    first_line = first_order.lines.get()

    second_order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=None,
        quantity=3,
    )

    assert second_order.pk == first_order.pk
    assert second_order.lines.count() == 1

    line = second_order.lines.get()

    assert line.pk == first_line.pk
    assert line.quantity_in_units == 5
    assert line.business_offer_selection.commercial_price_id is None


@pytest.mark.django_db
def test_same_product_different_catalog_offers_create_separate_lines(
    customer,
    apple,
    monkeypatch,
):
    batch = create_batch(
        batch_id="A-SPECIAL",
        product=apple,
        quantity=4,
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

    standard_offer = _standard_offer(
        available_units=6,
    )
    special_offer = _batch_offer(
        commercial_price=commercial_price,
        available_units=4,
        price=Decimal("8.50"),
    )

    catalog_product = _catalog_product(
        product=apple,
        available_units=10,
        offers=(
            standard_offer,
            special_offer,
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    order = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=None,
        quantity=2,
    )

    updated = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=commercial_price.pk,
        quantity=3,
    )

    assert updated.pk == order.pk
    assert updated.lines.count() == 2

    lines = list(
        updated.lines
        .select_related(
            "business_offer_selection__commercial_price",
        )
        .order_by("id")
    )

    standard_line, special_line = lines

    assert standard_line.product == apple
    assert standard_line.quantity_in_units == 2
    assert (
        standard_line.business_offer_selection.commercial_price_id
        is None
    )

    assert special_line.product == apple
    assert special_line.quantity_in_units == 3
    assert (
        special_line.business_offer_selection.commercial_price_id
        == commercial_price.pk
    )


@pytest.mark.django_db
def test_explicit_standard_offer_does_not_merge_with_legacy_product_line(
    customer,
    apple,
    stocked_inventory,
    monkeypatch,
):
    order = add_product_to_draft_order(
        customer=customer,
        product=apple,
        quantity=2,
    )

    legacy_line = order.lines.get()

    catalog_product = _catalog_product(
        product=apple,
        available_units=10,
        offers=(
            _standard_offer(
                available_units=10,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    updated = add_catalog_offer_to_draft_order(
        customer=customer,
        product=apple,
        commercial_price_id=None,
        quantity=1,
    )

    assert updated.lines.count() == 2

    legacy_line.refresh_from_db()

    assert legacy_line.quantity_in_units == 2
    assert not BusinessOfferSelection.objects.filter(
        order_line=legacy_line,
    ).exists()

    explicit_line = (
        updated.lines
        .exclude(pk=legacy_line.pk)
        .get()
    )

    assert explicit_line.quantity_in_units == 1
    assert (
        explicit_line.business_offer_selection.commercial_price_id
        is None
    )


@pytest.mark.django_db
def test_add_catalog_offer_rejects_quantity_above_offer_availability(
    customer,
    apple,
    monkeypatch,
):
    catalog_product = _catalog_product(
        product=apple,
        available_units=3,
        offers=(
            _standard_offer(
                available_units=3,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="only 3 units are currently available for this offer",
    ):
        add_catalog_offer_to_draft_order(
            customer=customer,
            product=apple,
            commercial_price_id=None,
            quantity=4,
        )


@pytest.mark.django_db
def test_add_catalog_offer_rejects_offer_not_in_business_catalog(
    customer,
    apple,
    monkeypatch,
):
    catalog_product = _catalog_product(
        product=apple,
        available_units=10,
        offers=(
            _standard_offer(
                available_units=10,
            ),
        ),
    )

    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (
            catalog_product,
        ),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="business offer is not currently available",
    ):
        add_catalog_offer_to_draft_order(
            customer=customer,
            product=apple,
            commercial_price_id=999_999,
        )


@pytest.mark.django_db
def test_add_catalog_offer_rejects_product_not_in_business_catalog(
    customer,
    apple,
    monkeypatch,
):
    monkeypatch.setattr(
        "business.services.list_business_catalog_products",
        lambda: (),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="product is not available in the business catalog",
    ):
        add_catalog_offer_to_draft_order(
            customer=customer,
            product=apple,
            commercial_price_id=None,
        )


@pytest.mark.django_db
def test_retail_commercial_price_cannot_be_selected_for_business(
    customer,
    apple,
):
    create_batch(
        batch_id="A-ORDINARY",
        product=apple,
        quantity=10,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    retail_price = CommercialPrice.objects.create(
        product=apple,
        batch=None,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )

    PriceAmount.objects.create(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="business offer is not currently available",
    ):
        add_catalog_offer_to_draft_order(
            customer=customer,
            product=apple,
            commercial_price_id=retail_price.pk,
        )


@pytest.mark.django_db
def test_disabled_business_commercial_price_cannot_be_selected(
    customer,
    apple,
):
    create_batch(
        batch_id="A-ORDINARY",
        product=apple,
        quantity=10,
        best_before=TODAY + timedelta(days=60),
        location="Shelf A1",
        today=TODAY,
    )

    disabled_price = CommercialPrice.objects.create(
        product=apple,
        batch=None,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=False,
    )

    PriceAmount.objects.create(
        commercial_price=disabled_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("12.50"),
    )

    with pytest.raises(
        InvalidOrderOperation,
        match="business offer is not currently available",
    ):
        add_catalog_offer_to_draft_order(
            customer=customer,
            product=apple,
            commercial_price_id=disabled_price.pk,
        )
