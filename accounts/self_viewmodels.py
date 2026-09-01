from __future__ import annotations

from dataclasses import dataclass, replace

from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from accounts.activity_viewmodels import (
    AccountActivityPresentation,
    build_account_activity_presentations,
)
from accounts.presentation import (
    AccountPresentation,
    build_account_presentation,
)
from accounts.roles import RoleSpec
from accounts.self_activity_links import self_activity_target_href
from accounts.selectors import (
    AccountActivity,
    AccountRecord,
)
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_secondary_get_action,
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


def build_self_account_detail_context(
    *,
    account: AccountRecord,
    activity_rows: tuple[AccountActivity, ...],
    cancel_url: str,
    role_spec: RoleSpec,
) -> AccountDetailContext:
    presented_account = build_account_presentation(account)
    presented_activity_rows = _build_self_activity_presentations(
        activities=activity_rows,
        role_spec=role_spec,
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
            secondary_actions=_build_self_account_secondary_actions(),
        ),
        title=_("My account"),
        description="",
        cancel_url=cancel_url,
    )


def _build_self_activity_presentations(
    *,
    activities: tuple[AccountActivity, ...],
    role_spec: RoleSpec,
) -> tuple[AccountActivityPresentation, ...]:
    presentations = build_account_activity_presentations(activities)

    return tuple(
        replace(
            presentation,
            target_href=self_activity_target_href(
                activity=activity,
                role_spec=role_spec,
            ),
        )
        for activity, presentation in zip(
            activities,
            presentations,
            strict=True,
        )
    )


def _build_account_header(
    *,
    account: AccountPresentation,
) -> DetailHeader:
    return DetailHeader(
        eyebrow=_("My account"),
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
            body_template="accounts/includes/detail_panel_activity.html",
            icon="inventory",
        ),
    )


def _build_self_account_secondary_actions() -> tuple[DetailAction, ...]:
    return (
        build_secondary_get_action(
            label=_("Change password"),
            href=reverse("password_change"),
        ),
        build_secondary_get_action(
            label=_("Back to start"),
            href=reverse("accounts:after_login"),
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


def _activity_summary(activity_count: int) -> str:
    return ngettext(
        "%(count)d event",
        "%(count)d events",
        activity_count,
    ) % {
        "count": activity_count,
    }
