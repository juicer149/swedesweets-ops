from __future__ import annotations

import inspect
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from customers.models import Customer, normalize_customer_email
from customers.services import create_customer, update_customer
from inventory.models import InventoryBatch
from inventory.services import create_batch
from orders.datatypes import OrderLineInput
from orders.models import Allocation, Order, OrderLine
from orders.services import (
    cancel_order,
    create_order,
    deliver_order,
    pack_order,
)
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
            help=(
                "Delete existing demo-domain data first. "
                "Does not delete your real admin/superuser."
            ),
        )
        parser.add_argument(
            "--with-demo-user",
            action="store_true",
            help=(
                "Create a non-superuser demo_ops account with an unusable "
                "password for order attribution."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()

        if options["reset"]:
            self._reset_demo_data()

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

        user, created = User.objects.get_or_create(
            username=DEMO_USER_USERNAME,
            defaults={
                "email": DEMO_USER_EMAIL,
                "is_staff": True,
                "is_superuser": False,
            },
        )

        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        return user

    # ==========================================================================
    # products
    # ==========================================================================

    def _create_products(self) -> dict[str, Product]:
        products: dict[str, Product] = {}

        for item in _load_product_catalog():
            product = self._create_product_from_catalog_item(item)
            products[_product_key(item)] = product

        return products

    def _create_product_from_catalog_item(
        self,
        item: dict[str, object],
    ) -> Product:
        existing = _find_existing_product(item)

        if existing is not None:
            product = existing
        else:
            result = _call_service(
                create_product,
                internal_number=item["internal_number"],
                manufacturer=item["manufacturer"],
                brand=item["brand"],
                name=item["name"],
                weight_per_box=item["weight_per_box"],
                vegan=item["vegan"],
            )
            product = _unwrap_product(result)

        _set_product_field_if_present(
            product=product,
            field_name="internal_number",
            value=item["internal_number"],
        )
        _set_product_field_if_present(
            product=product,
            field_name="manufacturer",
            value=item["manufacturer"],
        )
        _set_product_field_if_present(
            product=product,
            field_name="brand",
            value=item["brand"],
        )
        _set_product_field_if_present(
            product=product,
            field_name="name",
            value=item["name"],
        )
        _set_product_field_if_present(
            product=product,
            field_name="vegan",
            value=item["vegan"],
        )
        _set_product_field_if_present(
            product=product,
            field_name="active",
            value=item.get("active", True),
        )

        return product

    # ==========================================================================
    # customers
    # ==========================================================================

    def _create_customers(self) -> dict[str, Customer]:
        customers: dict[str, Customer] = {}

        for item in _load_customer_catalog():
            customers[str(item["key"])] = self._create_customer_from_catalog_item(item)

        return customers

    def _create_customer_from_catalog_item(
        self,
        item: dict[str, object],
    ) -> Customer:
        return self._create_customer(
            name=str(item["name"]),
            email=str(item["email"]),
            phone_number=str(item["phone_number"]),
            country=str(item["country"]),
            city=str(item["city"]),
            address_line=str(item["address_line"]),
        )

    def _create_customer(
        self,
        *,
        name: str,
        email: str,
        phone_number: str,
        country: str,
        city: str,
        address_line: str,
    ) -> Customer:
        normalized_email = normalize_customer_email(email)
        existing = Customer.objects.filter(email=normalized_email).first()

        if existing is not None:
            return update_customer(
                customer=existing,
                name=name,
                email=normalized_email,
                phone_number=phone_number,
                country=country,
                city=city,
                address_line=address_line,
            )

        return create_customer(
            name=name,
            email=normalized_email,
            phone_number=phone_number,
            country=country,
            city=city,
            address_line=address_line,
        )

    # ==========================================================================
    # inventory
    # ==========================================================================

    def _create_inventory(
        self,
        *,
        products: dict[str, Product],
        today: date,
    ) -> None:
        active_products = sorted(
            (
                product
                for product in products.values()
                if getattr(product, "active", True)
            ),
            key=_product_internal_number,
        )

        for product in active_products:
            self._create_primary_batch(
                product=product,
                today=today,
            )

            if _product_internal_number(product) % 7 == 0:
                self._create_secondary_active_batch(
                    product=product,
                    today=today,
                )

            if _product_internal_number(product) % 11 == 0:
                self._create_closed_demo_batch(
                    product=product,
                    today=today,
                )

            if _product_internal_number(product) % 13 == 0:
                self._create_depleted_demo_batch(
                    product=product,
                    today=today,
                )

        self._create_named_showcase_batches(
            products=products,
            today=today,
        )

    def _create_primary_batch(
        self,
        *,
        product: Product,
        today: date,
    ) -> InventoryBatch:
        internal_number = _product_internal_number(product)

        return self._create_active_batch(
            batch_id=f"P{internal_number:03d}-A",
            product=product,
            boxes=_primary_batch_boxes(internal_number),
            best_before=today + timedelta(days=_primary_batch_expiry_days(internal_number)),
            location=f"Shelf {_shelf_letter(internal_number)}{_shelf_number(internal_number)}",
            received_on=today - timedelta(days=internal_number % 18),
        )

    def _create_secondary_active_batch(
        self,
        *,
        product: Product,
        today: date,
    ) -> InventoryBatch:
        internal_number = _product_internal_number(product)

        return self._create_active_batch(
            batch_id=f"P{internal_number:03d}-B",
            product=product,
            boxes=_secondary_batch_boxes(internal_number),
            best_before=today + timedelta(days=90 + (internal_number % 70)),
            location=f"Reserve {_shelf_letter(internal_number)}{_shelf_number(internal_number)}",
            received_on=today - timedelta(days=3 + (internal_number % 12)),
        )

    def _create_closed_demo_batch(
        self,
        *,
        product: Product,
        today: date,
    ) -> InventoryBatch:
        internal_number = _product_internal_number(product)

        return self._create_closed_batch(
            batch_id=f"P{internal_number:03d}-C",
            product=product,
            boxes=4 + (internal_number % 6),
            best_before=today + timedelta(days=120 + (internal_number % 60)),
            location=f"Archive {_shelf_letter(internal_number)}",
            received_on=today - timedelta(days=45 + (internal_number % 20)),
        )

    def _create_depleted_demo_batch(
        self,
        *,
        product: Product,
        today: date,
    ) -> InventoryBatch:
        internal_number = _product_internal_number(product)

        return self._create_depleted_batch(
            batch_id=f"P{internal_number:03d}-D",
            product=product,
            initial_boxes=6 + (internal_number % 7),
            best_before=today + timedelta(days=30 + (internal_number % 40)),
            location=f"Backroom {_shelf_letter(internal_number)}",
            received_on=today - timedelta(days=60 + (internal_number % 30)),
        )

    def _create_named_showcase_batches(
        self,
        *,
        products: dict[str, Product],
        today: date,
    ) -> None:
        """Create a few human-friendly demo batches.

        The generated P### batches guarantee every active product is orderable.
        These named batches make detail pages nicer during the demo.
        """

        showcase_specs = [
            ("TTF-001", "p004", 18, 8, "Showcase A1"),
            ("BUB-001", "p003", 25, 10, "Showcase B1"),
            ("TYR-001", "p023", 14, 14, "Showcase C1"),
            ("AHL-001", "p038", 18, 30, "Showcase D1"),
            ("POL-001", "p013", 18, 38, "Showcase E1"),
            ("BUBZ-001", "p048", 16, 45, "Showcase F1"),
        ]

        for batch_id, product_key, boxes, expires_in_days, location in showcase_specs:
            product = products.get(product_key)

            if product is None:
                continue

            self._create_active_batch(
                batch_id=batch_id,
                product=product,
                boxes=boxes,
                best_before=today + timedelta(days=expires_in_days),
                location=location,
                received_on=today - timedelta(days=4),
            )

    def _create_active_batch(
        self,
        *,
        batch_id: str,
        product: Product,
        boxes: int,
        best_before: date,
        location: str,
        received_on: date | None = None,
    ) -> InventoryBatch:
        existing = InventoryBatch.objects.filter(batch_id=batch_id).first()

        if existing is not None:
            return existing

        return _call_service(
            create_batch,
            batch_id=batch_id,
            product=product,
            boxes=boxes,
            best_before=best_before,
            location=location,
            today=received_on or timezone.localdate(),
        )

    def _create_depleted_batch(
        self,
        *,
        batch_id: str,
        product: Product,
        initial_boxes: int,
        best_before: date,
        location: str,
        received_on: date | None = None,
    ) -> InventoryBatch:
        batch = self._create_active_batch(
            batch_id=batch_id,
            product=product,
            boxes=initial_boxes,
            best_before=best_before,
            location=location,
            received_on=received_on,
        )

        if batch.status != InventoryBatch.Status.DEPLETED:
            batch.adjust_boxes(boxes=0)

        return batch

    def _create_closed_batch(
        self,
        *,
        batch_id: str,
        product: Product,
        boxes: int,
        best_before: date,
        location: str,
        received_on: date | None = None,
    ) -> InventoryBatch:
        batch = self._create_active_batch(
            batch_id=batch_id,
            product=product,
            boxes=boxes,
            best_before=best_before,
            location=location,
            received_on=received_on,
        )

        if batch.status != InventoryBatch.Status.CLOSED:
            batch.close()

        return batch

    # ==========================================================================
    # orders
    # ==========================================================================

    def _create_orders(
        self,
        *,
        products: dict[str, Product],
        customers: dict[str, Customer],
        user,
    ) -> None:
        products_by_internal_number = {
            _product_internal_number(product): product
            for product in products.values()
        }

        for item in _load_order_catalog():
            order = self._create_order_from_catalog_item(
                item=item,
                products_by_internal_number=products_by_internal_number,
                customers=customers,
                user=user,
            )

            status = str(item["status"])

            if status == "placed":
                continue

            if status in {"packed", "delivered"}:
                order = self._pack_order(
                    order=order,
                    user=user,
                )

            if status == "delivered":
                self._deliver_order(
                    order=order,
                    user=user,
                )
                continue

            if status == "cancelled":
                self._cancel_order(
                    order=order,
                    user=user,
                    note=str(
                        item.get(
                            "cancel_note",
                            "Demo cancellation.",
                        )
                    ),
                )
                continue

            if status != "packed":
                raise ValueError(f"Unknown demo order status: {status!r}")

    def _create_order_from_catalog_item(
        self,
        *,
        item: dict[str, object],
        products_by_internal_number: dict[int, Product],
        customers: dict[str, Customer],
        user,
    ) -> Order:
        customer_key = str(item["customer"])

        if customer_key not in customers:
            raise ValueError(f"Unknown demo customer key: {customer_key!r}")

        lines = [
            _build_order_line_input(
                item=line_item,
                products_by_internal_number=products_by_internal_number,
            )
            for line_item in item["lines"]
        ]

        return self._create_order(
            customer=customers[customer_key],
            lines=lines,
            user=user,
        )

    def _create_order(
        self,
        *,
        customer: Customer,
        lines: list[OrderLineInput],
        user,
    ) -> Order:
        return _call_service(
            create_order,
            customer=customer,
            lines=lines,
            user=user,
        )

    def _pack_order(
        self,
        *,
        order: Order,
        user,
    ) -> Order:
        return _call_service(
            pack_order,
            order=order,
            user=user,
        )

    def _deliver_order(
        self,
        *,
        order: Order,
        user,
    ) -> Order:
        return _call_service(
            deliver_order,
            order=order,
            user=user,
        )

    def _cancel_order(
        self,
        *,
        order: Order,
        user,
        note: str,
    ) -> Order:
        return _call_service(
            cancel_order,
            order=order,
            user=user,
            reason=_demo_cancel_reason(),
            note=note,
        )


# ==============================================================================
# loading
# ==============================================================================


def _load_product_catalog() -> list[dict[str, object]]:
    data = _load_json_list(PRODUCT_CATALOG_PATH)
    return [_validate_product_catalog_item(item) for item in data]


def _load_customer_catalog() -> list[dict[str, object]]:
    data = _load_json_list(CUSTOMER_CATALOG_PATH)
    return [_validate_customer_catalog_item(item) for item in data]


def _load_order_catalog() -> list[dict[str, object]]:
    data = _load_json_list(ORDER_CATALOG_PATH)
    return [_validate_order_catalog_item(item) for item in data]


def _load_json_list(path: Path) -> list[object]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise TypeError(f"{path.name} must contain a list")

    return data


# ==============================================================================
# validation
# ==============================================================================


def _validate_product_catalog_item(
    item: object,
) -> dict[str, object]:
    if not isinstance(item, dict):
        raise TypeError("Each product catalog item must be an object")

    required_fields = {
        "internal_number",
        "manufacturer",
        "brand",
        "name",
        "weight_per_box",
        "vegan",
    }
    missing_fields = required_fields - set(item)

    if missing_fields:
        raise ValueError(
            f"Product catalog item is missing fields: "
            f"{', '.join(sorted(missing_fields))}"
        )

    return {
        "internal_number": int(item["internal_number"]),
        "manufacturer": str(item["manufacturer"]),
        "brand": str(item["brand"]),
        "name": str(item["name"]),
        "weight_per_box": int(item["weight_per_box"]),
        "vegan": bool(item["vegan"]),
        "active": bool(item.get("active", True)),
    }


def _validate_customer_catalog_item(
    item: object,
) -> dict[str, object]:
    if not isinstance(item, dict):
        raise TypeError("Each customer catalog item must be an object")

    required_fields = {
        "key",
        "name",
        "email",
        "phone_number",
        "country",
        "city",
        "address_line",
    }
    missing_fields = required_fields - set(item)

    if missing_fields:
        raise ValueError(
            f"Customer catalog item is missing fields: "
            f"{', '.join(sorted(missing_fields))}"
        )

    return {
        "key": str(item["key"]),
        "name": str(item["name"]),
        "email": str(item["email"]),
        "phone_number": str(item["phone_number"]),
        "country": str(item["country"]),
        "city": str(item["city"]),
        "address_line": str(item["address_line"]),
    }


def _validate_order_catalog_item(
    item: object,
) -> dict[str, object]:
    if not isinstance(item, dict):
        raise TypeError("Each order catalog item must be an object")

    required_fields = {
        "customer",
        "status",
        "lines",
    }
    missing_fields = required_fields - set(item)

    if missing_fields:
        raise ValueError(
            f"Order catalog item is missing fields: "
            f"{', '.join(sorted(missing_fields))}"
        )

    lines = item["lines"]

    if not isinstance(lines, list) or not lines:
        raise ValueError("Order catalog item lines must be a non-empty list")

    return {
        "customer": str(item["customer"]),
        "status": _validate_order_status(str(item["status"])),
        "cancel_note": str(item.get("cancel_note", "")),
        "lines": [_validate_order_line_item(line) for line in lines],
    }


def _validate_order_line_item(item: object) -> dict[str, int]:
    if not isinstance(item, dict):
        raise TypeError("Each order line item must be an object")

    required_fields = {
        "internal_number",
        "boxes",
    }
    missing_fields = required_fields - set(item)

    if missing_fields:
        raise ValueError(
            f"Order line item is missing fields: "
            f"{', '.join(sorted(missing_fields))}"
        )

    boxes = int(item["boxes"])

    if boxes <= 0:
        raise ValueError("Order line boxes must be positive")

    return {
        "internal_number": int(item["internal_number"]),
        "boxes": boxes,
    }


def _validate_order_status(status: str) -> str:
    allowed_statuses = {
        "placed",
        "packed",
        "delivered",
        "cancelled",
    }

    if status not in allowed_statuses:
        raise ValueError(
            f"Unknown demo order status {status!r}. "
            f"Expected one of: {', '.join(sorted(allowed_statuses))}"
        )

    return status


# ==============================================================================
# helpers
# ==============================================================================


def _build_order_line_input(
    *,
    item: dict[str, int],
    products_by_internal_number: dict[int, Product],
) -> OrderLineInput:
    internal_number = item["internal_number"]

    if internal_number not in products_by_internal_number:
        raise ValueError(
            f"Order line references unknown product internal_number={internal_number}"
        )

    return OrderLineInput.boxes(
        product=products_by_internal_number[internal_number],
        boxes=item["boxes"],
    )


def _find_existing_product(item: dict[str, object]) -> Product | None:
    internal_number = int(item["internal_number"])

    if _model_has_field(Product, "internal_number"):
        product = Product.objects.filter(internal_number=internal_number).first()

        if product is not None:
            return product

    sku = _expected_sku_for_catalog_item(item)
    return Product.objects.filter(sku=sku).first()


def _expected_sku_for_catalog_item(item: dict[str, object]) -> str:
    internal_number = int(item["internal_number"])
    return f"SS-{internal_number:03d}"


def _product_key(item: dict[str, object]) -> str:
    return f"p{int(item['internal_number']):03d}"


def _product_internal_number(product: Product) -> int:
    internal_number = getattr(product, "internal_number", None)

    if internal_number is None:
        return product.pk or 0

    return int(internal_number)


def _primary_batch_boxes(internal_number: int) -> int:
    return 18 + ((internal_number * 7) % 36)


def _secondary_batch_boxes(internal_number: int) -> int:
    return 10 + ((internal_number * 5) % 28)


def _primary_batch_expiry_days(internal_number: int) -> int:
    # Mix critical, soon and safe expiry dates while keeping every primary batch
    # orderable.
    if internal_number % 19 == 0:
        return 9

    if internal_number % 5 == 0:
        return 28 + (internal_number % 10)

    return 70 + ((internal_number * 3) % 120)


def _shelf_letter(internal_number: int) -> str:
    letters = "ABCDEFGH"
    return letters[internal_number % len(letters)]


def _shelf_number(internal_number: int) -> int:
    return 1 + (internal_number % 4)


def _unwrap_product(result: Any) -> Product:
    item = getattr(result, "item", result)

    if not isinstance(item, Product):
        raise TypeError(f"Expected Product, got {type(item)!r}")

    return item


def _set_product_field_if_present(
    *,
    product: Product,
    field_name: str,
    value: object,
) -> None:
    if not _model_has_field(Product, field_name):
        return

    if getattr(product, field_name) == value:
        return

    setattr(product, field_name, value)
    product.save(update_fields=[field_name])


def _model_has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False

    return True


def _call_service(function: Callable[..., Any], **kwargs):
    """Call a service with only keyword arguments it currently accepts.

    This keeps the demo seed tolerant while service signatures are still being
    refined during the MVP.
    """

    signature = inspect.signature(function)
    accepted_parameters = signature.parameters

    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in accepted_parameters.values()
    ):
        return function(**kwargs)

    filtered_kwargs = {
        key: value
        for key, value in kwargs.items()
        if key in accepted_parameters
    }

    return function(**filtered_kwargs)


def _demo_cancel_reason() -> str:
    try:
        field = Order._meta.get_field("cancel_reason")
    except FieldDoesNotExist:
        return ""

    for value, _label in field.choices:
        if value:
            return value

    return ""
