from __future__ import annotations


class InventoryError(ValueError):
    """Base class for inventory domain errors."""


class InvalidStockOperation(InventoryError):
    """Raised when an inventory operation would violate stock rules."""


class InvalidBatchStatusTransition(InventoryError):
    """Raised when a batch lifecycle transition is not allowed."""


class InsufficientStockError(InvalidStockOperation):
    """Raised when inventory cannot produce a complete batch-pick plan."""

    def __init__(
        self,
        *,
        product_name: str,
        requested_quantity: int,
        available_quantity: int,
        missing_quantity: int,
    ) -> None:
        self.product_name = product_name
        self.requested_quantity = requested_quantity
        self.available_quantity = available_quantity
        self.missing_quantity = missing_quantity

        unit_label = "unit" if available_quantity == 1 else "units"

        super().__init__(
            f"Only {available_quantity} {unit_label} available for {product_name}."
        )
