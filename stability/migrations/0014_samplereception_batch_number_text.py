from django.db import migrations, models


def populate_batch_text(apps, schema_editor):
    SampleReception = apps.get_model("stability", "SampleReception")
    for reception in SampleReception.objects.select_related("batch").all():
        if not reception.batch_number_text and reception.batch_id and reception.batch:
            reception.batch_number_text = reception.batch.code
            reception.save(update_fields=["batch_number_text"])


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0013_chamberdeviation_word_updates"),
    ]

    operations = [
        migrations.AddField(
            model_name="samplereception",
            name="batch_number_text",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(populate_batch_text, migrations.RunPython.noop),
    ]
