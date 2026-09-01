from accounts.roles import (
    AccountRole,
    Capability,
    RoleSpec,
)
from config.login_routing import get_after_login_redirect_name


def test_business_customer_redirects_to_business_portal():
    redirect_name = get_after_login_redirect_name(
        account_role=AccountRole.BUSINESS_CUSTOMER,
        role_spec=RoleSpec(
            capabilities=frozenset(
                {
                    Capability.VIEW_BUSINESS_PORTAL,
                }
            )
        ),
    )

    assert redirect_name == "business_portal:index"


def test_staff_redirects_to_ops():
    redirect_name = get_after_login_redirect_name(
        account_role=AccountRole.FULL_STAFF,
        role_spec=RoleSpec(
            capabilities=frozenset(
                {
                    Capability.VIEW_STAFF_OPS,
                }
            )
        ),
    )

    assert redirect_name == "index"


def test_unknown_account_falls_back_to_own_account():
    redirect_name = get_after_login_redirect_name(
        account_role=AccountRole.UNKNOWN,
        role_spec=RoleSpec(
            capabilities=frozenset(),
        ),
    )

    assert redirect_name == "accounts:me"
