"""
Navigation helpers for the shared account experience.
"""

from __future__ import annotations

from django.urls import reverse

from accounts.roles import AccountRole, RoleSpec


def build_home_href(
    *,
    account_role: AccountRole | None,
    role_spec: RoleSpec | None,
) -> str:
    if account_role is None or role_spec is None:
        return reverse("login")

    return reverse("accounts:after_login")
