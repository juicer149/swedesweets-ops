from __future__ import annotations

from accounts.roles import AccountRole, Capability, RoleSpec


CAPABILITIES = frozenset(
    {
        Capability.MANAGE_ACCOUNTS,
    }
)


VIEW_CAPABILITIES = {
    "ops_accounts:index": Capability.MANAGE_ACCOUNTS,
    "ops_accounts:create_internal": Capability.MANAGE_ACCOUNTS,
    "ops_accounts:edit_internal": Capability.MANAGE_ACCOUNTS,
    "ops_accounts:create_customer_account": Capability.MANAGE_ACCOUNTS,
    "ops_accounts:activate_customer_account": Capability.MANAGE_ACCOUNTS,
    "ops_accounts:deactivate_customer_account": Capability.MANAGE_ACCOUNTS,
    "ops_accounts:detail": Capability.MANAGE_ACCOUNTS,
}


def can_manage_customer_account_status(
    *,
    target_account_role: AccountRole,
    role_spec: RoleSpec,
) -> bool:
    return (
        target_account_role == AccountRole.BUSINESS_CUSTOMER
        and role_spec.allows(Capability.MANAGE_ACCOUNTS)
    )
