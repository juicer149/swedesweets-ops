from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


EXPIRY_CRITICAL_DAYS = 60
EXPIRY_SOON_DAYS = 90


class ExpiryState(StrEnum):
    EXPIRED = "expired"
    CRITICAL = "critical"
    SOON = "soon"
    SAFE = "safe"


@dataclass(frozen=True)
class ExpiryInfo:
    state: ExpiryState
    label: str
    days_left: int


def build_expiry_info(
    *,
    best_before: date,
    today: date,
) -> ExpiryInfo:
    days_left = (best_before - today).days

    if days_left < 0:
        return ExpiryInfo(
            state=ExpiryState.EXPIRED,
            label="Expired",
            days_left=days_left,
        )

    if days_left == 0:
        return ExpiryInfo(
            state=ExpiryState.CRITICAL,
            label="Expires today",
            days_left=days_left,
        )

    if days_left <= EXPIRY_CRITICAL_DAYS:
        return ExpiryInfo(
            state=ExpiryState.CRITICAL,
            label=f"Expires in {days_left} days",
            days_left=days_left,
        )

    if days_left <= EXPIRY_SOON_DAYS:
        return ExpiryInfo(
            state=ExpiryState.SOON,
            label=f"Expires in {days_left} days",
            days_left=days_left,
        )

    return ExpiryInfo(
        state=ExpiryState.SAFE,
        label="Best before",
        days_left=days_left,
    )
