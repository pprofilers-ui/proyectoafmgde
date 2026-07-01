from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0018_study_approval_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="study",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
