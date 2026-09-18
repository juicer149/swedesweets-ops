from django.urls import reverse


def test_business_account_routes_live_under_my_prefix():
    assert reverse("business_portal:index") == "/my/"
    assert reverse("business_portal:orders") == "/my/orders/"
    assert (
        reverse("business_portal:edit_store")
        == "/my/store/edit/"
    )
