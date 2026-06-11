from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from accounts.selectors import AccountListRow
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
        description="Manage internal and customer login accounts.",
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
    rows: tuple[AccountListRow, ...],
) -> tuple[AccountPageRow, ...]:
    return tuple(
        _build_account_page_row(row)
        for row in rows
    )


def _build_account_page_row(row: AccountListRow) -> AccountPageRow:
    status_tone = _status_tone(is_active=row.is_active)
    last_login_label = _datetime_label(row.last_login)
    date_joined_label = _datetime_label(row.date_joined)
    detail_href = reverse("accounts:detail", kwargs={"user_id": row.user_id})

    return AccountPageRow(
        user_id=row.user_id,
        email=row.email,
        role_label=row.role_label,
        linked_identity=row.linked_identity,
        status_label=row.status_label,
        status_tone=status_tone,
        last_login_label=last_login_label,
        date_joined_label=date_joined_label,
        detail_href=detail_href,
        card=_account_card(
            row=row,
            status_tone=status_tone,
            last_login_label=last_login_label,
            date_joined_label=date_joined_label,
            detail_href=detail_href,
        ),
    )


def _account_card(
    *,
    row: AccountListRow,
    status_tone: str,
    last_login_label: str,
    date_joined_label: str,
    detail_href: str,
) -> UiCard:
    return UiCard(
        tone=TONE_NEUTRAL if row.is_active else TONE_MUTED,
        css_class="mobile-card mobile-card--account",
        href=detail_href,
        aria_label=f"View account {row.email}",
        rows=(
            UiCardRow(
                left=UiText(
                    text=row.email,
                    css_class="ui-card-title",
                ),
                right=UiText(
                    text=row.status_label,
                    css_class=f"status-text status-text--{status_tone}",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.role_label,
                    label="Role",
                    css_class="ui-card-location",
                ),
            ),
            UiCardRow(
                left=UiText(
                    text=row.linked_identity,
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
    if active_view != ACCOUNT_VIEW_INTERNAL:
        return None

    return PageHeaderAction(
        label="Create internal account",
        href=reverse("accounts:create_internal"),
        icon="plus",
        aria_label="Create internal staff account",
    )


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
