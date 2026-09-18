from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.tests.factories import (
    customer_user_factory,
)
from customers.tests.factories import (
    customer_factory,
)


@pytest.mark.django_db
def test_business_customer_is_redirected_from_public_contact(
    client,
):
    customer = customer_factory()
    user = customer_user_factory(
        customer=customer,
    )

    client.force_login(
        user
    )

    response = client.get(
        reverse("public_site:contact")
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:contact"
    )


@pytest.mark.django_db
def test_business_customer_is_redirected_from_public_faq(
    client,
):
    customer = customer_factory()
    user = customer_user_factory(
        customer=customer,
    )

    client.force_login(
        user
    )

    response = client.get(
        reverse("public_site:faq")
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:faq"
    )


@pytest.mark.django_db
def test_anonymous_visitor_can_open_public_contact(
    client,
):
    response = client.get(
        reverse("public_site:contact")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_visitor_can_open_public_faq(
    client,
):
    response = client.get(
        reverse("public_site:faq")
    )

    assert response.status_code == 200
