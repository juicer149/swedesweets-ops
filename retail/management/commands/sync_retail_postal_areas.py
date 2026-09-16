from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from retail.delivery_areas import (
    PostalAreaFetchError,
    sync_retail_postal_areas,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Sync locally known retail postal areas from the upstream "
        "reference source. Only adds newly known postal areas; never "
        "modifies or deletes existing rows, including local `enabled` "
        "overrides."
    )

    def handle(self, *args, **options) -> None:
        try:
            result = sync_retail_postal_areas()
        except PostalAreaFetchError as exc:
            raise CommandError(
                f"retail postal-area sync aborted: {exc}"
            ) from exc

        self.stdout.write(
            f"Fetched:   {result.fetched}\n"
            f"Created:   {result.created}\n"
            f"Unchanged: {result.unchanged}\n"
            f"Stale:     {len(result.stale)}"
        )

        if result.stale:
            logger.warning(
                "Retail postal-area sync found %d stale local areas: %s",
                len(result.stale),
                ", ".join(
                    f"{record.postal_code} {record.city}"
                    for record in result.stale
                ),
            )
