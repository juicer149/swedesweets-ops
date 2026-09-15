from __future__ import annotations

from orders.models import Allocation, Order
from ops_portal.models import PickChecklistMark


def list_checked_allocation_ids_for_order(
    *,
    order: Order,
) -> frozenset[int]:
    """Return the set of allocation ids currently marked as picked."""

    return frozenset(
        PickChecklistMark.objects
        .filter(
            allocation__order=order,
        )
        .values_list(
            "allocation_id",
            flat=True,
        )
    )


class ChecklistAllocationNotFound(ValueError):
    """Raised when a toggle request targets an allocation outside the order."""


def toggle_checklist_mark(
    *,
    order: Order,
    allocation_id: int,
) -> bool:
    """Toggle a pick checklist mark for one allocation.

    Returns the new checked state. Only allocations that actually belong
    to the given order and are still RESERVED can be toggled - this is
    the boundary check against a request targeting another order's
    allocation, or a stale request for a line that's already been packed
    or removed.
    """

    allocation_exists = Allocation.objects.filter(
        pk=allocation_id,
        order=order,
        status=Allocation.Status.RESERVED,
    ).exists()

    if not allocation_exists:
        raise ChecklistAllocationNotFound(
            f"allocation {allocation_id} is not a reserved "
            f"allocation on order {order.pk}"
        )

    deleted_count, _ = PickChecklistMark.objects.filter(
        allocation_id=allocation_id,
    ).delete()

    if deleted_count:
        return False

    PickChecklistMark.objects.create(
        allocation_id=allocation_id,
    )

    return True
