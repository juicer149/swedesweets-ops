"""Re-home the Allocation ContentType (and thereby its Permission rows).

Place as reservations/migrations/0002_move_allocation_contenttype.py.

Permission rows hang off ContentType by FK, so moving the ContentType row
keeps every existing permission/group assignment intact. Only the
app_label part of the permission string changes
(orders.view_allocation -> reservations.view_allocation).

Idempotent: if the target ContentType already exists (e.g. re-run), it does
nothing rather than violating unique(app_label, model).
"""
from django.db import migrations


def _move(apps, schema_editor, old_label, new_label):
    ContentType = apps.get_model("contenttypes", "ContentType")
    qs = ContentType.objects.using(schema_editor.connection.alias)
    if qs.filter(app_label=new_label, model="allocation").exists():
        return
    qs.filter(app_label=old_label, model="allocation").update(app_label=new_label)


def forwards(apps, schema_editor):
    _move(apps, schema_editor, "orders", "reservations")


def backwards(apps, schema_editor):
    _move(apps, schema_editor, "reservations", "orders")


class Migration(migrations.Migration):
    dependencies = [
        ("reservations", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
