"""State-only: orders no longer owns Allocation (now reservations.Allocation).

The table orders_allocation is NOT dropped; reservations.Allocation uses it.
Must run after ops_portal/0002 so no FK in state points at the removed model.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0008_remove_orderline_unique_product_per_order"),
        ("ops_portal", "0002_repoint_pickchecklistmark_allocation"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="Allocation"),
            ],
        ),
    ]
