"""
Customer domain model.

class Customer
fields:
    name, email, phone_number, country, city, address_line

public API:
    .save(*args, **kwargs)
        -> Normalize customer fields before saving.

    .country_name -> str
        -> Return the display name for the stored country code.

    .address -> str
        -> Return a formatted address for display and map links.
"""

from __future__ import annotations

from django.db import models

from customers.errors import InvalidCustomerData


MAX_CUSTOMER_NAME_LENGTH = 120
MAX_CUSTOMER_COUNTRY_LENGTH = 80
MAX_CUSTOMER_CITY_LENGTH = 120
MAX_CUSTOMER_ADDRESS_LINE_LENGTH = 180
MAX_CUSTOMER_PHONE_LENGTH = 40

CUSTOMER_COUNTRY_LABELS = {
    "FR": "France",
    "CH": "Switzerland",
    "IT": "Italy",
}

CUSTOMER_COUNTRY_CODES = frozenset(CUSTOMER_COUNTRY_LABELS)


def _normalize_required_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    value = " ".join(value.strip().split())

    if not value:
        raise InvalidCustomerData(f"{field_name} must not be empty")

    if len(value) > max_length:
        raise InvalidCustomerData(
            f"{field_name} must be at most {max_length} characters"
        )

    return value


def normalize_customer_name(value: str) -> str:
    return _normalize_required_text(
        value,
        field_name="customer name",
        max_length=MAX_CUSTOMER_NAME_LENGTH,
    )


def normalize_customer_country(value: str) -> str:
    value = value.strip().upper()

    if not value:
        raise InvalidCustomerData("customer country must not be empty")

    if len(value) > MAX_CUSTOMER_COUNTRY_LENGTH:
        raise InvalidCustomerData(
            f"customer country must be at most "
            f"{MAX_CUSTOMER_COUNTRY_LENGTH} characters"
        )

    if value not in CUSTOMER_COUNTRY_CODES:
        raise InvalidCustomerData(f"unsupported customer country {value!r}")

    return value


def normalize_customer_city(value: str) -> str:
    return _normalize_required_text(
        value,
        field_name="customer city",
        max_length=MAX_CUSTOMER_CITY_LENGTH,
    )


def normalize_customer_address_line(value: str) -> str:
    return _normalize_required_text(
        value,
        field_name="customer address",
        max_length=MAX_CUSTOMER_ADDRESS_LINE_LENGTH,
    )


def normalize_customer_email(value: str) -> str:
    value = value.strip().lower()

    if not value:
        raise InvalidCustomerData("customer email must not be empty")

    return value


def normalize_customer_phone_number(value: str) -> str:
    value = "".join(
        character
        for character in value.strip()
        if not character.isspace() and character != "-"
    )

    if not value:
        raise InvalidCustomerData("customer phone number must not be empty")

    if len(value) > MAX_CUSTOMER_PHONE_LENGTH:
        raise InvalidCustomerData(
            f"customer phone number must be at most "
            f"{MAX_CUSTOMER_PHONE_LENGTH} characters"
        )

    return value


class Customer(models.Model):
    name = models.CharField(max_length=MAX_CUSTOMER_NAME_LENGTH)
    email = models.EmailField(max_length=254, unique=True)
    phone_number = models.CharField(max_length=MAX_CUSTOMER_PHONE_LENGTH)

    country = models.CharField(max_length=MAX_CUSTOMER_COUNTRY_LENGTH)
    city = models.CharField(max_length=MAX_CUSTOMER_CITY_LENGTH)
    address_line = models.CharField(max_length=MAX_CUSTOMER_ADDRESS_LINE_LENGTH)

    # Additional field to support soft deletion of customers.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "email"]

    @property
    def country_name(self) -> str:
        return CUSTOMER_COUNTRY_LABELS.get(self.country, self.country)

    @property
    def address(self) -> str:
        return f"{self.address_line}, {self.city}, {self.country_name}"

    def save(self, *args, **kwargs) -> None:
        """Normalize customer fields before saving."""

        update_fields = kwargs.get("update_fields")

        if update_fields is not None:
            update_fields = set(update_fields)

        should_save_all_fields = update_fields is None
        should_handle_name = should_save_all_fields or "name" in update_fields
        should_handle_email = should_save_all_fields or "email" in update_fields
        should_handle_phone = should_save_all_fields or "phone_number" in update_fields
        should_handle_country = should_save_all_fields or "country" in update_fields
        should_handle_city = should_save_all_fields or "city" in update_fields
        should_handle_address_line = (
            should_save_all_fields
            or "address_line" in update_fields
        )

        if should_handle_name:
            self.name = normalize_customer_name(self.name)

        if should_handle_email:
            self.email = normalize_customer_email(self.email)

        if should_handle_phone:
            self.phone_number = normalize_customer_phone_number(self.phone_number)

        if should_handle_country:
            self.country = normalize_customer_country(self.country)

        if should_handle_city:
            self.city = normalize_customer_city(self.city)

        if should_handle_address_line:
            self.address_line = normalize_customer_address_line(self.address_line)

        if update_fields is not None:
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
