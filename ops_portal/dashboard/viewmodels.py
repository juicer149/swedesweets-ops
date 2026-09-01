from __future__ import annotations

from dataclasses import dataclass

# -----------------------------------------------------------------------------
# Dashboard actions


@dataclass(frozen=True, slots=True)
class DashboardAction:
    label: str
    href: str
    css_class: str
    aria_label: str = ""
    icon: str = ""


# -----------------------------------------------------------------------------
# Dashboard queues


@dataclass(frozen=True, slots=True)
class DashboardQueueTab:
    key: str
    label: str
    count: int
    href: str
    tone: str
    icon: str
    is_active: bool = False


@dataclass(frozen=True, slots=True)
class DashboardQueueItem:
    title: str
    meta: str
    href: str
    action_label: str
    tone: str = "neutral"
    icon: str = ""


@dataclass(frozen=True, slots=True)
class DashboardQueuePanel:
    key: str
    title: str
    description: str
    items: tuple[DashboardQueueItem, ...]
    view_all_href: str
    view_all_label: str
