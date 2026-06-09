from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.policies import AUTH_EXEMPT_VIEWS, VIEW_CAPABILITIES
from accounts.roles import (
    AccountRole,
    CUSTOMER_SPEC,
    FULL_STAFF_SPEC,
    OWNER_SPEC,
    RESTRICTED_STAFF_SPEC,
    UNKNOWN_SPEC,
)
from accounts.tests.factories import (
    customer_membership_factory,
    full_staff_user_factory,
    restricted_staff_user_factory,
    superuser_factory,
    user_factory,
)
from customers.tests.factories import customer_factory


MISSING_OBJECT_ID = 999999

VIEW_KWARGS = {
    "accounts:detail": {"user_id": MISSING_OBJECT_ID},
    "accounts:edit_internal": {"user_id": MISSING_OBJECT_ID},
    "orders:detail": {"order_id": MISSING_OBJECT_ID},
    "orders:edit": {"order_id": MISSING_OBJECT_ID},
    "orders:cancel": {"order_id": MISSING_OBJECT_ID},
    "orders:pack": {"order_id": MISSING_OBJECT_ID},
    "orders:deliver": {"order_id": MISSING_OBJECT_ID},
    "inventory:detail": {"batch_pk": MISSING_OBJECT_ID},
    "inventory:edit": {"batch_pk": MISSING_OBJECT_ID},
    "inventory:close": {"batch_pk": MISSING_OBJECT_ID},
    "products:detail": {"product_pk": MISSING_OBJECT_ID},
    "products:edit": {"product_pk": MISSING_OBJECT_ID},
    "customers:detail": {"customer_pk": MISSING_OBJECT_ID},
    "customers:edit": {"customer_pk": MISSING_OBJECT_ID},
}

ALLOWED_GET_STATUS_CODES = {
    200,
    404,
}

DENIED_STATUS_CODE = 403
LOGIN_REDIRECT_STATUS_CODE = 302


def _url_for_view_name(view_name: str) -> str:
    return reverse(
        view_name,
        kwargs=VIEW_KWARGS.get(view_name, {}),
    )


def _expected_access_by_view(role_spec) -> dict[str, bool]:
    return {
        view_name: role_spec.allows(capability)
        for view_name, capability in VIEW_CAPABILITIES.items()
    }


def _assert_redirects_to_login(response) -> None:
    assert response.status_code == LOGIN_REDIRECT_STATUS_CODE
    assert response["Location"].startswith(f"{reverse('login')}?next=")


@pytest.mark.django_db
def test_anonymous_user_is_redirected_for_all_protected_views(client):
    for view_name in VIEW_CAPABILITIES:
        response = client.get(_url_for_view_name(view_name))

        _assert_redirects_to_login(response)


@pytest.mark.django_db
def test_anonymous_post_is_redirected_for_all_protected_views(client):
    for view_name in VIEW_CAPABILITIES:
        response = client.post(_url_for_view_name(view_name))

        _assert_redirects_to_login(response)


@pytest.mark.django_db
def test_owner_access_matches_declared_capabilities(client):
    user = superuser_factory()

    client.force_login(user)

    expected_access = _expected_access_by_view(OWNER_SPEC)

    for view_name, should_allow in expected_access.items():
        response = client.get(_url_for_view_name(view_name))

        if should_allow:
            assert response.status_code in ALLOWED_GET_STATUS_CODES
        else:
            assert response.status_code == DENIED_STATUS_CODE


@pytest.mark.django_db
def test_full_staff_access_matches_declared_capabilities(client):
    user = full_staff_user_factory()

    client.force_login(user)

    expected_access = _expected_access_by_view(FULL_STAFF_SPEC)

    for view_name, should_allow in expected_access.items():
        response = client.get(_url_for_view_name(view_name))

        if should_allow:
            assert response.status_code in ALLOWED_GET_STATUS_CODES
        else:
            assert response.status_code == DENIED_STATUS_CODE


@pytest.mark.django_db
def test_restricted_staff_access_matches_declared_capabilities(client):
    user = restricted_staff_user_factory()

    client.force_login(user)

    expected_access = _expected_access_by_view(RESTRICTED_STAFF_SPEC)

    for view_name, should_allow in expected_access.items():
        response = client.get(_url_for_view_name(view_name))

        if should_allow:
            assert response.status_code in ALLOWED_GET_STATUS_CODES
        else:
            assert response.status_code == DENIED_STATUS_CODE


@pytest.mark.django_db
def test_customer_user_access_matches_declared_capabilities(client):
    user = user_factory(username="customer@example.com")
    customer = customer_factory()

    customer_membership_factory(
        user=user,
        customer=customer,
    )

    client.force_login(user)

    expected_access = _expected_access_by_view(CUSTOMER_SPEC)

    for view_name, should_allow in expected_access.items():
        response = client.get(_url_for_view_name(view_name))

        if should_allow:
            assert response.status_code in ALLOWED_GET_STATUS_CODES
        else:
            assert response.status_code == DENIED_STATUS_CODE


@pytest.mark.django_db
def test_unknown_user_access_matches_declared_capabilities(client):
    user = user_factory(username="unknown@example.com")

    client.force_login(user)

    expected_access = _expected_access_by_view(UNKNOWN_SPEC)

    for view_name, should_allow in expected_access.items():
        response = client.get(_url_for_view_name(view_name))

        if should_allow:
            assert response.status_code in ALLOWED_GET_STATUS_CODES
        else:
            assert response.status_code == DENIED_STATUS_CODE


def test_every_policy_view_can_be_reversed():
    for view_name in VIEW_CAPABILITIES:
        assert _url_for_view_name(view_name)


def test_auth_exempt_views_are_not_also_protected():
    protected_view_names = set(VIEW_CAPABILITIES)
    auth_exempt_view_names = set(AUTH_EXEMPT_VIEWS)

    assert protected_view_names.isdisjoint(auth_exempt_view_names)


def test_role_specs_cover_expected_policy_shape():
    role_specs = {
        AccountRole.OWNER: OWNER_SPEC,
        AccountRole.FULL_STAFF: FULL_STAFF_SPEC,
        AccountRole.RESTRICTED_STAFF: RESTRICTED_STAFF_SPEC,
        AccountRole.CUSTOMER: CUSTOMER_SPEC,
        AccountRole.UNKNOWN: UNKNOWN_SPEC,
    }

    for role, role_spec in role_specs.items():
        expected_access = _expected_access_by_view(role_spec)

        assert set(expected_access) == set(VIEW_CAPABILITIES)
        assert role in AccountRole
