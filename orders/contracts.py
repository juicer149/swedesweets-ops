from __future__ import annotations

from typing import Protocol

from orders.models import Order


class OrderMutationGuard(Protocol):
    """Validate whether a locked order may be mutated."""

    def __call__(
        self,
        *,
        order: Order,
    ) -> None:
        ...


class OrderMutationPreparation(Protocol):
    """Perform required work around a shared order mutation."""

    def __call__(
        self,
        *,
        order: Order,
    ) -> None:
        ...
