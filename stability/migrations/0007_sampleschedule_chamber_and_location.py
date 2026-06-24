from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0006_alter_packagingconfiguration_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sampleschedule",
            name="chamber",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sample_schedules",
                to="stability.chamber",
            ),
        ),
        migrations.AddField(
            model_name="sampleschedule",
            name="chamber_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sample_schedules",
                to="stability.chamberlocation",
            ),
        ),
    ]
