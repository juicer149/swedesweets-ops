from __future__ import annotations

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from accounts.errors import InvalidAccountIdentity
from accounts.permissions import resolve_account_role
from accounts.policies import (
    AUTH_EXEMPT_VIEWS,
    EXEMPT_PATH_PREFIXES,
    VIEW_CAPABILITIES,
)
from accounts.roles import get_role_spec


class AccountContextMiddleware:
    """Attach business account role context to each request.

    Django authentication answers:

        Who is logged in?

    The accounts app answers:

        What business identity does that user represent?

    This middleware makes the resolved account role and role spec available on
    the request so views, navigation and access policy can make consistent
    decisions.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request.account_role = resolve_account_role(request.user)
        except InvalidAccountIdentity as error:
            raise PermissionDenied("Invalid account identity.") from error

        request.role_spec = get_role_spec(request.account_role)

        return self.get_response(request)


class ViewCapabilityMiddleware:
    """Deny access unless the resolved view has an explicit access policy.

    Access policy is declared centrally in accounts.policies.

    Rules:

        - exempt paths are ignored
        - auth-exempt views are allowed through this middleware
        - protected views require a capability
        - views missing from policy are denied
        - missing or false capabilities are denied
        - anonymous users are redirected to login for protected views

    Auth-exempt does not always mean public. Some Django auth views, such as
    password_change, enforce their own login requirement.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith(EXEMPT_PATH_PREFIXES):
            return None

        resolver_match = getattr(request, "resolver_match", None)

        if resolver_match is None:
            raise PermissionDenied(
                "Could not resolve access policy for this request."
            )

        view_name = resolver_match.view_name

        if view_name in AUTH_EXEMPT_VIEWS:
            return None

        required_capability = VIEW_CAPABILITIES.get(view_name)

        if required_capability is None:
            raise PermissionDenied(
                "This view does not declare an access policy."
            )

        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                login_url=settings.LOGIN_URL,
            )

        role_spec = getattr(request, "role_spec", None)

        if role_spec is None:
            raise PermissionDenied("Account role context is missing.")

        if not role_spec.allows(required_capability):
            raise PermissionDenied(
                "You do not have permission to access this page."
            )

        return None
