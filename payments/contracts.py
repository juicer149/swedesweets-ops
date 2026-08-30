from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class ExternalPaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class HostedPaymentRequest:
    reference: str
    amount: Decimal
    currency: str
    description: str
    customer_return_url: str
    webhook_url: str


@dataclass(frozen=True, slots=True)
class HostedPaymentSession:
    provider_payment_id: str
    redirect_url: str


@dataclass(frozen=True, slots=True)
class ExternalPaymentState:
    provider_payment_id: str
    status: ExternalPaymentStatus
    provider_transaction_id: str | None = None
    hosted_payment_url: str | None = None


class HostedPaymentProvider(Protocol):
    def create_payment(
        self,
        *,
        request: HostedPaymentRequest,
    ) -> HostedPaymentSession:
        ...

    def get_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> ExternalPaymentState:
        ...
