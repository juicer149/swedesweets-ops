from django.urls import reverse


def test_ops_routes_live_under_ops_prefix():
    assert reverse("ops_dashboard") == "/ops/"

    assert (
        reverse("ops_customers:index")
        == "/ops/customers/"
    )
    assert (
        reverse("ops_orders:index")
        == "/ops/orders/"
    )
    assert (
        reverse("ops_inventory:index")
        == "/ops/inventory/"
    )
    assert (
        reverse("ops_products:index")
        == "/ops/products/"
    )
    assert (
        reverse("ops_accounts:index")
        == "/ops/accounts/"
    )
