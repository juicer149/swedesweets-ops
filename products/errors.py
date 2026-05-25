from __future__ import annotations


class ProductError(ValueError):
    """Base class for product domain errors."""


class InvalidProductData(ProductError):
    """Raised when product data violates product rules."""


class UnsupportedOrderUnit(ProductError):
    """Raised when an order quantity uses an unsupported unit."""
