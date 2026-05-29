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
from orders.models import Allocation, Order, OrderLine
from products.models import Product
from products.services import create_product


DEMO_USER_USERNAME = "demo_ops"
DEMO_USER_EMAIL = "demo.ops@example.com"

COMMAND_DIR = Path(__file__).resolve().parent
PRODUCT_CATALOG_PATH = COMMAND_DIR / "seed_demo_products.json"
CUSTOMER_CATALOG_PATH = COMMAND_DIR / "seed_demo_customers.json"
BATCH_CATALOG_PATH = COMMAND_DIR / "seed_demo_batches.json"


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
        if options["reset"]:
            self._reset_demo_data()
        elif self._demo_data_exists():
            raise CommandError(
                "Demo data already exists. Run with --reset to recreate it."
            )

        self._get_seed_user(
            create_demo_user=options["with_demo_user"],
        )

        products = self._create_products()
        self._create_customers()
        self._create_inventory(products=products)

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
            customers[str(item["key"])] = customer

        return customers

    # ==========================================================================
    # inventory
    # ==========================================================================

    def _create_inventory(
        self,
        *,
        products: dict[int, Product],
    ) -> None:
        for item in _load_json_list(BATCH_CATALOG_PATH):
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


def _parse_best_before(item: dict[str, Any]) -> date:
    raw_best_before = item.get("best_before")

    if not raw_best_before:
        raise CommandError(
            "Batch item is missing required field 'best_before': "
            f"{item!r}"
        )

    try:
        return date.fromisoformat(str(raw_best_before))
    except ValueError as error:
        raise CommandError(
            "Batch item has invalid 'best_before'. "
            "Expected YYYY-MM-DD: "
            f"{item!r}"
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
                f"{item!r}"
            ) from error

    raw_received_days_ago = item.get("received_days_ago", 1)

    try:
        received_days_ago = int(raw_received_days_ago)
    except TypeError as error:
        raise CommandError(
            "Batch item has invalid 'received_days_ago': "
            f"{item!r}"
        ) from error
    except ValueError as error:
        raise CommandError(
            "Batch item has invalid 'received_days_ago': "
            f"{item!r}"
        ) from error

    if received_days_ago < 0:
        raise CommandError(
            "Batch item 'received_days_ago' must be non-negative: "
            f"{item!r}"
        )

    return timezone.localdate() - timedelta(days=received_days_ago)
