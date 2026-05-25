from __future__ import annotations
from __future__ import annotations

from common.ui import TONE_NEUTRAL, UiText
from customers.models import Customer


CUSTOMER_CARD_CLASS = "mobile-card mobile-card--customer"

CUSTOMER_TITLE_CLASS = "ui-card-title"
CUSTOMER_CONTACT_CLASS = "ui-card-contact"
CUSTOMER_ACTION_CLASS = "text-link"

CUSTOMER_ACTION_LABEL = "View customer →"

EXTERNAL_LINK_TARGET = "_blank"
EXTERNAL_LINK_REL = "noopener noreferrer"


def customer_table_address(customer: Customer) -> str:
    return customer.address


def customer_card_tone():
    return TONE_NEUTRAL


def customer_name_text(customer: Customer) -> UiText:
    return UiText(
        text=customer.name,
        css_class=CUSTOMER_TITLE_CLASS,
    )
