from __future__ import annotations

from customers.forms import (
    CUSTOMER_COUNTRY_CHOICES,
    CustomerForm,
    build_customer_edit_initial_data,
)


def valid_customer_form_data(**overrides):
    data = {
        "name": "Nordic Corner Shop",
        "email": "orders@example.fr",
        "phone_number": "+33 6 12 34 56 78",
        "country": "FR",
        "city": "Chamonix-Mont-Blanc",
        "address_line": "123 Rue du Mont Blanc",
    }
    data.update(overrides)
    return data


def test_customer_country_choices_match_supported_countries():
    assert CUSTOMER_COUNTRY_CHOICES == [
        ("FR", "France"),
        ("CH", "Switzerland"),
        ("IT", "Italy"),
    ]


def test_customer_form_accepts_valid_data():
    form = CustomerForm(data=valid_customer_form_data())

    assert form.is_valid(), form.errors

    assert form.cleaned_data["name"] == "Nordic Corner Shop"
    assert form.cleaned_data["email"] == "orders@example.fr"
    assert form.cleaned_data["phone_number"] == "+33 6 12 34 56 78"
    assert form.cleaned_data["country"] == "FR"
    assert form.cleaned_data["city"] == "Chamonix-Mont-Blanc"
    assert form.cleaned_data["address_line"] == "123 Rue du Mont Blanc"


def test_customer_form_rejects_missing_required_fields():
    form = CustomerForm(
        data=valid_customer_form_data(
            name="",
            email="",
            phone_number="",
            country="",
            city="",
            address_line="",
        )
    )

    assert not form.is_valid()

    assert "name" in form.errors
    assert "email" in form.errors
    assert "phone_number" in form.errors
    assert "country" in form.errors
    assert "city" in form.errors
    assert "address_line" in form.errors


def test_customer_form_rejects_invalid_email():
    form = CustomerForm(data=valid_customer_form_data(email="not-an-email"))

    assert not form.is_valid()
    assert "email" in form.errors


def test_customer_form_rejects_invalid_country_choice():
    form = CustomerForm(data=valid_customer_form_data(country="SE"))

    assert not form.is_valid()
    assert "country" in form.errors


def test_customer_form_configures_country_widget_metadata():
    form = CustomerForm()

    assert form.fields["country"].widget.attrs["data-enhanced-select"] == "true"
    assert form.fields["country"].widget.attrs["data-enhanced-select-search"] == "false"


def test_customer_form_stores_customer_instance():
    customer = object()

    form = CustomerForm(customer=customer)

    assert form.customer is customer


def test_build_customer_edit_initial_data(customer):
    assert build_customer_edit_initial_data(customer) == {
        "name": "Nordic Corner Shop",
        "email": "orders@example.fr",
        "phone_number": "+33612345678",
        "country": "FR",
        "city": "Chamonix-Mont-Blanc",
        "address_line": "123 Rue du Mont Blanc",
    }
