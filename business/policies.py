from __future__ import annotations

from business.models import BusinessOfferSelection
from business.selectors import (
    list_business_catalog_products,
)
from common.catalog.contracts import (
    CatalogOffer,
    CatalogOfferKind,
    CatalogProduct,
)
from inventory.errors import InsufficientStockError
from inventory.selectors import (
    list_orderable_batches_for_product,
)
from orders.errors import InvalidOrderOperation
from orders.models import (
    Order,
    OrderLine,
)
from reservations.planning import (
    InsufficientReservationCapacity,
)
from reservations.services import (
    reserve_order_line_from_pool,
)


def prepare_business_order_for_placement(
    *,
    order: Order,
) -> None:
    """Reserve inventory according to each business line's selection.

    Legacy business lines without BusinessOfferSelection retain ordinary
    FEFO behavior.

    Explicit standard catalog selections reserve from the ordinary business
    pool excluding batches exposed as separate special offers.

    Explicit batch selections reserve only from the exact selected batch.

    Business owns channel-specific stock eligibility composition.
    Reservations owns locking, accounting, FEFO planning and persistence.
    """

    if order.channel != Order.Channel.BUSINESS:
        raise InvalidOrderOperation(
            "Business placement policy requires a business order"
        )

    lines = list(
        order.lines
        .select_related(
            "product",
            "business_offer_selection__commercial_price",
        )
        .order_by("id")
    )

    if not lines:
        raise InvalidOrderOperation(
            "order must contain at least one line"
        )

    catalog_products_by_product_id: (
        dict[int, CatalogProduct] | None
    ) = None

    for line in lines:
        try:
            selection = line.business_offer_selection
        except BusinessOfferSelection.DoesNotExist:
            batches = list_orderable_batches_for_product(
                product=line.product,
            )
        else:
            if catalog_products_by_product_id is None:
                catalog_products_by_product_id = {
                    catalog_product.product.id: catalog_product
                    for catalog_product in (
                        list_business_catalog_products()
                    )
                }

            catalog_product = (
                catalog_products_by_product_id.get(
                    line.product_id
                )
            )

            if catalog_product is None:
                raise InvalidOrderOperation(
                    f"{line.product.display_name} "
                    "is no longer available in the business catalog"
                )

            offer = _resolve_explicit_selection(
                selection=selection,
                catalog_product=catalog_product,
            )

            batches = _batches_for_explicit_offer(
                line=line,
                catalog_product=catalog_product,
                offer=offer,
            )

        try:
            reserve_order_line_from_pool(
                order_line=line,
                batches=batches,
                quantity=line.quantity_in_units,
                reserved_until=None,
            )
        except InsufficientReservationCapacity as exc:
            raise InsufficientStockError(
                product_name=line.product.display_name,
                requested_quantity=(
                    exc.requested_quantity
                ),
                available_quantity=(
                    exc.available_quantity
                ),
                missing_quantity=(
                    exc.missing_quantity
                ),
            ) from exc


def _resolve_explicit_selection(
    *,
    selection: BusinessOfferSelection,
    catalog_product: CatalogProduct,
) -> CatalogOffer:
    if selection.commercial_price_id is None:
        return _standard_offer(
            catalog_product=catalog_product,
        )

    for offer in catalog_product.offers:
        if (
            offer.commercial_price_id
            == selection.commercial_price_id
        ):
            return offer

    raise InvalidOrderOperation(
        "selected business offer is no longer available"
    )


def _standard_offer(
    *,
    catalog_product: CatalogProduct,
) -> CatalogOffer:
    for offer in catalog_product.offers:
        if offer.kind == CatalogOfferKind.STANDARD:
            return offer

    raise InvalidOrderOperation(
        "standard business offer is no longer available"
    )


def _batches_for_explicit_offer(
    *,
    line: OrderLine,
    catalog_product: CatalogProduct,
    offer: CatalogOffer,
):
    batches = list_orderable_batches_for_product(
        product=line.product,
    )

    if offer.kind == CatalogOfferKind.BATCH:
        if offer.batch_id is None:
            raise InvalidOrderOperation(
                "batch offer has no batch"
            )

        return batches.filter(
            pk=offer.batch_id,
        )

    special_batch_ids = [
        candidate.batch_id
        for candidate in catalog_product.offers
        if (
            candidate.kind == CatalogOfferKind.BATCH
            and candidate.batch_id is not None
        )
    ]

    if not special_batch_ids:
        return batches

    return batches.exclude(
        pk__in=special_batch_ids,
    )
