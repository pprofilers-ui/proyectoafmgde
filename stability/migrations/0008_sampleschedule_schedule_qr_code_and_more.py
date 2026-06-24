from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0007_sampleschedule_chamber_and_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="sampleschedule",
            name="label_printed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sampleschedule",
            name="schedule_qr_code",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
