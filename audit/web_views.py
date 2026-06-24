from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from openpyxl import Workbook

from .models import AuditTrail


ACTION_LABELS = {
    "create": "Alta registrada",
    "update": "Modificacion registrada",
    "delete": "Eliminacion registrada",
    "web_create_study": "Estudio creado",
    "web_create_reception": "Recepcion registrada",
    "web_create_sample": "Muestra creada",
    "web_label_sample": "Muestra etiquetada",
    "web_place_in_chamber": "Entrada en camara registrada",
    "web_extract_sample": "Extraccion registrada",
    "web_create_sample_schedule": "Fecha de muestreo creada",
    "web_update_sample_schedule": "Fecha de muestreo actualizada",
    "web_delete_sample_schedule": "Fecha de muestreo eliminada",
    "web_generate_sample_schedule_label": "Etiqueta de fecha de muestreo generada",
    "web_withdraw_sample_schedule": "Fecha de muestreo retirada de camara",
    "web_create_chamber_deviation": "Desviacion de camara registrada",
    "web_recalculate_sampling_point": "Fecha de muestreo recalculada",
    "recalculate_date": "Recalculo de fecha registrado",
    "label_sample": "Muestra etiquetada",
    "place_in_chamber": "Entrada en camara registrada",
    "extract_sample": "Extraccion registrada",
    "seed_data": "Carga inicial de datos",
}

ENTITY_LABELS = {
    "Study": "Estudio",
    "Sample": "Muestra",
    "SampleReception": "Recepcion",
    "SampleSchedule": "Fecha de muestreo",
    "StockMovement": "Movimiento de stock",
    "SamplingPoint": "Punto de muestreo",
    "Chamber": "Camara",
    "ChamberDeviation": "Desviacion de camara",
    "ChamberLocation": "Ubicacion de camara",
    "StorageCondition": "Condicion de conservacion",
    "Product": "Producto",
    "ProductBatch": "Lote",
    "PackagingConfiguration": "Acondicionado",
    "LabelTemplate": "Plantilla de etiqueta",
    "User": "Usuario",
}


def _friendly_action(action):
    return ACTION_LABELS.get(action, action.replace("_", " ").capitalize())


def _friendly_entity(entity_name):
    return ENTITY_LABELS.get(entity_name, entity_name)


def _friendly_route(item):
    route_map = {
        "/app/studies/create/": "Pantalla de estudios",
        "/app/samples/create/": "Pantalla de muestras",
        "/app/operations/reception/": "Pantalla de operaciones / recepcion",
        "/app/operations/label/": "Pantalla de operaciones / etiquetado",
        "/app/operations/chamber/": "Pantalla de operaciones / entrada en camara",
        "/app/operations/extract/": "Pantalla de operaciones / extraccion",
        "/app/deviations/create/": "Pantalla de desviaciones",
        "/login/": "Inicio de sesion",
    }
    return route_map.get(item.request_path, item.request_path or "-")


def _decorate_audit(item):
    item.friendly_action = _friendly_action(item.action)
    item.friendly_entity = _friendly_entity(item.entity_name)
    item.friendly_route = _friendly_route(item)
    return item


def _filtered_audits(request):
    queryset = AuditTrail.objects.select_related("performed_by").all()
    entity_name = request.GET.get("entity_name")
    action_type = request.GET.get("action_type")
    company_code = request.GET.get("company_code")

    if entity_name:
        queryset = queryset.filter(entity_name__icontains=entity_name)
    if action_type:
        queryset = queryset.filter(action_type=action_type)
    if company_code:
        queryset = queryset.filter(company_code__icontains=company_code)
    return queryset


@login_required
def audit_list(request):
    audits = [_decorate_audit(item) for item in _filtered_audits(request)[:300]]
    context = {
        "audits": audits,
        "action_types": AuditTrail.ActionType.choices,
    }
    return render(request, "web/audit_list.html", context)


@login_required
def audit_detail(request, pk):
    audit = AuditTrail.objects.select_related("performed_by").get(pk=pk)
    audit = _decorate_audit(audit)
    return render(request, "web/audit_detail.html", {"audit": audit})


@login_required
def audit_export_excel(request):
    audits = _filtered_audits(request)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Audit Trail"
    worksheet.append(
        [
            "Fecha",
            "Usuario",
            "Accion",
            "Tipo",
            "Entidad",
            "Entity ID",
            "Company",
            "Metodo",
            "Ruta",
            "Objeto",
        ]
    )

    for item in audits:
        decorated = _decorate_audit(item)
        worksheet.append(
            [
                decorated.performed_at.strftime("%Y-%m-%d %H:%M:%S"),
                decorated.performed_by.username if decorated.performed_by else "",
                decorated.friendly_action,
                decorated.action_type,
                decorated.friendly_entity,
                decorated.entity_id,
                decorated.company_code,
                decorated.request_method,
                decorated.friendly_route,
                decorated.object_repr,
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="audit_trail.xlsx"'
    return response


@login_required
def audit_print_view(request):
    audits = [_decorate_audit(item) for item in _filtered_audits(request)[:500]]
    return render(request, "web/audit_print.html", {"audits": audits})
