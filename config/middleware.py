from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from config.policies import AUTH_EXEMPT_VIEWS


class LoginRequiredMiddleware:
    """Require authentication for protected application views.

    Global route exemptions are composed in config.policies.

    Django authentication views such as login and password reset must be
    reachable before login. Auth-exempt does not necessarily mean public:
    views such as password_change may still enforce authentication themselves.

    Inactive authenticated sessions are logged out and redirected to the
    inactive-account information page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not request.user.is_active:
                logout(request)
                return redirect("accounts:inactive")

            return self.get_response(request)

        if self._is_exempt_path(request.path_info):
            return self.get_response(request)

        if self._is_auth_exempt_view(request.path_info):
            return self.get_response(request)

        return redirect_to_login(
            request.get_full_path(),
            settings.LOGIN_URL,
            "next",
        )

    @staticmethod
    def _is_exempt_path(path: str) -> bool:
        exempt_prefixes = (
            LoginRequiredMiddleware._path_from_url(settings.LOGIN_URL),
            "/accounts/login/",
            "/accounts/logout/",
            "/admin/",
            settings.STATIC_URL,
            getattr(settings, "MEDIA_URL", ""),
            "/favicon.ico",
        )

        return any(
            prefix and path.startswith(prefix)
            for prefix in exempt_prefixes
        )

    @staticmethod
    def _is_auth_exempt_view(path: str) -> bool:
        try:
            resolver_match = resolve(path)
        except Resolver404:
            return False

        return resolver_match.view_name in AUTH_EXEMPT_VIEWS

    @staticmethod
    def _path_from_url(url: str) -> str:
        parsed_url = urlparse(url)

        return parsed_url.path or url
