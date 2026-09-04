from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import InventoryBatch
from pricing.models import CommercialPrice, PriceAmount
from pricing.tests.factories import (
    commercial_price_factory,
    price_amount_factory,
)
from retail.selectors import (
    get_batch_for_batch_offer,
    get_batch_for_retail_price,
    list_batches_for_product_offer,
    list_batches_for_retail_price,
)
from retail.tests.factories import (
    retail_batch_offer_factory,
    retail_inventory_batch_factory,
    retail_product_factory,
    retail_product_offer_factory,
)


@pytest.mark.django_db
def test_product_offer_returns_eligible_product_batches():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        quantity=10,
        best_before=today + timedelta(days=30),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    )

    assert batches == [batch]


@pytest.mark.django_db
def test_product_offer_excludes_batch_with_enabled_batch_offer():
    today = timezone.localdate()
    product = retail_product_factory()

    product_offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    ordinary_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    clearance_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-002",
        best_before=today + timedelta(days=10),
    )

    retail_batch_offer_factory(
        batch=clearance_batch,
        enabled=True,
        price=Decimal("3.90"),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=product_offer,
            today=today,
        )
    )

    assert batches == [ordinary_batch]


@pytest.mark.django_db
def test_product_offer_includes_batch_with_disabled_batch_offer():
    today = timezone.localdate()
    product = retail_product_factory()

    product_offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    retail_batch_offer_factory(
        batch=batch,
        enabled=False,
        price=Decimal("3.90"),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=product_offer,
            today=today,
        )
    )

    assert batches == [batch]


@pytest.mark.django_db
def test_product_offer_returns_batches_in_fefo_order():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    later_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-002",
        best_before=today + timedelta(days=60),
    )

    earlier_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=20),
    )

    batches = list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    )

    assert batches == [
        earlier_batch,
        later_batch,
    ]


@pytest.mark.django_db
def test_product_offer_excludes_depleted_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        quantity=10,
    )
    batch.adjust_quantity(quantity=0)

    assert batch.status == InventoryBatch.Status.DEPLETED

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_excludes_closed_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
    )
    batch.close()

    assert batch.status == InventoryBatch.Status.CLOSED

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_excludes_expired_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    batch.best_before = today - timedelta(days=1)
    batch.save(update_fields=["best_before", "updated_at"])

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_excludes_batch_expiring_today():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
        best_before=today + timedelta(days=30),
    )

    batch.best_before = today
    batch.save(update_fields=["best_before", "updated_at"])

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_product_offer_does_not_return_batches_for_other_product():
    today = timezone.localdate()

    product = retail_product_factory(
        name="Product A",
    )
    other_product = retail_product_factory(
        name="Product B",
    )

    offer = retail_product_offer_factory(
        product=product,
        enabled=True,
        price=Decimal("6.90"),
    )

    retail_inventory_batch_factory(
        product=other_product,
        today=today,
        batch_id="RET-OTHER",
    )

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_disabled_product_offer_has_no_batch_pool():
    today = timezone.localdate()
    product = retail_product_factory()

    offer = retail_product_offer_factory(
        product=product,
        enabled=False,
        price=Decimal("6.90"),
    )

    retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
    )

    assert list(
        list_batches_for_product_offer(
            offer=offer,
            today=today,
        )
    ) == []


@pytest.mark.django_db
def test_batch_offer_returns_exact_configured_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    batch = get_batch_for_batch_offer(
        offer=offer,
        today=today,
    )

    assert batch == offer.batch


@pytest.mark.django_db
def test_batch_offer_never_falls_through_to_another_batch():
    today = timezone.localdate()
    product = retail_product_factory()

    offered_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-001",
    )

    retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="RET-002",
    )

    offer = retail_batch_offer_factory(
        batch=offered_batch,
        enabled=True,
        price=Decimal("3.90"),
    )

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        == offered_batch
    )


@pytest.mark.django_db
def test_disabled_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=False,
        price=Decimal("3.90"),
    )

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )


@pytest.mark.django_db
def test_depleted_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    offer.batch.adjust_quantity(quantity=0)

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )


@pytest.mark.django_db
def test_closed_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    offer.batch.close()

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )


@pytest.mark.django_db
def test_expired_batch_offer_has_no_batch():
    today = timezone.localdate()

    offer = retail_batch_offer_factory(
        enabled=True,
        price=Decimal("3.90"),
    )

    offer.batch.best_before = today - timedelta(days=1)
    offer.batch.save(
        update_fields=[
            "best_before",
            "updated_at",
        ]
    )

    assert (
        get_batch_for_batch_offer(
            offer=offer,
            today=today,
        )
        is None
    )



@pytest.mark.django_db
def test_product_wide_retail_price_returns_eligible_product_batches():
    today = timezone.localdate()
    product = retail_product_factory()

    commercial_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="PRICE-RET-001",
        quantity=10,
        best_before=today + timedelta(days=30),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [batch]


@pytest.mark.django_db
def test_product_wide_retail_price_excludes_batch_with_own_retail_price():
    today = timezone.localdate()
    product = retail_product_factory()

    product_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=product_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("6.90"),
    )

    ordinary_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="PRICE-RET-ORDINARY",
        best_before=today + timedelta(days=30),
    )
    special_batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="PRICE-RET-SPECIAL",
        best_before=today + timedelta(days=10),
    )

    batch_price = commercial_price_factory(
        product=product,
        batch=special_batch,
        channel=CommercialPrice.Channel.RETAIL,
        reason=CommercialPrice.Reason.SHORT_DATED,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=batch_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("3.90"),
        original_price=Decimal("6.90"),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=product_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [ordinary_batch]


@pytest.mark.django_db
def test_product_wide_retail_price_keeps_batch_without_requested_currency():
    today = timezone.localdate()
    product = retail_product_factory()

    product_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=product_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="PRICE-RET-SEK-ONLY",
    )

    batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=batch_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("39.00"),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=product_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [batch]


@pytest.mark.django_db
def test_product_wide_retail_price_does_not_exclude_business_batch_price():
    today = timezone.localdate()
    product = retail_product_factory()

    retail_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=retail_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("6.90"),
    )

    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="PRICE-BUSINESS-BATCH",
    )

    business_batch_price = commercial_price_factory(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=business_batch_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("4.90"),
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=retail_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
    ) == [batch]


@pytest.mark.django_db
def test_batch_specific_retail_price_returns_exact_batch():
    today = timezone.localdate()
    product = retail_product_factory()
    batch = retail_inventory_batch_factory(
        product=product,
        today=today,
        batch_id="PRICE-BATCH-EXACT",
    )

    commercial_price = commercial_price_factory(
        product=product,
        batch=batch,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
        reason=CommercialPrice.Reason.SHORT_DATED,
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("3.90"),
    )

    assert (
        get_batch_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
            today=today,
        )
        == batch
    )


@pytest.mark.django_db
def test_product_wide_retail_price_has_no_exact_batch():
    product = retail_product_factory()
    commercial_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("6.90"),
    )

    assert get_batch_for_retail_price(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
    ) is None


@pytest.mark.django_db
def test_retail_price_requires_requested_currency():
    product = retail_product_factory()
    commercial_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.RETAIL,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.SEK,
        price=Decimal("69.00"),
    )

    retail_inventory_batch_factory(
        product=product,
        batch_id="PRICE-NO-EUR",
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )
    ) == []


@pytest.mark.django_db
def test_retail_stock_pool_rejects_business_commercial_price():
    product = retail_product_factory()
    commercial_price = commercial_price_factory(
        product=product,
        channel=CommercialPrice.Channel.BUSINESS,
        enabled=True,
    )
    price_amount_factory(
        commercial_price=commercial_price,
        currency=PriceAmount.Currency.EUR,
        price=Decimal("5.90"),
    )

    retail_inventory_batch_factory(
        product=product,
        batch_id="PRICE-BUSINESS-ONLY",
    )

    assert list(
        list_batches_for_retail_price(
            commercial_price=commercial_price,
            currency=PriceAmount.Currency.EUR,
        )
    ) == []
