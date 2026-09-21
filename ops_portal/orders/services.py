from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from fulfillment.services import pack_order as pack_order_with_reservations
from ops_portal.models import PickChecklistMark
from ops_portal.orders.drafts import (
    build_ops_order_draft,
    resolve_ops_order_lines,
)
from ops_portal.orders.policies import prepare_ops_order_for_placement
from orders.datatypes import OrderLineInput
from orders.models import Order
from reservations.models import Allocation
from orders.services import (
    create_draft_order,
    place_order as place_shared_order,
    update_placed_order as update_shared_placed_order,
)
from reservations.policies import (
    clear_order_reservations_before_line_replacement,
)


def create_order(
    *,
    customer,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Create and immediately place an order from the ops portal.

    Mirrors business.create_order's two-step shape (build draft, then
    place it) without importing from business - draft-building and
    placement preparation both use ops_portal's own, catalog-offer-free
    equivalents.
    """

    draft = build_ops_order_draft(
        customer=customer,
        lines=lines,
    )

    order = create_draft_order(
        draft=draft,
    )

    return place_shared_order(
        order=order,
        preparation=prepare_ops_order_for_placement,
        user=user,
    )


@transaction.atomic
def pack_order_and_clear_checklist(
    *,
    order: Order,
    user=None,
) -> Order:
    """Pack an order, then clear its ops-only pick checklist cache.

    Wrapped in its own atomic block so the mark cleanup can never be
    silently skipped after a successful pack - if it fails, the whole
    operation (including the pack itself) rolls back. fulfillment.pack_order
    is called unmodified; this function only adds the ops-specific cache
    cleanup on top, keeping the dependency direction correct (ops_portal
    depends on fulfillment, never the reverse).
    """

    packed_order = pack_order_with_reservations(
        order=order,
        user=user,
    )

    PickChecklistMark.objects.filter(
        allocation__order=packed_order,
    ).delete()

    return packed_order


@transaction.atomic
def update_placed_order_and_preserve_checklist(
    *,
    order: Order,
    lines: Iterable[OrderLineInput],
    user=None,
) -> Order:
    """Edit a placed order, preserving checklist marks for untouched lines.

    orders.update_placed_order deletes every OrderLine and every
    Allocation before rebuilding them, regardless of whether a given
    line actually changed - so Allocation ids are never stable across
    an edit, and PickChecklistMark's CASCADE delete would otherwise wipe
    every mark unconditionally.

    A checklist mark is only carried over for a product whose total
    quantity is EXACTLY unchanged by this edit. Any product that was
    added, removed, or had its quantity changed loses its mark - staff
    have not yet physically verified the new quantity, so a stale
    checkmark would be misleading. Among unchanged-quantity products,
    (product_id, batch_id) is used as a stable identity across the
    rebuild, since batch assignment is deterministic (FEFO) and an
    untouched line almost always lands on the same batch again.

    Calls the shared, channel-neutral orders.update_placed_order
    directly - never business.update_placed_order - so ops_portal has
    no dependency on the business app.
    """

    resolved_lines = resolve_ops_order_lines(
        lines=lines,
    )

    old_quantity_by_product_id = dict(
        order.lines
        .values_list(
            "product_id",
            "quantity_in_units",
        )
    )

    new_quantity_by_product_id = {
        resolved_line.product.id: resolved_line.quantity_in_units
        for resolved_line in resolved_lines
    }

    unchanged_product_ids = {
        product_id
        for product_id, old_quantity in old_quantity_by_product_id.items()
        if new_quantity_by_product_id.get(product_id) == old_quantity
    }

    checked_keys = set(
        Allocation.objects
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
            pick_checklist_mark__isnull=False,
            batch__product_id__in=unchanged_product_ids,
        )
        .values_list(
            "batch__product_id",
            "batch_id",
        )
    )

    updated_order = update_shared_placed_order(
        order=order,
        lines=resolved_lines,
        before_replacement=clear_order_reservations_before_line_replacement,
        preparation=prepare_ops_order_for_placement,
        user=user,
    )

    if checked_keys:
        new_allocations = (
            Allocation.objects
            .filter(
                order=updated_order,
                status=Allocation.Status.RESERVED,
            )
            .select_related("batch")
        )

        PickChecklistMark.objects.bulk_create(
            [
                PickChecklistMark(allocation=allocation)
                for allocation in new_allocations
                if (
                    allocation.batch.product_id,
                    allocation.batch_id,
                ) in checked_keys
            ]
        )

    return updated_order
