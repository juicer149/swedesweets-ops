from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


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


class HostedPaymentProvider(Protocol):
    def create_payment(
        self,
        *,
        request: HostedPaymentRequest,
    ) -> HostedPaymentSession:
        ...
