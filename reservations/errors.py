from __future__ import annotations

from orders.errors import OrderError


class InvalidAllocationStatusTransition(OrderError):
    """Raised when an allocation lifecycle transition is not allowed."""
