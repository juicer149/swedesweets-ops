from __future__ import annotations

from django import forms


FORM_FIELD_FULL = "form-field--full"
FORM_FIELD_HALF = "form-field--half"
FORM_FIELD_THIRD = "form-field--third"


def set_form_field_layout(
    form: forms.BaseForm,
    *,
    full: tuple[str, ...] = (),
    half: tuple[str, ...] = (),
    third: tuple[str, ...] = (),
) -> None:
    """Attach layout metadata to Django form fields.

    This is presentation metadata only. The template reads it and applies
    a wrapper class around each rendered field.
    """

    for field_name in full:
        _set_layout_class(form, field_name, FORM_FIELD_FULL)

    for field_name in half:
        _set_layout_class(form, field_name, FORM_FIELD_HALF)

    for field_name in third:
        _set_layout_class(form, field_name, FORM_FIELD_THIRD)


def _set_layout_class(
    form: forms.BaseForm,
    field_name: str,
    layout_class: str,
) -> None:
    if field_name not in form.fields:
        raise KeyError(f"Unknown form field: {field_name}")

    form.fields[field_name].layout_class = layout_class
