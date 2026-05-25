from __future__ import annotations


class CustomerError(ValueError):
    """Base class for customer domain errors."""


class InvalidCustomerData(CustomerError):
    """Raised when customer data violates domain rules."""
