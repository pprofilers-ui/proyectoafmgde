import os
from datetime import date, timedelta

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from audit.models import AuditTrail  # noqa: E402
from stability.models import (  # noqa: E402
    Chamber,
    ChamberDeviation,
    ChamberLocation,
    LabelTemplate,
    PackagingConfiguration,
    Product,
    ProductBatch,
    Sample,
    SampleReception,
    SamplingPoint,
    StabilityAlert,
    StockMovement,
    StorageCondition,
    Study,
)


User = get_user_model()


def create_users():
    admin_user, _ = User.objects.update_or_create(
        username="admin",
        defaults={
            "email": "admin@afmgde.local",
            "is_staff": True,
            "is_superuser": True,
            "user_type": User.UserType.INTERNAL,
            "company_code": "AGQ",
            "contact_code": "ADMIN",
            "address_code": "CENTRAL",
            "is_quality_admin": True,
        },
    )
    admin_user.set_password("Admin12345!")
    admin_user.save()
    return admin_user


def build_master_data():
    LabelTemplate.objects.update_or_create(
        code="LBL-STD-01",
        defaults={
            "name": "Etiqueta estandar estabilidad",
            "study_type": "General",
            "condition_code": "COND-40-75",
            "format_name": "Caja / contenedor",
            "color_hex": "#FFD99B",
            "is_active": True,
        },
    )
    product, _ = Product.objects.update_or_create(
        code="PROD-A",
        defaults={
            "name": "Producto A",
            "reference": "REF-001",
            "dosage_form": "Comprimido",
            "strength": "500 mg",
            "company_code": "AGQ",
        },
    )
    packaging, _ = PackagingConfiguration.objects.update_or_create(
        code="PACK-BLISTER",
        defaults={
            "name": "Blister aluminio PVC",
            "material": "ALU/PVC",
            "presentation": "30 comprimidos",
        },
    )
    batch, _ = ProductBatch.objects.update_or_create(
        code="LOT-A-2026-001",
        defaults={
            "product": product,
            "packaging": packaging,
            "manufactured_at": date.today() - timedelta(days=40),
            "expiry_date": date.today() + timedelta(days=700),
            "quantity_released": 1500,
        },
    )
    condition_25, _ = StorageCondition.objects.update_or_create(
        code="COND-25-60",
        defaults={
            "name": "Largo plazo 25/60",
            "temperature_set_point": 25.00,
            "humidity_set_point": 60.00,
            "light_condition": "Protegido de la luz",
        },
    )
    condition_40, _ = StorageCondition.objects.update_or_create(
        code="COND-40-75",
        defaults={
            "name": "Acelerada 40/75",
            "temperature_set_point": 40.00,
            "humidity_set_point": 75.00,
        },
    )
    location_a, _ = ChamberLocation.objects.update_or_create(
        code="LOC-A1",
        defaults={"name": "Zona A1", "room": "Sala A", "shelf": "S1", "position": "P1"},
    )
    location_b, _ = ChamberLocation.objects.update_or_create(
        code="LOC-B1",
        defaults={"name": "Zona B1", "room": "Sala B", "shelf": "S2", "position": "P4"},
    )
    chamber_25, _ = Chamber.objects.update_or_create(
        code="CAM-25-60",
        defaults={
            "name": "Camara 25C / 60HR",
            "location": "Sala A",
            "storage_condition": condition_25,
            "chamber_location": location_a,
            "temperature_set_point": 25.00,
            "humidity_set_point": 60.00,
            "is_active": True,
        },
    )
    chamber_40, _ = Chamber.objects.update_or_create(
        code="CAM-40-75",
        defaults={
            "name": "Camara 40C / 75HR",
            "location": "Sala B",
            "storage_condition": condition_40,
            "chamber_location": location_b,
            "temperature_set_point": 40.00,
            "humidity_set_point": 75.00,
            "is_active": True,
        },
    )
    return product, packaging, batch, chamber_25, chamber_40


def create_study(product, packaging, batch):
    study, _ = Study.objects.update_or_create(
        code="EST-001",
        defaults={
            "title": "Estabilidad acelerada producto A",
            "product": product,
            "batch": batch,
            "packaging": packaging,
            "product_name": product.name,
            "batch_number": batch.code,
            "packaging_description": packaging.name,
            "company_code": "AGQ",
            "status": Study.Status.ACTIVE,
            "start_date": date.today() - timedelta(days=15),
            "end_date": date.today() + timedelta(days=180),
        },
    )
    return study


def create_sampling_points(study):
    points = []
    for label, days in [("T0", 0), ("T1", 30), ("T2", 60), ("T3", 90)]:
        point, _ = SamplingPoint.objects.update_or_create(
            study=study,
            label=label,
            defaults={
                "target_date": date.today() + timedelta(days=days),
                "tolerance_days": 3,
            },
        )
        points.append(point)
    return points


def create_reception(study, batch):
    reception, _ = SampleReception.objects.update_or_create(
        reception_number="REC-001",
        defaults={
            "study": study,
            "batch": batch,
            "received_from": "Produccion interna",
            "received_by": "QA Demo",
            "received_at": timezone.now() - timedelta(days=7),
            "quantity_received": 48,
            "status": SampleReception.Status.RECEIVED,
            "notes": "Recepcion inicial para estudio fase 1.",
        },
    )
    return reception


def create_samples(study, reception, points, chamber):
    label_template = LabelTemplate.objects.get(code="LBL-STD-01")
    created = []
    for idx, point in enumerate(points, start=1):
        sample, _ = Sample.objects.update_or_create(
            sample_code=f"{study.code}-M-{idx:03d}",
            defaults={
                "study": study,
                "reception": reception,
                "sampling_point": point,
                "chamber": chamber,
                "label_template": label_template,
                "qr_code": f"QR::{study.code}-M-{idx:03d}",
                "label_printed_at": timezone.now() - timedelta(days=5),
                "quantity": 12,
                "current_stock": 12 if idx != 4 else 1,
                "status": Sample.Status.IN_CHAMBER if idx <= 3 else Sample.Status.LABELLED,
                "received_at": timezone.now() - timedelta(days=7),
                "placed_in_chamber_at": timezone.now() - timedelta(days=5) if idx <= 3 else None,
                "shelf": "S1" if idx <= 2 else "S2",
                "tray": f"T{idx}",
                "container": f"C{idx}",
                "physical_position": f"P{idx}",
            },
        )
        created.append(sample)
    return created


def create_stock_movements(samples):
    for sample in samples:
        StockMovement.objects.get_or_create(
            sample=sample,
            movement_type=StockMovement.MovementType.RECEPTION,
            quantity_delta=sample.quantity,
            notes="Carga inicial de recepcion",
        )
        StockMovement.objects.get_or_create(
            sample=sample,
            movement_type=StockMovement.MovementType.LABEL,
            quantity_delta=0,
            notes="Etiquetado inicial demo",
        )


def create_deviation_and_alerts(study, chamber, low_stock_sample):
    ChamberDeviation.objects.update_or_create(
        chamber=chamber,
        study=study,
        detected_at=timezone.now() - timedelta(days=2),
        defaults={
            "description": "Desviacion puntual de humedad detectada durante control rutinario.",
            "impact_assessment": "Se revisa el punto T1 y queda pendiente recalculo auditado.",
            "requires_recalculation": True,
        },
    )
    StabilityAlert.objects.update_or_create(
        title="Extraccion proxima T1",
        defaults={
            "study": study,
            "message": "El punto T1 vence dentro de los proximos dias.",
            "severity": StabilityAlert.Severity.INFO,
            "status": StabilityAlert.Status.OPEN,
            "due_date": date.today() + timedelta(days=2),
        },
    )
    StabilityAlert.objects.update_or_create(
        title=f"Stock bajo {low_stock_sample.sample_code}",
        defaults={
            "study": study,
            "sample": low_stock_sample,
            "message": "La muestra se encuentra con stock minimo para extracciones futuras.",
            "severity": StabilityAlert.Severity.WARNING,
            "status": StabilityAlert.Status.OPEN,
            "due_date": date.today(),
        },
    )


def create_audit(admin_user, study):
    AuditTrail.objects.update_or_create(
        action="seed_data",
        entity_name="Study",
        entity_id=str(study.pk),
        defaults={
            "payload": {"source": "seed_demo_data.py", "message": "Carga inicial demo de fase 1."},
            "performed_by": admin_user,
        },
    )


def main():
    admin_user = create_users()
    product, packaging, batch, chamber_25, chamber_40 = build_master_data()
    study = create_study(product, packaging, batch)
    points = create_sampling_points(study)
    reception = create_reception(study, batch)
    samples = create_samples(study, reception, points, chamber_40)
    create_stock_movements(samples)
    create_deviation_and_alerts(study, chamber_40, samples[-1])
    create_audit(admin_user, study)

    print("Datos demo de fase 1 cargados correctamente.")
    print("Superusuario: admin / Admin12345!")


if __name__ == "__main__":
    main()
