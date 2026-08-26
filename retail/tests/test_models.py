from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from retail.tests.factories import retail_postal_area_factory


@pytest.mark.django_db
def test_retail_postal_area_normalizes_country_postal_code_and_city():
    area = retail_postal_area_factory(
        country_code=" fr ",
        postal_code=" 74000 ",
        city="  Annecy  ",
    )

    assert area.country_code == "FR"
    assert area.postal_code == "74000"
    assert area.city == "Annecy"


@pytest.mark.django_db
def test_retail_postal_area_collapses_city_whitespace():
    area = retail_postal_area_factory(
        city="La   Roche-sur-Foron",
    )

    assert area.city == "La Roche-sur-Foron"


@pytest.mark.django_db
def test_retail_postal_area_is_enabled_by_default():
    area = retail_postal_area_factory()

    assert area.enabled is True


@pytest.mark.django_db
def test_retail_postal_area_combination_must_be_unique():
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74000",
        city="Annecy",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            retail_postal_area_factory(
                country_code="FR",
                postal_code="74000",
                city="Annecy",
            )


@pytest.mark.django_db
def test_same_postal_code_can_represent_different_cities():
    first = retail_postal_area_factory(
        postal_code="74000",
        city="Annecy",
    )
    second = retail_postal_area_factory(
        postal_code="74000",
        city="Annecy Cedex",
    )

    assert first.pk != second.pk
