from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


# Ops policy:
# A batch is considered critical when best_before is this many days away.
EXPIRY_CRITICAL_DAYS = 60
# A batch is considered soon when best_before is this many days away.
EXPIRY_SOON_DAYS = 90

# Ops policy:
# A batch is no longer orderable when best_before is this many days away.
#
# 0 means:
#   best_before <= today  -> not orderable
#   best_before > today   -> orderable
#
# If the client later wants to stop selling 14 days before expiry,
# change this to 14.
ORDERABLE_BEFORE_EXPIRY_DAYS = 0


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


def orderable_best_before_cutoff(*, today: date) -> date:
    return today + timedelta(days=ORDERABLE_BEFORE_EXPIRY_DAYS)


def is_orderable_best_before(*, best_before: date, today: date) -> bool:
    return best_before > orderable_best_before_cutoff(today=today)


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
