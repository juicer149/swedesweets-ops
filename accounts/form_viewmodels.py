from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.urls import reverse

from accounts.forms import InternalAccountCreateForm, InternalAccountEditForm
from accounts.list_viewmodels import ACCOUNT_VIEW_INTERNAL


@dataclass(frozen=True, slots=True)
class AccountFormContext:
    title: str
    description: str
    submit_label: str
    cancel_url: str
    form: InternalAccountCreateForm | InternalAccountEditForm

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "submit_label": self.submit_label,
            "cancel_url": self.cancel_url,
            "form": self.form,
        }


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
    user_id: int,
) -> AccountFormContext:
    return AccountFormContext(
        form=form,
        title="Edit internal account",
        description=(
            "Update account email, staff access level and login status."
        ),
        submit_label="Save account",
        cancel_url=reverse("accounts:detail", kwargs={"user_id": user_id}),
    )


def _accounts_internal_url() -> str:
    return (
        f"{reverse('accounts:index')}"
        f"?view={ACCOUNT_VIEW_INTERNAL}#accounts-list"
    )
