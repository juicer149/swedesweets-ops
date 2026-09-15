from __future__ import annotations

from django.db import transaction

from fulfillment.services import pack_order as pack_order_with_reservations
from ops_portal.models import PickChecklistMark
from orders.models import Order


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
