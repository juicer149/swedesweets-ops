from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from django.db import transaction

from orders.contracts import OrderMutationGuard
from orders.models import Order


ReturnT = TypeVar("ReturnT")


def locked_order(
    *,
    guard: OrderMutationGuard | None = None,
):
    """Run an order mutation atomically against a freshly locked row.

    The decorator owns persistence mechanics:

        transaction
        -> SELECT ... FOR UPDATE
        -> optional lifecycle guard
        -> mutation

    The decorated function owns the actual domain operation.
    """

    def decorate(
        function: Callable[..., ReturnT],
    ) -> Callable[..., ReturnT]:
        @wraps(function)
        @transaction.atomic
        def wrapper(
            *,
            order: Order,
            **kwargs: Any,
        ) -> ReturnT:
            locked_order = (
                Order.objects
                .select_for_update()
                .get(pk=order.pk)
            )

            if guard is not None:
                guard(
                    order=locked_order,
                )

            return function(
                order=locked_order,
                **kwargs,
            )

        return cast(
            Callable[..., ReturnT],
            wrapper,
        )

    return decorate
