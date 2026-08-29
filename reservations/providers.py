from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Q, Sum
from django.utils import timezone

from orders.models import Allocation
from reservations.protocols import BatchQuantity


def active_allocation_reservations(
    *,
    batch_pks: tuple[int, ...],
) -> Iterable[BatchQuantity]:
    """Yield active Allocation quantities grouped by inventory batch.

    Reservation activity belongs to Allocation itself:

    RESERVED
    and
    reserved_until is NULL or lies in the future.
    """

    if not batch_pks:
        return

    now = timezone.now()

    rows = (
        Allocation.objects
        .filter(
            batch_id__in=batch_pks,
            status=Allocation.Status.RESERVED,
        )
        .filter(
            Q(reserved_until__isnull=True)
            | Q(reserved_until__gt=now)
        )
        .values("batch_id")
        .annotate(total=Sum("quantity"))
    )

    for row in rows:
        yield (
            row["batch_id"],
            row["total"] or 0,
        )
