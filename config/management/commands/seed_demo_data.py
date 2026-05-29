from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from customers.models import Customer, normalize_customer_email
from customers.services import create_customer
from inventory.models import InventoryBatch
from inventory.services import create_batch
from orders.datatypes import OrderLineInput
from orders.models import Allocation, Order, OrderLine
from orders.services import create_order, deliver_order, pack_order
from products.models import Product
from products.services import create_product


DEMO_USER_USERNAME = "demo_ops"
DEMO_USER_EMAIL = "demo.ops@example.com"

COMMAND_DIR = Path(__file__).resolve().parent

PRODUCT_CATALOG_PATH = COMMAND_DIR / "seed_demo_products.json"
CUSTOMER_CATALOG_PATH = COMMAND_DIR / "seed_demo_customers.json"
BATCH_CATALOG_DIR = COMMAND_DIR / "seed_demo_batches"
ORDER_CATALOG_DIR = COMMAND_DIR / "seed_demo_orders"


class Command(BaseCommand):
    help = "Seed demo data for SwedeSweets MVP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo-domain data before seeding.",
        )
        parser.add_argument(
            "--with-demo-user",
            action="store_true",
            help="Create a demo_ops staff user with an unusable password.",
        )
        parser.add_argument(
            "--with-orders",
            action="store_true",
            help="Seed historical demo orders and consume inventory.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_demo_data()
        elif self._demo_data_exists():
            raise CommandError(
                "Demo data already exists. Run with --reset to recreate it."
            )

        seed_user = self._get_seed_user(
            create_demo_user=options["with_demo_user"],
        )

        products = self._create_products()
        customers = self._create_customers()
        self._create_inventory(products=products)

        if options["with_orders"]:
            self._create_orders(
                products=products,
                customers=customers,
                user=seed_user,
            )

        self.stdout.write(
            self.style.SUCCESS("Demo data seeded successfully.")
        )

    # ==========================================================================
    # reset
    # ==========================================================================

    def _demo_data_exists(self) -> bool:
        return (
            Product.objects.exists()
            or Customer.objects.exists()
            or InventoryBatch.objects.exists()
            or Order.objects.exists()
        )

    def _reset_demo_data(self) -> None:
        Allocation.objects.all().delete()
        OrderLine.objects.all().delete()
        Order.objects.all().delete()
        InventoryBatch.objects.all().delete()
        Customer.objects.all().delete()
        Product.objects.all().delete()

    # ==========================================================================
    # users
    # ==========================================================================

    def _get_seed_user(self, *, create_demo_user: bool):
        User = get_user_model()

        existing_superuser = (
            User.objects
            .filter(is_superuser=True)
            .order_by("id")
            .first()
        )

        if existing_superuser is not None:
            return existing_superuser

        if not create_demo_user:
            return None

        user = User.objects.create(
            username=DEMO_USER_USERNAME,
            email=DEMO_USER_EMAIL,
            is_staff=True,
            is_superuser=False,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

        return user

    # ==========================================================================
    # products
    # ==========================================================================

    def _create_products(self) -> dict[int, Product]:
        products: dict[int, Product] = {}

        for item in _load_json_list(PRODUCT_CATALOG_PATH):
            product = self._create_product(item)

            if product.internal_number is None:
                raise CommandError(
                    f"Product {product!s} is missing internal_number."
                )

            products[product.internal_number] = product

        return products

    def _create_product(self, item: dict[str, Any]) -> Product:
        result = create_product(
            internal_number=int(item["internal_number"]),
            manufacturer=str(item["manufacturer"]),
            brand=str(item["brand"]),
            name=str(item["name"]),
            weight_per_unit=int(item["weight_per_unit"]),
            stock_unit=str(item.get("stock_unit", Product.StockUnit.BOX)),
            vegan=bool(item["vegan"]),
        )

        product = getattr(result, "item", result)

        if not bool(item.get("active", True)):
            product.active = False
            product.save(update_fields=["active"])

        return product

    # ==========================================================================
    # customers
    # ==========================================================================

    def _create_customers(self) -> dict[str, Customer]:
        customers: dict[str, Customer] = {}

        for item in _load_json_list(CUSTOMER_CATALOG_PATH):
            customer = create_customer(
                name=str(item["name"]),
                email=normalize_customer_email(str(item["email"])),
                phone_number=str(item["phone_number"]),
                country=str(item["country"]),
                city=str(item["city"]),
                address_line=str(item["address_line"]),
            )

            key = str(item["key"])

            if key in customers:
                raise CommandError(f"Duplicate customer key in seed data: {key}")

            customers[key] = customer

        return customers

    # ==========================================================================
    # inventory
    # ==========================================================================

    def _create_inventory(
        self,
        *,
        products: dict[int, Product],
    ) -> None:
        for item in _load_batch_items(BATCH_CATALOG_DIR):
            self._create_batch_from_item(
                item=item,
                products=products,
            )

    def _create_batch_from_item(
        self,
        *,
        item: dict[str, Any],
        products: dict[int, Product],
    ) -> InventoryBatch:
        internal_number = int(item["internal_number"])

        if internal_number not in products:
            source_name = str(item.get("invoice_name", "unknown source line"))
            raise CommandError(
                f"Batch references unknown product #{internal_number}: "
                f"{source_name}"
            )

        product = products[internal_number]

        return create_batch(
            product=product,
            quantity=int(item["quantity"]),
            best_before=_parse_best_before(item),
            location=str(item["location"]),
            today=_parse_received_date(item),
            allow_non_future_best_before=True,
        )

    # ==========================================================================
    # orders
    # ==========================================================================

    def _create_orders(
        self,
        *,
        products: dict[int, Product],
        customers: dict[str, Customer],
        user,
    ) -> None:
        if not ORDER_CATALOG_DIR.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Order catalog directory does not exist: {ORDER_CATALOG_DIR}"
                )
            )
            return

        created_count = 0
        skipped_count = 0

        for order_data in _load_order_records(ORDER_CATALOG_DIR):
            if _should_skip_order(order_data):
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped order {_order_seed_label(order_data)}"
                    )
                )
                continue

            unmapped_items = order_data.get("unmapped_items", [])

            if unmapped_items:
                self.stdout.write(
                    self.style.WARNING(
                        f"Order {_order_seed_label(order_data)} has "
                        f"{len(unmapped_items)} unmapped item(s). "
                        "They will not consume inventory."
                    )
                )

            inventory_items = order_data.get("items", [])

            if not inventory_items:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped order {_order_seed_label(order_data)} "
                        "because it has no inventory items."
                    )
                )
                continue

            customer_key = str(order_data["customer_key"])

            if customer_key not in customers:
                raise CommandError(
                    f"Order {_order_seed_label(order_data)} references "
                    f"unknown customer_key {customer_key!r}."
                )

            line_inputs = _build_order_line_inputs(
                order_data=order_data,
                products=products,
            )

            try:
                order = create_order(
                    customer=customers[customer_key],
                    lines=line_inputs,
                    user=user,
                )
                order = pack_order(order=order, user=user)
                order = deliver_order(order=order, user=user)
                _apply_historical_order_timestamp(
                    order=order,
                    order_date=_parse_order_date(order_data),
                )
            except Exception as error:
                raise CommandError(
                    f"Could not seed order {_order_seed_label(order_data)}: "
                    f"{error}"
                ) from error

            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Historical orders seeded: {created_count}; skipped: {skipped_count}."
            )
        )


# ==============================================================================
# loading: generic
# ==============================================================================


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise CommandError(f"{path.name} must contain a JSON list.")

    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise CommandError(
                f"{path.name} item #{index} must be a JSON object: {item!r}"
            )

    return data


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise CommandError(f"{path.name} must contain a JSON object.")

    return data


# ==============================================================================
# loading: batches
# ==============================================================================


def _load_batch_items(directory: Path) -> Iterator[dict[str, Any]]:
    if not directory.exists():
        raise CommandError(
            f"Batch catalog directory does not exist: {directory}"
        )

    if not directory.is_dir():
        raise CommandError(
            f"Batch catalog path is not a directory: {directory}"
        )

    batch_files = sorted(directory.glob("*.json"))

    if not batch_files:
        raise CommandError(
            f"Batch catalog directory contains no JSON files: {directory}"
        )

    for path in batch_files:
        yield from _load_batch_items_from_file(path)


def _load_batch_items_from_file(path: Path) -> Iterator[dict[str, Any]]:
    document = _load_json_object(path)

    schema_version = document.get("schema_version")

    if schema_version != 1:
        raise CommandError(
            f"{path.name} has unsupported schema_version: {schema_version!r}. "
            "Expected schema_version 1."
        )

    receipts = document.get("receipts")

    if not isinstance(receipts, list):
        raise CommandError(
            f"{path.name} must contain a 'receipts' list."
        )

    for receipt_index, receipt in enumerate(receipts, start=1):
        if not isinstance(receipt, dict):
            raise CommandError(
                f"{path.name} receipt #{receipt_index} must be a JSON object."
            )

        yield from _load_batch_items_from_receipt(
            path=path,
            receipt=receipt,
            receipt_index=receipt_index,
        )


def _load_batch_items_from_receipt(
    *,
    path: Path,
    receipt: dict[str, Any],
    receipt_index: int,
) -> Iterator[dict[str, Any]]:
    source = receipt.get("source")

    if not isinstance(source, dict):
        raise CommandError(
            f"{path.name} receipt #{receipt_index} must contain "
            "a 'source' object."
        )

    supplier = receipt.get("supplier", {})

    if not isinstance(supplier, dict):
        raise CommandError(
            f"{path.name} receipt #{receipt_index} field 'supplier' "
            "must be an object if provided."
        )

    items = receipt.get("items")

    if not isinstance(items, list):
        raise CommandError(
            f"{path.name} receipt #{receipt_index} must contain "
            "an 'items' list."
        )

    received_date = _required_source_field(
        path=path,
        receipt_index=receipt_index,
        source=source,
        field_name="received_date",
    )

    invoice_number = source.get("invoice_number")
    supplier_order_number = source.get("supplier_order_number")
    supplier_name = supplier.get("name")

    for item_index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise CommandError(
                f"{path.name} receipt #{receipt_index} item #{item_index} "
                "must be a JSON object."
            )

        yield {
            **item,
            "received_date": item.get("received_date", received_date),
            "invoice_number": item.get("invoice_number", invoice_number),
            "supplier_order_number": item.get(
                "supplier_order_number",
                supplier_order_number,
            ),
            "supplier_name": item.get("supplier_name", supplier_name),
            "_source_file": path.name,
            "_receipt_index": receipt_index,
            "_item_index": item_index,
        }


def _required_source_field(
    *,
    path: Path,
    receipt_index: int,
    source: dict[str, Any],
    field_name: str,
) -> str:
    value = source.get(field_name)

    if not value:
        raise CommandError(
            f"{path.name} receipt #{receipt_index} source is missing "
            f"required field {field_name!r}."
        )

    return str(value)


# ==============================================================================
# loading: orders
# ==============================================================================


def _load_order_records(directory: Path) -> Iterator[dict[str, Any]]:
    if not directory.exists():
        return

    if not directory.is_dir():
        raise CommandError(
            f"Order catalog path is not a directory: {directory}"
        )

    for path in sorted(directory.glob("*.json")):
        yield from _load_order_records_from_file(path)


def _load_order_records_from_file(path: Path) -> Iterator[dict[str, Any]]:
    document = _load_json_object(path)

    schema_version = document.get("schema_version")

    if schema_version != 1:
        raise CommandError(
            f"{path.name} has unsupported schema_version: {schema_version!r}. "
            "Expected schema_version 1."
        )

    orders = document.get("orders")

    if not isinstance(orders, list):
        raise CommandError(f"{path.name} must contain an 'orders' list.")

    for order_index, order_data in enumerate(orders, start=1):
        if not isinstance(order_data, dict):
            raise CommandError(
                f"{path.name} order #{order_index} must be a JSON object."
            )

        yield {
            **order_data,
            "_source_file": path.name,
            "_order_index": order_index,
        }


# ==============================================================================
# parsing: batches
# ==============================================================================


def _parse_best_before(item: dict[str, Any]) -> date:
    raw_best_before = item.get("best_before")

    if not raw_best_before:
        raise CommandError(
            "Batch item is missing required field 'best_before': "
            f"{_format_batch_item_context(item)}"
        )

    try:
        return date.fromisoformat(str(raw_best_before))
    except ValueError as error:
        raise CommandError(
            "Batch item has invalid 'best_before'. "
            "Expected YYYY-MM-DD: "
            f"{_format_batch_item_context(item)}"
        ) from error


def _parse_received_date(item: dict[str, Any]) -> date:
    raw_received_date = item.get("received_date")

    if raw_received_date:
        try:
            return date.fromisoformat(str(raw_received_date))
        except ValueError as error:
            raise CommandError(
                "Batch item has invalid 'received_date'. "
                "Expected YYYY-MM-DD: "
                f"{_format_batch_item_context(item)}"
            ) from error

    raw_received_days_ago = item.get("received_days_ago", 1)

    try:
        received_days_ago = int(raw_received_days_ago)
    except (TypeError, ValueError) as error:
        raise CommandError(
            "Batch item has invalid 'received_days_ago': "
            f"{_format_batch_item_context(item)}"
        ) from error

    if received_days_ago < 0:
        raise CommandError(
            "Batch item 'received_days_ago' must be non-negative: "
            f"{_format_batch_item_context(item)}"
        )

    return timezone.localdate() - timedelta(days=received_days_ago)


def _format_batch_item_context(item: dict[str, Any]) -> str:
    source_file = item.get("_source_file", "unknown file")
    receipt_index = item.get("_receipt_index", "?")
    item_index = item.get("_item_index", "?")
    invoice_code = item.get("invoice_code", "unknown invoice code")
    invoice_name = item.get("invoice_name", "unknown invoice name")

    return (
        f"{source_file}, receipt #{receipt_index}, item #{item_index}, "
        f"{invoice_code} {invoice_name}"
    )


# ==============================================================================
# parsing: orders
# ==============================================================================


def _should_skip_order(order_data: dict[str, Any]) -> bool:
    if bool(order_data.get("skip", False)):
        return True

    raw_order_date = str(order_data.get("order_date", "")).strip().lower()
    raw_customer_key = str(order_data.get("customer_key", "")).strip().lower()

    return (
        not raw_order_date
        or raw_order_date in {"unknown", "fill_in", "todo"}
        or not raw_customer_key
        or raw_customer_key in {"unknown", "unknown_customer", "fill_in", "todo"}
    )


def _build_order_line_inputs(
    *,
    order_data: dict[str, Any],
    products: dict[int, Product],
) -> list[OrderLineInput]:
    raw_items = order_data.get("items")

    if not isinstance(raw_items, list):
        raise CommandError(
            f"Order {_order_seed_label(order_data)} must contain an 'items' list."
        )

    line_inputs: list[OrderLineInput] = []

    for item_index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise CommandError(
                f"Order {_order_seed_label(order_data)} item #{item_index} "
                "must be a JSON object."
            )

        line_inputs.append(
            _build_order_line_input(
                order_data=order_data,
                item=item,
                item_index=item_index,
                products=products,
            )
        )

    return line_inputs


def _build_order_line_input(
    *,
    order_data: dict[str, Any],
    item: dict[str, Any],
    item_index: int,
    products: dict[int, Product],
) -> OrderLineInput:
    try:
        internal_number = int(item["internal_number"])
    except KeyError as error:
        raise CommandError(
            f"Order {_order_seed_label(order_data)} item #{item_index} "
            "is missing 'internal_number'."
        ) from error

    if internal_number not in products:
        raise CommandError(
            f"Order {_order_seed_label(order_data)} item #{item_index} "
            f"references unknown product #{internal_number}."
        )

    product = products[internal_number]
    quantity = _parse_decimal(item.get("sold_quantity", item.get("quantity")))
    unit = _normalize_seed_order_unit(
        item.get("sold_unit", item.get("unit", product.stock_unit))
    )

    if unit == "kg":
        return OrderLineInput.kg(
            product=product,
            kg=quantity,
        )

    if unit == "grams":
        return OrderLineInput.grams(
            product=product,
            grams=int(quantity),
        )

    if unit in {"stock_unit", "unit", "units", "piece", "pieces", "bag", "bags", "box", "boxes", "case", "cases"}:
        if quantity != quantity.to_integral_value():
            raise CommandError(
                f"Order {_order_seed_label(order_data)} item #{item_index} "
                f"uses unit {unit!r}, but quantity {quantity} is not a whole number."
            )

        return OrderLineInput.stock_units(
            product=product,
            quantity=int(quantity),
        )

    raise CommandError(
        f"Order {_order_seed_label(order_data)} item #{item_index} "
        f"has unsupported unit {unit!r}."
    )


def _normalize_seed_order_unit(value: Any) -> str:
    unit = str(value).strip().lower()

    aliases = {
        "kg": "kg",
        "kilo": "kg",
        "kilos": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "g": "grams",
        "gram": "grams",
        "grams": "grams",
        "stock": "stock_unit",
        "stock_unit": "stock_unit",
        "stock_units": "stock_unit",
        "unit": "stock_unit",
        "units": "stock_unit",
        "quantity": "stock_unit",
        "piece": "piece",
        "pieces": "pieces",
        "st": "pieces",
        "pcs": "pieces",
        "bag": "bag",
        "bags": "bags",
        "box": "box",
        "boxes": "boxes",
        "case": "case",
        "cases": "cases",
    }

    return aliases.get(unit, unit)


def _parse_decimal(value: Any) -> Decimal:
    if value is None:
        raise CommandError("Missing decimal value.")

    normalized = str(value).strip().replace(",", ".")

    try:
        return Decimal(normalized)
    except Exception as error:
        raise CommandError(f"Invalid decimal value: {value!r}") from error


def _parse_order_date(order_data: dict[str, Any]) -> date:
    raw_order_date = order_data.get("order_date")

    if not raw_order_date:
        raise CommandError(
            f"Order {_order_seed_label(order_data)} is missing 'order_date'."
        )

    try:
        return date.fromisoformat(str(raw_order_date))
    except ValueError as error:
        raise CommandError(
            f"Order {_order_seed_label(order_data)} has invalid order_date. "
            "Expected YYYY-MM-DD."
        ) from error


def _apply_historical_order_timestamp(
    *,
    order: Order,
    order_date: date,
) -> None:
    historical_datetime = timezone.make_aware(
        datetime.combine(order_date, time(hour=12))
    )

    Order.objects.filter(pk=order.pk).update(
        created_at=historical_datetime,
        updated_at=historical_datetime,
        placed_at=historical_datetime,
        packed_at=historical_datetime,
        delivered_at=historical_datetime,
    )


def _order_seed_label(order_data: dict[str, Any]) -> str:
    seed_key = order_data.get("seed_key")

    if seed_key:
        return str(seed_key)

    source_file = order_data.get("_source_file", "unknown file")
    order_index = order_data.get("_order_index", "?")
    invoice_number = order_data.get("invoice_number", "unknown invoice")

    return f"{source_file} order #{order_index} invoice {invoice_number}"
