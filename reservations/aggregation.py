from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from reservations.protocols import ReservationProvider


def aggregate_reserved_quantities(
    *,
    batch_pks: Iterable[int],
    providers: Iterable[ReservationProvider],
) -> dict[int, int]:
    """Aggregate reserved quantity from one or more reservation providers."""

    pks = tuple(batch_pks)

    if not pks:
        return {}

    requested_pks = set(pks)
    totals: dict[int, int] = defaultdict(int)

    for provider in providers:
        for batch_pk, quantity in provider(
            batch_pks=pks,
        ):
            if batch_pk not in requested_pks:
                continue

            if quantity < 0:
                raise ValueError(
                    "reserved quantity must not be negative"
                )

            totals[batch_pk] += quantity

    return dict(totals)
