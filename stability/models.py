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
        DRAFT = "draft", "Borrador"
        ACTIVE = "active", "Activo"
        CLOSED = "closed", "Cerrado"

    code = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    client = models.ForeignKey("Client", related_name="studies", on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, related_name="studies", on_delete=models.PROTECT, null=True, blank=True)
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


class SampleReception(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        RECEIVED = "received", "Recibida"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    study = models.ForeignKey(Study, related_name="receptions", on_delete=models.CASCADE)
    batch = models.ForeignKey(ProductBatch, related_name="receptions", on_delete=models.SET_NULL, null=True, blank=True)
    reception_number = models.CharField(max_length=50, unique=True)
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
    detected_at = models.DateTimeField()
    description = models.TextField()
    impact_assessment = models.TextField(blank=True)
    requires_recalculation = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Desviación de Cámara"
        verbose_name_plural = "Desviaciones de Cámaras"
    
    def __str__(self):
        return f"{self.chamber.code} - {self.detected_at:%Y-%m-%d %H:%M}"


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
