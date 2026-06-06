from __future__ import annotations

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

from accounts.policies import PUBLIC_VIEWS, VIEW_CAPABILITIES
from accounts.roles import Capability


EXEMPT_VIEW_NAME_PREFIXES = (
    "admin:",
)


def _iter_named_view_names(
    patterns,
    *,
    namespace: str = "",
):
    for pattern in patterns:
        if isinstance(pattern, URLPattern):
            if pattern.name is None:
                continue

            if namespace:
                yield f"{namespace}:{pattern.name}"
            else:
                yield pattern.name

            continue

        if isinstance(pattern, URLResolver):
            child_namespace = namespace

            if pattern.namespace:
                child_namespace = (
                    f"{namespace}:{pattern.namespace}"
                    if namespace
                    else pattern.namespace
                )

            yield from _iter_named_view_names(
                pattern.url_patterns,
                namespace=child_namespace,
            )


def _project_view_names() -> set[str]:
    view_names = set(_iter_named_view_names(get_resolver().url_patterns))

    return {
        view_name
        for view_name in view_names
        if not view_name.startswith(EXEMPT_VIEW_NAME_PREFIXES)
    }


def test_all_policy_capabilities_are_declared_capabilities():
    policy_capabilities = set(VIEW_CAPABILITIES.values())

    unknown_capabilities = policy_capabilities - set(Capability)

    assert unknown_capabilities == set()


@pytest.mark.django_db
def test_all_policy_view_names_exist_in_urlconf():
    view_names = _project_view_names()
    policy_view_names = set(VIEW_CAPABILITIES) | set(PUBLIC_VIEWS)

    missing_view_names = policy_view_names - view_names

    assert missing_view_names == set()


@pytest.mark.django_db
def test_all_project_views_have_access_policy():
    view_names = _project_view_names()
    policy_view_names = set(VIEW_CAPABILITIES) | set(PUBLIC_VIEWS)

    views_without_policy = view_names - policy_view_names

    assert views_without_policy == set()
