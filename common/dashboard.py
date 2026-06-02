from __future__ import annotations

from dataclasses import dataclass

from common.ui import UiTone


@dataclass(frozen=True)
class DashboardAction:
    label: str
    href: str
    css_class: str
    aria_label: str = ""
    icon: str = ""


@dataclass(frozen=True)
class DashboardMetric:
    value: int
    label: str
    href: str = ""
    tone: str = ""


@dataclass(frozen=True)
class DashboardSummaryCard:
    title: str
    count: int
    description: str
    href: str
    action_label: str
    tone: UiTone
    empty_text: str
    icon: str


@dataclass(frozen=True)
class DashboardQueueTab:
    key: str
    label: str
    count: int
    href: str
    tone: str
    icon: str
    is_active: bool = False


@dataclass(frozen=True)
class DashboardQueueItem:
    title: str
    meta: str
    href: str
    action_label: str
    tone: str = "neutral"
    icon: str = ""


@dataclass(frozen=True)
class DashboardQueuePanel:
    key: str
    title: str
    description: str
    items: tuple[DashboardQueueItem, ...]
    view_all_href: str
    view_all_label: str
