from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from accounts.selectors import AccountActivityRow, AccountListRow
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_secondary_get_action,
)


@dataclass(frozen=True, slots=True)
class AccountDetailContext:
    account: AccountListRow
    activity_rows: tuple[AccountActivityRow, ...]
    detail_card: DetailCard
    title: str
    description: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "account": self.account,
            "activity_rows": self.activity_rows,
            "activity_count": len(self.activity_rows),
            "detail_card": self.detail_card,
            "title": self.title,
            "description": self.description,
            "cancel_url": self.cancel_url,
        }


def build_account_detail_context(
    *,
    account: AccountListRow,
    activity_rows: tuple[AccountActivityRow, ...],
    cancel_url: str,
) -> AccountDetailContext:
    return AccountDetailContext(
        account=account,
        activity_rows=activity_rows,
        detail_card=DetailCard(
            header=_build_account_header(account),
            panels=_build_account_detail_panels(
                account=account,
                activity_count=len(activity_rows),
            ),
            secondary_actions=_build_account_secondary_actions(account),
        ),
        title=account.email,
        description="",
        cancel_url=cancel_url,
    )


def _build_account_header(account: AccountListRow) -> DetailHeader:
    return DetailHeader(
        eyebrow="Account",
        title=account.email,
        status_label=account.status_label,
        status_class=_account_status_class(account),
        status_icon="users",
    )


def _build_account_detail_panels(
    *,
    account: AccountListRow,
    activity_count: int,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="account",
            label="Account",
            summary=account.role_label,
            body_template="accounts/includes/detail_panel_account.html",
            icon="users",
            is_active=True,
        ),
        DetailPanel(
            key="activity",
            label="Activity",
            summary=_activity_summary(activity_count),
            body_template="accounts/includes/detail_panel_activity.html",
            icon="inventory",
        ),
    )


def _build_account_secondary_actions(
    account: AccountListRow,
) -> tuple[DetailAction, ...]:
    return (
        build_secondary_get_action(
            label="Back to accounts",
            href=_accounts_internal_url(),
        ),
    )


def _account_status_class(account: AccountListRow) -> str:
    if account.is_active:
        return "status-text status-text--success"

    return "status-text status-text--neutral"


def _activity_summary(activity_count: int) -> str:
    if activity_count == 1:
        return "1 event"

    return f"{activity_count} events"


def _accounts_internal_url() -> str:
    return f"{reverse('accounts:index')}?view=internal#accounts-list"


def account_datetime_label(value: datetime | None) -> str:
    if value is None:
        return "Never"

    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
