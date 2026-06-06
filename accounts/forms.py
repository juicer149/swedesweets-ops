from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.roles import StaffAccessLevel
from common.form_layout import set_form_field_layout


INTERNAL_ACCOUNT_ACCESS_LEVEL_CHOICES = (
    (StaffAccessLevel.RESTRICTED.value, "Restricted staff"),
    (StaffAccessLevel.FULL.value, "Full staff"),
)


class InternalAccountCreateForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        label="Email",
        error_messages={
            "required": "Enter an email address.",
            "invalid": "Enter a valid email address.",
            "max_length": "Email address must be at most 254 characters.",
        },
        widget=forms.EmailInput(
            attrs={
                "placeholder": "e.g. packer@example.com",
                "autocomplete": "email",
            }
        ),
    )

    access_level = forms.ChoiceField(
        choices=INTERNAL_ACCOUNT_ACCESS_LEVEL_CHOICES,
        initial=StaffAccessLevel.RESTRICTED.value,
        label="Access level",
        help_text=(
            "Restricted staff can work with orders and inventory. "
            "Full staff can manage operations and accounts."
        ),
        error_messages={
            "required": "Choose an access level.",
            "invalid_choice": "Choose a valid access level.",
        },
        widget=forms.RadioSelect(
            attrs={
                "class": "radio-chip-group",
            }
        ),
    )

    password1 = forms.CharField(
        label="Temporary password",
        strip=False,
        error_messages={
            "required": "Enter a temporary password.",
        },
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        error_messages={
            "required": "Confirm the temporary password.",
        },
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
            }
        ),
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        set_form_field_layout(
            self,
            full=("email", "access_level"),
            half=("password1", "password2"),
        )

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()

    def clean(self) -> dict:
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if not password1 or not password2:
            return cleaned_data

        if password1 != password2:
            self.add_error("password2", "Passwords do not match.")
            return cleaned_data

        try:
            validate_password(password1)
        except ValidationError as error:
            self.add_error("password1", error)

        return cleaned_data
