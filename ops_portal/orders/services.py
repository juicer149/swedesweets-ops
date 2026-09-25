from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from business.datatypes import BusinessOfferLineInput
from business.drafts import resolve_business_offer_lines
from business.policies import prepare_business_order_for_placement
from fulfillment.services import pack_order as pack_order_with_reservations
from ops_portal.models import PickChecklistMark
from ops_portal.orders.drafts import build_ops_order_draft
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
    lines: Iterable[BusinessOfferLineInput],
    user=None,
) -> Order:
    """Create and immediately place an order from the ops portal.

    Ops owns the staff-facing workflow and draft adaptation. Business owns
    BUSINESS placement semantics, including the stock pool represented by
    each commercial offer.
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
        preparation=prepare_business_order_for_placement,
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
    lines: Iterable[BusinessOfferLineInput],
    user=None,
) -> Order:
    """Edit a placed order, preserving marks for untouched order lines.

    The shared order service preserves an OrderLine when its commercial
    offer remains part of the order. Reservations are still rebuilt, so
    Allocation ids are not stable across an edit.

    A checklist mark is carried over only when the exact durable order
    line keeps the same quantity. Quantity changes invalidate the mark:
    staff have not physically verified the new amount.

    For unchanged lines, (order_line_id, batch_id) is stable across the
    reservation rebuild and distinguishes separate commercial offers for
    the same product.

    The shared order service performs the line replacement so ops can preserve
    its checklist workflow. BUSINESS placement semantics are delegated to the
    business policy when reservations are rebuilt.
    """

    resolved_lines = resolve_business_offer_lines(
        lines=lines,
    )

    incoming_quantity_by_offer_id = {
        resolved_line.commercial_offer.pk:
        resolved_line.quantity_in_units
        for resolved_line in resolved_lines
    }

    unchanged_line_ids = {
        line.id
        for line in (
            order.lines
            .only(
                "id",
                "commercial_offer_id",
                "quantity_in_units",
            )
        )
        if (
            incoming_quantity_by_offer_id.get(
                line.commercial_offer_id
            )
            == line.quantity_in_units
        )
    }

    checked_keys = set(
        Allocation.objects
        .filter(
            order=order,
            status=Allocation.Status.RESERVED,
            pick_checklist_mark__isnull=False,
            order_line_id__in=unchanged_line_ids,
        )
        .values_list(
            "order_line_id",
            "batch_id",
        )
    )

    updated_order = update_shared_placed_order(
        order=order,
        lines=resolved_lines,
        before_replacement=clear_order_reservations_before_line_replacement,
        preparation=prepare_business_order_for_placement,
        user=user,
    )

    if checked_keys:
        new_allocations = (
            Allocation.objects
            .filter(
                order=updated_order,
                status=Allocation.Status.RESERVED,
            )
        )

        PickChecklistMark.objects.bulk_create(
            [
                PickChecklistMark(
                    allocation=allocation
                )
                for allocation in new_allocations
                if (
                    allocation.order_line_id,
                    allocation.batch_id,
                ) in checked_keys
            ]
        )

    return updated_order
