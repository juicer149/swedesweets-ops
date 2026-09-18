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
def test_business_customer_is_redirected_from_generic_account_page(
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
        reverse("accounts:me")
    )

    assert response.status_code == 302
    assert response["Location"] == reverse(
        "business_portal:index"
    )
