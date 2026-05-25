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
