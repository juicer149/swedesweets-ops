from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import (
    MagicMock,
    patch,
)

import pytest

from payments.contracts import HostedPaymentRequest
from payments.providers.sumup import (
    SumUpHostedPaymentProvider,
    SumUpPaymentError,
)


def _request() -> HostedPaymentRequest:
    return HostedPaymentRequest(
        reference="payment-42",
        amount=Decimal("25.00"),
        currency="EUR",
        description="SwedeSweets order 17",
        customer_return_url=(
            "https://shop.example.com/payment/return"
        ),
        webhook_url=(
            "https://shop.example.com/payment/webhook"
        ),
    )


def _urlopen_response(
    payload: dict[str, object],
):
    response = MagicMock()
    response.read.return_value = json.dumps(
        payload,
    ).encode("utf-8")

    context_manager = MagicMock()
    context_manager.__enter__.return_value = response

    return context_manager


def test_sumup_provider_creates_hosted_checkout():
    provider = SumUpHostedPaymentProvider(
        api_key="test-key",
        merchant_code="M123456",
    )

    with patch(
        "payments.providers.sumup.urlopen",
        return_value=_urlopen_response(
            {
                "id": "sumup-checkout-123",
                "hosted_checkout_url": (
                    "https://checkout.sumup.com/pay/123"
                ),
            }
        ),
    ) as mocked_urlopen:
        session = provider.create_payment(
            request=_request(),
        )

    assert (
        session.provider_payment_id
        == "sumup-checkout-123"
    )
    assert (
        session.redirect_url
        == "https://checkout.sumup.com/pay/123"
    )

    http_request = mocked_urlopen.call_args.args[0]

    assert (
        http_request.full_url
        == "https://api.sumup.com/v0.1/checkouts"
    )
    assert (
        http_request.headers["Authorization"]
        == "Bearer test-key"
    )

    payload = json.loads(
        http_request.data.decode("utf-8")
    )

    assert payload == {
        "checkout_reference": "payment-42",
        "amount": 25.0,
        "currency": "EUR",
        "merchant_code": "M123456",
        "description": "SwedeSweets order 17",
        "redirect_url": (
            "https://shop.example.com/payment/return"
        ),
        "return_url": (
            "https://shop.example.com/payment/webhook"
        ),
        "hosted_checkout": {
            "enabled": True,
        },
    }


def test_sumup_provider_rejects_missing_checkout_id():
    provider = SumUpHostedPaymentProvider(
        api_key="test-key",
        merchant_code="M123456",
    )

    with patch(
        "payments.providers.sumup.urlopen",
        return_value=_urlopen_response(
            {
                "hosted_checkout_url": (
                    "https://checkout.sumup.com/pay/123"
                ),
            }
        ),
    ):
        with pytest.raises(
            SumUpPaymentError,
            match="checkout id",
        ):
            provider.create_payment(
                request=_request(),
            )


def test_sumup_provider_rejects_missing_hosted_checkout_url():
    provider = SumUpHostedPaymentProvider(
        api_key="test-key",
        merchant_code="M123456",
    )

    with patch(
        "payments.providers.sumup.urlopen",
        return_value=_urlopen_response(
            {
                "id": "sumup-checkout-123",
            }
        ),
    ):
        with pytest.raises(
            SumUpPaymentError,
            match="hosted checkout URL",
        ):
            provider.create_payment(
                request=_request(),
            )


def test_sumup_provider_requires_credentials():
    with pytest.raises(
        ValueError,
        match="API key",
    ):
        SumUpHostedPaymentProvider(
            api_key="",
            merchant_code="M123456",
        )

    with pytest.raises(
        ValueError,
        match="merchant code",
    ):
        SumUpHostedPaymentProvider(
            api_key="test-key",
            merchant_code="",
        )
