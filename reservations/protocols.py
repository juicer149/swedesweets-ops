from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol, TypeAlias


BatchQuantity: TypeAlias = tuple[int, int]


@dataclass(frozen=True, slots=True)
class BatchAvailability:
    """Physical batch data required by reservation planning."""

    batch_pk: int
    batch_code: str
    product_id: int
    physical_quantity: int
    best_before: date


@dataclass(frozen=True, slots=True)
class BatchPick:
    """Planned reservation from one physical batch."""

    batch_pk: int
    quantity: int


class ReservationProvider(Protocol):
    def __call__(
        self,
        *,
        batch_pks: tuple[int, ...],
    ) -> Iterable[BatchQuantity]:
        """Return reserved quantity grouped by requested batch primary key."""

        ...
