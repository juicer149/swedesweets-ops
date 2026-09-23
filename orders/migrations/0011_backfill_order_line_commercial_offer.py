"""Backfill OrderLine.commercial_offer from channel selection tables.

Order of resolution:

1. Real explicit provenance wins. A BusinessOfferSelection or
   RetailOfferSelection pointing at a CommercialPrice is copied verbatim and
   is never overwritten.

2. Remaining BUSINESS lines are normalized to the product's standard
   BUSINESS offer. Normal business selling was the only commercial
   alternative before explicit offers existed, so this is semantic
   normalization of a previously implicit concept - not fabricated
   provenance. This covers both lines with no selection row at all and
   selections explicitly marked as the unpriced business standard
   (commercial_price=NULL).

3. Anything still unresolved stops the migration. Retail provenance is never
   invented, and a missing standard offer means pricing.0002 did not run or
   a product was created without one.

Lines that already have a commercial offer are left alone, so the migration
is idempotent. Reverse is a no-op: the field is dropped by the schema
migration, and the selection tables still hold the original data at this
point.
"""

from django.db import migrations

BUSINESS = "business"
RETAIL = "retail"


def backfill_commercial_offers(apps, schema_editor):
    OrderLine = apps.get_model("orders", "OrderLine")
    CommercialPrice = apps.get_model("pricing", "CommercialPrice")
    BusinessOfferSelection = apps.get_model("business", "BusinessOfferSelection")
    RetailOfferSelection = apps.get_model("retail", "RetailOfferSelection")
    db = schema_editor.connection.alias

    explicit_offer_by_line_id: dict[int, int] = {}

    for model in (BusinessOfferSelection, RetailOfferSelection):
        explicit_offer_by_line_id.update(
            model.objects.using(db)
            .filter(commercial_price__isnull=False)
            .values_list("order_line_id", "commercial_price_id")
        )

    standard_offer_by_product_id = dict(
        CommercialPrice.objects.using(db)
        .filter(channel=BUSINESS, batch__isnull=True)
        .values_list("product_id", "id")
    )

    lines = (
        OrderLine.objects.using(db)
        .filter(commercial_offer__isnull=True)
        .select_related("order")
        .only("id", "product_id", "order__channel")
    )

    unresolved: list[str] = []
    updated: list = []

    for line in lines.iterator():
        offer_id = explicit_offer_by_line_id.get(line.id)

        if offer_id is None and line.order.channel == BUSINESS:
            offer_id = standard_offer_by_product_id.get(line.product_id)

            if offer_id is None:
                unresolved.append(
                    f"line {line.id}: business product {line.product_id} "
                    "has no standard BUSINESS offer"
                )
                continue

        if offer_id is None:
            unresolved.append(
                f"line {line.id}: {line.order.channel} line has no explicit "
                "commercial offer and none may be inferred"
            )
            continue

        line.commercial_offer_id = offer_id
        updated.append(line)

    if unresolved:
        raise RuntimeError(
            "Cannot resolve a commercial offer for "
            f"{len(unresolved)} order line(s):\n  "
            + "\n  ".join(unresolved[:20])
            + ("\n  ..." if len(unresolved) > 20 else "")
        )

    OrderLine.objects.using(db).bulk_update(
        updated,
        ["commercial_offer"],
        batch_size=500,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0010_orderline_commercial_offer"),
        ("business", "0001_initial"),
        ("retail", "0010_remove_retailcartline_unique_retail_commercial_price_per_cart_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_commercial_offers,
            migrations.RunPython.noop,
        ),
    ]
