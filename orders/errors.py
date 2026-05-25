from __future__ import annotations


class OrderError(ValueError):
    """Base class for order domain errors."""


class InvalidOrderOperation(OrderError):
    """Raised when an order workflow operation is not allowed."""


class InvalidOrderStatusTransition(OrderError):
    """Raised when an order lifecycle transition is not allowed."""


class InvalidAllocationStatusTransition(OrderError):
    """Raised when an allocation lifecycle transition is not allowed."""
