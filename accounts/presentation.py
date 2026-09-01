from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse
from django.utils.translation import gettext as _

from accounts.roles import AccountRole, get_role_label, get_staff_access_level_label
from accounts.selectors import (
    AccountIdentity,
    AccountIdentityKind,
    AccountRecord,
)


@dataclass(frozen=True, slots=True)
class AccountPresentation:
    user_id: int
    email: str
    account_role: AccountRole
    role_label: str
    linked_identity: str
    linked_identity_href: str
    status_label: str
    is_active: bool
    last_login: datetime | None
    date_joined: datetime


def build_account_presentation(
    account: AccountRecord,
    *,
    link_customer: bool = True,
) -> AccountPresentation:
    return AccountPresentation(
        user_id=account.user_id,
        email=account.email,
        account_role=account.account_role,
        role_label=_role_label(account),
        linked_identity=_linked_identity_label(account.identity),
        linked_identity_href=_linked_identity_href(
            identity=account.identity,
            link_customer=link_customer,
        ),
        status_label=_status_label(
            is_active=account.is_active,
        ),
        is_active=account.is_active,
        last_login=account.last_login,
        date_joined=account.date_joined,
    )


def _role_label(account: AccountRecord) -> str:
    match account.identity.kind:
        case AccountIdentityKind.INVALID_STAFF_AND_CUSTOMER:
            return _("Invalid identity")
        case AccountIdentityKind.INVALID_STAFF:
            return _("Invalid staff account")
        case AccountIdentityKind.INVALID_CUSTOMER:
            return _("Invalid customer account")
        case _:
            return get_role_label(account.account_role)


def _linked_identity_label(identity: AccountIdentity) -> str:
    match identity.kind:
        case AccountIdentityKind.OWNER:
            return _("Superuser")

        case AccountIdentityKind.STAFF:
            return _("Internal staff · %(access_level)s") % {
                "access_level": get_staff_access_level_label(
                    identity.staff_access_level
                ),
            }

        case AccountIdentityKind.BUSINESS_CUSTOMER:
            return identity.customer_name

        case AccountIdentityKind.INVALID_STAFF_AND_CUSTOMER:
            return _("Staff and customer · %(customer)s") % {
                "customer": identity.customer_name,
            }

        case AccountIdentityKind.INVALID_STAFF:
            return _("Internal staff")

        case AccountIdentityKind.INVALID_CUSTOMER:
            return identity.customer_name

        case AccountIdentityKind.UNLINKED:
            return "—"

    return "—"


def _linked_identity_href(
    *,
    identity: AccountIdentity,
    link_customer: bool,
) -> str:
    if not link_customer or identity.customer_id is None:
        return ""

    return reverse(
        "customers:detail",
        kwargs={
            "customer_pk": identity.customer_id,
        },
    )


def _status_label(*, is_active: bool) -> str:
    if is_active:
        return _("Active")

    return _("Inactive")
