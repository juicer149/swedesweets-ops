from __future__ import annotations

from decimal import Decimal

from django import forms

from common.form_layout import set_form_field_layout
from pricing.models import CommercialPrice, PriceAmount


PRICE_DECIMAL_PLACES = 2
PRICE_MAX_DIGITS = 10

PRICING_STATUS_ACTIVE = "active"
PRICING_STATUS_INACTIVE = "inactive"

BUSINESS_STATUS_HELP_TEXT = (
    "Active means the product can be ordered in the B2B portal. "
    "A price is optional; inactive hides the product from B2B ordering."
)

RETAIL_STATUS_HELP_TEXT = (
    "Active retail pricing needs at least one currency amount."
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
        error_messages={
            "invalid": "Enter a valid price.",
            "min_value": "Price must be greater than zero.",
            "max_digits": "Price is too large.",
            "max_decimal_places": (
                "Use at most two decimal places."
            ),
        },
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "placeholder": "0.00",
            }
        ),
    )


def _pricing_status_field(
    *,
    help_text: str = "",
    initial: str = PRICING_STATUS_INACTIVE,
) -> forms.ChoiceField:
    return forms.ChoiceField(
        choices=(
            (
                PRICING_STATUS_ACTIVE,
                "Active",
            ),
            (
                PRICING_STATUS_INACTIVE,
                "Inactive",
            ),
        ),
        initial=initial,
        label="Status",
        help_text=help_text,
        error_messages={
            "required": "Choose pricing status.",
            "invalid_choice": (
                "Choose a valid pricing status."
            ),
        },
        widget=forms.RadioSelect(
            attrs={
                "class": "radio-chip-group",
            }
        ),
    )


class ProductPricingForm(forms.Form):
    business_eur = _price_field(
        label="EUR",
    )
    business_sek = _price_field(
        label="SEK",
    )
    # New products are orderable in B2B by default, matching the historical
    # behavior and the 2b data migration (standard offers created enabled).
    business_status = _pricing_status_field(
        help_text=BUSINESS_STATUS_HELP_TEXT,
        initial=PRICING_STATUS_ACTIVE,
    )

    retail_eur = _price_field(
        label="EUR",
    )
    retail_sek = _price_field(
        label="SEK",
    )
    retail_status = _pricing_status_field(
        help_text=RETAIL_STATUS_HELP_TEXT,
    )

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            full=(
                "business_status",
                "retail_status",
            ),
            half=(
                "business_eur",
                "business_sek",
                "retail_eur",
                "retail_sek",
            ),
        )

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()

        # BUSINESS status is channel availability, and the business standard
        # offer may be unpriced, so an active business status needs no amount.
        # RETAIL checkout requires a concrete price, so active retail pricing
        # still needs at least one amount.
        self._validate_active_channel_has_amount(
            channel=CommercialPrice.Channel.RETAIL,
            status_field="retail_status",
            amount_fields=(
                "retail_eur",
                "retail_sek",
            ),
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
        """Translate presentation values into the pricing service contract."""

        return {
            "business_eur": (
                self.cleaned_data["business_eur"]
            ),
            "business_sek": (
                self.cleaned_data["business_sek"]
            ),
            "business_enabled": (
                self.business_enabled
            ),
            "retail_eur": (
                self.cleaned_data["retail_eur"]
            ),
            "retail_sek": (
                self.cleaned_data["retail_sek"]
            ),
            "retail_enabled": (
                self.retail_enabled
            ),
        }

    def _validate_active_channel_has_amount(
        self,
        *,
        channel: str,
        status_field: str,
        amount_fields: tuple[str, str],
    ) -> None:
        status = self.cleaned_data.get(
            status_field
        )

        if status != PRICING_STATUS_ACTIVE:
            return

        has_amount = any(
            self.cleaned_data.get(field_name)
            is not None
            for field_name in amount_fields
        )

        if has_amount:
            return

        channel_label = CommercialPrice.Channel(
            channel
        ).label

        self.add_error(
            status_field,
            (
                f"{channel_label} pricing needs at least "
                "one configured currency amount."
            ),
        )


def build_product_pricing_initial_data(
    *,
    business_price: CommercialPrice | None,
    retail_price: CommercialPrice | None,
) -> dict[str, object]:
    return {
        "business_eur": _amount_value(
            business_price,
            currency=PriceAmount.Currency.EUR,
        ),
        "business_sek": _amount_value(
            business_price,
            currency=PriceAmount.Currency.SEK,
        ),
        "business_status": _pricing_status(
            business_price,
        ),
        "retail_eur": _amount_value(
            retail_price,
            currency=PriceAmount.Currency.EUR,
        ),
        "retail_sek": _amount_value(
            retail_price,
            currency=PriceAmount.Currency.SEK,
        ),
        "retail_status": _pricing_status(
            retail_price,
        ),
    }


def _pricing_status(
    commercial_price: CommercialPrice | None,
) -> str:
    if (
        commercial_price is not None
        and commercial_price.enabled
    ):
        return PRICING_STATUS_ACTIVE

    return PRICING_STATUS_INACTIVE


def _amount_value(
    commercial_price: CommercialPrice | None,
    *,
    currency: str,
) -> Decimal | None:
    if commercial_price is None:
        return None

    for amount in commercial_price.amounts.all():
        if amount.currency == currency:
            return amount.price

    return None
