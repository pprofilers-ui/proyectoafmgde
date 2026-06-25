from django.db import migrations, models
import django.db.models.deletion


def seed_study_types(apps, schema_editor):
    StudyType = apps.get_model("stability", "StudyType")
    Study = apps.get_model("stability", "Study")

    defaults = [
        ("ONGOING", "On Going"),
        ("INUSE", "In Use"),
        ("ACELERADA", "Acelerada"),
        ("INDUSTRIAL_ICH", "Industrial ICH"),
    ]
    for code, name in defaults:
        StudyType.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})

    for study in Study.objects.all():
        if study.packaging_description and not study.comments:
            study.comments = study.packaging_description
        if study.product_id and not study.product_code:
            try:
                study.product_code = study.product.code
            except Exception:
                pass
        update_fields = []
        if study.comments:
            update_fields.append("comments")
        if study.product_code:
            update_fields.append("product_code")
        if update_fields:
            study.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("stability", "0009_sampleschedule_removed_at_removed_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Tipo de Estudio",
                "verbose_name_plural": "Tipos de Estudio",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="study",
            name="comments",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="study",
            name="product_code",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="study",
            name="protocol",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="study",
            name="specification",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="study",
            name="study_type",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="studies", to="stability.studytype"),
        ),
        migrations.RunPython(seed_study_types, migrations.RunPython.noop),
    ]
