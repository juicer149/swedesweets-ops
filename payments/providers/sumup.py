from __future__ import annotations

import json
from decimal import Decimal
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.request import (
    Request,
    urlopen,
)

from payments.contracts import (
    HostedPaymentRequest,
    HostedPaymentSession,
)


SUMUP_API_BASE_URL = "https://api.sumup.com"
SUMUP_CHECKOUTS_PATH = "/v0.1/checkouts"


class SumUpPaymentError(RuntimeError):
    """Raised when SumUp cannot create a hosted payment checkout."""


class SumUpHostedPaymentProvider:
    """Create hosted SumUp checkout sessions.

    This adapter owns only SumUp-specific HTTP and payload mapping.
    """

    def __init__(
        self,
        *,
        api_key: str,
        merchant_code: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        api_key = api_key.strip()
        merchant_code = merchant_code.strip()

        if not api_key:
            raise ValueError(
                "SumUp API key is required"
            )

        if not merchant_code:
            raise ValueError(
                "SumUp merchant code is required"
            )

        self._api_key = api_key
        self._merchant_code = merchant_code
        self._timeout_seconds = timeout_seconds

    def create_payment(
        self,
        *,
        request: HostedPaymentRequest,
    ) -> HostedPaymentSession:
        payload = {
            "checkout_reference": request.reference,
            "amount": _decimal_to_json_number(
                request.amount,
            ),
            "currency": request.currency,
            "merchant_code": self._merchant_code,
            "description": request.description,
            "redirect_url": request.customer_return_url,
            "return_url": request.webhook_url,
            "hosted_checkout": {
                "enabled": True,
            },
        }

        response = self._post_json(
            path=SUMUP_CHECKOUTS_PATH,
            payload=payload,
        )

        provider_payment_id = response.get(
            "id"
        )
        redirect_url = response.get(
            "hosted_checkout_url"
        )

        if not isinstance(
            provider_payment_id,
            str,
        ) or not provider_payment_id:
            raise SumUpPaymentError(
                "SumUp checkout response has no checkout id"
            )

        if not isinstance(
            redirect_url,
            str,
        ) or not redirect_url:
            raise SumUpPaymentError(
                "SumUp checkout response has no hosted checkout URL"
            )

        return HostedPaymentSession(
            provider_payment_id=provider_payment_id,
            redirect_url=redirect_url,
        )

    def _post_json(
        self,
        *,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        body = json.dumps(
            payload,
        ).encode("utf-8")

        http_request = Request(
            url=f"{SUMUP_API_BASE_URL}{path}",
            data=body,
            method="POST",
            headers={
                "Authorization": (
                    f"Bearer {self._api_key}"
                ),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(
                http_request,
                timeout=self._timeout_seconds,
            ) as response:
                response_body = response.read()

        except HTTPError as exc:
            raise SumUpPaymentError(
                f"SumUp returned HTTP {exc.code}"
            ) from exc

        except URLError as exc:
            raise SumUpPaymentError(
                "Could not reach SumUp"
            ) from exc

        try:
            data = json.loads(
                response_body,
            )
        except json.JSONDecodeError as exc:
            raise SumUpPaymentError(
                "SumUp returned invalid JSON"
            ) from exc

        if not isinstance(
            data,
            dict,
        ):
            raise SumUpPaymentError(
                "SumUp returned an invalid checkout response"
            )

        return data


def _decimal_to_json_number(
    value: Decimal,
) -> float:
    return float(value)
