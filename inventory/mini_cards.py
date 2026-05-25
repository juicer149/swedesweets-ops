from __future__ import annotations

from common.ui import UiCard, UiCardRow, UiText
from inventory.models import InventoryBatch
from inventory.presentation import (
    INVENTORY_CARD_CLASS,
    INVENTORY_BATCH_ACTION_LABEL,
    batch_status_presentation,
    boxes_label,
)


def build_batch_mini_card(
    *,
    batch: InventoryBatch,
    batch_href: str,
) -> UiCard:
    status = batch_status_presentation(batch)

    return UiCard(
        tone=status.tone,
        css_class=INVENTORY_CARD_CLASS,
        rows=(
            UiCardRow(
                left=UiText(
                    text=batch.batch_id,
                    css_class="ui-card-id",
                ),
                right=status.text,
            ),
            UiCardRow(
                left=UiText(
                    text=boxes_label(batch.boxes),
                    css_class="ui-card-title",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=(f"Best before {batch.best_before:%Y-%m-%d}"),
                    css_class="ui-card-strong ui-card-strong--compact",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=batch.location,
                    css_class="ui-card-muted",
                ),
            ),
        ),
        action=UiText(
            text=INVENTORY_BATCH_ACTION_LABEL,
            href=batch_href,
            css_class="text-link",
        ),
    )
