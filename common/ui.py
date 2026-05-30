"""
Reusable presentation value objects.

This module contains small immutable objects that describe how already-known
domain data should be presented in templates.

It should not query the database.
It should not own business rules.
It should not know about HTTP requests.

Good use:
    Order status "placed" -> warning tone
    8 units -> "8 units left", low/safe/empty quantity class
    Customer email -> mailto link

Bad use:
    Fetch orders from database
    Decide whether an order may be packed
    Change model state

The purpose is to keep templates dumb and predictable. Selectors/viewmodels build
these objects; templates render them.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class UiTone:
    """Semantic UI tone.

    A tone is presentation language, not domain language.

    Domain:
        placed
        packed
        active
        depleted

    Presentation:
        warning
        info
        success
        danger
        muted
    """

    key: str
    label: str
    card_class: str
    text_class: str


@dataclass(frozen=True)
class UiText:
    """Renderable text atom.

    If href is empty, templates render this as a span.
    If href exists, templates render this as an anchor.

    label is rendered above text.
    subtext is rendered below text.
    """

    text: str
    href: str = ""
    css_class: str = "ui-text"
    target: str = ""
    rel: str = ""
    aria_label: str = ""
    label: str = ""
    label_class: str = "ui-card-label"
    subtext: str = ""
    subtext_class: str = "ui-card-muted"
    icon: str = ""
    icon_class: str = "ui-text__icon"


@dataclass(frozen=True)
class UiCardRow:
    """One visual card row split into left / center / right cells."""

    left: UiText | None = None
    center: UiText | None = None
    right: UiText | None = None


@dataclass(frozen=True)
class UiCard:
    """Generic card view model.

    css_class decides how the card is rendered visually:

        "mobile-card mobile-card--customer"
        "mobile-card mobile-card--inventory"
        "dashboard-card"

    If href is set and action is empty, templates may render the whole card
    as one clickable link.

    If action is set, templates should render the card as an article with an
    explicit action to avoid nested links.
    """

    tone: UiTone
    rows: tuple[UiCardRow, ...]
    action: UiText | None = None
    css_class: str = "mobile-card"
    href: str = ""
    aria_label: str = ""
    footer_hint: str = ""


@dataclass(frozen=True)
class QuantityInfo:
    value: int
    level: str
    label: str
    css_class: str


@dataclass(frozen=True)
class StatusPresentation:
    value: str
    label: str
    tone: UiTone
    text: UiText
    button_class: str = ""
    href: str = ""
    icon: str = ""


TONE_NEUTRAL = UiTone(
    key="neutral",
    label="Neutral",
    card_class="mobile-card--neutral",
    text_class="status-text--neutral",
)

TONE_MUTED = UiTone(
    key="muted",
    label="Muted",
    card_class="mobile-card--muted",
    text_class="status-text--muted",
)

TONE_WARNING = UiTone(
    key="warning",
    label="Warning",
    card_class="mobile-card--warning",
    text_class="status-text--warning",
)

TONE_INFO = UiTone(
    key="info",
    label="Info",
    card_class="mobile-card--info",
    text_class="status-text--info",
)

TONE_SUCCESS = UiTone(
    key="success",
    label="Success",
    card_class="mobile-card--success",
    text_class="status-text--success",
)

TONE_DANGER = UiTone(
    key="danger",
    label="Danger",
    card_class="mobile-card--danger",
    text_class="status-text--danger",
)


def build_quantity_info(
    *,
    quantity: int,
    low_threshold: int = 10,
) -> QuantityInfo:
    """Return presentation info for a stock quantity."""

    if quantity <= 0:
        return QuantityInfo(
            value=quantity,
            level="empty",
            label="0 units left",
            css_class="quantity-text quantity-text--empty",
        )

    if quantity <= low_threshold:
        return QuantityInfo(
            value=quantity,
            level="low",
            label=f"{quantity} units left",
            css_class="quantity-text quantity-text--low",
        )

    return QuantityInfo(
        value=quantity,
        level="safe",
        label=f"{quantity} units left",
        css_class="quantity-text quantity-text--safe",
    )


def mailto_link(email: str) -> str:
    return f"mailto:{email}"


def tel_link(phone_number: str) -> str:
    return f"tel:{phone_number}"


def maps_search_link(address: str) -> str:
    query = quote_plus(address)
    return f"https://www.google.com/maps/search/?api=1&query={query}"
