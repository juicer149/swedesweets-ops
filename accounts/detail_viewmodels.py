from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.urls import reverse
from django.utils import timezone

from accounts.access import can_manage_customer_account_status
from accounts.roles import AccountRole, RoleSpec
from accounts.selectors import AccountActivityRow, AccountListRow
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_danger_get_action,
    build_secondary_get_action,
)


# -----------------------------------------------------------------------------
# Account detail page context


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


@dataclass(frozen=True, slots=True)
class CustomerAccountStatusContext:
    title: str
    description: str
    submit_label: str
    submit_tone: str
    cancel_url: str
    account_user: object
    customer: object
    context_items: tuple[dict[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "submit_tone": self.submit_tone,
            "cancel_url": self.cancel_url,
            "account_user": self.account_user,
            "customer": self.customer,
            "context_items": self.context_items,
        }


# -----------------------------------------------------------------------------
# Public builders


def build_account_detail_context(
    *,
    account: AccountListRow,
    activity_rows: tuple[AccountActivityRow, ...],
    cancel_url: str,
    role_spec: RoleSpec,
    edit_url: str = "",
) -> AccountDetailContext:
    return AccountDetailContext(
        account=account,
        activity_rows=activity_rows,
        detail_card=DetailCard(
            header=_build_account_header(
                account=account,
                eyebrow="Account",
                title=account.email,
            ),
            panels=_build_account_detail_panels(
                account=account,
                activity_count=len(activity_rows),
            ),
            content_card_class=_account_detail_card_class(account),
            secondary_actions=_build_manager_account_secondary_actions(
                account=account,
                edit_url=edit_url,
                role_spec=role_spec,
            ),
        ),
        title=account.email,
        description="",
        cancel_url=cancel_url,
    )


def build_self_account_detail_context(
    *,
    account: AccountListRow,
    activity_rows: tuple[AccountActivityRow, ...],
    cancel_url: str,
) -> AccountDetailContext:
    return AccountDetailContext(
        account=account,
        activity_rows=activity_rows,
        detail_card=DetailCard(
            header=_build_account_header(
                account=account,
                eyebrow="My account",
                title=account.email,
            ),
            panels=_build_account_detail_panels(
                account=account,
                activity_count=len(activity_rows),
            ),
            content_card_class=_account_detail_card_class(account),
            secondary_actions=_build_self_account_secondary_actions(),
        ),
        title="My account",
        description="",
        cancel_url=cancel_url,
    )


def build_customer_account_status_context(
    *,
    membership: Any,
    is_active: bool,
) -> CustomerAccountStatusContext:
    account_user = membership.user
    action_label = _customer_account_status_action_label(
        is_active=is_active,
    )

    return CustomerAccountStatusContext(
        title=f"{action_label} for {account_user.email}",
        description=_customer_account_status_description(
            is_active=is_active,
        ),
        submit_label=action_label,
        submit_tone=_customer_account_status_submit_tone(
            is_active=is_active,
        ),
        cancel_url=reverse(
            "accounts:detail",
            kwargs={"user_id": account_user.pk},
        ),
        account_user=account_user,
        customer=membership.customer,
        context_items=(
            {
                "label": "Login email",
                "value": account_user.email,
            },
            {
                "label": "Linked customer",
                "value": membership.customer.name,
            },
            {
                "label": "Current status",
                "value": _active_status_label(
                    is_active=account_user.is_active,
                ),
            },
        ),
    )


def customer_account_status_success_message(
    *,
    email: str,
    is_active: bool,
) -> str:
    if is_active:
        return f"Customer account {email} activated."

    return f"Customer account {email} deactivated."


# -----------------------------------------------------------------------------
# Detail card builders


def _build_account_header(
    *,
    account: AccountListRow,
    eyebrow: str,
    title: str,
) -> DetailHeader:
    return DetailHeader(
        eyebrow=eyebrow,
        title=title,
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


def _build_manager_account_secondary_actions(
    *,
    account: AccountListRow,
    edit_url: str,
    role_spec: RoleSpec,
) -> tuple[DetailAction, ...]:
    actions: list[DetailAction] = []

    if edit_url:
        actions.append(
            build_secondary_get_action(
                label="Edit account",
                href=edit_url,
            )
        )

    if can_manage_customer_account_status(
        target_account_role=account.account_role,
        role_spec=role_spec,
    ):
        actions.append(_build_customer_account_status_action(account))

    actions.append(
        build_secondary_get_action(
            label="Back to accounts",
            href=_accounts_url_for_account(account),
        )
    )

    return tuple(actions)


def _build_customer_account_status_action(
    account: AccountListRow,
) -> DetailAction:
    if account.is_active:
        return build_danger_get_action(
            label="Deactivate login",
            href=reverse(
                "accounts:deactivate_customer_account",
                kwargs={"user_id": account.user_id},
            ),
        )

    return build_secondary_get_action(
        label="Activate login",
        href=reverse(
            "accounts:activate_customer_account",
            kwargs={"user_id": account.user_id},
        ),
    )


def _build_self_account_secondary_actions() -> tuple[DetailAction, ...]:
    return (
        build_secondary_get_action(
            label="Change password",
            href=reverse("password_change"),
        ),
        build_secondary_get_action(
            label="Back to start",
            href=reverse("accounts:after_login"),
        ),
    )


# -----------------------------------------------------------------------------
# Presentation helpers


def _account_detail_card_class(account: AccountListRow) -> str:
    if account.is_active:
        return ""

    return "content-card--muted"


def _account_status_class(account: AccountListRow) -> str:
    if account.is_active:
        return "status-text status-text--success"

    return "status-text status-text--neutral"


def _activity_summary(activity_count: int) -> str:
    if activity_count == 1:
        return "1 event"

    return f"{activity_count} events"


def _customer_account_status_action_label(
    *,
    is_active: bool,
) -> str:
    if is_active:
        return "Activate login"

    return "Deactivate login"


def _customer_account_status_submit_tone(
    *,
    is_active: bool,
) -> str:
    if is_active:
        return "success"

    return "danger"


def _customer_account_status_description(
    *,
    is_active: bool,
) -> str:
    if is_active:
        return "Allow this customer account to log in again."

    return (
        "Prevent this customer account from logging in. "
        "Existing customer data and historical records are kept."
    )


def _active_status_label(
    *,
    is_active: bool,
) -> str:
    if is_active:
        return "Active"

    return "Inactive"


def account_datetime_label(value: datetime | None) -> str:
    if value is None:
        return "Never"

    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


# -----------------------------------------------------------------------------
# Navigation helpers


def _accounts_url_for_account(account: AccountListRow) -> str:
    if account.account_role == AccountRole.CUSTOMER:
        return _accounts_customer_url()

    if account.account_role == AccountRole.UNKNOWN:
        return _accounts_unlinked_url()

    return _accounts_internal_url()


def _accounts_internal_url() -> str:
    return f"{reverse('accounts:index')}?view=internal#accounts-list"


def _accounts_customer_url() -> str:
    return f"{reverse('accounts:index')}?view=customer#accounts-list"


def _accounts_unlinked_url() -> str:
    return f"{reverse('accounts:index')}?view=unlinked#accounts-list"
