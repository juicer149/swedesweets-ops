from __future__ import annotations

from django.db import models


class BusinessOfferSelection(models.Model):
    """Commercial selection attached to one business OrderLine.

    `commercial_price=None` represents an explicitly unpriced standard
    business selection.

    A non-null CommercialPrice preserves the exact pricing definition chosen
    by the business customer. Channel, product and current sellability are
    application invariants validated by business services.

    OrderLine remains the durable order-line identity and owns quantity and
    price snapshot.
    """

    order_line = models.OneToOneField(
        "orders.OrderLine",
        on_delete=models.CASCADE,
        related_name="business_offer_selection",
    )

    commercial_price = models.ForeignKey(
        "pricing.CommercialPrice",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="business_order_line_selections",
    )

    def __str__(self) -> str:
        if self.commercial_price_id is None:
            return (
                f"Order line {self.order_line_id} "
                "-> unpriced business standard"
            )

        return (
            f"Order line {self.order_line_id} "
            f"-> commercial price {self.commercial_price_id}"
        )
