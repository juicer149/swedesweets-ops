from __future__ import annotations

from accounts.roles import AccountRole, Capability, RoleSpec


AUTH_EXEMPT_VIEWS = frozenset(
    {
        "login",
        "logout",
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
        Capability.MANAGE_ACCOUNTS,
        Capability.VIEW_OWN_ACCOUNT,
        Capability.EDIT_OWN_ACCOUNT,
    }
)


VIEW_CAPABILITIES = {
    "accounts:after_login": Capability.VIEW_OWN_ACCOUNT,
    "accounts:index": Capability.MANAGE_ACCOUNTS,
    "accounts:me": Capability.VIEW_OWN_ACCOUNT,

    "accounts:create_internal": Capability.MANAGE_ACCOUNTS,
    "accounts:edit_internal": Capability.MANAGE_ACCOUNTS,

    "accounts:create_customer_account": Capability.MANAGE_ACCOUNTS,
    "accounts:activate_customer_account": Capability.MANAGE_ACCOUNTS,
    "accounts:deactivate_customer_account": Capability.MANAGE_ACCOUNTS,

    "accounts:detail": Capability.MANAGE_ACCOUNTS,
}


def get_after_login_redirect_name(
    *,
    account_role: AccountRole,
    role_spec: RoleSpec,
) -> str:
    if account_role == AccountRole.CUSTOMER:
        return "customer_portal:index"

    if role_spec.allows(Capability.VIEW_STAFF_OPS):
        return "index"

    return "accounts:me"


def can_manage_customer_account_status(
    *,
    target_account_role: AccountRole,
    role_spec: RoleSpec,
) -> bool:
    return (
        target_account_role == AccountRole.CUSTOMER
        and role_spec.allows(Capability.MANAGE_ACCOUNTS)
    )
