from django.db import migrations, models


def seed_deviation_codes(apps, schema_editor):
    ChamberDeviation = apps.get_model("stability", "ChamberDeviation")
    year = 2026
    seq = 1
    for deviation in ChamberDeviation.objects.order_by("id"):
        if not deviation.deviation_code:
            deviation.deviation_code = f"DEV-{year}-{seq:03d}"
            deviation.save(update_fields=["deviation_code"])
            seq += 1


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0012_samplereception_operational_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="chamberdeviation",
            name="deviation_code",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="chamberdeviation",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(seed_deviation_codes, migrations.RunPython.noop),
    ]
