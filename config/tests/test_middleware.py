from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import reverse

from config.middleware import LoginRequiredMiddleware


def _response(_request):
    return HttpResponse("ok")


def _request(
    *,
    path: str,
    user,
):
    request = RequestFactory().get(path)
    request.user = user
    return request


def test_authenticated_active_user_is_allowed_through():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path="/orders/",
        user=SimpleNamespace(
            is_authenticated=True,
            is_active=True,
        ),
    )

    response = middleware(request)

    assert response.status_code == 200
    assert response.content == b"ok"


def test_anonymous_user_is_redirected_to_login_for_protected_path():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path="/orders/",
        user=AnonymousUser(),
    )

    response = middleware(request)

    assert response.status_code == 302
    assert response["Location"].startswith(
        f"{reverse('login')}?next="
    )


def test_login_path_is_available_to_anonymous_user():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path=reverse("login"),
        user=AnonymousUser(),
    )

    response = middleware(request)

    assert response.status_code == 200


def test_admin_path_is_available_to_anonymous_user():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path="/admin/",
        user=AnonymousUser(),
    )

    response = middleware(request)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/static/app.css",
        "/media/example.jpg",
        "/favicon.ico",
    ],
)
def test_asset_paths_are_available_to_anonymous_user(path):
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path=path,
        user=AnonymousUser(),
    )

    response = middleware(request)

    assert response.status_code == 200


@override_settings(LOGIN_URL="/sign-in/")
def test_configured_login_path_is_available_to_anonymous_user():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path="/sign-in/",
        user=AnonymousUser(),
    )

    response = middleware(request)

    assert response.status_code == 200


def test_auth_exempt_view_is_available_to_anonymous_user():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path=reverse("password_reset"),
        user=AnonymousUser(),
    )

    response = middleware(request)

    assert response.status_code == 200


def test_inactive_authenticated_user_is_logged_out_and_redirected():
    middleware = LoginRequiredMiddleware(_response)
    request = _request(
        path="/orders/",
        user=SimpleNamespace(
            is_authenticated=True,
            is_active=False,
        ),
    )

    with patch("config.middleware.logout") as logout:
        response = middleware(request)

    logout.assert_called_once_with(request)
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:inactive")
