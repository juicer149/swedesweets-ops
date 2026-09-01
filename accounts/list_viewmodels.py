from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from accounts.presentation import (
    AccountPresentation,
    build_account_presentation,
)
from accounts.selectors import AccountRecord
from common.page_header import PageHeader, PageHeaderAction
from common.ui import (
    TONE_MUTED,
    TONE_NEUTRAL,
    UiCard,
    UiCardRow,
    UiText,
)

ACCOUNT_VIEW_INTERNAL = "internal"
ACCOUNT_VIEW_CUSTOMER = "customer"
ACCOUNT_VIEW_UNLINKED = "unlinked"


@dataclass(frozen=True, slots=True)
class AccountViewLink:
    key: str
    label: str
    href: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class AccountPageRow:
    user_id: int
    email: str
    role_label: str
    linked_identity: str
    linked_identity_href: str
    status_label: str
    status_tone: str
    last_login_label: str
    date_joined_label: str
    detail_href: str
    card: UiCard


def build_accounts_page_header(*, active_view: str) -> PageHeader:
    return PageHeader(
        title="Accounts",
        title_id="accounts-title",
        description="",
        action=_build_accounts_page_action(active_view=active_view),
    )


def build_account_view_links(
    *,
    active_view: str,
) -> tuple[AccountViewLink, ...]:
    return (
        AccountViewLink(
            key=ACCOUNT_VIEW_INTERNAL,
            label="Internal",
            href=_accounts_view_href(ACCOUNT_VIEW_INTERNAL),
            is_active=active_view == ACCOUNT_VIEW_INTERNAL,
        ),
        AccountViewLink(
            key=ACCOUNT_VIEW_CUSTOMER,
            label="Customer",
            href=_accounts_view_href(ACCOUNT_VIEW_CUSTOMER),
            is_active=active_view == ACCOUNT_VIEW_CUSTOMER,
        ),
        AccountViewLink(
            key=ACCOUNT_VIEW_UNLINKED,
            label="Unlinked",
            href=_accounts_view_href(ACCOUNT_VIEW_UNLINKED),
            is_active=active_view == ACCOUNT_VIEW_UNLINKED,
        ),
    )


def build_account_page_rows(
    records: tuple[AccountRecord, ...],
) -> tuple[AccountPageRow, ...]:
    return tuple(
        _build_account_page_row(record)
        for record in records
    )


def _build_account_page_row(
    record: AccountRecord,
) -> AccountPageRow:
    account = build_account_presentation(record)
    status_tone = _status_tone(is_active=account.is_active)
    last_login_label = _datetime_label(account.last_login)
    date_joined_label = _datetime_label(account.date_joined)
    detail_href = reverse(
        "accounts:detail",
        kwargs={"user_id": account.user_id},
    )

    return AccountPageRow(
        user_id=account.user_id,
        email=account.email,
        role_label=account.role_label,
        linked_identity=account.linked_identity,
        linked_identity_href=account.linked_identity_href,
        status_label=account.status_label,
        status_tone=status_tone,
        last_login_label=last_login_label,
        date_joined_label=date_joined_label,
        detail_href=detail_href,
        card=_account_card(
            account=account,
            status_tone=status_tone,
            last_login_label=last_login_label,
            date_joined_label=date_joined_label,
            detail_href=detail_href,
        ),
    )


def _account_card(
    *,
    account: AccountPresentation,
    status_tone: str,
    last_login_label: str,
    date_joined_label: str,
    detail_href: str,
) -> UiCard:
    return UiCard(
        tone=TONE_NEUTRAL if account.is_active else TONE_MUTED,
        css_class="mobile-card mobile-card--account",
        href=detail_href,
        aria_label=f"View account {account.email}",
        rows=(
            UiCardRow(
                left=UiText(
                    text=account.email,
                    css_class="ui-card-title",
                ),
                right=UiText(
                    text=account.status_label,
                    css_class=f"status-text status-text--{status_tone}",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=account.role_label,
                    label="Role",
                    css_class="ui-card-location",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=account.linked_identity,
                    label="Linked identity",
                    css_class="ui-card-location",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=last_login_label,
                    label="Last login",
                    css_class="ui-card-location",
                ),
                right=UiText(
                    text=date_joined_label,
                    label="Joined",
                    css_class="ui-card-location",
                ),
            ),
        ),
    )


def _build_accounts_page_action(
    *,
    active_view: str,
) -> PageHeaderAction | None:
    if active_view == ACCOUNT_VIEW_INTERNAL:
        return PageHeaderAction(
            label="Create internal account",
            href=reverse("accounts:create_internal"),
            icon="plus",
            aria_label="Create internal staff account",
        )

    if active_view == ACCOUNT_VIEW_CUSTOMER:
        return PageHeaderAction(
            label="Create customer account",
            href=reverse("accounts:create_customer_account"),
            icon="plus",
            aria_label="Create customer login account",
        )

    return None


def _accounts_view_href(view: str) -> str:
    return f"{reverse('accounts:index')}?view={view}#accounts-list"


def _status_tone(*, is_active: bool) -> str:
    if is_active:
        return "success"

    return "neutral"


def _datetime_label(value: datetime | None) -> str:
    if value is None:
        return "Never"

    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
