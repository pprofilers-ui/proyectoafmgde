from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Product(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True)
    dosage_form = models.CharField(max_length=100, blank=True)
    strength = models.CharField(max_length=100, blank=True)
    company_code = models.CharField(max_length=50, default="AGQ")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class PackagingConfiguration(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    material = models.CharField(max_length=100, blank=True)
    presentation = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Formato"
        verbose_name_plural = "Formatos"
        
    def __str__(self):
        return f"{self.code} - {self.name}"


class LabelTemplate(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    study_type = models.CharField(max_length=100, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    condition_code = models.CharField(max_length=50, blank=True)
    format_name = models.CharField(max_length=100, blank=True)
    color_hex = models.CharField(max_length=20, default="#DCEBFF")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Plantilla de Etiqueta"
        verbose_name_plural = "Plantillas de Etiquetas"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Client(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True, blank=True)
    description = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return f"{self.code} - {self.description}"

    def save(self, *args, **kwargs):
        if not self.code:
            year = timezone.localdate().year
            prefix = f"CLI-{year}-"
            existing = Client.objects.filter(code__startswith=prefix).values_list("code", flat=True)
            max_seq = 0
            for value in existing:
                suffix = value.replace(prefix, "")
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))
            self.code = f"{prefix}{max_seq + 1:03d}"
        super().save(*args, **kwargs)


class StudyType(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de Estudio"
        verbose_name_plural = "Tipos de Estudio"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductBatch(TimeStampedModel):
    code = models.CharField(max_length=100, unique=True)
    product = models.ForeignKey(Product, related_name="batches", on_delete=models.CASCADE)
    packaging = models.ForeignKey(
        PackagingConfiguration,
        related_name="batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    manufactured_at = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    quantity_released = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Lote de Producto"
        verbose_name_plural = "Lotes de Productos"
    
    def __str__(self):
        return self.code


class StorageCondition(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    temperature_set_point = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_set_point = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    light_condition = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Condición de Almacenamiento"
        verbose_name_plural = "Condiciones de Almacenamiento"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ChamberLocation(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    room = models.CharField(max_length=255, blank=True)
    shelf = models.CharField(max_length=50, blank=True)
    position = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Ubicación de Cámara"
        verbose_name_plural = "Ubicaciones de Cámaras"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Study(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "En Elaboración"
        ACTIVE = "active", "Aprobado"
        SUSPENDED = "suspended", "Suspendido"
        CLOSED = "closed", "Finalizado"

    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    study_type = models.ForeignKey("StudyType", related_name="studies", on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey("Client", related_name="studies", on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, related_name="studies", on_delete=models.PROTECT, null=True, blank=True)
    product_code = models.CharField(max_length=100, blank=True)
    protocol = models.CharField(max_length=100, blank=True)
    specification = models.CharField(max_length=255, blank=True)
    batch = models.ForeignKey(ProductBatch, related_name="studies", on_delete=models.PROTECT, null=True, blank=True)
    packaging = models.ForeignKey(
        PackagingConfiguration,
        related_name="studies",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=255)
    batch_number = models.CharField(max_length=100)
    packaging_description = models.CharField(max_length=255, blank=True)
    comments = models.TextField(blank=True)
    company_code = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Estudio de Estabilidad"
        verbose_name_plural = "Estudios de Estabilidad"

    def __str__(self):
        return f"{self.code} - {self.title}"


class Chamber(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    storage_condition = models.ForeignKey(
        StorageCondition,
        related_name="chambers",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    chamber_location = models.ForeignKey(
        ChamberLocation,
        related_name="chambers",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    temperature_set_point = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_set_point = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cámara"
        verbose_name_plural = "Cámaras"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class SamplingPoint(TimeStampedModel):
    study = models.ForeignKey(Study, related_name="sampling_points", on_delete=models.CASCADE)
    label = models.CharField(max_length=100)
    target_date = models.DateField()
    tolerance_days = models.PositiveIntegerField(default=0)
    recalculated_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["target_date"]
        verbose_name = "Punto de Muestreo"
        verbose_name_plural = "Puntos de Muestreo"

    @property
    def effective_date(self):
        return self.recalculated_date or self.target_date

    def __str__(self):
        return f"{self.study.code} - {self.label}"


class SamplingPointTemplate(TimeStampedModel):
    month_number = models.PositiveIntegerField(unique=True)
    label = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["month_number"]
        verbose_name = "Maestro Punto de Muestreo"
        verbose_name_plural = "Maestros Puntos de Muestreo"

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = f"{self.month_number}M"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class SampleReception(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        RECEIVED = "received", "Recibida"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    study = models.ForeignKey(Study, related_name="receptions", on_delete=models.CASCADE)
    batch = models.ForeignKey(ProductBatch, related_name="receptions", on_delete=models.SET_NULL, null=True, blank=True)
    batch_number_text = models.CharField(max_length=100, blank=True)
    packaging = models.ForeignKey(
        PackagingConfiguration,
        related_name="receptions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reception_number = models.CharField(max_length=50, unique=True)
    presentation = models.CharField(max_length=255, blank=True)
    batch_size = models.PositiveIntegerField(default=0)
    bulk_code = models.CharField(max_length=100, blank=True)
    api_batch = models.CharField(max_length=100, blank=True)
    api_code = models.CharField(max_length=100, blank=True)
    primary_packing_material = models.CharField(max_length=255, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    received_from = models.CharField(max_length=255, blank=True)
    received_by = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_expected = models.PositiveIntegerField(default=0)
    discrepancy_notes = models.TextField(blank=True)
    quantity_assigned = models.PositiveIntegerField(default=0)
    quantity_reserved = models.PositiveIntegerField(default=0)
    quantity_contingency = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Recepción de Muestra"
        verbose_name_plural = "Recepciones de Muestras"
    
    def __str__(self):
        return self.reception_number


class Sample(TimeStampedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Recibida"
        LABELLED = "labelled", "Etiquetada"
        IN_CHAMBER = "in_chamber", "En camara"
        EXTRACTED = "extracted", "Extraida"
        ANALYSED = "analysed", "Analizada"
        DESTROYED = "destroyed", "Destruida"
        BLOCKED = "blocked", "Bloqueada"

    study = models.ForeignKey(Study, related_name="samples", on_delete=models.CASCADE)
    reception = models.ForeignKey(SampleReception, related_name="samples", on_delete=models.SET_NULL, null=True, blank=True)
    sampling_point = models.ForeignKey(SamplingPoint, related_name="samples", on_delete=models.SET_NULL, null=True, blank=True)
    chamber = models.ForeignKey(Chamber, related_name="samples", on_delete=models.SET_NULL, null=True, blank=True)
    shelf = models.CharField(max_length=50, blank=True)
    tray = models.CharField(max_length=50, blank=True)
    container = models.CharField(max_length=50, blank=True)
    physical_position = models.CharField(max_length=50, blank=True)
    label_template = models.ForeignKey(
        LabelTemplate,
        related_name="samples",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sample_code = models.CharField(max_length=100, unique=True)
    qr_code = models.CharField(max_length=255, blank=True)
    label_printed_at = models.DateTimeField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    current_stock = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    received_at = models.DateTimeField(null=True, blank=True)
    placed_in_chamber_at = models.DateTimeField(null=True, blank=True)
    extracted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Muestra"
        verbose_name_plural = "Muestras"
        
    def __str__(self):
        return self.sample_code


class SampleSchedule(TimeStampedModel):
    sample = models.ForeignKey(Sample, related_name="schedules", on_delete=models.CASCADE)
    planned_date = models.DateField()
    label = models.CharField(max_length=100, blank=True)
    schedule_qr_code = models.CharField(max_length=255, blank=True)
    label_printed_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="removed_sample_schedules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    chamber = models.ForeignKey(
        Chamber,
        related_name="sample_schedules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    chamber_location = models.ForeignKey(
        ChamberLocation,
        related_name="sample_schedules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    
    quantity = models.PositiveIntegerField(
            "Cantidad",
            default=1
        )

    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["planned_date", "id"]
        verbose_name = "Fecha de Muestreo"
        verbose_name_plural = "Fechas de Muestreo"

    def __str__(self):
        suffix = f" - {self.label}" if self.label else ""
        return f"{self.sample.sample_code} - {self.planned_date}{suffix}"


class StudyPlanningEntry(TimeStampedModel):
    class AnalysisType(models.TextChoices):
        FQ = "fq", "FQ"
        MICRO = "micro", "Micro"

    study = models.ForeignKey(Study, related_name="planning_entries", on_delete=models.CASCADE)
    sampling_point_template = models.ForeignKey(
        SamplingPointTemplate,
        related_name="planning_entries",
        on_delete=models.PROTECT,
    )
    chamber = models.ForeignKey(Chamber, related_name="planning_entries", on_delete=models.PROTECT)
    analysis_type = models.CharField(max_length=20, choices=AnalysisType.choices)
    subsample_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sampling_point_template__month_number", "chamber__code", "analysis_type"]
        verbose_name = "Linea de Planificacion"
        verbose_name_plural = "Lineas de Planificacion"
        constraints = [
            models.UniqueConstraint(
                fields=["study", "sampling_point_template", "chamber", "analysis_type"],
                name="unique_study_planning_entry",
            )
        ]

    def __str__(self):
        return f"{self.study.code} - {self.sampling_point_template.label} - {self.chamber.code} - {self.get_analysis_type_display()}"


class PlannedSubsample(TimeStampedModel):
    class AnalysisType(models.TextChoices):
        FQ = "fq", "FQ"
        MICRO = "micro", "Micro"

    class Status(models.TextChoices):
        IN_CHAMBER = "in_chamber", "En camara"
        WITHDRAWN = "withdrawn", "Retirada"

    study = models.ForeignKey(Study, related_name="planned_subsamples", on_delete=models.CASCADE)
    sampling_point_template = models.ForeignKey(
        SamplingPointTemplate,
        related_name="planned_subsamples",
        on_delete=models.PROTECT,
    )
    chamber = models.ForeignKey(
        Chamber,
        related_name="planned_subsamples",
        on_delete=models.PROTECT,
    )
    analysis_type = models.CharField(max_length=20, choices=AnalysisType.choices)
    code = models.CharField(max_length=120, unique=True)
    planned_date = models.DateField(null=True, blank=True)
    actual_sampling_date = models.DateField(null=True, blank=True)
    analysis_date = models.DateField(null=True, blank=True)
    location_notes = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_CHAMBER)

    class Meta:
        ordering = ["sampling_point_template__month_number", "code"]
        verbose_name = "Submuestra Planificada"
        verbose_name_plural = "Submuestras Planificadas"

    def __str__(self):
        return self.code


class StockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        RECEPTION = "reception", "Recepcion"
        LABEL = "label", "Etiquetado"
        CHAMBER_IN = "chamber_in", "Entrada en camara"
        EXTRACTION = "extraction", "Extraccion"
        ADJUSTMENT = "adjustment", "Ajuste"

    sample = models.ForeignKey(Sample, related_name="stock_movements", on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity_delta = models.IntegerField()
    notes = models.CharField(max_length=255, blank=True)
    executed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-executed_at"]
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"

    def __str__(self):
        return f"{self.sample.sample_code} - {self.movement_type}"


class ChamberDeviation(TimeStampedModel):
    chamber = models.ForeignKey(Chamber, related_name="deviations", on_delete=models.CASCADE)
    study = models.ForeignKey(Study, related_name="deviations", on_delete=models.SET_NULL, null=True, blank=True)
    deviation_code = models.CharField(max_length=100, blank=True, db_index=True)
    detected_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField()
    impact_assessment = models.TextField(blank=True)
    requires_recalculation = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Desviación de Cámara"
        verbose_name_plural = "Desviaciones de Cámaras"
    
    def save(self, *args, **kwargs):
        if not self.deviation_code:
            year = timezone.localdate().year
            prefix = f"DEV-{year}-"
            existing = ChamberDeviation.objects.filter(
                deviation_code__startswith=prefix
            ).values_list("deviation_code", flat=True)
            max_seq = 0
            for value in existing:
                suffix = (value or "").replace(prefix, "")
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))
            self.deviation_code = f"{prefix}{max_seq + 1:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.deviation_code or self.chamber.code} - {self.detected_at:%Y-%m-%d %H:%M}"


class StabilityAlert(TimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Informativa"
        WARNING = "warning", "Advertencia"
        CRITICAL = "critical", "Critica"

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"

    study = models.ForeignKey(Study, related_name="alerts", on_delete=models.CASCADE, null=True, blank=True)
    sample = models.ForeignKey(Sample, related_name="alerts", on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]
        verbose_name = "Alerta de Estabilidad"
        verbose_name_plural = "Alertas de Estabilidad"
    
    def __str__(self):
        return self.title
