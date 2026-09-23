"""Add the (temporarily nullable) commercial offer identity to OrderLine.

The field becomes NOT NULL after every line has been backfilled.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0009_move_allocation_to_reservation"),
        ("pricing", "0002_create_business_standard_offers"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderline",
            name="commercial_offer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="order_lines",
                to="pricing.commercialprice",
            ),
        ),
    ]
