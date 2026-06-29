"""
Small pure helpers for table query URLs and sorting.

This module contains no Django model knowledge. It only knows how to normalize
sort values and build URLs from query parameters.
"""

from __future__ import annotations

from urllib.parse import urlencode

ASCENDING_DIRECTION = "asc"
DESCENDING_DIRECTION = "desc"


def normalize_sort(
    sort: str | None,
    *,
    allowed_sorts: dict[str, tuple[str, ...]],
    default_sort: str,
) -> str:
    if sort in allowed_sorts:
        return sort

    return default_sort


def sort_field(sort: str) -> str:
    return sort.removeprefix("-")


def sort_direction(sort: str) -> str:
    if sort.startswith("-"):
        return DESCENDING_DIRECTION

    return ASCENDING_DIRECTION


def sort_value(
    *,
    field: str,
    direction: str,
) -> str:
    if direction == DESCENDING_DIRECTION:
        return f"-{field}"

    return field


def next_sort_for_field(
    *,
    field: str,
    active_sort: str,
) -> str:
    if sort_field(active_sort) != field:
        return field

    if sort_direction(active_sort) == ASCENDING_DIRECTION:
        return f"-{field}"

    return field


def build_query_url(
    *,
    base_path: str,
    params: dict[str, str],
    anchor: str = "",
) -> str:
    query_string = urlencode({key: value for key, value in params.items() if value})

    url = base_path

    if query_string:
        url = f"{url}?{query_string}"

    if anchor:
        url = f"{url}#{anchor}"

    return url
