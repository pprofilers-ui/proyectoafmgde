from django.db import migrations, models


def create_initial_study_modes(apps, schema_editor):
    StudyMode = apps.get_model("stability", "StudyMode")
    for code, name in (
        ("CONSERVACION", "Conservación"),
        ("ANALISIS", "Análisis"),
    ):
        StudyMode.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )


def remove_initial_study_modes(apps, schema_editor):
    StudyMode = apps.get_model("stability", "StudyMode")
    StudyMode.objects.filter(code__in=["CONSERVACION", "ANALISIS"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0019_alter_study_start_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyMode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Modalidad de Estudio",
                "verbose_name_plural": "Modalidades de Estudio",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="study",
            name="study_mode",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="studies", to="stability.studymode"),
        ),
        migrations.RunPython(create_initial_study_modes, remove_initial_study_modes),
    ]
