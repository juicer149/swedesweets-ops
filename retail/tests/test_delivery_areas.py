from __future__ import annotations

import logging
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from retail.delivery_areas import (
    PostalAreaFetchError,
    PostalAreaRecord,
    PostalAreaSyncResult,
    fetch_postal_areas,
    sync_retail_postal_areas,
)
from retail.models import RetailPostalArea
from retail.tests.factories import retail_postal_area_factory


def _fake_fetch(*records: tuple[str, str, str]):
    def _fetch() -> list[PostalAreaRecord]:
        return [
            PostalAreaRecord(
                country_code=country_code,
                postal_code=postal_code,
                city=city,
            )
            for country_code, postal_code, city in records
        ]

    return _fetch


@pytest.mark.django_db
def test_fetch_postal_areas_only_returns_department_74_in_france():
    records = fetch_postal_areas()

    assert records

    for record in records:
        assert record.country_code == "FR"
        assert record.postal_code.startswith("74")
        assert record.city


@pytest.mark.django_db
def test_sync_creates_previously_unknown_postal_areas(monkeypatch):
    monkeypatch.setattr(
        "retail.delivery_areas.fetch_postal_areas",
        _fake_fetch(
            ("FR", "74400", "Chamonix-Mont-Blanc"),
            ("FR", "74310", "Les Houches"),
        ),
    )

    result = sync_retail_postal_areas()

    assert result == PostalAreaSyncResult(
        fetched=2,
        created=2,
        unchanged=0,
        stale=(),
    )

    created = RetailPostalArea.objects.get(
        postal_code="74400",
        city="Chamonix-Mont-Blanc",
    )

    assert created.enabled is True


@pytest.mark.django_db
def test_sync_leaves_existing_enabled_true_area_untouched(monkeypatch):
    area = retail_postal_area_factory(
        country_code="FR",
        postal_code="74400",
        city="Chamonix-Mont-Blanc",
        enabled=True,
    )
    original_updated_at = area.updated_at

    monkeypatch.setattr(
        "retail.delivery_areas.fetch_postal_areas",
        _fake_fetch(
            ("FR", "74400", "Chamonix-Mont-Blanc"),
        ),
    )

    result = sync_retail_postal_areas()

    area.refresh_from_db()

    assert result == PostalAreaSyncResult(
        fetched=1,
        created=0,
        unchanged=1,
        stale=(),
    )
    assert area.enabled is True
    assert area.updated_at == original_updated_at


@pytest.mark.django_db
def test_sync_leaves_existing_disabled_area_disabled(monkeypatch):
    area = retail_postal_area_factory(
        country_code="FR",
        postal_code="74400",
        city="Chamonix-Mont-Blanc",
        enabled=False,
    )

    monkeypatch.setattr(
        "retail.delivery_areas.fetch_postal_areas",
        _fake_fetch(
            ("FR", "74400", "Chamonix-Mont-Blanc"),
        ),
    )

    result = sync_retail_postal_areas()

    area.refresh_from_db()

    assert result.created == 0
    assert result.unchanged == 1
    assert area.enabled is False


@pytest.mark.django_db
def test_sync_reports_stale_areas_without_deleting_or_disabling(monkeypatch):
    area = retail_postal_area_factory(
        country_code="FR",
        postal_code="74999",
        city="Ghost Town",
        enabled=True,
    )

    monkeypatch.setattr(
        "retail.delivery_areas.fetch_postal_areas",
        _fake_fetch(
            ("FR", "74400", "Chamonix-Mont-Blanc"),
        ),
    )

    result = sync_retail_postal_areas()

    area.refresh_from_db()

    assert result.created == 1
    assert result.stale == (
        PostalAreaRecord(
            country_code="FR",
            postal_code="74999",
            city="Ghost Town",
        ),
    )

    assert RetailPostalArea.objects.filter(pk=area.pk).exists()
    assert area.enabled is True


@pytest.mark.django_db
def test_sync_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        "retail.delivery_areas.fetch_postal_areas",
        _fake_fetch(
            ("FR", "74400", "Chamonix-Mont-Blanc"),
            ("FR", "74310", "Les Houches"),
        ),
    )

    first = sync_retail_postal_areas()
    second = sync_retail_postal_areas()

    assert first.created == 2
    assert second.created == 0
    assert second.unchanged == 2

    assert RetailPostalArea.objects.count() == 2


@pytest.mark.django_db
def test_fetch_failure_leaves_database_untouched(monkeypatch):
    retail_postal_area_factory(
        country_code="FR",
        postal_code="74400",
        city="Chamonix-Mont-Blanc",
    )

    def _broken_fetch() -> list[PostalAreaRecord]:
        raise PostalAreaFetchError("upstream source returned no records")

    monkeypatch.setattr(
        "retail.delivery_areas.fetch_postal_areas",
        _broken_fetch,
    )

    with pytest.raises(
        PostalAreaFetchError,
        match="upstream source returned no records",
    ):
        sync_retail_postal_areas()

    assert RetailPostalArea.objects.count() == 1


@pytest.mark.django_db
def test_sync_retail_postal_areas_management_command_reports_summary(
    monkeypatch,
):
    result = PostalAreaSyncResult(
        fetched=5,
        created=1,
        unchanged=4,
        stale=(),
    )

    monkeypatch.setattr(
        "retail.management.commands.sync_retail_postal_areas."
        "sync_retail_postal_areas",
        lambda: result,
    )

    stdout = StringIO()

    call_command(
        "sync_retail_postal_areas",
        stdout=stdout,
    )

    output = stdout.getvalue()

    assert "Fetched:   5" in output
    assert "Created:   1" in output
    assert "Unchanged: 4" in output
    assert "Stale:     0" in output


def test_command_aborts_with_command_error_on_fetch_failure(monkeypatch):
    def _broken_sync() -> PostalAreaSyncResult:
        raise PostalAreaFetchError("upstream source returned no records")

    monkeypatch.setattr(
        "retail.management.commands.sync_retail_postal_areas."
        "sync_retail_postal_areas",
        _broken_sync,
    )

    with pytest.raises(
        CommandError,
        match="retail postal-area sync aborted",
    ):
        call_command(
            "sync_retail_postal_areas",
            stdout=StringIO(),
        )


def test_command_logs_a_single_warning_when_stale_areas_are_found(
    monkeypatch,
    caplog,
):
    stale_record = PostalAreaRecord(
        country_code="FR",
        postal_code="74999",
        city="Ghost Town",
    )
    result = PostalAreaSyncResult(
        fetched=1,
        created=0,
        unchanged=1,
        stale=(stale_record,),
    )

    monkeypatch.setattr(
        "retail.management.commands.sync_retail_postal_areas."
        "sync_retail_postal_areas",
        lambda: result,
    )

    with caplog.at_level(logging.WARNING):
        call_command(
            "sync_retail_postal_areas",
            stdout=StringIO(),
        )

    warnings = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING
    ]

    assert len(warnings) == 1
    assert "74999" in warnings[0].getMessage()
