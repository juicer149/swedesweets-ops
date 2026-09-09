from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from accounts.models import StaffAccount
from ops_portal.accounts.list_viewmodels import (
    ACCOUNT_VIEW_CUSTOMER,
    ACCOUNT_VIEW_INTERNAL,
)
from ops_portal.accounts.forms import (
    CustomerAccountCreateForm,
    InternalAccountCreateForm,
    InternalAccountEditForm,
)


@dataclass(frozen=True, slots=True)
class FormContextItem:
    label: str
    value: Any


@dataclass(frozen=True, slots=True)
class AccountFormContext:
    title: str
    description: str
    submit_label: str
    cancel_url: str
    form: (
        CustomerAccountCreateForm
        | InternalAccountCreateForm
        | InternalAccountEditForm
    )
    staff_account: StaffAccount | None = None
    account_context_items: list[FormContextItem] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
            "form": self.form,
            "staff_account": self.staff_account,
            "account_context_items": (
                self.account_context_items or []
            ),
        }


def build_create_customer_account_form_context(
    *,
    form: CustomerAccountCreateForm,
) -> AccountFormContext:
    return AccountFormContext(
        form=form,
        title="Create customer account",
        description=(
            "Create a customer portal login linked to an existing customer."
        ),
        submit_label="Create account",
        cancel_url=_accounts_customer_url(),
    )


def build_create_internal_account_form_context(
    *,
    form: InternalAccountCreateForm,
) -> AccountFormContext:
    return AccountFormContext(
        form=form,
        title="Create internal account",
        description=(
            "Create a login account for full or restricted operations staff."
        ),
        submit_label="Create account",
        cancel_url=_accounts_internal_url(),
    )


def build_edit_internal_account_form_context(
    *,
    form: InternalAccountEditForm,
    staff_account: StaffAccount,
) -> AccountFormContext:
    return AccountFormContext(
        form=form,
        staff_account=staff_account,
        account_context_items=build_account_context_items(
            staff_account
        ),
        title="Edit internal account",
        description=(
            "Update account email, staff access level and login status."
        ),
        submit_label="Save account",
        cancel_url=reverse(
            "ops_accounts:detail",
            kwargs={
                "user_id": staff_account.user_id,
            },
        ),
    )


def build_account_context_items(
    staff_account: StaffAccount,
) -> list[FormContextItem]:
    return [
        FormContextItem(
            label="Access level",
            value=staff_account.get_access_level_display(),
        ),
        FormContextItem(
            label="Status",
            value=(
                "Active"
                if staff_account.user.is_active
                else "Inactive"
            ),
        ),
    ]


def _accounts_customer_url() -> str:
    return (
        f"{reverse('ops_accounts:index')}"
        f"?view={ACCOUNT_VIEW_CUSTOMER}#accounts-list"
    )


def _accounts_internal_url() -> str:
    return (
        f"{reverse('ops_accounts:index')}"
        f"?view={ACCOUNT_VIEW_INTERNAL}#accounts-list"
    )
