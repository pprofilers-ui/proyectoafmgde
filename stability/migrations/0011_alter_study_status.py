from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0010_studytype_and_study_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="study",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "En Elaboración"),
                    ("active", "Aprobado"),
                    ("suspended", "Suspendido"),
                    ("closed", "Finalizado"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
    ]
