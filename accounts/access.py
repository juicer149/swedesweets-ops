from __future__ import annotations

from accounts.roles import Capability


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
