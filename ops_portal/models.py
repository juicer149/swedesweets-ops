# ops_portal/models.py

from __future__ import annotations

from django.db import models

from orders.models import Allocation


class PickChecklistMark(models.Model):
    """Ops-only cache of which reserved pick lines have been physically picked.

    This is not domain truth - Allocation/Order already own the real state
    (RESERVED vs CONSUMED, order status). This table exists only so pack
    staff don't lose their place mid-pick when navigating away and back.
    Rows are created on demand (a missing row means "not checked") and are
    deleted once the order is packed - see fulfillment.services.pack_order,
    which deletes marks in the same transaction that consumes reservations.
    """

    allocation = models.OneToOneField(
        Allocation,
        on_delete=models.CASCADE,
        related_name="pick_checklist_mark",
    )
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pick checklist mark"
        verbose_name_plural = "Pick checklist marks"

    def __str__(self) -> str:
        return f"Checked: allocation #{self.allocation_id}"
