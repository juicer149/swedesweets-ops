from __future__ import annotations

from django.core.management.base import BaseCommand

from retail.reconciliation import (
    reconcile_pending_retail_payments,
)


class Command(BaseCommand):
    help = "Reconcile pending retail payments with their payment provider."

    def handle(
        self,
        *args,
        **options,
    ) -> None:
        summary = reconcile_pending_retail_payments()

        message = (
            "Payment reconciliation complete: "
            f"selected={summary.selected} "
            f"checked={summary.checked} "
            f"succeeded={summary.succeeded} "
            f"failed={summary.failed} "
            f"pending={summary.pending} "
            f"cancelled={summary.cancelled} "
            f"unresolved={summary.unresolved} "
            f"errors={summary.errors}"
        )

        if summary.errors:
            self.stdout.write(
                self.style.WARNING(
                    message
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                message
            )
        )
