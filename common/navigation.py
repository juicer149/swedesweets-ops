from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import Capability, RoleSpec


@dataclass(frozen=True, slots=True)
class NavItem:
    """A single link in a primary navigation."""

    label: str
    route_name: str
    namespace: str
    icon: str
    capability: Capability
    active_url_names: tuple[str, ...] = ()

    @property
    def href(self) -> str:
        return reverse(self.route_name)


def filter_nav_items(
    *,
    candidates: tuple[NavItem, ...],
    role_spec: RoleSpec,
) -> tuple[NavItem, ...]:
    return tuple(
        item
        for item in candidates
        if role_spec.allows(item.capability)
    )
