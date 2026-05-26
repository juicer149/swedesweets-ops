from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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
from orders.services import cancel_order, create_order, deliver_order, pack_order
from products.models import Product
from products.services import create_product


DEMO_USER_USERNAME = "demo_ops"
DEMO_USER_EMAIL = "demo.ops@example.com"

COMMAND_DIR = Path(__file__).resolve().parent
PRODUCT_CATALOG_PATH = COMMAND_DIR / "seed_demo_products.json"
CUSTOMER_CATALOG_PATH = COMMAND_DIR / "seed_demo_customers.json"
ORDER_CATALOG_PATH = COMMAND_DIR / "seed_demo_orders.json"


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

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()

        if options["reset"]:
            self._reset_demo_data()
        elif self._demo_data_exists():
            raise CommandError(
                "Demo data already exists. Run with --reset to recreate it."
            )

        user = self._get_seed_user(
            create_demo_user=options["with_demo_user"],
        )

        products = self._create_products()
        customers = self._create_customers()

        self._create_inventory(
            products=products,
            today=today,
        )
        self._create_orders(
            products=products,
            customers=customers,
            user=user,
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
            products[product.internal_number] = product

        return products

    def _create_product(self, item: dict[str, Any]) -> Product:
        result = create_product(
            internal_number=int(item["internal_number"]),
            manufacturer=str(item["manufacturer"]),
            brand=str(item["brand"]),
            name=str(item["name"]),
            weight_per_box=int(item["weight_per_box"]),
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
            customers[str(item["key"])] = customer

        return customers

    # ==========================================================================
    # inventory
    # ==========================================================================

    def _create_inventory(
        self,
        *,
        products: dict[int, Product],
        today: date,
    ) -> None:
        active_products = sorted(
            (
                product
                for product in products.values()
                if product.active
            ),
            key=lambda product: product.catalog_sort_key,
        )

        for index, product in enumerate(active_products):
            self._create_active_demo_batch(
                product=product,
                index=index,
                today=today,
            )

        self._create_closed_demo_batch(
            products=products,
            today=today,
        )

    def _create_active_demo_batch(
        self,
        *,
        product: Product,
        index: int,
        today: date,
    ) -> InventoryBatch:
        internal_number = product.internal_number or index + 1

        return create_batch(
            product=product,
            boxes=_demo_boxes(internal_number),
            best_before=today + timedelta(
                days=_demo_best_before_days(
                    internal_number=internal_number,
                    index=index,
                )
            ),
            location=_demo_location(index),
            today=today - timedelta(days=_demo_received_days(internal_number)),
        )

    def _create_closed_demo_batch(
        self,
        *,
        products: dict[int, Product],
        today: date,
    ) -> InventoryBatch | None:
        product = products.get(23)

        if product is None:
            return None

        batch = create_batch(
            product=product,
            boxes=8,
            best_before=today + timedelta(days=120),
            location="Archive A1",
            today=today - timedelta(days=30),
        )
        batch.close()

        return batch

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
        for item in _load_json_list(ORDER_CATALOG_PATH):
            order = self._create_order_from_item(
                item=item,
                products=products,
                customers=customers,
                user=user,
            )

            status = str(item["status"])

            if status == "placed":
                continue

            if status in {"packed", "delivered"}:
                order = pack_order(
                    order=order,
                    user=user,
                )

            if status == "delivered":
                deliver_order(
                    order=order,
                    user=user,
                )
                continue

            if status == "cancelled":
                cancel_order(
                    order=order,
                    user=user,
                    reason=_first_cancel_reason(),
                    note=str(item.get("cancel_note", "Demo cancellation.")),
                )
                continue

            if status != "packed":
                raise CommandError(f"Unknown demo order status: {status!r}")

    def _create_order_from_item(
        self,
        *,
        item: dict[str, Any],
        products: dict[int, Product],
        customers: dict[str, Customer],
        user,
    ) -> Order:
        customer_key = str(item["customer"])

        if customer_key not in customers:
            raise CommandError(f"Unknown demo customer key: {customer_key!r}")

        lines = [
            _build_order_line_input(
                item=line_item,
                products=products,
            )
            for line_item in item["lines"]
        ]

        return create_order(
            customer=customers[customer_key],
            lines=lines,
            user=user,
        )


# ==============================================================================
# loading
# ==============================================================================


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise CommandError(f"{path.name} must contain a JSON list.")

    return data


# ==============================================================================
# helpers
# ==============================================================================


def _build_order_line_input(
    *,
    item: dict[str, Any],
    products: dict[int, Product],
) -> OrderLineInput:
    internal_number = int(item["internal_number"])

    if internal_number not in products:
        raise CommandError(
            f"Order line references unknown product #{internal_number}."
        )

    return OrderLineInput.boxes(
        product=products[internal_number],
        boxes=int(item["boxes"]),
    )


def _demo_boxes(internal_number: int) -> int:
    """Return deterministic demo stock between 10 and 40 boxes."""

    return 10 + ((internal_number * 17) % 31)


def _demo_best_before_days(
    *,
    internal_number: int,
    index: int,
) -> int:
    """Return controlled best-before spread for demo inventory."""

    if internal_number == 4:
        return 10

    if internal_number == 10:
        return 40

    return 70 + index


def _demo_location(index: int) -> str:
    """Generate A1..A9, B1..B9, C1.. etc."""

    shelf_index = index // 9
    shelf_number = (index % 9) + 1
    shelf_letter = chr(ord("A") + shelf_index)

    return f"{shelf_letter}{shelf_number}"


def _demo_received_days(internal_number: int) -> int:
    return 1 + (internal_number % 14)


def _first_cancel_reason() -> str:
    for value, _label in Order.CancelReason.choices:
        if value:
            return value

    return ""
