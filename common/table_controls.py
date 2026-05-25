"""
Reusable table control view models.

This module builds links for table filters, desktop sort headers and mobile sort
controls.

It does not render HTML.
It does not query the database.
It does not know about any specific app.

A page decides which components it wants to render:

    {% include "includes/table/filter_chips.html" %}
    {% include "includes/table/sort_select.html" %}
    {% include "includes/table/sort_headers.html" %}

This module only prepares the data those components need.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.table_tools import (
    build_query_url,
    next_sort_for_field,
    normalize_sort,
    sort_direction,
    sort_field,
    sort_value,
)


@dataclass(frozen=True)
class TableFilter:
    value: str
    label: str


@dataclass(frozen=True)
class TableSortField:
    field: str
    label: str


@dataclass(frozen=True)
class TableFilterLink:
    value: str
    label: str
    url: str
    is_active: bool


@dataclass(frozen=True)
class TableSortLink:
    field: str
    label: str
    url: str
    is_active: bool
    direction: str

@dataclass(frozen=True)
class QuickJumpOption:
    label: str
    url: str


@dataclass(frozen=True)
class QuickJumpSearch:
    title: str
    title_id: str
    select_id: str
    placeholder: str
    aria_label: str
    options: list[QuickJumpOption]

@dataclass(frozen=True)
class MobileSortDirection:
    label: str
    symbol: str
    url: str


@dataclass(frozen=True)
class TableControlsTemplate:
    filters_title_id: str
    filters_aria_label: str
    sort_title_id: str
    sort_select_id: str


@dataclass(frozen=True)
class TableControls:
    base_path: str
    anchor: str = ""
    active_filter: str = ""
    active_sort: str = ""
    filter_query_key: str = ""
    default_sort: str = ""

    @classmethod
    def from_request_values(
        cls,
        *,
        base_path: str,
        anchor: str = "",
        requested_filter: str | None = None,
        requested_sort: str | None = None,
        filters: list[TableFilter] | None = None,
        allowed_sorts: dict[str, tuple[str, ...]] | None = None,
        default_sort: str = "",
        filter_query_key: str = "",
    ) -> TableControls:
        filters = filters or [] 
        allowed_sorts = allowed_sorts or {}

        active_filter = _normalize_filter(
            requested_filter,
            filters=filters,
        )
        active_sort = _normalize_optional_sort(
            requested_sort,
            allowed_sorts=allowed_sorts,
            default_sort=default_sort,
        )

        return cls(
            base_path=base_path,
            anchor=anchor,
            active_filter=active_filter,
            active_sort=active_sort,
            filter_query_key=filter_query_key,
            default_sort=default_sort,
        )

    def build_filter_links(
        self,
        filters: list[TableFilter],
    ) -> list[TableFilterLink]:
        return [
            TableFilterLink(
                value=filter_.value,
                label=filter_.label,
                url=self._build_url(
                    filter_value=filter_.value,
                    sort=self.active_sort,
                ),
                is_active=filter_.value == self.active_filter,
            )
            for filter_ in filters
        ]

    def build_table_sort_links(
        self,
        sort_fields: list[TableSortField],
    ) -> list[TableSortLink]:
        if not self.active_sort:
            return []

        active_field = sort_field(self.active_sort)

        return [
            TableSortLink(
                field=sort.field,
                label=sort.label,
                url=self._build_url(
                    filter_value=self.active_filter,
                    sort=next_sort_for_field(
                        field=sort.field,
                        active_sort=self.active_sort,
                    ),
                ),
                is_active=active_field == sort.field,
                direction=(
                    sort_direction(self.active_sort)
                    if active_field == sort.field
                    else ""
                ),
            )
            for sort in sort_fields
        ]

    def build_mobile_sort_fields(
        self,
        sort_fields: list[TableSortField],
    ) -> list[TableSortLink]:
        if not self.active_sort:
            return []

        active_field = sort_field(self.active_sort)
        active_direction = sort_direction(self.active_sort)

        return [
            TableSortLink(
                field=sort.field,
                label=sort.label,
                url=self._build_url(
                    filter_value=self.active_filter,
                    sort=sort_value(
                        field=sort.field,
                        direction=active_direction,
                    ),
                ),
                is_active=active_field == sort.field,
                direction=active_direction if active_field == sort.field else "",
            )
            for sort in sort_fields
        ]

    def build_mobile_sort_direction(self) -> MobileSortDirection | None:
        if not self.active_sort:
            return None

        active_field = sort_field(self.active_sort)
        active_direction = sort_direction(self.active_sort)
        next_direction = (
            "desc"
            if active_direction == "asc"
            else "asc"
        )

        return MobileSortDirection(
            label=(
                "Descending"
                if active_direction == "asc"
                else "Ascending"
            ),
            symbol=(
                "↓"
                if active_direction == "asc"
                else "↑"
            ),
            url=self._build_url(
                filter_value=self.active_filter,
                sort=sort_value(
                    field=active_field,
                    direction=next_direction,
                ),
            ),
        )

    def _build_url(
        self,
        *,
        filter_value: str,
        sort: str,
    ) -> str:
        params: dict[str, str] = {}

        if filter_value and self.filter_query_key:
            params[self.filter_query_key] = filter_value

        if sort and sort != self.default_sort:
            params["sort"] = sort

        return build_query_url(
            base_path=self.base_path,
            anchor=self.anchor,
            params=params,
        )


def _normalize_filter(
    requested_filter: str | None,
    *,
    filters: list[TableFilter],
) -> str:
    requested_filter = requested_filter or ""

    if not filters:
        return ""

    allowed_values = {
        filter_.value
        for filter_ in filters
    }

    if requested_filter in allowed_values:
        return requested_filter

    return ""


def _normalize_optional_sort(
    requested_sort: str | None,
    *,
    allowed_sorts: dict[str, tuple[str, ...]],
    default_sort: str,
) -> str:
    if not allowed_sorts or not default_sort:
        return ""

    return normalize_sort(
        requested_sort,
        allowed_sorts=allowed_sorts,
        default_sort=default_sort,
    )
