from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0011_alter_study_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="samplereception",
            name="api_batch",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="api_code",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="batch_size",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="bulk_code",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="manufacture_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="packaging",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="receptions", to="stability.packagingconfiguration"),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="presentation",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="samplereception",
            name="primary_packing_material",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
