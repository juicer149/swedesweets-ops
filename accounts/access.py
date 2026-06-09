from __future__ import annotations

from accounts.roles import Capability


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
    }
)


VIEW_CAPABILITIES = {
    "accounts:index": Capability.MANAGE_ACCOUNTS,
    "accounts:detail": Capability.MANAGE_ACCOUNTS,
    "accounts:create_internal": Capability.MANAGE_ACCOUNTS,
    "accounts:edit_internal": Capability.MANAGE_ACCOUNTS,
    "accounts:me": Capability.VIEW_OWN_ACCOUNT,
}
