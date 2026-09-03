from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.forms import Form

from inventory.models import InventoryBatch


@dataclass(frozen=True)
class FormContextItem:
    label: str
    value: Any


@dataclass(frozen=True)
class BatchFormContext:
    form: Form
    title: str
    description: str
    submit_label: str
    cancel_url: str
    batch: InventoryBatch | None = None
    batch_context_items: list[FormContextItem] | None = None

    def as_dict(self) -> dict[str, object]:
        context: dict[str, object] = {
            "form": self.form,
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
        }

        if self.batch is not None:
            context["batch"] = self.batch

        if self.batch_context_items is not None:
            context["batch_context_items"] = self.batch_context_items

        return context


@dataclass(frozen=True)
class CloseBatchContext:
    batch: InventoryBatch
    batch_context_items: list[FormContextItem]
    title: str
    description: str
    submit_label: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "batch": self.batch,
            "batch_context_items": self.batch_context_items,
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
        }


def build_create_batch_form_context(
    *,
    form: Form,
    cancel_url: str,
) -> BatchFormContext:
    return BatchFormContext(
        form=form,
        title="Add batch",
        description="",
        submit_label="Add batch",
        cancel_url=cancel_url,
    )


def build_edit_batch_form_context(
    *,
    batch: InventoryBatch,
    form: Form,
    cancel_url: str,
) -> BatchFormContext:
    return BatchFormContext(
        form=form,
        batch=batch,
        batch_context_items=build_batch_context_items(batch),
        title=f"Edit batch {batch.batch_id}",
        description=(
            "Correct physical stock, location or best-before date. "
            "Product and batch ID are kept fixed for traceability."
        ),
        submit_label="Update batch",
        cancel_url=cancel_url,
    )


def build_close_batch_form_context(
    *,
    batch: InventoryBatch,
    cancel_url: str,
) -> CloseBatchContext:
    return CloseBatchContext(
        batch=batch,
        batch_context_items=build_close_batch_context_items(batch),
        title=f"Close batch {batch.batch_id}",
        description="",
        submit_label="Close batch",
        cancel_url=cancel_url,
    )


def build_batch_context_items(batch: InventoryBatch) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="Product",
            value=batch.product.catalog_label,
        ),
        FormContextItem(
            label="Status",
            value=batch.get_status_display(),
        ),
        FormContextItem(
            label="Location",
            value=batch.location,
        ),
    ]


def build_close_batch_context_items(batch: InventoryBatch) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="Product",
            value=batch.product.catalog_label,
        ),
        FormContextItem(
            label="Quantity",
            value=batch.product.stock_quantity_label(batch.quantity),
        ),
        FormContextItem(
            label="Status",
            value=batch.get_status_display(),
        ),
    ]
