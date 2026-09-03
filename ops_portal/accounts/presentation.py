from __future__ import annotations

from dataclasses import replace

from django.urls import reverse

from accounts.presentation import (
    AccountPresentation,
    build_account_presentation,
)
from accounts.selectors import AccountRecord


def build_ops_account_presentation(
    account: AccountRecord,
) -> AccountPresentation:
    presentation = build_account_presentation(account)

    if account.identity.customer_id is None:
        return presentation

    return replace(
        presentation,
        linked_identity_href=reverse(
            "ops_customers:detail",
            kwargs={
                "customer_pk": account.identity.customer_id,
            },
        ),
    )
