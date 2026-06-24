from copy import deepcopy

from django import forms
from django.contrib import admin

from audit.admin import AuditTrailAdmin

from .models import (
    Chamber,
    ChamberDeviation,
    ChamberLocation,
    Client,
    PackagingConfiguration,
    Product,
    ProductBatch,
    Sample,
    SampleSchedule,
    SampleReception,
    SamplingPoint,
    StabilityAlert,
    StockMovement,
    StorageCondition,
    Study,
)
from .web_forms import SampleReceptionForm as WebSampleReceptionForm


def _apply_admin_field_labels(model, labels):
    for field_name, label in labels.items():
        try:
            model._meta.get_field(field_name).verbose_name = label
        except Exception:
            continue


_apply_admin_field_labels(Product, {
    "code": "Código",
    "name": "Nombre",
    "reference": "Referencia",
    "dosage_form": "Forma farmacéutica",
    "strength": "Concentración",
    "company_code": "Código empresa",
    "is_active": "Activo",
})
_apply_admin_field_labels(PackagingConfiguration, {
    "code": "Código",
    "name": "Nombre",
    "material": "Material",
    "presentation": "Presentación",
    "is_active": "Activo",
})
_apply_admin_field_labels(Client, {
    "code": "Código cliente",
    "description": "Descripción",
    "address": "Dirección",
    "email": "Email",
    "phone": "Teléfono",
    "notes": "Notas",
})
_apply_admin_field_labels(ProductBatch, {
    "code": "Código",
    "product": "Producto",
    "packaging": "Acondicionado",
    "manufactured_at": "Fecha de fabricación",
    "expiry_date": "Fecha de caducidad",
    "quantity_released": "Cantidad liberada",
    "notes": "Notas",
})
_apply_admin_field_labels(StorageCondition, {
    "code": "Código",
    "name": "Nombre",
    "temperature_set_point": "Temperatura objetivo",
    "humidity_set_point": "Humedad objetivo",
    "light_condition": "Condición lumínica",
    "is_active": "Activo",
})
_apply_admin_field_labels(ChamberLocation, {
    "code": "Código",
    "name": "Nombre",
    "room": "Sala",
    "shelf": "Estantería",
    "position": "Posición",
    "is_active": "Activo",
})
_apply_admin_field_labels(Study, {
    "code": "Código",
    "title": "Título",
    "client": "Cliente",
    "packaging": "Acondicionado",
    "product_name": "Nombre del producto",
    "batch_number": "Número de lote",
    "packaging_description": "Comentarios",
    "company_code": "Código empresa",
    "status": "Estado",
    "start_date": "Fecha de inicio",
    "end_date": "Fecha de fin",
})
_apply_admin_field_labels(Chamber, {
    "code": "Código",
    "name": "Nombre",
    "location": "Ubicación",
    "storage_condition": "Condición de almacenamiento",
    "chamber_location": "Ubicación de cámara",
    "temperature_set_point": "Temperatura objetivo",
    "humidity_set_point": "Humedad objetivo",
    "is_active": "Activo",
})
_apply_admin_field_labels(SamplingPoint, {
    "study": "Estudio",
    "label": "Etiqueta",
    "target_date": "Fecha objetivo",
    "tolerance_days": "Días de tolerancia",
    "recalculated_date": "Fecha recalculada",
})
_apply_admin_field_labels(SampleReception, {
    "study": "Estudio",
    "batch": "Lote",
    "reception_number": "Número de recepción",
    "received_from": "Recibido desde",
    "received_by": "Recibido por",
    "received_at": "Fecha y hora de recepción",
    "quantity_received": "Cantidad recibida",
    "quantity_expected": "Cantidad prevista",
    "discrepancy_notes": "Discrepancias",
    "quantity_assigned": "Cantidad asignada",
    "quantity_reserved": "Cantidad reservada",
    "quantity_contingency": "Cantidad de contingencia",
    "status": "Estado",
    "notes": "Notas",
})
_apply_admin_field_labels(Sample, {
    "study": "Estudio",
    "reception": "Recepción",
    "sampling_point": "Fecha de muestreo",
    "chamber": "Cámara",
    "shelf": "Estantería",
    "tray": "Bandeja",
    "container": "Contenedor",
    "physical_position": "Posición física",
    "label_template": "Plantilla de etiqueta",
    "sample_code": "Código de muestra",
    "qr_code": "Código QR",
    "label_printed_at": "Etiqueta impresa en",
    "quantity": "Cantidad",
    "current_stock": "Stock actual",
    "status": "Estado",
    "received_at": "Fecha de recepción",
    "placed_in_chamber_at": "Entrada en cámara",
    "extracted_at": "Fecha de extracción",
})
_apply_admin_field_labels(SampleSchedule, {
    "sample": "Muestra",
    "planned_date": "Fecha de muestreo",
    "label": "Código fecha de muestreo",
    "schedule_qr_code": "Texto QR",
    "label_printed_at": "Etiqueta impresa en",
    "removed_at": "Fecha salida",
    "removed_by": "Retirada por",
    "chamber": "Cámara",
    "chamber_location": "Ubicación",
    "quantity": "Cantidad",
    "notes": "Notas",
    "is_active": "Activo",
})
_apply_admin_field_labels(StockMovement, {
    "sample": "Muestra",
    "movement_type": "Tipo de movimiento",
    "quantity_delta": "Variación de cantidad",
    "notes": "Notas",
    "executed_at": "Ejecutado en",
})
_apply_admin_field_labels(ChamberDeviation, {
    "chamber": "Cámara",
    "study": "Estudio",
    "detected_at": "Detectado en",
    "description": "Descripción",
    "impact_assessment": "Evaluación de impacto",
    "requires_recalculation": "Requiere recalculo",
})
_apply_admin_field_labels(StabilityAlert, {
    "title": "Título",
    "study": "Estudio",
    "sample": "Muestra",
    "severity": "Severidad",
    "status": "Estado",
    "message": "Mensaje",
    "due_date": "Vence",
})


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "reference", "dosage_form", "strength", "company_code", "is_active")
    list_filter = ("company_code", "is_active")
    search_fields = ("code", "name", "reference")
    
    # ---- COPIA ESTO DENTRO DE PRODUCTADMIN ----
    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(PackagingConfiguration)
class PackagingConfigurationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "material", "presentation", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "material")
    
    # ==== PERMISOS PARA QUE PUEDA ASIGNAR LOS ACONDICIONAMIENTOS ====
    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "email", "phone")
    search_fields = ("code", "description", "email", "phone")
    readonly_fields = ("code",)

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ("code", "product", "packaging", "manufactured_at", "expiry_date", "quantity_released")
    list_filter = ("product", "packaging")
    search_fields = ("code", "product__name")
    
    # ==== 🚀 EVITA EL ERROR DE JSON CON LOS DECIMALES EN LOS LOTES ====
    def save_model(self, request, obj, form, change):
        if hasattr(obj, 'quantity_released') and obj.quantity_released is not None:
            obj.quantity_released = float(obj.quantity_released)
        super().save_model(request, obj, form, change)

    # ==== PERMISOS PARA EL USUARIO DE MAESTROS ====
    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(StorageCondition)
class StorageConditionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "temperature_set_point", "humidity_set_point", "light_condition", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    
    # ---- AÑADE ESTO PARA QUE PUEDA ASIGNAR CONDICIONES ----
    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff
    
    # ==== ESTE TRUCO INTERCEPTA EL FORMULARIO Y EVITA EL ERROR DE JSON ====
    def save_model(self, request, obj, form, change):
        # Forzamos a que los datos del formulario pasen como floats limpios de Python
        if obj.temperature_set_point is not None:
            obj.temperature_set_point = float(obj.temperature_set_point)
        if obj.humidity_set_point is not None:
            obj.humidity_set_point = float(obj.humidity_set_point)
        
        # Llama al guardado normal de Django una vez limpio
        super().save_model(request, obj, form, change)


@admin.register(ChamberLocation)
class ChamberLocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "room", "shelf", "position", "is_active")
    list_filter = ("is_active", "room")
    search_fields = ("code", "name", "room")
    
    # ---- AÑADE ESTO PARA QUE PUEDA ASIGNAR UBICACIONES ----
    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "client", "product_name", "batch_number", "company_code", "status", "start_date", "end_date")
    list_filter = ("status", "company_code", "client")
    search_fields = ("code", "title", "product_name", "batch_number", "client__code", "client__description")


@admin.register(Chamber)
class ChamberAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "location", "storage_condition", "chamber_location", "is_active")
    list_filter = ("is_active", "storage_condition")
    search_fields = ("code", "name", "location")
    
    # ---- COPIA ESTO DENTRO DE CHAMBERADMIN ----
    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff
    
    # ==== 🚀 AGREGA ESTO AL FINAL DE CHAMBERADMIN ====
    def save_model(self, request, obj, form, change):
        # Si el usuario ha escrito algo en la temperatura, lo convertimos a float limpio
        if hasattr(obj, 'temperature_set_point') and obj.temperature_set_point is not None:
            obj.temperature_set_point = float(obj.temperature_set_point)
            
        # Si el usuario ha escrito algo en la humedad, lo convertimos a float limpio
        if hasattr(obj, 'humidity_set_point') and obj.humidity_set_point is not None:
            obj.humidity_set_point = float(obj.humidity_set_point)
            
        # Una vez transformados a float, Django y el sistema de logs los guardarán sin romper el JSON
        super().save_model(request, obj, form, change)


@admin.register(SamplingPoint)
class SamplingPointAdmin(admin.ModelAdmin):
    list_display = ("study", "label", "target_date", "tolerance_days", "recalculated_date")
    list_filter = ("study",)
    search_fields = ("label", "study__code", "study__title")


class SampleReceptionAdminForm(WebSampleReceptionForm):
    sample_code = forms.CharField(label="Código de muestra", required=False, disabled=True)

    class Meta(WebSampleReceptionForm.Meta):
        exclude = ("reception_number",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sample_code = ""
        if self.instance and self.instance.pk:
            first_sample = self.instance.samples.order_by("created_at").first()
            if first_sample:
                sample_code = first_sample.sample_code
        self.fields["sample_code"].initial = sample_code
        self.fields["sample_code"].widget.attrs["readonly"] = True
        self.order_fields([
            "study",
            "sample_code",
            "batch",
            "received_from",
            "received_by",
            "received_at",
            "quantity_received",
            "quantity_expected",
            "discrepancy_notes",
            "quantity_assigned",
            "quantity_reserved",
            "quantity_contingency",
            "status",
            "notes",
        ])


@admin.register(SampleReception)
class SampleReceptionAdmin(admin.ModelAdmin):
    list_display = ("codigo_muestra", "study", "batch", "received_from", "received_at", "quantity_received", "status")
    list_filter = ("status", "study")
    search_fields = ("received_from", "study__code", "study__title")
    form = SampleReceptionAdminForm
    fields = (
        "study",
        "sample_code",
        "batch",
        "received_from",
        "received_by",
        "received_at",
        "quantity_received",
        "quantity_expected",
        "discrepancy_notes",
        "quantity_assigned",
        "quantity_reserved",
        "quantity_contingency",
        "status",
        "notes",
    )

    @admin.display(description="Código de muestra")
    def codigo_muestra(self, obj):
        first_sample = obj.samples.order_by("created_at").first()
        return first_sample.sample_code if first_sample else "-"


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sample_code", "study", "reception", "sampling_point", "chamber", "quantity", "current_stock", "status")
    list_filter = ("status", "chamber", "study")
    search_fields = ("sample_code", "study__code", "qr_code")


@admin.register(SampleSchedule)
class SampleScheduleAdmin(admin.ModelAdmin):
    list_display = ("sample", "planned_date", "codigo_fecha", "texto_qr", "chamber", "chamber_location", "quantity", "fecha_salida", "is_active")
    list_filter = ("is_active", "planned_date", "chamber", "chamber_location")
    search_fields = ("sample__sample_code", "label", "schedule_qr_code", "notes", "chamber__code", "chamber_location__code")
    readonly_fields = ("label", "schedule_qr_code", "label_printed_at", "removed_at", "removed_by")
    
    fields = (
            "sample",
            "planned_date",
            "label",
            "schedule_qr_code",
            "label_printed_at",
            "removed_at",
            "removed_by",
            "chamber",
            "chamber_location",
            "quantity",
            "notes",
            "is_active",
        )

    
    @admin.display(description="Código fecha de muestreo")
    def codigo_fecha(self, obj):
        return obj.label

    @admin.display(description="Texto QR")
    def texto_qr(self, obj):
        return obj.schedule_qr_code or "-"

    @admin.display(description="Fecha salida")
    def fecha_salida(self, obj):
        return obj.removed_at or "-"



@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("sample", "movement_type", "quantity_delta", "executed_at", "notes")
    list_filter = ("movement_type",)
    search_fields = ("sample__sample_code", "notes")


@admin.register(ChamberDeviation)
class ChamberDeviationAdmin(admin.ModelAdmin):
    list_display = ("chamber", "study", "detected_at", "requires_recalculation")
    list_filter = ("requires_recalculation", "chamber")
    search_fields = ("chamber__code", "study__code", "description")


@admin.register(StabilityAlert)
class StabilityAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "study", "sample", "severity", "status", "due_date")
    list_filter = ("severity", "status")
    search_fields = ("title", "message")


# =====================================================================
# 🚀 CONTROL DE PERMISOS AUTOMÁTICO (VISTA TOTAL MENOS USUARIOS Y GRUPOS)
# =====================================================================

# 1. Definimos exactamente qué clases Admin del archivo queremos autorizar para el Staff
clases_maestras = [
    ProductAdmin, PackagingConfigurationAdmin, ProductBatchAdmin,
    StorageConditionAdmin, ChamberLocationAdmin, StudyAdmin,
    ChamberAdmin, SamplingPointAdmin, SampleReceptionAdmin,
    SampleAdmin, SampleScheduleAdmin, StockMovementAdmin, ChamberDeviationAdmin, 
    StabilityAlertAdmin, AuditTrailAdmin
]

# 2. Recorremos los modelos registrados en Django y aplicamos los permisos a sus instancias
for modelo, instance_admin in admin.site._registry.items():
    if type(instance_admin) in clases_maestras:
        instance_admin.has_module_permission = lambda request: request.user.is_staff
        instance_admin.has_view_permission = lambda request, obj=None: request.user.is_staff
        instance_admin.has_add_permission = lambda request: request.user.is_staff
        instance_admin.has_change_permission = lambda request, obj=None: request.user.is_staff
        instance_admin.has_delete_permission = lambda request, obj=None: request.user.is_staff


_original_get_app_list = admin.site.get_app_list


def _grouped_admin_app_list(request, app_label=None):
    app_list = _original_get_app_list(request, app_label)
    grouped_apps = []

    maestros_order = [
        "Client",
        "Chamber",
        "ChamberLocation",
        "StorageCondition",
        "PackagingConfiguration",
    ]
    stability_order = [
        "Study",
        "SampleReception",
        "SamplingPoint",
        "SampleSchedule",
        "StockMovement",
        "ChamberDeviation",
        "StabilityAlert",
    ]
    hidden_models = {"Product", "ProductBatch", "SamplingPoint", "Sample"}

    for app in app_list:
        if app.get("app_label") != "stability":
            grouped_apps.append(app)
            continue

        model_map = {model.get("object_name"): model for model in app.get("models", [])}
        model_map = {
            object_name: model
            for object_name, model in model_map.items()
            if object_name not in hidden_models
        }

        maestros_models_list = [
            model_map[name]
            for name in maestros_order
            if name in model_map
        ]
        stability_models_list = [
            model_map[name]
            for name in stability_order
            if name in model_map
        ]

        if maestros_models_list:
            maestros = deepcopy(app)
            maestros["name"] = "Maestros"
            maestros["app_label"] = "maestros"
            maestros["models"] = maestros_models_list + ([model_map["Client"]] if "Client" in model_map else [])
            grouped_apps.append(maestros)

        if stability_models_list:
            estabilidad = deepcopy(app)
            estabilidad["name"] = "Gestión de Estabilidades"
            estabilidad["app_label"] = "gestion_estabilidades"
            estabilidad["models"] = stability_models_list
            grouped_apps.append(estabilidad)
    return grouped_apps


admin.site.get_app_list = _grouped_admin_app_list
