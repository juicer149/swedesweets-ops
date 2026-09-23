"""Export order history as domain-level JSON.

The export describes the business domain, not the Django ORM: stable natural
keys (customer email, product SKU, batch id) replace database primary keys, so
the file can be read and re-imported without knowing the current schema.

It is an extra safety line and a source of up-to-date seed data. It does not
replace a real database backup.

The raw export contains customer and order data. Write it OUTSIDE the git
repository and keep it out of version control. This command refuses to write
inside the repository unless --allow-inside-repo is given.

Usage:
    python manage.py export_order_history --output-dir /safe/path/order-export

Reads only. On PostgreSQL the whole export runs in one REPEATABLE READ,
READ ONLY transaction, so it is internally consistent and cannot write.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Prefetch

from customers.models import Customer
from orders.models import Order, OrderLine
from products.models import Product

EXPORT_FORMAT = "swedesweets-order-history"
EXPORT_FORMAT_VERSION = 1
EXPORT_FILENAME = "orders.json"

_ACTOR_FIELDS = (
    "edited_by",
    "placed_by",
    "packed_by",
    "delivered_by",
    "cancelled_by",
)


class Command(BaseCommand):
    help = (
        "Export order history as domain-level JSON (read-only). "
        "Write to a directory outside the git repository."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--output-dir",
            required=True,
            help="Directory for orders.json (must be outside the repository).",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace an existing orders.json.",
        )
        parser.add_argument(
            "--allow-inside-repo",
            action="store_true",
            help="Allow writing inside the repository (not recommended).",
        )

    def handle(self, *args, **options) -> None:
        output_dir = Path(options["output_dir"]).expanduser().resolve()
        repo_root = Path(settings.BASE_DIR).resolve()

        if output_dir.is_relative_to(repo_root) and not options["allow_inside_repo"]:
            raise CommandError(
                f"Refusing to write inside the repository ({repo_root}). "
                "The export contains customer and order data; choose a "
                "directory outside the repo."
            )

        target = output_dir / EXPORT_FILENAME

        if target.exists() and not options["overwrite"]:
            raise CommandError(f"{target} already exists; use --overwrite.")

        with _read_only_snapshot():
            payload = build_order_history_export()

        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        digest = _write_json_atomically(target, payload)
        (output_dir / f"{EXPORT_FILENAME}.sha256").write_text(
            f"{digest}  {EXPORT_FILENAME}\n"
        )

        counts = payload["counts"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {counts['orders']} orders / {counts['order_lines']} "
                f"lines to {target}"
            )
        )
        self.stdout.write(f"by_status={counts['orders_by_status']}")
        self.stdout.write(
            "lines_with_explicit_offer="
            f"{counts['order_lines_with_explicit_offer']}"
        )
        self.stdout.write(f"sha256={digest}")


@contextmanager
def _read_only_snapshot():
    """One consistent, read-only view of the database (PostgreSQL)."""

    already_in_transaction = connection.in_atomic_block

    with transaction.atomic():
        if connection.vendor == "postgresql" and not already_in_transaction:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )

        yield


def build_order_history_export(*, exported_at: datetime | None = None) -> dict[str, Any]:
    exported_at = exported_at or datetime.now(UTC)

    lines = OrderLine.objects.select_related(
        "product",
        "business_offer_selection__commercial_price__product",
        "business_offer_selection__commercial_price__batch",
        "retail_offer_selection__commercial_price__product",
        "retail_offer_selection__commercial_price__batch",
    ).order_by("id")

    orders = (
        Order.objects.select_related("customer", *_ACTOR_FIELDS)
        .prefetch_related(Prefetch("lines", queryset=lines))
        .order_by("id")
    )

    exported_orders = [_order_record(order) for order in orders]

    by_status = Counter(record["status"] for record in exported_orders)
    by_channel = Counter(record["channel"] for record in exported_orders)
    line_records = [
        line for record in exported_orders for line in record["lines"]
    ]

    return {
        "format": EXPORT_FORMAT,
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": exported_at.astimezone(UTC).isoformat(),
        "counts": {
            "orders": len(exported_orders),
            "order_lines": len(line_records),
            "orders_by_status": dict(sorted(by_status.items())),
            "orders_by_channel": dict(sorted(by_channel.items())),
            "order_lines_with_explicit_offer": sum(
                1 for line in line_records if line["offer"] is not None
            ),
            "database": {
                "customers": Customer.objects.count(),
                "products": Product.objects.count(),
                "orders": Order.objects.count(),
                "order_lines": OrderLine.objects.count(),
            },
        },
        "orders": exported_orders,
    }


def _order_record(order: Order) -> dict[str, Any]:
    return {
        "source_order_id": order.id,
        "channel": order.channel,
        "currency": order.currency,
        "status": order.status,
        "customer": _customer_ref(order.customer),
        "buyer": {
            "name": order.buyer_name_snapshot,
            "email": order.buyer_email_snapshot,
            "phone_number": order.buyer_phone_snapshot,
            "country": order.buyer_country_snapshot,
            "postal_code": order.buyer_postal_code_snapshot,
            "city": order.buyer_city_snapshot,
            "address_line": order.buyer_address_line_snapshot,
        },
        "created_at": _iso(order.created_at),
        "edited_at": _iso(order.edited_at),
        "placed_at": _iso(order.placed_at),
        "packed_at": _iso(order.packed_at),
        "delivered_at": _iso(order.delivered_at),
        "cancelled_at": _iso(order.cancelled_at),
        "actors": {
            field.removesuffix("_by"): _username(getattr(order, field))
            for field in _ACTOR_FIELDS
        },
        "cancel_reason": order.cancel_reason,
        "cancel_note": order.cancel_note,
        "total": _decimal(order.total),
        "lines": [_line_record(line) for line in order.lines.all()],
    }


def _line_record(line: OrderLine) -> dict[str, Any]:
    return {
        "source_line_id": line.id,
        "product": _product_ref(line.product),
        "quantity": _decimal(line.quantity),
        "unit": line.unit,
        "quantity_in_units": line.quantity_in_units,
        "unit_price_snapshot": _decimal(line.unit_price_snapshot),
        "line_total": _decimal(line.line_total),
        "offer": _offer_ref(line),
    }


def _offer_ref(line: OrderLine) -> dict[str, Any] | None:
    """Reference to the explicit commercial offer recorded for this line.

    None means: no explicit offer was recorded (historical pre-offer business
    line, or a business selection explicitly marked unpriced/standard).
    """

    business = getattr(line, "business_offer_selection", None)
    retail = getattr(line, "retail_offer_selection", None)

    business_price = business.commercial_price if business is not None else None
    retail_price = retail.commercial_price if retail is not None else None

    if business_price is not None and retail_price is not None:
        raise CommandError(
            f"Order line {line.id} has both a business and a retail offer "
            "selection; refusing to guess."
        )

    price = business_price or retail_price

    if price is None:
        return None

    return {
        "channel": price.channel,
        "product": _product_ref(price.product),
        "batch_id": price.batch.batch_id if price.batch_id is not None else None,
    }


def _customer_ref(customer: Customer | None) -> dict[str, str] | None:
    if customer is None:
        return None

    return {
        "email": customer.email,
        "name": customer.name,
    }


def _product_ref(product: Product) -> dict[str, Any]:
    return {
        "sku": product.sku,
        "internal_number": product.internal_number,
    }


def _username(user) -> str | None:
    return user.get_username() if user is not None else None


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _write_json_atomically(target: Path, payload: dict[str, Any]) -> str:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    data = text.encode("utf-8")

    temporary = target.with_suffix(".json.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)

    with os.fdopen(fd, "wb") as handle:
        handle.write(data)

    os.replace(temporary, target)

    return hashlib.sha256(data).hexdigest()
