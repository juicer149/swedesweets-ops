from __future__ import annotations

from accounts.roles import AccountRole, Capability, RoleSpec


AUTH_EXEMPT_VIEWS = frozenset(
    {
        "login",
        "logout",
        "set_language",
        "password_change",
        "password_change_done",
        "password_reset",
        "password_reset_confirm",
        "password_reset_done",
        "password_reset_complete",
        "accounts:inactive",
    }
)


CAPABILITIES = frozenset(
    {
        Capability.VIEW_OWN_ACCOUNT,
        Capability.EDIT_OWN_ACCOUNT,
    }
)


VIEW_CAPABILITIES = {
    "accounts:after_login": Capability.VIEW_OWN_ACCOUNT,
    "accounts:me": Capability.VIEW_OWN_ACCOUNT,
}


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
