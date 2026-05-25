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
        requested_boxes: int,
        available_boxes: int,
        missing_boxes: int,
    ) -> None:
        self.product_name = product_name
        self.requested_boxes = requested_boxes
        self.available_boxes = available_boxes
        self.missing_boxes = missing_boxes

        box_label = "box" if available_boxes == 1 else "boxes"

        super().__init__(
            f"Only {available_boxes} {box_label} available for {product_name}."
        )
