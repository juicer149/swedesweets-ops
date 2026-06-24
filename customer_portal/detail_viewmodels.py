from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from common.detail_cards import (
    DetailCard,
    DetailHeader,
    DetailPanel,
)
from common.ui import (
    TONE_NEUTRAL,
    UiCard,
    UiCardRow,
    UiText,
)
from orders.models import Order, OrderLine
from orders.presentation import (
    contents_summary,
    customer_order_status_label,
    order_detail_card_class,
    order_detail_status_class,
    order_status_icon,
    quantity_label,
)
from products.models import Product
from products.presentation import (
    translated_product_catalog_label,
    translated_product_name,
)


@dataclass(frozen=True, slots=True)
class PortalOrderContentLine:
    product: Product
    quantity: int
    quantity_label: str
    unit: str
    catalog_label: str
    card: UiCard


@dataclass(frozen=True, slots=True)
class PortalOrderDetailContext:
    order: Order
    content_lines: tuple[PortalOrderContentLine, ...]
    product_count: int
    total_quantity: int
    total_quantity_label: str
    detail_card: DetailCard
    title: str
    customer_status_label: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "order": self.order,
            "content_lines": self.content_lines,
            "product_count": self.product_count,
            "total_quantity": self.total_quantity,
            "total_quantity_label": self.total_quantity_label,
            "detail_card": self.detail_card,
            "title": self.title,
            "customer_status_label": self.customer_status_label,
            "cancel_url": self.cancel_url,
        }


def build_portal_order_detail_context(
    *,
    order: Order,
    language_code: str,
) -> PortalOrderDetailContext:
    order_lines = tuple(order.lines.select_related("product").all())
    content_lines = tuple(
        _build_content_line(
            line,
            language_code=language_code,
        )
        for line in order_lines
    )
    product_count = len(content_lines)
    total_quantity = sum(line.quantity for line in content_lines)

    return PortalOrderDetailContext(
        order=order,
        content_lines=content_lines,
        product_count=product_count,
        total_quantity=total_quantity,
        total_quantity_label=quantity_label(total_quantity),
        detail_card=DetailCard(
            header=_build_order_header(order),
            panels=_build_order_detail_panels(
                order=order,
                product_count=product_count,
                total_quantity=total_quantity,
            ),
            content_card_class=(
                "portal-order-detail-card "
                f"{order_detail_card_class(order.status)}"
            ),
        ),
        title=_("Order #%(order_id)s") % {"order_id": order.pk},
        customer_status_label=customer_order_status_label(order.status),
        cancel_url=reverse("customer_portal:orders"),
    )


def _build_order_header(order: Order) -> DetailHeader:
    return DetailHeader(
        eyebrow=_("Order details"),
        title=_("Order #%(order_id)s") % {"order_id": order.pk},
        status_label=customer_order_status_label(order.status),
        status_class=order_detail_status_class(order.status),
        status_icon=order_status_icon(order.status),
    )


def _build_order_detail_panels(
    *,
    order: Order,
    product_count: int,
    total_quantity: int,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="order",
            label=_("Order"),
            summary=_("Details"),
            body_template="customer_portal/includes/detail_panel_order.html",
            icon="cart",
            is_active=order.status == Order.Status.CANCELLED,
        ),
        DetailPanel(
            key="items",
            label=_("Items"),
            summary=contents_summary(
                product_count=product_count,
                total_quantity=total_quantity,
            ),
            body_template="customer_portal/includes/detail_panel_items.html",
            icon="box",
            is_active=order.status != Order.Status.CANCELLED,
        ),
    )


def _build_content_line(
    line: OrderLine,
    *,
    language_code: str,
) -> PortalOrderContentLine:
    product = line.product
    line_quantity_label = quantity_label(line.quantity_in_units)
    catalog_label = translated_product_catalog_label(
        product,
        language_code=language_code,
    )

    return PortalOrderContentLine(
        product=product,
        quantity=line.quantity_in_units,
        quantity_label=line_quantity_label,
        unit=line.get_unit_display(),
        catalog_label=catalog_label,
        card=_build_content_line_card(
            product=product,
            quantity_label=line_quantity_label,
            catalog_label=catalog_label,
            language_code=language_code,
        ),
    )


def _build_content_line_card(
    *,
    product: Product,
    quantity_label: str,
    catalog_label: str,
    language_code: str,
) -> UiCard:
    return UiCard(
        tone=TONE_NEUTRAL,
        css_class="mobile-card mobile-card--neutral portal-detail-item-card",
        rows=(
            UiCardRow(
                left=UiText(
                    text=translated_product_name(
                        product,
                        language_code=language_code,
                    ),
                    css_class="ui-card-title",
                    subtext=catalog_label,
                ),
                right=UiText(
                    text=quantity_label,
                    css_class="ui-card-order-meta",
                ),
            ),
        ),
    )
