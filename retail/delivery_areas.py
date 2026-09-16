from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from retail.models import (
    RetailPostalArea,
    normalize_city,
    normalize_country_code,
    normalize_postal_code,
)


RETAIL_SERVICE_COUNTRY = "FR"
RETAIL_SERVICE_DEPARTMENT_PREFIX = "74"


class PostalAreaFetchError(Exception):
    """Raised when upstream postal-area data cannot be trusted."""


@dataclass(frozen=True, slots=True)
class PostalAreaRecord:
    country_code: str
    postal_code: str
    city: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.country_code, self.postal_code, self.city)


@dataclass(frozen=True, slots=True)
class PostalAreaSyncResult:
    fetched: int
    created: int
    unchanged: int
    stale: tuple[PostalAreaRecord, ...]


def fetch_postal_areas() -> list[PostalAreaRecord]:
    """Return the current reference set of deliverable postal areas.

    v1: a hardcoded seed for departement 74 (Haute-Savoie), scoped to the
    Chamonix area. This will later be replaced by a call to
    geo.api.gouv.fr for the same departement, without changing the
    contract this function returns to `sync_retail_postal_areas`.

    Note: identity here is (country_code, postal_code, city). If an
    upstream source later renames a commune, that is treated as a new
    postal area (old key becomes stale, new key is created) rather than
    as a rename of the same destination. This is a deliberate v1
    limitation, not an oversight - see delivery-area sync design notes.
    """

    raw_records = [
        ("FR", "74400", "Chamonix-Mont-Blanc"),
        ("FR", "74310", "Les Houches"),
        ("FR", "74170", "Saint-Gervais-les-Bains"),
        ("FR", "74190", "Passy"),
        ("FR", "74300", "Sallanches"),
    ]

    records = [
        _normalize_record(
            country_code=country_code,
            postal_code=postal_code,
            city=city,
        )
        for country_code, postal_code, city in raw_records
    ]

    _validate_records(records)

    return _deduplicate(records)


@transaction.atomic
def sync_retail_postal_areas() -> PostalAreaSyncResult:
    """Add newly known postal areas without touching existing rows.

    Fetch and validation happen before this function is called
    (`fetch_postal_areas` runs first, outside any lock), so no network
    I/O occurs inside the transaction.

    Existing rows, including their local `enabled` override, are never
    modified or deleted. Postal areas that used to be known locally but
    are no longer present upstream are reported as stale for manual
    review; they are not disabled or removed automatically.
    """

    fetched_records = fetch_postal_areas()

    fetched_by_key = {
        record.key: record
        for record in fetched_records
    }

    existing_keys = set(
        RetailPostalArea.objects
        .values_list("country_code", "postal_code", "city")
    )

    new_keys = set(fetched_by_key) - existing_keys
    stale_keys = existing_keys - set(fetched_by_key)

    if new_keys:
        RetailPostalArea.objects.bulk_create(
            [
                RetailPostalArea(
                    country_code=key[0],
                    postal_code=key[1],
                    city=key[2],
                    enabled=True,
                )
                for key in new_keys
            ]
        )

    stale_records = tuple(
        PostalAreaRecord(
            country_code=key[0],
            postal_code=key[1],
            city=key[2],
        )
        for key in sorted(stale_keys)
    )

    return PostalAreaSyncResult(
        fetched=len(fetched_by_key),
        created=len(new_keys),
        unchanged=len(fetched_by_key) - len(new_keys),
        stale=stale_records,
    )


def _normalize_record(
    *,
    country_code: str,
    postal_code: str,
    city: str,
) -> PostalAreaRecord:
    return PostalAreaRecord(
        country_code=normalize_country_code(country_code),
        postal_code=normalize_postal_code(postal_code),
        city=normalize_city(city),
    )


def _validate_records(
    records: list[PostalAreaRecord],
) -> None:
    if not records:
        raise PostalAreaFetchError(
            "postal-area fetch returned no records"
        )

    for record in records:
        if record.country_code != RETAIL_SERVICE_COUNTRY:
            raise PostalAreaFetchError(
                f"postal area {record.postal_code} is outside the "
                f"supported country {RETAIL_SERVICE_COUNTRY}"
            )

        if not record.postal_code.startswith(
            RETAIL_SERVICE_DEPARTMENT_PREFIX
        ):
            raise PostalAreaFetchError(
                f"postal area {record.postal_code} is outside "
                f"departement {RETAIL_SERVICE_DEPARTMENT_PREFIX}"
            )

        if not record.city:
            raise PostalAreaFetchError(
                f"postal area {record.postal_code} is missing a city"
            )


def _deduplicate(
    records: list[PostalAreaRecord],
) -> list[PostalAreaRecord]:
    deduplicated: dict[tuple[str, str, str], PostalAreaRecord] = {}

    for record in records:
        deduplicated[record.key] = record

    return list(deduplicated.values())
