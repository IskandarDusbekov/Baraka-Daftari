"""Mavjud foydalanuvchilarga UUID beriladi, keyin maydon unique qilinadi."""
import uuid

from django.db import migrations, models


def fill_uids(apps, schema_editor):
    TgUser = apps.get_model("core", "TgUser")
    batch = []
    for user in TgUser.objects.filter(uid__isnull=True).only("id").iterator(chunk_size=2000):
        user.uid = uuid.uuid4()
        batch.append(user)
        if len(batch) >= 2000:
            TgUser.objects.bulk_update(batch, ["uid"])
            batch = []
    if batch:
        TgUser.objects.bulk_update(batch, ["uid"])


class Migration(migrations.Migration):
    dependencies = [("core", "0009_security_feedback_seo")]

    operations = [
        migrations.RunPython(fill_uids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tguser",
            name="uid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
