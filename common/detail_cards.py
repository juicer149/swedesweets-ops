from __future__ import annotations

from dataclasses import dataclass


ACTION_METHOD_GET = "get"
ACTION_METHOD_POST = "post"

ACTION_TONE_SECONDARY = "secondary"
ACTION_TONE_PACK = "pack"
ACTION_TONE_DELIVER = "deliver"
ACTION_TONE_DANGER = "danger"


@dataclass(frozen=True)
class DetailHeader:
    eyebrow: str
    title: str
    status_label: str = ""
    status_class: str = ""
    status_icon: str = ""


@dataclass(frozen=True)
class DetailPanel:
    key: str
    label: str
    summary: str
    body_template: str
    icon: str = ""
    is_active: bool = False


@dataclass(frozen=True)
class DetailAction:
    label: str
    href: str = ""
    icon: str = ""
    method: str = ACTION_METHOD_GET
    tone: str = ACTION_TONE_SECONDARY
    client_behavior: str = ""
    is_disabled: bool = False


@dataclass(frozen=True)
class DetailCard:
    header: DetailHeader
    panels: tuple[DetailPanel, ...]
    content_card_class: str = ""
    primary_action: DetailAction | None = None
    secondary_action: DetailAction | None = None
    secondary_actions: tuple[DetailAction, ...] = ()
