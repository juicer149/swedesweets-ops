from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from accounts.roles import RoleSpec
from common.detail_cards import (
    DetailAction,
    DetailCard,
    DetailHeader,
    DetailPanel,
    build_danger_get_action,
    build_secondary_get_action,
)
from common.ui import UiCard
from inventory.expiry import build_expiry_info
from inventory.models import InventoryBatch
from ops_portal.inventory.access import (
    can_close_batch,
    can_edit_batch,
)
from ops_portal.inventory.presentation import (
    batch_detail_card_class,
    batch_detail_status_class,
    batch_status_icon,
)
from ops_portal.orders.mini_cards import (
    build_order_usage_mini_card,
)
from ops_portal.products.mini_cards import (
    build_product_mini_card,
)
from pricing.models import CommercialPrice, PriceAmount
from reservations.datatypes import BatchUsage


@dataclass(frozen=True, slots=True)
class BatchStockSummary:
    physical_quantity: int
    physical_quantity_label: str
    reserved_quantity: int
    reserved_quantity_label: str
    available_quantity: int
    available_quantity_label: str
    is_orderable: bool

    @classmethod
    def from_batch_and_allocations(
        cls,
        *,
        batch: InventoryBatch,
        allocations: list[BatchUsage],
    ) -> BatchStockSummary:
        reserved_quantity = sum(
            usage.quantity
            for usage in allocations
            if usage.is_active_reservation
        )

        available_quantity = max(
            batch.quantity - reserved_quantity,
            0,
        )

        return cls(
            physical_quantity=batch.quantity,
            physical_quantity_label=(
                batch.product.stock_quantity_label(
                    batch.quantity
                )
            ),
            reserved_quantity=reserved_quantity,
            reserved_quantity_label=(
                batch.product.stock_quantity_label(
                    reserved_quantity
                )
            ),
            available_quantity=available_quantity,
            available_quantity_label=(
                batch.product.stock_quantity_label(
                    available_quantity
                )
            ),
            is_orderable=(
                batch.status
                == InventoryBatch.Status.ACTIVE
                and batch.product.active
                and available_quantity > 0
            ),
        )


@dataclass(frozen=True, slots=True)
class BatchPriceAmountSummary:
    currency: str
    price: Decimal

    @property
    def price_label(self) -> str:
        return f"{self.price:.2f}"


@dataclass(frozen=True, slots=True)
class BatchChannelPricingSummary:
    label: str
    enabled: bool
    amounts: tuple[BatchPriceAmountSummary, ...]

    @property
    def status_label(self) -> str:
        return (
            "Active"
            if self.enabled
            else "Inactive"
        )


@dataclass(frozen=True, slots=True)
class BatchPricingSummary:
    reason: str
    reason_label: str
    business: BatchChannelPricingSummary
    retail: BatchChannelPricingSummary

    @property
    def is_configured(self) -> bool:
        return bool(
            self.business.amounts
            or self.retail.amounts
        )

    @property
    def has_active_offer(self) -> bool:
        return (
            self.business.enabled
            or self.retail.enabled
        )

    @property
    def panel_summary(self) -> str:
        if not self.is_configured:
            return "Standard pricing"

        if self.reason_label:
            return self.reason_label

        return "Special pricing"


@dataclass(frozen=True, slots=True)
class BatchUsageRow:
    order_id: int
    order_href: str
    customer_name: str
    customer_href: str
    quantity: int
    quantity_label: str
    allocation_status: str
    order_status: str
    card: UiCard


@dataclass(frozen=True, slots=True)
class BatchDetailContext:
    batch: InventoryBatch
    stock: BatchStockSummary
    pricing: BatchPricingSummary
    product_href: str
    product_card: UiCard
    usage_rows: list[BatchUsageRow]
    usage_count: int
    detail_card: DetailCard
    title: str
    description: str
    cancel_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "batch": self.batch,
            "stock": self.stock,
            "pricing": self.pricing,
            "product_href": self.product_href,
            "product_card": self.product_card,
            "usage_rows": self.usage_rows,
            "usage_count": self.usage_count,
            "detail_card": self.detail_card,
            "title": self.title,
            "description": self.description,
            "cancel_url": self.cancel_url,
        }


def build_batch_detail_context(
    *,
    batch: InventoryBatch,
    allocations: list[BatchUsage],
    business_price: CommercialPrice | None,
    retail_price: CommercialPrice | None,
    cancel_url: str,
    role_spec: RoleSpec,
) -> BatchDetailContext:
    usage_rows = _build_usage_rows(
        allocations,
    )

    stock = BatchStockSummary.from_batch_and_allocations(
        batch=batch,
        allocations=allocations,
    )

    pricing = _build_batch_pricing_summary(
        business_price=business_price,
        retail_price=retail_price,
    )

    product_href = reverse(
        "ops_products:detail",
        kwargs={
            "product_pk": batch.product_id,
        },
    )

    return BatchDetailContext(
        batch=batch,
        stock=stock,
        pricing=pricing,
        product_href=product_href,
        product_card=build_product_mini_card(
            product=batch.product,
            product_href=product_href,
        ),
        usage_rows=usage_rows,
        usage_count=len(usage_rows),
        detail_card=DetailCard(
            header=_build_batch_header(
                batch,
            ),
            panels=_build_batch_detail_panels(
                stock=stock,
                pricing=pricing,
                usage_count=len(usage_rows),
            ),
            content_card_class=(
                batch_detail_card_class(
                    batch,
                )
            ),
            secondary_actions=(
                build_batch_secondary_actions(
                    batch=batch,
                    role_spec=role_spec,
                )
            ),
        ),
        title=f"Batch {batch.batch_id}",
        description="",
        cancel_url=cancel_url,
    )


def build_batch_secondary_actions(
    *,
    batch: InventoryBatch,
    role_spec: RoleSpec,
) -> tuple[DetailAction, ...]:
    actions: list[DetailAction] = []

    if can_edit_batch(
        batch=batch,
        role_spec=role_spec,
    ):
        actions.append(
            build_secondary_get_action(
                label="Edit batch",
                href=reverse(
                    "ops_inventory:edit",
                    kwargs={
                        "batch_pk": batch.pk,
                    },
                ),
            )
        )

    if can_close_batch(
        batch=batch,
        role_spec=role_spec,
    ):
        actions.append(
            build_danger_get_action(
                label="Close batch",
                href=reverse(
                    "ops_inventory:close",
                    kwargs={
                        "batch_pk": batch.pk,
                    },
                ),
            )
        )

    return tuple(actions)


def _build_batch_header(
    batch: InventoryBatch,
) -> DetailHeader:
    return DetailHeader(
        eyebrow="Batch",
        title=batch.batch_id,
        status_label=batch.get_status_display(),
        status_class=batch_detail_status_class(
            batch
        ),
        status_icon=batch_status_icon(
            batch
        ),
    )


def _build_batch_detail_panels(
    *,
    stock: BatchStockSummary,
    pricing: BatchPricingSummary,
    usage_count: int,
) -> tuple[DetailPanel, ...]:
    return (
        DetailPanel(
            key="batch",
            label="Batch",
            summary=stock.available_quantity_label,
            body_template=(
                "ops_portal/inventory/includes/"
                "detail_panel_batch.html"
            ),
            icon="tag",
            is_active=True,
        ),
        DetailPanel(
            key="pricing",
            label="Pricing",
            summary=pricing.panel_summary,
            body_template=(
                "ops_portal/inventory/includes/"
                "detail_panel_pricing.html"
            ),
            icon="tag",
        ),
        DetailPanel(
            key="usage",
            label="Usage",
            summary=_usage_summary(
                usage_count
            ),
            body_template=(
                "ops_portal/inventory/includes/"
                "detail_panel_usage.html"
            ),
            icon="inventory",
        ),
    )


def _build_batch_pricing_summary(
    *,
    business_price: CommercialPrice | None,
    retail_price: CommercialPrice | None,
) -> BatchPricingSummary:
    reason = _pricing_reason(
        business_price=business_price,
        retail_price=retail_price,
    )

    return BatchPricingSummary(
        reason=reason,
        reason_label=_reason_label(
            reason
        ),
        business=_build_channel_pricing_summary(
            label="Business",
            commercial_price=business_price,
        ),
        retail=_build_channel_pricing_summary(
            label="Retail",
            commercial_price=retail_price,
        ),
    )


def _build_channel_pricing_summary(
    *,
    label: str,
    commercial_price: CommercialPrice | None,
) -> BatchChannelPricingSummary:
    if commercial_price is None:
        return BatchChannelPricingSummary(
            label=label,
            enabled=False,
            amounts=(),
        )

    amounts = tuple(
        BatchPriceAmountSummary(
            currency=amount.currency,
            price=amount.price,
        )
        for amount in commercial_price.amounts.all()
    )

    return BatchChannelPricingSummary(
        label=label,
        enabled=commercial_price.enabled,
        amounts=amounts,
    )


def _pricing_reason(
    *,
    business_price: CommercialPrice | None,
    retail_price: CommercialPrice | None,
) -> str:
    if (
        business_price is not None
        and business_price.reason
    ):
        return business_price.reason

    if (
        retail_price is not None
        and retail_price.reason
    ):
        return retail_price.reason

    return ""


def _reason_label(
    reason: str,
) -> str:
    if not reason:
        return ""

    return CommercialPrice.Reason(
        reason
    ).label


def _build_usage_rows(
    allocations: list[BatchUsage],
) -> list[BatchUsageRow]:
    rows: list[BatchUsageRow] = []

    for usage in allocations:
        order_href = reverse(
            "ops_orders:detail",
            kwargs={
                "order_id": usage.order.pk,
            },
        )

        customer_href = ""

        if usage.customer_id is not None:
            customer_href = reverse(
                "ops_customers:detail",
                kwargs={
                    "customer_pk": usage.customer_id,
                },
            )

        rows.append(
            BatchUsageRow(
                order_id=usage.order.pk,
                order_href=order_href,
                customer_name=usage.buyer_name,
                customer_href=customer_href,
                quantity=usage.quantity,
                quantity_label=usage.quantity_label,
                allocation_status=(
                    usage.allocation_status
                ),
                order_status=usage.order_status,
                card=build_order_usage_mini_card(
                    order=usage.order,
                    order_href=order_href,
                    customer_name=usage.buyer_name,
                    allocation_status=(
                        usage.allocation_status
                    ),
                    quantity_label_text=(
                        usage.quantity_label
                    ),
                ),
            )
        )

    return rows


def _usage_summary(
    usage_count: int,
) -> str:
    if usage_count == 1:
        return "1 allocation"

    return f"{usage_count} allocations"


def batch_expiry_label(
    batch: InventoryBatch,
) -> str:
    expiry = build_expiry_info(
        best_before=batch.best_before,
        today=timezone.localdate(),
    )

    return expiry.label
