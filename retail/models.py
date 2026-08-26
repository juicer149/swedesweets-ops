from __future__ import annotations

from django.db import models


MAX_RETAIL_COUNTRY_CODE_LENGTH = 2
MAX_RETAIL_POSTAL_CODE_LENGTH = 10
MAX_RETAIL_CITY_LENGTH = 120


def normalize_country_code(value: str) -> str:
    return value.strip().upper()


def normalize_postal_code(value: str) -> str:
    return value.strip()


def normalize_city(value: str) -> str:
    return " ".join(value.strip().split())


class RetailPostalArea(models.Model):
    """A destination where retail orders may be delivered.

    Postal areas are reference data, expected to be populated from an
    authoritative external source.

    `enabled` is a local business override. It allows SwedeSweets to disable a
    destination without deleting the underlying postal reference data.
    """

    country_code = models.CharField(
        max_length=MAX_RETAIL_COUNTRY_CODE_LENGTH,
    )
    postal_code = models.CharField(
        max_length=MAX_RETAIL_POSTAL_CODE_LENGTH,
    )
    city = models.CharField(
        max_length=MAX_RETAIL_CITY_LENGTH,
    )

    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "country_code",
            "postal_code",
            "city",
        ]
        indexes = [
            models.Index(fields=["country_code", "postal_code"]),
            models.Index(fields=["enabled"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "country_code",
                    "postal_code",
                    "city",
                ],
                name="unique_retail_postal_area",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        self.country_code = normalize_country_code(self.country_code)
        self.postal_code = normalize_postal_code(self.postal_code)
        self.city = normalize_city(self.city)

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.postal_code} {self.city}, {self.country_code}"
