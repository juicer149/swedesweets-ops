from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from accounts.activity_viewmodels import AccountActivityPresentation
from accounts.presentation import AccountPresentation
from accounts.roles import AccountRole, RoleSpec
from accounts.selectors import (
    AccountActivity,
    AccountRecord,
)
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_danger_get_action,
    build_secondary_get_action,
)
from ops_portal.accounts.access import (
    can_manage_customer_account_status,
)
from ops_portal.accounts.activity_viewmodels import (
    build_ops_account_activity_presentations,
)
from ops_portal.accounts.presentation import (
    build_ops_account_presentation,
)


@dataclass(frozen=True, slots=True)
class AccountDetailContext:
    account: AccountPresentation
    activity_rows: tuple[AccountActivityPresentation, ...]
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


def build_account_detail_context(
    *,
    account: AccountRecord,
    activity_rows: tuple[AccountActivity, ...],
    cancel_url: str,
    role_spec: RoleSpec,
    edit_url: str = "",
) -> AccountDetailContext:
    presented_account = build_ops_account_presentation(account)
    presented_activity_rows = build_ops_account_activity_presentations(
        activity_rows
    )

    return AccountDetailContext(
        account=presented_account,
        activity_rows=presented_activity_rows,
        detail_card=DetailCard(
            header=_build_account_header(
                account=presented_account,
            ),
            panels=_build_account_detail_panels(
                account=presented_account,
                activity_count=len(presented_activity_rows),
            ),
            content_card_class=_account_detail_card_class(
                presented_account
            ),
            secondary_actions=_build_manager_account_secondary_actions(
                account=presented_account,
                edit_url=edit_url,
                role_spec=role_spec,
            ),
        ),
        title=presented_account.email,
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
        title=_("%(action)s for %(email)s")
        % {
            "action": action_label,
            "email": account_user.email,
        },
        description=_customer_account_status_description(
            is_active=is_active,
        ),
        submit_label=action_label,
        submit_tone=_customer_account_status_submit_tone(
            is_active=is_active,
        ),
        cancel_url=reverse(
            "ops_accounts:detail",
            kwargs={
                "user_id": account_user.pk,
            },
        ),
        account_user=account_user,
        customer=membership.customer,
        context_items=(
            {
                "label": _("Login email"),
                "value": account_user.email,
            },
            {
                "label": _("Linked customer"),
                "value": membership.customer.name,
            },
            {
                "label": _("Current status"),
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
        return _("Customer account %(email)s activated.") % {
            "email": email,
        }

    return _("Customer account %(email)s deactivated.") % {
        "email": email,
    }


def _build_account_header(
    *,
    account: AccountPresentation,
) -> DetailHeader:
    return DetailHeader(
        eyebrow=_("Account"),
        title=account.email,
        status_label=account.status_label,
        status_class=_account_status_class(account),
        status_icon="users",
    )


def _build_account_detail_panels(
    *,
    account: AccountPresentation,
    activity_count: int,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="account",
            label=_("Account"),
            summary=account.role_label,
            body_template="accounts/includes/detail_panel_account.html",
            icon="users",
            is_active=True,
        ),
        DetailPanel(
            key="activity",
            label=_("Activity"),
            summary=_activity_summary(activity_count),
            body_template=(
                "ops_portal/accounts/includes/"
                "detail_panel_activity.html"
            ),
            icon="inventory",
        ),
    )


def _build_manager_account_secondary_actions(
    *,
    account: AccountPresentation,
    edit_url: str,
    role_spec: RoleSpec,
) -> tuple[DetailAction, ...]:
    actions: list[DetailAction] = []

    if edit_url:
        actions.append(
            build_secondary_get_action(
                label=_("Edit account"),
                href=edit_url,
            )
        )

    if can_manage_customer_account_status(
        target_account_role=account.account_role,
        role_spec=role_spec,
    ):
        actions.append(
            _build_customer_account_status_action(account)
        )

    actions.append(
        build_secondary_get_action(
            label=_("Back to accounts"),
            href=_accounts_url_for_account(account),
        )
    )

    return tuple(actions)


def _build_customer_account_status_action(
    account: AccountPresentation,
) -> DetailAction:
    if account.is_active:
        return build_danger_get_action(
            label=_("Deactivate login"),
            href=reverse(
                "ops_accounts:deactivate_customer_account",
                kwargs={
                    "user_id": account.user_id,
                },
            ),
        )

    return build_secondary_get_action(
        label=_("Activate login"),
        href=reverse(
            "ops_accounts:activate_customer_account",
            kwargs={
                "user_id": account.user_id,
            },
        ),
    )


def _account_detail_card_class(
    account: AccountPresentation,
) -> str:
    if account.is_active:
        return ""

    return "content-card--muted"


def _account_status_class(
    account: AccountPresentation,
) -> str:
    if account.is_active:
        return "status-text status-text--success"

    return "status-text status-text--neutral"


def _activity_summary(
    activity_count: int,
) -> str:
    return ngettext(
        "%(count)d event",
        "%(count)d events",
        activity_count,
    ) % {
        "count": activity_count,
    }


def _customer_account_status_action_label(
    *,
    is_active: bool,
) -> str:
    if is_active:
        return _("Activate login")

    return _("Deactivate login")


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
        return _("Allow this customer account to log in again.")

    return _(
        "Prevent this customer account from logging in. "
        "Existing customer data and historical records are kept."
    )


def _active_status_label(
    *,
    is_active: bool,
) -> str:
    if is_active:
        return _("Active")

    return _("Inactive")


def _accounts_url_for_account(
    account: AccountPresentation,
) -> str:
    match account.account_role:
        case AccountRole.BUSINESS_CUSTOMER:
            return _accounts_customer_url()

        case AccountRole.UNKNOWN:
            return _accounts_unlinked_url()

        case _:
            return _accounts_internal_url()


def _accounts_internal_url() -> str:
    return (
        f"{reverse('ops_accounts:index')}"
        "?view=internal#accounts-list"
    )


def _accounts_customer_url() -> str:
    return (
        f"{reverse('ops_accounts:index')}"
        "?view=customer#accounts-list"
    )


def _accounts_unlinked_url() -> str:
    return (
        f"{reverse('ops_accounts:index')}"
        "?view=unlinked#accounts-list"
    )
