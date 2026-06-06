from __future__ import annotations

from accounts.roles import Capability


PUBLIC_VIEWS = frozenset(
    {
        "login",
        "logout",
        "password_change",
        "password_change_done",
        "password_reset",
        "password_reset_done",
        "password_reset_confirm",
        "password_reset_complete",
    }
)


CAPABILITIES = frozenset(
    {
        Capability.MANAGE_ACCOUNTS,
    }
)


VIEW_CAPABILITIES = {
    "accounts:index": Capability.MANAGE_ACCOUNTS,
    "accounts:create_internal": Capability.MANAGE_ACCOUNTS,
}
