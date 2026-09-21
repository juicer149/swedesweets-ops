"""State-only: PickChecklistMark.allocation now targets reservations.Allocation.

Same table, same column, same FK constraint in the database -> no DDL.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ops_portal", "0001_initial"),
        ("reservations", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="pickchecklistmark",
                    name="allocation",
                    field=models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pick_checklist_mark",
                        to="reservations.allocation",
                    ),
                ),
            ],
        ),
    ]
