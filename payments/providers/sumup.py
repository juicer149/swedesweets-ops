from __future__ import annotations

import json
from decimal import Decimal
from urllib.error import (
    HTTPError,
    URLError,
)
from urllib.parse import quote
from urllib.request import (
    Request,
    urlopen,
)

from payments.contracts import (
    ExternalPaymentState,
    ExternalPaymentStatus,
    HostedPaymentRequest,
    HostedPaymentSession,
)


SUMUP_API_BASE_URL = "https://api.sumup.com"
SUMUP_CHECKOUTS_PATH = "/v0.1/checkouts"


class SumUpPaymentError(RuntimeError):
    """Raised when communication with SumUp cannot be trusted."""


class SumUpHostedPaymentProvider:
    """Adapter between our payment contract and SumUp Online Payments."""

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

        response = self._request_json(
            method="POST",
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

    def get_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> ExternalPaymentState:
        """Retrieve and normalize the current SumUp checkout state."""

        provider_payment_id = (
            provider_payment_id.strip()
        )

        if not provider_payment_id:
            raise ValueError(
                "provider payment id is required"
            )

        encoded_id = quote(
            provider_payment_id,
            safe="",
        )

        response = self._request_json(
            method="GET",
            path=(
                f"{SUMUP_CHECKOUTS_PATH}/"
                f"{encoded_id}"
            ),
        )

        response_id = response.get(
            "id"
        )

        if (
            not isinstance(response_id, str)
            or response_id != provider_payment_id
        ):
            raise SumUpPaymentError(
                "SumUp returned an unexpected checkout id"
            )

        status = response.get(
            "status"
        )

        if status == "PENDING":
            return ExternalPaymentState(
                provider_payment_id=response_id,
                status=ExternalPaymentStatus.PENDING,
            )

        if status in {
            "FAILED",
            "EXPIRED",
        }:
            return ExternalPaymentState(
                provider_payment_id=response_id,
                status=ExternalPaymentStatus.FAILED,
            )

        if status == "PAID":
            transaction_id = response.get(
                "transaction_id"
            )

            if not isinstance(
                transaction_id,
                str,
            ) or not transaction_id:
                raise SumUpPaymentError(
                    "paid SumUp checkout has no transaction id"
                )

            return ExternalPaymentState(
                provider_payment_id=response_id,
                status=ExternalPaymentStatus.SUCCEEDED,
                provider_transaction_id=transaction_id,
            )

        raise SumUpPaymentError(
            f"unsupported SumUp checkout status: {status!r}"
        )

    def _request_json(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        body = None

        if payload is not None:
            body = json.dumps(
                payload,
            ).encode("utf-8")

        http_request = Request(
            url=f"{SUMUP_API_BASE_URL}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": (
                    f"Bearer {self._api_key}"
                ),
                "Accept": "application/json",
                "Content-Type": "application/json",
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
