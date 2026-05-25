from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from common.ui import (
    UiCard,
    UiCardRow,
    UiText,
    mailto_link,
    maps_search_link,
    tel_link,
)
from customers.models import Customer
from customers.presentation import (
    CUSTOMER_ACTION_CLASS,
    CUSTOMER_ACTION_LABEL,
    CUSTOMER_CARD_CLASS,
    CUSTOMER_CONTACT_CLASS,
    EXTERNAL_LINK_REL,
    EXTERNAL_LINK_TARGET,
    customer_card_tone,
    customer_name_text,
)


@dataclass(frozen=True)
class CustomerPageRow:
    customer: Customer
    detail_href: str
    card: UiCard


def build_customer_page_rows(customers: list[Customer]) -> list[CustomerPageRow]:
    return [
        build_customer_page_row(customer)
        for customer in customers
    ]


def build_customer_page_row(customer: Customer) -> CustomerPageRow:
    detail_href = _customer_detail_href(customer)

    return CustomerPageRow(
        customer=customer,
        detail_href=detail_href,
        card=_customer_card(
            customer=customer,
            detail_href=detail_href,
        ),
    )


def _customer_card(
    *,
    customer: Customer,
    detail_href: str,
) -> UiCard:
    return UiCard(
        tone=customer_card_tone(),
        css_class=CUSTOMER_CARD_CLASS,
        rows=_customer_card_rows(customer),
        action=_customer_detail_action(detail_href),
    )


def _customer_card_rows(customer: Customer) -> tuple[UiCardRow, ...]:
    return (
        _customer_name_row(customer),
        _customer_email_row(customer),
        _customer_phone_row(customer),
        _customer_address_row(customer),
    )


def _customer_name_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=customer_name_text(customer),
    )


def _customer_email_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=customer.email,
            href=mailto_link(customer.email),
            css_class=CUSTOMER_CONTACT_CLASS,
            icon="mail",
            icon_class="ui-card-contact__icon",
        ),
    )


def _customer_phone_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=customer.phone_number,
            href=tel_link(customer.phone_number),
            css_class=CUSTOMER_CONTACT_CLASS,
            icon="phone",
            icon_class="ui-card-contact__icon",
        ),
    )


def _customer_address_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=customer.address,
            href=maps_search_link(customer.address),
            css_class=CUSTOMER_CONTACT_CLASS,
            target=EXTERNAL_LINK_TARGET,
            rel=EXTERNAL_LINK_REL,
            icon="map-pin",
            icon_class="ui-card-contact__icon",
        ),
    )


def _customer_detail_action(detail_href: str) -> UiText:
    return UiText(
        text=CUSTOMER_ACTION_LABEL,
        href=detail_href,
        css_class=CUSTOMER_ACTION_CLASS,
    )


def _customer_detail_href(customer: Customer) -> str:
    return reverse("customers:detail", kwargs={"customer_pk": customer.pk})
