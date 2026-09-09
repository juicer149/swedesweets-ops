from __future__ import annotations

from decimal import Decimal

from django import forms

from pricing.models import CommercialPrice, PriceAmount


PRICE_DECIMAL_PLACES = 2
PRICE_MAX_DIGITS = 10

PRICING_STATUS_ACTIVE = "active"
PRICING_STATUS_INACTIVE = "inactive"

PRICING_STATUS_CHOICES = (
    (PRICING_STATUS_ACTIVE, "Active"),
    (PRICING_STATUS_INACTIVE, "Inactive"),
)


def _price_field(
    *,
    label: str,
) -> forms.DecimalField:
    return forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        max_digits=PRICE_MAX_DIGITS,
        decimal_places=PRICE_DECIMAL_PLACES,
        label=label,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "placeholder": "0.00",
            }
        ),
    )


def _status_field(
    *,
    label: str,
) -> forms.ChoiceField:
    return forms.ChoiceField(
        choices=PRICING_STATUS_CHOICES,
        initial=PRICING_STATUS_INACTIVE,
        label=label,
        widget=forms.RadioSelect(
            attrs={
                "class": "radio-chip-group",
            }
        ),
    )


class BatchPricingForm(forms.Form):
    reason = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Choose reason"),
            *CommercialPrice.Reason.choices,
        ),
        label="Reason",
    )

    business_eur = _price_field(
        label="EUR",
    )
    business_sek = _price_field(
        label="SEK",
    )
    business_status = _status_field(
        label="Status",
    )

    retail_eur = _price_field(
        label="EUR",
    )
    retail_sek = _price_field(
        label="SEK",
    )
    retail_status = _status_field(
        label="Status",
    )

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()

        self._validate_channel(
            cleaned_data=cleaned_data,
            channel_name="Business",
            eur_field="business_eur",
            sek_field="business_sek",
            status_field="business_status",
        )
        self._validate_channel(
            cleaned_data=cleaned_data,
            channel_name="Retail",
            eur_field="retail_eur",
            sek_field="retail_sek",
            status_field="retail_status",
        )

        has_pricing = any(
            cleaned_data.get(field_name) is not None
            for field_name in (
                "business_eur",
                "business_sek",
                "retail_eur",
                "retail_sek",
            )
        )

        if (
            has_pricing
            and not cleaned_data.get("reason")
        ):
            self.add_error(
                "reason",
                "Choose why this batch has special pricing.",
            )

        return cleaned_data

    @property
    def business_enabled(self) -> bool:
        return (
            self.cleaned_data["business_status"]
            == PRICING_STATUS_ACTIVE
        )

    @property
    def retail_enabled(self) -> bool:
        return (
            self.cleaned_data["retail_status"]
            == PRICING_STATUS_ACTIVE
        )

    def pricing_values(self) -> dict[str, object]:
        return {
            "reason": self.cleaned_data["reason"],
            "business_eur": self.cleaned_data[
                "business_eur"
            ],
            "business_sek": self.cleaned_data[
                "business_sek"
            ],
            "business_enabled": self.business_enabled,
            "retail_eur": self.cleaned_data[
                "retail_eur"
            ],
            "retail_sek": self.cleaned_data[
                "retail_sek"
            ],
            "retail_enabled": self.retail_enabled,
        }

    def _validate_channel(
        self,
        *,
        cleaned_data: dict[str, object],
        channel_name: str,
        eur_field: str,
        sek_field: str,
        status_field: str,
    ) -> None:
        if (
            cleaned_data.get(status_field)
            != PRICING_STATUS_ACTIVE
        ):
            return

        if (
            cleaned_data.get(eur_field) is not None
            or cleaned_data.get(sek_field) is not None
        ):
            return

        self.add_error(
            status_field,
            (
                f"{channel_name} pricing needs at least "
                f"one amount before it can be active."
            ),
        )


def build_batch_pricing_initial_data(
    *,
    business_price: CommercialPrice | None,
    retail_price: CommercialPrice | None,
) -> dict[str, object]:
    reason = _pricing_reason(
        business_price=business_price,
        retail_price=retail_price,
    )

    return {
        "reason": reason,
        "business_eur": _amount_value(
            commercial_price=business_price,
            currency=PriceAmount.Currency.EUR,
        ),
        "business_sek": _amount_value(
            commercial_price=business_price,
            currency=PriceAmount.Currency.SEK,
        ),
        "business_status": _pricing_status(
            business_price
        ),
        "retail_eur": _amount_value(
            commercial_price=retail_price,
            currency=PriceAmount.Currency.EUR,
        ),
        "retail_sek": _amount_value(
            commercial_price=retail_price,
            currency=PriceAmount.Currency.SEK,
        ),
        "retail_status": _pricing_status(
            retail_price
        ),
    }


def _amount_value(
    *,
    commercial_price: CommercialPrice | None,
    currency: str,
) -> Decimal | None:
    if commercial_price is None:
        return None

    for amount in commercial_price.amounts.all():
        if amount.currency == currency:
            return amount.price

    return None


def _pricing_status(
    commercial_price: CommercialPrice | None,
) -> str:
    if (
        commercial_price is not None
        and commercial_price.enabled
    ):
        return PRICING_STATUS_ACTIVE

    return PRICING_STATUS_INACTIVE


def _pricing_reason(
    *,
    business_price: CommercialPrice | None,
    retail_price: CommercialPrice | None,
) -> str:
    if business_price is not None and business_price.reason:
        return business_price.reason

    if retail_price is not None and retail_price.reason:
        return retail_price.reason

    return ""
