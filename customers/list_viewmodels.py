from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from accounts.roles import RoleSpec
from common.page_header import PageHeader, PageHeaderAction
from common.ui import (
    TONE_NEUTRAL,
    UiCard,
    UiCardRow,
    UiText,
    mailto_link,
    maps_search_link,
    tel_link,
)
from customers.access import can_create_customer
from customers.models import Customer


@dataclass(frozen=True, slots=True)
class CustomerPageRow:
    customer: Customer
    detail_href: str
    card: UiCard


def build_customers_page_header(*, role_spec: RoleSpec) -> PageHeader:
    return PageHeader(
        title="Customers",
        title_id="customers-title",
        action=_build_add_customer_header_action(role_spec=role_spec),
    )


def _build_add_customer_header_action(
    *,
    role_spec: RoleSpec,
) -> PageHeaderAction | None:
    if not can_create_customer(role_spec=role_spec):
        return None

    return PageHeaderAction(
        label="Add customer",
        href=reverse("customers:create"),
        aria_label="Add a new customer",
    )


def build_customer_page_rows(customers: list[Customer]) -> list[CustomerPageRow]:
    return [
        _build_customer_page_row(customer)
        for customer in customers
    ]


def _build_customer_page_row(customer: Customer) -> CustomerPageRow:
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
        tone=TONE_NEUTRAL,
        css_class="mobile-card mobile-card--customer",
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
        left=UiText(
            text=customer.name,
            css_class="ui-card-title",
        ),
    )


def _customer_email_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=customer.email,
            href=mailto_link(customer.email),
            css_class="ui-card-contact",
            icon="mail",
            icon_class="ui-card-contact__icon",
        ),
    )


def _customer_phone_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=customer.phone_number,
            href=tel_link(customer.phone_number),
            css_class="ui-card-contact",
            icon="phone",
            icon_class="ui-card-contact__icon",
        ),
    )


def _customer_address_row(customer: Customer) -> UiCardRow:
    return UiCardRow(
        left=UiText(
            text=customer.address,
            href=maps_search_link(customer.address),
            css_class="ui-card-contact",
            target="_blank",
            rel="noopener noreferrer",
            icon="map-pin",
            icon_class="ui-card-contact__icon",
        ),
    )


def _customer_detail_action(detail_href: str) -> UiText:
    return UiText(
        text="View customer →",
        href=detail_href,
        css_class="ui-card-link",
    )


def _customer_detail_href(customer: Customer) -> str:
    return reverse("customers:detail", kwargs={"customer_pk": customer.pk})
