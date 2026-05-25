from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.views import redirect_to_login


class LoginRequiredMiddleware:
    """Require authentication for all non-exempt application pages.

    Admin keeps its own login flow. Static and media files are ignored.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        if self._is_exempt_path(request.path_info):
            return self.get_response(request)

        return redirect_to_login(
            request.get_full_path(),
            settings.LOGIN_URL,
            "next",
        )

    def _is_exempt_path(self, path: str) -> bool:
        exempt_prefixes = (
            self._path_from_url(settings.LOGIN_URL),
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
    def _path_from_url(url: str) -> str:
        parsed_url = urlparse(url)
        return parsed_url.path or url
