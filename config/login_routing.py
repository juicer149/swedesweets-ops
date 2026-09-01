from __future__ import annotations

from accounts.roles import (
    AccountRole,
    Capability,
    RoleSpec,
)


def get_after_login_redirect_name(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> str:
    if account_role == AccountRole.BUSINESS_CUSTOMER:
        return "business_portal:index"

    if role_spec.allows(Capability.VIEW_STAFF_OPS):
        return "index"

    return "accounts:me"
