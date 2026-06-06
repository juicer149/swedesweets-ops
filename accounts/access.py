from __future__ import annotations


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
