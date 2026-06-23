from django.contrib import admin

from .models import AuditTrail


def _apply_admin_field_labels(model, labels):
    for field_name, label in labels.items():
        try:
            model._meta.get_field(field_name).verbose_name = label
        except Exception:
            continue


_apply_admin_field_labels(AuditTrail, {
    "action": "Acción",
    "action_type": "Tipo de acción",
    "entity_name": "Entidad",
    "entity_id": "ID de entidad",
    "object_repr": "Objeto",
    "payload": "Datos",
    "changes": "Cambios",
    "request_path": "Ruta",
    "request_method": "Método",
    "company_code": "Código empresa",
    "contact_code": "Código contacto",
    "performed_by": "Realizado por",
    "performed_at": "Realizado en",
})


ENTITY_LABELS = {
    "Study": "Estudio",
    "Sample": "Muestra",
    "SampleSchedule": "Fecha de muestreo",
    "SampleReception": "Recepción de muestra",
    "SamplingPoint": "Punto de muestreo",
    "Chamber": "Cámara",
    "ChamberDeviation": "Desviación de cámara",
    "StabilityAlert": "Alerta de estabilidad",
    "Product": "Producto",
    "ProductBatch": "Lote de producto",
    "PackagingConfiguration": "Configuración de acondicionamiento",
    "StorageCondition": "Condición de almacenamiento",
    "ChamberLocation": "Ubicación de cámara",
    "User": "Usuario",
}

ACTION_LABELS = {
    "create": "Alta",
    "update": "Modificación",
    "delete": "Borrado",
    "custom": "Acción manual",
}

METHOD_LABELS = {
    "POST": "Formulario / alta",
    "GET": "Consulta",
    "PUT": "Actualización",
    "PATCH": "Actualización parcial",
    "DELETE": "Borrado",
}


@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = (
        'entity_name',
        'entity_id',
        'action',
        'action_type',
        'performed_by',
        'company_code',
        'request_method',
        'performed_at',
    )
    list_filter = ('entity_name', 'action', 'action_type', 'company_code', 'request_method')
    search_fields = ('entity_name', 'entity_id', 'object_repr', 'request_path')
    readonly_fields = (
        'action',
        'action_type',
        'entity_name',
        'entity_id',
        'object_repr',
        'payload',
        'changes',
        'request_path',
        'request_method',
        'company_code',
        'contact_code',
        'performed_by',
        'performed_at',
    )

    def entity_name_display(self, obj):
        return ENTITY_LABELS.get(obj.entity_name, obj.entity_name)

    def action_type_display(self, obj):
        return ACTION_LABELS.get(obj.action_type, obj.action_type)

    def request_method_display(self, obj):
        return METHOD_LABELS.get(obj.request_method, obj.request_method)

    entity_name_display.short_description = "Entidad"
    action_type_display.short_description = "Tipo de acción"
    request_method_display.short_description = "Método"

    list_display = (
        "entity_name_display",
        "entity_id",
        "action",
        "action_type_display",
        "performed_by",
        "company_code",
        "request_method_display",
        "performed_at",
    )
    list_filter = ("entity_name", "action", "action_type", "company_code", "request_method")
