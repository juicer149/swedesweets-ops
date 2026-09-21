"""State-only: Allocation moves from orders to reservations.

The physical table `orders_allocation` is kept (Meta.db_table), so no
database operation runs. State mirrors orders.Allocation as of orders/0008.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("inventory", "0001_initial"),
        ("orders", "0008_remove_orderline_unique_product_per_order"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Allocation",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("quantity", models.PositiveIntegerField()),
                        ("status", models.CharField(choices=[("reserved", "Reserved"), ("consumed", "Consumed"), ("cancelled", "Cancelled")], default="reserved", max_length=20)),
                        ("reserved_until", models.DateTimeField(blank=True, null=True)),
                        ("batch", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="inventory.inventorybatch")),
                        ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="orders.order")),
                        ("order_line", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="orders.orderline")),
                    ],
                    options={
                        "db_table": "orders_allocation",
                        "indexes": [
                            models.Index(fields=["status"], name="orders_allo_status_89c1d8_idx"),
                            models.Index(fields=["order", "status"], name="orders_allo_order_i_d66c46_idx"),
                            models.Index(fields=["batch", "status"], name="orders_allo_batch_i_32cc21_idx"),
                        ],
                        "constraints": [
                            models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="allocation_quantity_gt_0"),
                        ],
                    },
                ),
            ],
        ),
    ]
