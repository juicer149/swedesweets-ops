"""Make the implicit BUSINESS standard offer explicit for every product.

Before explicit offers, every active product with stock was orderable in the
business channel without any CommercialPrice row. This migration creates the
product-level BUSINESS offer each product lacks:

    channel = business
    batch   = NULL
    reason  = ""
    enabled = True
    (no PriceAmount - price is optional for the business standard offer)

Existing product-level BUSINESS offers are left untouched, including their
enabled flag, reason and amounts. Batch-specific offers do not count as a
standard offer.

`enabled` is deliberately not derived from Product.active: product status is
the global gate, offer.enabled is the channel gate.

Uses historical models only (no application code), so it keeps working when
pricing services change. Idempotent. Reverse is a no-op: the rows it created
cannot be told apart from ones created later by ensure_standard_offer.
"""

from django.db import migrations

BUSINESS = "business"


def create_business_standard_offers(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    CommercialPrice = apps.get_model("pricing", "CommercialPrice")
    db = schema_editor.connection.alias

    products_with_standard_offer = (
        CommercialPrice.objects.using(db)
        .filter(channel=BUSINESS, batch__isnull=True)
        .values("product_id")
    )

    missing_product_ids = (
        Product.objects.using(db)
        .exclude(pk__in=products_with_standard_offer)
        .values_list("pk", flat=True)
    )

    CommercialPrice.objects.using(db).bulk_create(
        [
            CommercialPrice(
                product_id=product_id,
                batch=None,
                channel=BUSINESS,
                reason="",
                enabled=True,
            )
            for product_id in missing_product_ids.iterator()
        ],
        batch_size=500,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_business_standard_offers,
            migrations.RunPython.noop,
        ),
    ]
