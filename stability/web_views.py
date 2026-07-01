import base64
from io import BytesIO
import calendar
from datetime import timedelta
import os
from pathlib import Path
import re
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.dateparse import parse_date
from django.utils import timezone
from dotenv import load_dotenv
import qrcode

from audit.utils import register_audit_event

from .models import Chamber, ChamberDeviation, ChamberLocation, Client, LabelTemplate, PlannedSubsample, Product, ProductBatch, Sample, SampleReception, SampleSchedule, SamplingPoint, SamplingPointTemplate, StabilityAlert, StockMovement, Study, StudyPlanningEntry
from .web_forms import ChamberDeviationForm, ChamberPlacementForm, SampleCreateForm, SampleExtractionForm, SampleLabelForm, SampleRegistrationForm, SampleReceptionForm, SampleScheduleEditForm, SampleScheduleForm, StudyCreateForm, StudyEditForm


DEFAULT_SAMPLING_SCHEDULE = [
    ("T0", 0),
    ("T1", 30),
    ("T2", 60),
    ("T3", 90),
]

STUDY_CODE_PATTERN = "EST-{year}-{seq:03d}"
SAMPLE_CODE_PATTERN = "{study_code}-M-{seq:04d}"
RECEPTION_CODE_PATTERN = "REC-{year}-{seq:03d}"
BASE_DIR = Path(__file__).resolve().parent.parent


def _next_sequence(existing_values):
    max_seq = 0
    for value in existing_values:
        match = re.search(r"(\d+)$", value or "")
        if match:
            max_seq = max(max_seq, int(match.group(1)))
    return max_seq + 1


def generate_study_code():
    year = timezone.localdate().year
    existing = Study.objects.filter(code__startswith=f"EST-{year}-").values_list("code", flat=True)
    seq = _next_sequence(existing)
    return STUDY_CODE_PATTERN.format(year=year, seq=seq)


def generate_sample_code(study):
    existing = Sample.objects.filter(study=study).values_list("sample_code", flat=True)
    seq = _next_sequence(existing)
    return SAMPLE_CODE_PATTERN.format(study_code=study.code, seq=seq)


def _planned_subsample_code_base(study):
    first_sample = study.samples.order_by("created_at", "id").first()
    if first_sample and first_sample.sample_code:
        return first_sample.sample_code
    return study.code


def _generate_planned_subsample_code(study, seq):
    return f"{_planned_subsample_code_base(study)}-P-{seq:04d}"


def _refresh_planned_subsample_codes_for_study(study):
    subsamples_to_update = []
    for index, subsample in enumerate(study.planned_subsamples.order_by("id"), start=1):
        subsample.code = _generate_planned_subsample_code(study, index)
        subsamples_to_update.append(subsample)

    if subsamples_to_update:
        PlannedSubsample.objects.bulk_update(subsamples_to_update, ["code", "updated_at"])


def _refresh_sample_dependent_codes(sample):
    if sample.qr_code:
        sample.qr_code = f"QR::{sample.sample_code}"
        sample.save(update_fields=["qr_code", "updated_at"])

    schedules_to_update = []
    for index, schedule in enumerate(sample.schedules.order_by("created_at", "id"), start=1):
        schedule.label = f"{sample.sample_code}-F{index:03d}"
        if schedule.schedule_qr_code:
            schedule.schedule_qr_code = f"QR::{schedule.label}"
        schedules_to_update.append(schedule)

    if schedules_to_update:
        SampleSchedule.objects.bulk_update(schedules_to_update, ["label", "schedule_qr_code", "updated_at"])

    _refresh_planned_subsample_codes_for_study(sample.study)


def generate_reception_number():
    year = timezone.localdate().year
    prefix = f"REC-{year}-"
    existing = SampleReception.objects.filter(reception_number__startswith=prefix).values_list(
        "reception_number",
        flat=True,
    )
    seq = _next_sequence(existing)
    return RECEPTION_CODE_PATTERN.format(year=year, seq=seq)


def _get_page_size(request, allowed_sizes=None, default=10):
    allowed = allowed_sizes or {5, 10, 25, 50}
    try:
        page_size = int(request.GET.get("page_size") or default)
    except (TypeError, ValueError):
        page_size = default
    if page_size not in allowed:
        page_size = default
    return page_size


def _schedule_audit_changes(before_schedule, after_schedule):
    return {
        "planned_date": {
            "before": str(before_schedule.planned_date) if before_schedule and before_schedule.planned_date else None,
            "after": str(after_schedule.planned_date) if after_schedule.planned_date else None,
        },
        "chamber": {
            "before": before_schedule.chamber.code if before_schedule and before_schedule.chamber else None,
            "after": after_schedule.chamber.code if after_schedule.chamber else None,
        },
        "chamber_location": {
            "before": before_schedule.chamber_location.code if before_schedule and before_schedule.chamber_location else None,
            "after": after_schedule.chamber_location.code if after_schedule.chamber_location else None,
        },
        "quantity": {
            "before": before_schedule.quantity if before_schedule else None,
            "after": after_schedule.quantity,
        },
        "notes": {
            "before": before_schedule.notes if before_schedule else None,
            "after": after_schedule.notes,
        },
        "is_active": {
            "before": before_schedule.is_active if before_schedule else None,
            "after": after_schedule.is_active,
        },
        "removed_at": {
            "before": before_schedule.removed_at.isoformat() if before_schedule and before_schedule.removed_at else None,
            "after": after_schedule.removed_at.isoformat() if after_schedule.removed_at else None,
        },
        "removed_by": {
            "before": before_schedule.removed_by.username if before_schedule and before_schedule.removed_by else None,
            "after": after_schedule.removed_by.username if after_schedule.removed_by else None,
        },
    }


def _build_schedule_qr_code(schedule):
    return f"QR::{schedule.label}" if schedule.label else f"QR::SCHEDULE::{schedule.pk}"


def resolve_batch_from_code(batch_code):
    batch_code = (batch_code or "").strip()
    if not batch_code:
        return None
    return ProductBatch.objects.filter(code=batch_code).first()


def recalculate_reception_assigned_quantity(sample):
    reception = getattr(sample, "reception", None)
    if not reception:
        return 0
    assigned_total = sample.schedules.filter(is_active=True).aggregate(total=Sum("quantity")).get("total") or 0
    if assigned_total == 0:
        assigned_total = (
            sample.study.planned_subsamples.aggregate(total=Sum("quantity")).get("total") or 0
        )
    if reception.quantity_assigned != assigned_total:
        reception.quantity_assigned = assigned_total
        reception.save(update_fields=["quantity_assigned", "updated_at"])
    return assigned_total


def ensure_study_sampling_points(study):
    created_points = []
    base_start_date = getattr(study, "start_date", None)
    if study.sampling_points.exists() or not base_start_date:
        return created_points

    for label, days_offset in DEFAULT_SAMPLING_SCHEDULE:
        point = SamplingPoint.objects.create(
            study=study,
            label=label,
            target_date=base_start_date + timedelta(days=days_offset),
            tolerance_days=3,
        )
        created_points.append(point)
    return created_points


def ensure_sampling_point_templates():
    existing_months = set(SamplingPointTemplate.objects.values_list("month_number", flat=True))
    missing = []
    for month_number in range(1, 37):
        if month_number not in existing_months:
            missing.append(
                SamplingPointTemplate(
                    month_number=month_number,
                    label=f"{month_number}M",
                    is_active=True,
                )
            )
    if missing:
        SamplingPointTemplate.objects.bulk_create(missing)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_planning_matrix(study, chambers, templates):
    saved_entries = {
        (entry.sampling_point_template_id, entry.chamber_id, entry.analysis_type): entry.subsample_quantity
        for entry in study.planning_entries.all()
    }
    rows = []
    for template in templates:
        chamber_values = []
        has_any_quantity = False
        for chamber in chambers:
            fq_value = saved_entries.get((template.id, chamber.id, StudyPlanningEntry.AnalysisType.FQ), 0)
            micro_value = saved_entries.get((template.id, chamber.id, StudyPlanningEntry.AnalysisType.MICRO), 0)
            if fq_value or micro_value:
                has_any_quantity = True
            chamber_values.append({"chamber": chamber, "fq": fq_value, "micro": micro_value})
        if has_any_quantity:
            rows.append(
                {
                    "template_id": template.id,
                    "label": template.label,
                    "chamber_values": chamber_values,
                }
            )
    if not rows and templates:
        rows.append(
            {
                "template_id": templates[0].id,
                "label": templates[0].label,
                "chamber_values": [{"chamber": chamber, "fq": 0, "micro": 0} for chamber in chambers],
            }
        )
    return rows


def _save_study_planning_entries(request, study, chambers, templates):
    submitted_template_ids = request.POST.getlist("sampling_point_template")
    valid_templates = {str(template.id): template for template in templates}
    entries_to_create = []
    has_valid_template = False

    for raw_template_id in submitted_template_ids:
        template = valid_templates.get(str(raw_template_id))
        if not template:
            continue
        has_valid_template = True
        for chamber in chambers:
            fq_value = max(_safe_int(request.POST.get(f"qty_{template.id}_{chamber.id}_fq")), 0)
            micro_value = max(_safe_int(request.POST.get(f"qty_{template.id}_{chamber.id}_micro")), 0)
            if fq_value > 0:
                entries_to_create.append(
                    StudyPlanningEntry(
                        study=study,
                        sampling_point_template=template,
                        chamber=chamber,
                        analysis_type=StudyPlanningEntry.AnalysisType.FQ,
                        subsample_quantity=fq_value,
                    )
                )
            if micro_value > 0:
                entries_to_create.append(
                    StudyPlanningEntry(
                        study=study,
                        sampling_point_template=template,
                        chamber=chamber,
                        analysis_type=StudyPlanningEntry.AnalysisType.MICRO,
                        subsample_quantity=micro_value,
                    )
                )

    if not has_valid_template:
        return False, "Debes seleccionar al menos un punto de muestreo."

    with transaction.atomic():
        study.planning_entries.all().delete()
        if entries_to_create:
            StudyPlanningEntry.objects.bulk_create(entries_to_create)

    register_audit_event(
        study,
        "web_save_study_planning",
        payload={"study": study.code, "entries_count": len(entries_to_create)},
        changes={"planning_entries": {"before": None, "after": len(entries_to_create)}},
    )
    return True, None


def _extract_planning_entries_from_request(request, chambers, templates):
    submitted_template_ids = request.POST.getlist("sampling_point_template")
    valid_templates = {str(template.id): template for template in templates}
    extracted_entries = {}
    has_valid_template = False

    for raw_template_id in submitted_template_ids:
        template = valid_templates.get(str(raw_template_id))
        if not template:
            continue
        has_valid_template = True
        for chamber in chambers:
            fq_value = max(_safe_int(request.POST.get(f"qty_{template.id}_{chamber.id}_fq")), 0)
            micro_value = max(_safe_int(request.POST.get(f"qty_{template.id}_{chamber.id}_micro")), 0)
            if fq_value > 0:
                extracted_entries[(template.id, chamber.id, StudyPlanningEntry.AnalysisType.FQ)] = fq_value
            if micro_value > 0:
                extracted_entries[(template.id, chamber.id, StudyPlanningEntry.AnalysisType.MICRO)] = micro_value

    return has_valid_template, extracted_entries


def _request_planning_matches_saved(study, request, chambers, templates):
    has_valid_template, request_entries = _extract_planning_entries_from_request(request, chambers, templates)
    if not has_valid_template:
        return True

    saved_entries = {
        (entry.sampling_point_template_id, entry.chamber_id, entry.analysis_type): entry.subsample_quantity
        for entry in study.planning_entries.all()
    }
    return request_entries == saved_entries


def _study_received_quantity_total(study):
    total = (
        Sample.objects.filter(study=study, reception__isnull=False)
        .aggregate(total=Sum("reception__quantity_received"))
        .get("total")
    )
    return total or 0


def _study_planned_quantity_total(study):
    return study.planning_entries.aggregate(total=Sum("subsample_quantity")).get("total") or 0


def _generate_study_planning(study):
    planning_entries = list(
        study.planning_entries.select_related("sampling_point_template", "chamber").order_by(
            "sampling_point_template__month_number",
            "chamber__code",
            "analysis_type",
        )
    )
    if not planning_entries:
        return False, "Primero debes guardar una planificacion base con cantidades por punto y camara."

    planned_quantity_total = _study_planned_quantity_total(study)
    received_quantity_total = _study_received_quantity_total(study)
    if planned_quantity_total > received_quantity_total:
        return (
            False,
            f"La cantidad total planificada ({planned_quantity_total}) no puede superar la cantidad recibida ({received_quantity_total}).",
        )

    planned_subsamples = []
    sequence = 1
    for entry in planning_entries:
        planned_subsamples.append(
            PlannedSubsample(
                study=study,
                sampling_point_template=entry.sampling_point_template,
                chamber=entry.chamber,
                analysis_type=entry.analysis_type,
                code=_generate_planned_subsample_code(study, sequence),
                planned_date=None,
                actual_sampling_date=None,
                analysis_date=None,
                quantity=entry.subsample_quantity,
                location_notes="",
                status=PlannedSubsample.Status.IN_CHAMBER,
            )
        )
        sequence += 1

    with transaction.atomic():
        study.planned_subsamples.all().delete()
        PlannedSubsample.objects.bulk_create(planned_subsamples)
        for sample in study.samples.select_related("reception"):
            recalculate_reception_assigned_quantity(sample)

    register_audit_event(
        study,
        "web_generate_study_planning",
        payload={"study": study.code, "subsamples_count": len(planned_subsamples)},
        changes={"planned_subsamples": {"before": None, "after": len(planned_subsamples)}},
    )
    return True, len(planned_subsamples)


def _add_months(source_date, months):
    month_index = source_date.month - 1 + months
    year = source_date.year + (month_index // 12)
    month = (month_index % 12) + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return source_date.replace(year=year, month=month, day=day)


def _validate_study_can_be_approved(study):
    if not study.start_date:
        return False, "No puedes aprobar el estudio sin fecha de inicio."
    if not study.planning_entries.exists():
        return False, "No puedes aprobar el estudio sin planificacion base."
    if not study.planned_subsamples.exists():
        return False, "No puedes aprobar el estudio sin generar la planificacion."
    return True, None


def _apply_planned_dates_on_approval(study):
    updated_fields = []
    for subsample in study.planned_subsamples.select_related("sampling_point_template"):
        planned_date = _add_months(study.start_date, subsample.sampling_point_template.month_number)
        if subsample.planned_date != planned_date:
            subsample.planned_date = planned_date
            updated_fields.append(subsample)
    if updated_fields:
        PlannedSubsample.objects.bulk_update(updated_fields, ["planned_date", "updated_at"])


def _calculate_study_end_date(study):
    return (
        study.planned_subsamples.exclude(planned_date__isnull=True)
        .order_by("-planned_date")
        .values_list("planned_date", flat=True)
        .first()
    )


def _study_has_generated_planning(study):
    return study.planned_subsamples.exists()


def _withdraw_planned_subsample(study, subsample_id):
    if study.status != Study.Status.ACTIVE:
        return False, "Solo puedes retirar submuestras cuando el estudio esta aprobado."

    subsample = study.planned_subsamples.filter(pk=subsample_id).first()
    if not subsample:
        return False, "La submuestra seleccionada no existe para este estudio."

    if subsample.status == PlannedSubsample.Status.WITHDRAWN:
        return False, "La submuestra ya estaba retirada."

    subsample.status = PlannedSubsample.Status.WITHDRAWN
    subsample.actual_sampling_date = timezone.localdate()
    subsample.save(update_fields=["status", "actual_sampling_date", "updated_at"])

    register_audit_event(
        subsample,
        "web_withdraw_planned_subsample",
        payload={"study": study.code, "code": subsample.code},
        changes={
            "status": {"before": PlannedSubsample.Status.IN_CHAMBER, "after": subsample.status},
            "actual_sampling_date": {"before": None, "after": str(subsample.actual_sampling_date)},
        },
    )
    return True, None


def _update_planned_subsample(study, subsample_id, request):
    subsample = study.planned_subsamples.filter(pk=subsample_id).first()
    if not subsample:
        return False, "La submuestra seleccionada no existe para este estudio."

    analysis_date_raw = (request.POST.get("analysis_date") or "").strip()
    quantity_raw = (request.POST.get("quantity") or "").strip()
    subsample.quantity = _safe_int(quantity_raw, None) if quantity_raw else None
    subsample.storage_location = (request.POST.get("storage_location") or "").strip()
    subsample.location_notes = (request.POST.get("location_notes") or "").strip()
    subsample.analysis_date = parse_date(analysis_date_raw) if analysis_date_raw else None
    subsample.save(update_fields=["quantity", "storage_location", "location_notes", "analysis_date", "updated_at"])

    register_audit_event(
        subsample,
        "web_update_planned_subsample",
        payload={"study": study.code, "code": subsample.code},
        changes={"updated": {"before": False, "after": True}},
    )
    return True, None


def _planned_location_matches_chamber(chamber, location_code):
    chamber_code = (getattr(chamber, "code", "") or "").strip().upper().replace("-", "")
    normalized_location_code = (location_code or "").strip().upper()
    if not chamber_code or not normalized_location_code:
        return False
    return normalized_location_code.startswith(f"{chamber_code}-")


def _update_planned_subsample_location(study, subsample_id, request):
    subsample = study.planned_subsamples.select_related("chamber").filter(pk=subsample_id).first()
    if not subsample:
        return False, "La submuestra seleccionada no existe para este estudio."

    storage_location = (request.POST.get("storage_location") or "").strip()
    if storage_location and not _planned_location_matches_chamber(subsample.chamber, storage_location):
        return False, "La ubicación seleccionada no pertenece a la cámara de esta submuestra."

    before_location = subsample.storage_location
    subsample.storage_location = storage_location
    subsample.save(update_fields=["storage_location", "updated_at"])

    register_audit_event(
        subsample,
        "web_update_planned_subsample_location",
        payload={"study": study.code, "code": subsample.code},
        changes={"storage_location": {"before": before_location, "after": subsample.storage_location}},
    )
    return True, None


def _mark_planned_subsample_label_printed(subsample):
    subsample.label_printed_at = timezone.now()
    subsample.save(update_fields=["label_printed_at", "updated_at"])
    register_audit_event(
        subsample,
        "web_print_planned_subsample_label",
        payload={"code": subsample.code},
        changes={"label_printed_at": {"before": None, "after": subsample.label_printed_at.isoformat()}},
    )


class AppLoginView(LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("web-studies")


class AppLogoutView(LogoutView):
    pass


@login_required
def dashboard(request):
    studies = Study.objects.order_by("-created_at")[:5]
    alerts = StabilityAlert.objects.filter(status=StabilityAlert.Status.OPEN).order_by("due_date")[:8]
    upcoming_points = SamplingPoint.objects.order_by("recalculated_date", "target_date")[:8]
    chamber_load = Chamber.objects.annotate(sample_count=Count("samples")).order_by("-sample_count", "code")[:6]
    upcoming_extractions = Sample.objects.select_related("study", "sampling_point").filter(
        sampling_point__isnull=False,
        current_stock__gt=0,
    ).order_by("sampling_point__recalculated_date", "sampling_point__target_date")[:8]
    context = {
        "studies_count": Study.objects.count(),
        "samples_count": Sample.objects.count(),
        "receptions_count": SampleReception.objects.count(),
        "low_stock_count": Sample.objects.filter(current_stock__lte=2).count(),
        "stock_total": Sample.objects.aggregate(total=Sum("current_stock")).get("total") or 0,
        "active_studies_count": Study.objects.filter(status=Study.Status.ACTIVE).count(),
        "closed_studies_count": Study.objects.filter(status=Study.Status.CLOSED).count(),
        "open_deviations_count": ChamberDeviation.objects.filter(requires_recalculation=True).count(),
        "upcoming_entries_count": Sample.objects.filter(
            status__in=[Sample.Status.RECEIVED, Sample.Status.LABELLED]
        ).count(),
        "alerts": alerts,
        "studies": studies,
        "upcoming_points": upcoming_points,
        "upcoming_extractions": upcoming_extractions,
        "chamber_load": chamber_load,
        "today": timezone.localdate(),
    }
    return render(request, "web/dashboard.html", context)


@login_required
def studies_list(request):
    search_term = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    client_filter = (request.GET.get("client") or "").strip()
    product_filter = (request.GET.get("product") or "").strip()
    try:
        page_size = int(request.GET.get("page_size") or 10)
    except (TypeError, ValueError):
        page_size = 10
    if page_size not in {10, 25, 50}:
        page_size = 10

    studies = Study.objects.select_related("study_type", "client", "product").annotate(sample_count=Count("samples", distinct=True))
    if search_term:
        studies = studies.filter(
            Q(code__icontains=search_term)
            | Q(title__icontains=search_term)
            | Q(product_name__icontains=search_term)
            | Q(product_code__icontains=search_term)
            | Q(client__description__icontains=search_term)
        )
    if status_filter in {choice for choice, _label in Study.Status.choices}:
        studies = studies.filter(status=status_filter)
    if client_filter.isdigit():
        studies = studies.filter(client_id=int(client_filter))
    if product_filter.isdigit():
        studies = studies.filter(product_id=int(product_filter))
    studies = studies.order_by("-created_at")

    paginator = Paginator(studies, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)

    filter_params = {
        "q": search_term,
        "status": status_filter,
        "client": client_filter,
        "product": product_filter,
        "page_size": page_size,
    }
    query_string = urlencode({key: value for key, value in filter_params.items() if value not in {"", None}})
    total_count = paginator.count
    start_index = page_obj.start_index() if total_count else 0
    end_index = page_obj.end_index() if total_count else 0

    return render(
        request,
        "web/studies.html",
        {
            "studies": page_obj.object_list,
            "page_obj": page_obj,
            "page_numbers": page_numbers,
            "page_size": page_size,
            "query_string": query_string,
            "total_count": total_count,
            "start_index": start_index,
            "end_index": end_index,
            "study_form": StudyCreateForm(),
            "edit_study_form": StudyEditForm(),
            "search_term": search_term,
            "selected_status": status_filter,
            "selected_client": client_filter,
            "selected_product": product_filter,
            "status_choices": Study.Status.choices,
            "clients": Client.objects.order_by("description"),
            "products": Product.objects.order_by("name"),
        },
    )


@login_required
def create_study_web(request):
    if request.method != "POST":
        return redirect("web-studies")
    form = StudyCreateForm(request.POST)
    if form.is_valid():
        study = form.save(commit=False)
        if not study.code:
            study.code = generate_study_code()
        study.company_code = getattr(request, "company_code", "") or getattr(request.user, "company_code", "") or "AGQ"
        if study.product and not study.product_code:
            study.product_code = study.product.code
        if study.product and not study.product_name:
            study.product_name = study.product.name
        if study.status == Study.Status.ACTIVE:
            can_approve, error_message = _validate_study_can_be_approved(study)
            if not can_approve:
                messages.error(request, error_message or "No se pudo aprobar el estudio.")
                return redirect("web-studies")
        study.save()
        created_points = ensure_study_sampling_points(study)
        if study.status == Study.Status.ACTIVE:
            _apply_planned_dates_on_approval(study)
            study.end_date = _calculate_study_end_date(study)
            study.approved_at = timezone.now()
            study.approved_by = request.user if request.user.is_authenticated else None
            study.save(update_fields=["end_date", "approved_at", "approved_by", "updated_at"])
        register_audit_event(
            study,
            "web_create_study",
            payload={"code": study.code, "title": study.title},
            changes={"status": {"before": None, "after": study.status}},
        )
        for point in created_points:
            register_audit_event(
                point,
                "web_create_sampling_point",
                payload={"study": study.code, "point": point.label},
                changes={"target_date": {"before": None, "after": str(point.target_date)}},
            )
        messages.success(request, f"Estudio {study.code} creado correctamente.")
    else:
        if wants_print and is_ajax:
            errors = []
            for field_errors in form.errors.values():
                errors.extend(field_errors)
            return JsonResponse({"ok": False, "errors": errors}, status=400)
        if wants_print and is_ajax:
            errors = []
            for field_errors in form.errors.values():
                errors.extend(field_errors)
            return JsonResponse({"ok": False, "errors": errors}, status=400)
        messages.error(request, "No se pudo crear el estudio. Revisa los campos obligatorios.")
    return redirect("web-studies")


@login_required
def edit_study_web(request, pk):
    study = get_object_or_404(Study, pk=pk)
    if request.method != "POST":
        return redirect("web-studies")
    original_status = study.status
    form = StudyEditForm(request.POST, instance=study)
    if form.is_valid():
        updated_study = form.save(commit=False)
        is_approving = original_status != Study.Status.ACTIVE and updated_study.status == Study.Status.ACTIVE
        if not updated_study.code:
            updated_study.code = study.code
        if updated_study.product and not updated_study.product_code:
            updated_study.product_code = updated_study.product.code
        if updated_study.product and not updated_study.product_name:
            updated_study.product_name = updated_study.product.name

        if is_approving:
            can_approve, error_message = _validate_study_can_be_approved(updated_study)
            if not can_approve:
                messages.error(request, error_message or "No se pudo aprobar el estudio.")
                return redirect("web-studies")

        updated_study.save()
        if is_approving:
            _apply_planned_dates_on_approval(updated_study)
            updated_study.end_date = _calculate_study_end_date(updated_study)
            updated_study.approved_at = timezone.now()
            updated_study.approved_by = request.user if request.user.is_authenticated else None
            updated_study.save(update_fields=["end_date", "approved_at", "approved_by", "updated_at"])
        register_audit_event(
            updated_study,
            "web_update_study",
            payload={"code": updated_study.code, "title": updated_study.title},
            changes={"status": {"before": original_status, "after": updated_study.status}},
        )
        messages.success(request, f"Estudio {updated_study.code} actualizado correctamente.")
    else:
        messages.error(request, "No se pudo actualizar el estudio. Revisa los campos obligatorios.")
    return redirect("web-studies")


@login_required
def delete_study_web(request, pk):
    study = get_object_or_404(Study, pk=pk)
    if request.method == "POST":
        if study.status != Study.Status.DRAFT:
            messages.error(request, "Solo se pueden eliminar estudios en elaboracion.")
            return redirect("web-studies")
        register_audit_event(
            study,
            "web_delete_study",
            payload={"code": study.code, "title": study.title},
            changes={"deleted": {"before": False, "after": True}},
        )
        study.delete()
        messages.success(request, f"Estudio {study.code} eliminado correctamente.")
    return redirect("web-studies")


@login_required
def samples_list(request):
    study_id = request.GET.get("study")
    search_term = (request.GET.get("q") or "").strip()
    page_size = _get_page_size(request)
    auto_open_create = request.GET.get("open") == "create"
    sample_initial = {}
    study = None
    reception = None
    client_code = ""
    if study_id:
        study = get_object_or_404(Study, pk=study_id)
        if study.client:
            client_code = study.client.code

        sample_initial["study"] = study
        sample_initial["sample_code"] = generate_sample_code(study)
        reception = (
            SampleReception.objects.filter(study=study)
            .order_by("-received_at", "-created_at")
            .first()
        )
        if reception:
            sample_initial["reception"] = reception
            if reception.quantity_received:
                sample_initial["quantity"] = reception.quantity_received
                sample_initial["current_stock"] = reception.quantity_received
    sample_code_preview = generate_sample_code(study) if study else ""
    samples = Sample.objects.select_related(
        "study",
        "study__client",
        "sampling_point",
        "chamber",
        "reception",
        "reception__packaging",
        "reception__batch",
    )
    
    if study_id:
        samples = samples.filter(study_id=study_id)
    if search_term:
        samples = samples.filter(
            Q(sample_code__icontains=search_term)
            | Q(study__code__icontains=search_term)
            | Q(study__client__description__icontains=search_term)
            | Q(study__client__code__icontains=search_term)
        )

    samples = samples.order_by("-created_at")
    paginator = Paginator(samples, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)
    filter_params = {
        "study": study_id,
        "q": search_term,
        "page_size": page_size,
    }
    query_string = urlencode({key: value for key, value in filter_params.items() if value not in {"", None}})
    samples = list(page_obj.object_list)
    for sample in samples:
        sample.assigned_quantity_live = recalculate_reception_assigned_quantity(sample)

    return render(
        request,
        "web/samples.html",
        {
            "samples": samples,
            "sample_form": SampleRegistrationForm(initial=sample_initial),
            "sample_edit_form": SampleRegistrationForm(),
            "preselected_study": study,
            "preselected_reception": reception,
            "sample_code_preview": sample_code_preview,
            "client_code": client_code,
            "auto_open_create_sample": auto_open_create,
            "search_term": search_term,
            "page_obj": page_obj,
            "page_numbers": page_numbers,
            "page_size": page_size,
            "query_string": query_string,
            "total_count": paginator.count,
            "start_index": page_obj.start_index() if paginator.count else 0,
            "end_index": page_obj.end_index() if paginator.count else 0,
        },
    )


@login_required
def sample_schedules_view(request, pk):
    sample = get_object_or_404(Sample.objects.select_related("study"), pk=pk)
    sample.assigned_quantity_live = recalculate_reception_assigned_quantity(sample)
    schedules = sample.schedules.select_related("chamber", "chamber_location").order_by("planned_date", "id")
    context = {
        "sample": sample,
        "schedules": schedules,
        "schedule_form": SampleScheduleForm(),
        "filter_active": True,
    }
    return render(request, "web/sample_schedules.html", context)


@login_required
def planning_list_view(request):
    status_filter = (request.GET.get("status") or "").strip()
    page_size = _get_page_size(request)
    studies = Study.objects.select_related("study_type", "client", "product")
    if status_filter in {choice for choice, _label in Study.Status.choices}:
        studies = studies.filter(status=status_filter)
    studies = studies.order_by("-created_at")
    paginator = Paginator(studies, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)
    filter_params = {
        "status": status_filter,
        "page_size": page_size,
    }
    query_string = urlencode({key: value for key, value in filter_params.items() if value not in {"", None}})
    context = {
        "studies": page_obj.object_list,
        "selected_status": status_filter,
        "status_choices": Study.Status.choices,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "page_size": page_size,
        "query_string": query_string,
        "total_count": paginator.count,
        "start_index": page_obj.start_index() if paginator.count else 0,
        "end_index": page_obj.end_index() if paginator.count else 0,
    }
    return render(request, "web/planning_list.html", context)


@login_required
def planning_study_view(request, pk):
    study = get_object_or_404(
        Study.objects.select_related("study_type", "client", "product"),
        pk=pk,
    )
    page_size = _get_page_size(request)
    ensure_sampling_point_templates()
    chambers = list(Chamber.objects.filter(is_active=True).order_by("code"))
    chamber_locations = list(ChamberLocation.objects.filter(is_active=True).order_by("code"))
    templates = list(SamplingPointTemplate.objects.filter(is_active=True).order_by("month_number"))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "generate_planning":
            if not _request_planning_matches_saved(study, request, chambers, templates):
                messages.error(
                    request,
                    "Hay cambios sin guardar en la planificacion base. Guarda primero la plantilla actualizada antes de generar.",
                )
                return redirect("web-study-planning", pk=study.pk)
            ok, result = _generate_study_planning(study)
            if ok:
                messages.success(request, f"Planificacion generada correctamente con {result} submuestras.")
                return redirect("web-study-planning", pk=study.pk)
            messages.error(request, result or "No se pudo generar la planificacion.")
        elif action == "withdraw_subsample":
            ok, error_message = _withdraw_planned_subsample(study, request.POST.get("subsample_id"))
            if ok:
                messages.success(request, "Submuestra retirada correctamente.")
                return redirect("web-study-planning", pk=study.pk)
            messages.error(request, error_message or "No se pudo retirar la submuestra.")
            return redirect("web-study-planning", pk=study.pk)
        elif action == "edit_subsample":
            ok, error_message = _update_planned_subsample(study, request.POST.get("subsample_id"), request)
            if ok:
                messages.success(request, "Submuestra actualizada correctamente.")
            else:
                messages.error(request, error_message or "No se pudo actualizar la submuestra.")
            return redirect("web-study-planning", pk=study.pk)
        elif action == "update_subsample_location":
            ok, error_message = _update_planned_subsample_location(study, request.POST.get("subsample_id"), request)
            if ok:
                messages.success(request, "Ubicación actualizada correctamente.")
            else:
                messages.error(request, error_message or "No se pudo actualizar la ubicación.")
            return redirect("web-study-planning", pk=study.pk)
        else:
            ok, error_message = _save_study_planning_entries(request, study, chambers, templates)
            if ok:
                messages.success(request, "Planificacion base guardada correctamente.")
                return redirect("web-study-planning", pk=study.pk)
            messages.error(request, error_message or "No se pudo guardar la planificacion.")

    study_samples = list(
        Sample.objects.select_related("chamber", "sampling_point", "reception", "reception__packaging", "reception__batch")
        .filter(study=study)
        .order_by("sample_code")
    )
    for sample in study_samples:
        sample.assigned_quantity_live = recalculate_reception_assigned_quantity(sample)
    planning_rows = (
        SampleSchedule.objects.select_related("sample", "chamber", "chamber_location")
        .filter(sample__study=study)
        .order_by("planned_date", "sample__sample_code", "id")[:25]
    )
    planning_matrix_rows = _build_planning_matrix(study, chambers, templates)
    generated_subsamples_qs = study.planned_subsamples.select_related("sampling_point_template", "chamber").order_by(
        "sampling_point_template__month_number",
        "code",
    )
    paginator = Paginator(generated_subsamples_qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)
    query_string = urlencode({"page_size": page_size})
    context = {
        "study": study,
        "study_samples": study_samples,
        "planning_rows": planning_rows,
        "planning_matrix_rows": planning_matrix_rows,
        "active_chambers": chambers,
        "chamber_locations": chamber_locations,
        "sampling_point_templates": templates,
        "generated_subsamples": page_obj.object_list,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "page_size": page_size,
        "query_string": query_string,
        "total_count": paginator.count,
        "start_index": page_obj.start_index() if paginator.count else 0,
        "end_index": page_obj.end_index() if paginator.count else 0,
    }
    return render(request, "web/planning.html", context)


def _build_client_report_context(study):
    study_samples = list(
        Sample.objects.select_related("reception", "reception__packaging", "reception__batch")
        .filter(study=study)
        .order_by("sample_code")
    )
    for sample in study_samples:
        sample.assigned_quantity_live = recalculate_reception_assigned_quantity(sample)

    planned_subsamples = list(
        study.planned_subsamples.select_related(
            "sampling_point_template",
            "chamber",
            "chamber__storage_condition",
        ).order_by(
            "sampling_point_template__month_number",
            "chamber__code",
            "code",
        )
    )

    chamber_conditions = []
    chamber_seen = set()
    for subsample in planned_subsamples:
        if subsample.chamber_id in chamber_seen:
            continue
        chamber_seen.add(subsample.chamber_id)
        chamber_conditions.append(
            {
                "chamber_code": subsample.chamber.code,
                "condition_label": (
                    subsample.chamber.storage_condition.name
                    if subsample.chamber.storage_condition
                    else "-"
                ),
                "temperature": (
                    f"{subsample.chamber.temperature_set_point:g} C"
                    if subsample.chamber.temperature_set_point is not None
                    else "-"
                ),
                "humidity": (
                    f"{subsample.chamber.humidity_set_point:g} %"
                    if subsample.chamber.humidity_set_point is not None
                    else "-"
                ),
            }
        )

    planning_groups_map = {}
    for subsample in planned_subsamples:
        key = subsample.sampling_point_template_id
        if key not in planning_groups_map:
            planning_groups_map[key] = {
                "title": f"Punto de muestreo: {subsample.sampling_point_template.label}",
                "month_number": subsample.sampling_point_template.month_number,
                "rows": [],
            }
        planning_groups_map[key]["rows"].append(subsample)

    planning_groups = sorted(
        planning_groups_map.values(),
        key=lambda item: item["month_number"],
    )

    total_received = sum((sample.reception.quantity_received or sample.quantity or 0) for sample in study_samples)
    total_assigned = sum(sample.assigned_quantity_live or 0 for sample in study_samples)
    total_subsamples = len(planned_subsamples)
    withdrawn_subsamples = sum(
        1 for subsample in planned_subsamples if subsample.status == PlannedSubsample.Status.WITHDRAWN
    )
    pending_subsamples = total_subsamples - withdrawn_subsamples
    summary_copy = (
        f"Se han recibido {len(study_samples)} muestras con un total de {total_received} unidades y "
        f"se han asignado {total_assigned}. La planificacion incluye {total_subsamples} submuestras, "
        f"de las cuales {withdrawn_subsamples} han sido retiradas y {pending_subsamples} siguen programadas o en camara."
    )

    return {
        "study": study,
        "study_samples": study_samples,
        "planned_subsamples": planned_subsamples,
        "chamber_conditions": chamber_conditions,
        "planning_groups": planning_groups,
        "summary_copy": summary_copy,
        "generated_at": timezone.localtime(timezone.now()),
        "default_email_subject": f"Informe global del estudio {study.code}",
        "default_email_message": (
            f"Adjuntamos el informe global del estudio {study.code} - {study.title}.\n\n"
            "Este correo se ha generado desde NetLab One Stability."
        ),
    }


def _parse_email_recipients(raw_value):
    recipients = []
    for chunk in (raw_value or "").replace(";", ",").split(","):
        email = chunk.strip()
        if not email:
            continue
        validate_email(email)
        recipients.append(email)
    return recipients


def _get_runtime_email_setting(name, default=""):
    load_dotenv(BASE_DIR / ".env", override=True)
    raw_value = os.getenv(name, getattr(settings, name, default))
    if raw_value is None:
        return default
    return str(raw_value).strip().strip('"').strip("'")


def _client_report_pdf_link_callback(uri, rel):
    if uri.startswith(settings.STATIC_URL):
        relative_path = uri.replace(settings.STATIC_URL, "", 1).lstrip("/")
        return str(BASE_DIR / "static" / relative_path)
    if uri.startswith(settings.MEDIA_URL):
        relative_path = uri.replace(settings.MEDIA_URL, "", 1).lstrip("/")
        return str(Path(settings.MEDIA_ROOT) / relative_path)
    return uri


def _render_client_report_pdf(context, request=None):
    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise ValueError(
            "No se pudo generar el PDF porque falta instalar xhtml2pdf en este entorno."
        ) from exc

    pdf_html = render_to_string("web/client_report_pdf.html", context, request=request)
    pdf_buffer = BytesIO()
    pdf = pisa.CreatePDF(
        src=pdf_html,
        dest=pdf_buffer,
        encoding="utf-8",
        link_callback=_client_report_pdf_link_callback,
    )
    if pdf.err:
        raise ValueError("No se pudo generar el PDF del informe.")
    return pdf_buffer.getvalue()


def _send_client_report_email(request, study, context):
    if _get_runtime_email_setting("REPORT_EMAIL_ENABLED", "true").lower() != "true":
        raise ValueError("El envio de correo esta desactivado en la configuracion actual.")
    email_host_user = _get_runtime_email_setting("EMAIL_HOST_USER")
    email_host_password = _get_runtime_email_setting("EMAIL_HOST_PASSWORD")
    default_from_email = _get_runtime_email_setting("DEFAULT_FROM_EMAIL") or email_host_user

    if not email_host_user or not email_host_password:
        raise ValueError("Falta configurar EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en el archivo .env.")

    recipients = _parse_email_recipients(request.POST.get("email_to"))
    if not recipients:
        raise ValueError("Debes indicar al menos un destinatario.")

    subject = (request.POST.get("email_subject") or "").strip() or context["default_email_subject"]
    message = (request.POST.get("email_message") or "").strip() or context["default_email_message"]
    report_url = request.build_absolute_uri(f"/app/studies/{study.pk}/client-report/")
    html_body = (
        f"<p>{message.replace(chr(10), '<br>')}</p>"
        f"<p><strong>Estudio:</strong> {study.code} - {study.title}</p>"
        f"<p>Puedes consultar tambien la vista web del informe aqui: "
        f"<a href=\"{report_url}\">{report_url}</a></p>"
    )

    attachment_context = {
        **context,
        "email_mode": True,
    }
    report_pdf = _render_client_report_pdf(attachment_context, request=request)

    email = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=default_from_email,
        to=recipients,
    )
    email.connection = get_connection(
        host=_get_runtime_email_setting("EMAIL_HOST", "smtp.gmail.com"),
        port=int(_get_runtime_email_setting("EMAIL_PORT", "587") or 587),
        username=email_host_user,
        password=email_host_password,
        use_tls=_get_runtime_email_setting("EMAIL_USE_TLS", "true").lower() == "true",
        use_ssl=_get_runtime_email_setting("EMAIL_USE_SSL", "false").lower() == "true",
    )
    email.attach_alternative(html_body, "text/html")
    email.attach(
        filename=f"informe_{study.code}.pdf",
        content=report_pdf,
        mimetype="application/pdf",
    )
    email.send(fail_silently=False)
    return recipients


@login_required
def client_report_view(request, pk):
    study = get_object_or_404(
        Study.objects.select_related("study_type", "client", "product"),
        pk=pk,
    )
    if not _study_has_generated_planning(study):
        messages.error(request, "Solo se puede generar el informe cliente cuando el estudio tenga la planificacion generada.")
        return redirect("web-study-planning", pk=study.pk)

    context = _build_client_report_context(study)
    if request.method == "POST" and request.POST.get("action") == "send_email":
        context["email_to_value"] = request.POST.get("email_to", "").strip()
        context["email_subject_value"] = request.POST.get("email_subject", "").strip() or context["default_email_subject"]
        context["email_message_value"] = request.POST.get("email_message", "").strip() or context["default_email_message"]
        context["open_email_modal"] = True
        try:
            recipients = _send_client_report_email(request, study, context)
            register_audit_event(
                study,
                "web_send_client_report_email",
                payload={"code": study.code, "recipients": recipients},
                changes={"report_email_sent": {"before": False, "after": True}},
            )
            messages.success(request, f"Informe enviado correctamente a {', '.join(recipients)}.")
            return redirect("web-client-report", pk=study.pk)
        except (ValueError, ValidationError) as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"No se pudo enviar el correo: {exc}")
    return render(request, "web/client_report.html", context)


@login_required
def planned_subsample_label_batch_view(request, pk):
    study = get_object_or_404(
        Study.objects.select_related("study_type", "client", "product"),
        pk=pk,
    )
    if not _study_has_generated_planning(study):
        messages.error(request, "Solo se pueden imprimir etiquetas cuando el estudio tenga la planificacion generada.")
        return redirect("web-study-planning", pk=study.pk)

    subsamples = list(
        study.planned_subsamples.select_related("chamber", "chamber__storage_condition", "sampling_point_template")
        .order_by("sampling_point_template__month_number", "chamber__code", "code")
    )
    for subsample in subsamples:
        if not subsample.label_printed_at:
            _mark_planned_subsample_label_printed(subsample)
        qr_value = f"QR::{subsample.code}"
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(qr_value)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        subsample.qr_value = qr_value
        subsample.qr_image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    context = {
        "study": study,
        "subsamples": subsamples,
        "autoprint": request.GET.get("autoprint") == "1",
    }
    return render(request, "web/planned_subsample_label_batch.html", context)


@login_required
def alerts_list(request):
    page_size = _get_page_size(request)
    alerts = StabilityAlert.objects.select_related("study", "sample").order_by("status", "due_date")
    paginator = Paginator(alerts, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)
    query_string = urlencode({"page_size": page_size})
    return render(request, "web/alerts.html", {
        "alerts": page_obj.object_list,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "page_size": page_size,
        "query_string": query_string,
        "total_count": paginator.count,
        "start_index": page_obj.start_index() if paginator.count else 0,
        "end_index": page_obj.end_index() if paginator.count else 0,
    })


@login_required
def operations_hub(request):
    selected_chamber = request.GET.get("chamber", "").strip()
    selected_study = request.GET.get("study", "").strip()
    show_history = request.GET.get("show") == "all"
    page_size = _get_page_size(request)
    chamber_contents = SampleSchedule.objects.select_related(
        "sample",
        "sample__study",
        "chamber",
        "chamber_location",
        "removed_by",
    ).filter(chamber__isnull=False)
    if selected_chamber:
        chamber_contents = chamber_contents.filter(chamber_id=selected_chamber)
    if selected_study:
        chamber_contents = chamber_contents.filter(sample__study_id=selected_study)
    if not show_history:
        chamber_contents = chamber_contents.filter(is_active=True)

    chamber_summary = Chamber.objects.filter(is_active=True).annotate(
        active_schedule_count=Count("sample_schedules", filter=Q(sample_schedules__is_active=True))
    ).order_by("code")
    context = {
        "chambers": Chamber.objects.filter(is_active=True).order_by("code"),
        "studies": Study.objects.order_by("code"),
        "selected_chamber": selected_chamber,
        "selected_study": selected_study,
        "show_history": show_history,
        "chamber_summary": chamber_summary,
        "active_count": chamber_contents.filter(is_active=True).count() if show_history else chamber_contents.count(),
        "retired_count": chamber_contents.filter(is_active=False).count() if show_history else 0,
    }
    chamber_contents = chamber_contents.order_by("chamber__code", "planned_date", "sample__sample_code", "id")
    paginator = Paginator(chamber_contents, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)
    filter_params = {
        "chamber": selected_chamber,
        "study": selected_study,
        "show": "all" if show_history else "active",
        "page_size": page_size,
    }
    context.update({
        "chamber_contents": page_obj.object_list,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "page_size": page_size,
        "query_string": urlencode({key: value for key, value in filter_params.items() if value not in {"", None}}),
        "total_count": paginator.count,
        "start_index": page_obj.start_index() if paginator.count else 0,
        "end_index": page_obj.end_index() if paginator.count else 0,
    })
    return render(request, "web/operations.html", context)


@login_required
def annual_plan_view(request):
    today = timezone.localdate()
    next_30_days = today + timedelta(days=30)
    located_in_chamber_filter = Q(status=PlannedSubsample.Status.IN_CHAMBER) & ~Q(storage_location="")

    active_studies = list(
        Study.objects.select_related("client", "product")
        .filter(status=Study.Status.ACTIVE)
        .order_by("start_date", "code")
    )
    planned_studies = list(
        Study.objects.select_related("client", "product")
        .filter(status=Study.Status.DRAFT)
        .order_by("start_date", "code")
    )

    upcoming_pending_subsamples = (
        PlannedSubsample.objects.select_related("study", "chamber", "sampling_point_template")
        .filter(located_in_chamber_filter, planned_date__gte=today)
        .order_by("planned_date", "study__code", "sampling_point_template__month_number")
    )
    next_subsample_by_study = {}
    for subsample in upcoming_pending_subsamples:
        next_subsample_by_study.setdefault(subsample.study_id, subsample)

    active_study_rows = []
    for study in active_studies[:6]:
        next_hito = next_subsample_by_study.get(study.id)
        active_study_rows.append(
            {
                "study": study,
                "next_hito_label": (
                    f"{next_hito.sampling_point_template.label} - {next_hito.planned_date.strftime('%d/%m/%Y')}"
                    if next_hito and next_hito.planned_date
                    else "Sin proximos hitos"
                ),
            }
        )

    chamber_rows = []
    chambers = list(
        Chamber.objects.select_related("storage_condition")
        .filter(is_active=True)
        .annotate(
            active_subsample_count=Count(
                "planned_subsamples",
                filter=Q(planned_subsamples__status=PlannedSubsample.Status.IN_CHAMBER) & ~Q(planned_subsamples__storage_location=""),
            ),
            open_deviation_count=Count("deviations", filter=Q(deviations__ended_at__isnull=True)),
        )
        .order_by("code")
    )
    for chamber in chambers:
        chamber_rows.append(
            {
                "chamber": chamber,
                "condition_label": chamber.storage_condition.name if chamber.storage_condition else "-",
                "state_label": "En desviacion" if chamber.open_deviation_count else "Operativa",
                "state_tone": "danger" if chamber.open_deviation_count else "success",
                "subsample_count": chamber.active_subsample_count,
            }
        )

    monthly_withdrawals = []
    for offset in range(12):
        month_anchor = (today.replace(day=1) + timedelta(days=offset * 32)).replace(day=1)
        if offset == 11:
            next_month = (month_anchor + timedelta(days=32)).replace(day=1)
        else:
            next_month = (month_anchor + timedelta(days=32)).replace(day=1)
        month_subsamples = PlannedSubsample.objects.filter(
            located_in_chamber_filter,
            planned_date__gte=month_anchor,
            planned_date__lt=next_month,
        )
        monthly_withdrawals.append(
            {
                "month_label": f"{calendar.month_name[month_anchor.month]} {month_anchor.year}",
                "withdrawal_count": month_subsamples.count(),
                "study_count": month_subsamples.values("study_id").distinct().count(),
                "chamber_count": month_subsamples.values("chamber_id").distinct().count(),
            }
        )

    recent_deviations = list(
        ChamberDeviation.objects.select_related("chamber")
        .order_by("-detected_at")[:8]
    )
    for deviation in recent_deviations:
        deviation.state_label = "Abierta" if not deviation.ended_at else "Cerrada"
        deviation.state_tone = "danger" if not deviation.ended_at else "neutral"

    overdue_subsamples = list(
        PlannedSubsample.objects.select_related("study", "study__client", "chamber")
        .filter(located_in_chamber_filter, planned_date__lt=today)
        .order_by("study__code", "planned_date", "code")
    )
    overdue_alerts_map = {}
    for subsample in overdue_subsamples:
        bucket = overdue_alerts_map.setdefault(
            subsample.study_id,
            {
                "study": subsample.study,
                "client_label": subsample.study.client.description if subsample.study.client else "-",
                "count": 0,
                "oldest_date": subsample.planned_date,
                "chambers": set(),
            },
        )
        bucket["count"] += 1
        if subsample.planned_date and subsample.planned_date < bucket["oldest_date"]:
            bucket["oldest_date"] = subsample.planned_date
        if subsample.chamber_id:
            bucket["chambers"].add(subsample.chamber.code)

    overdue_alerts = []
    for study_id, data in sorted(overdue_alerts_map.items(), key=lambda item: (item[1]["oldest_date"], item[1]["study"].code)):
        chambers_involved = sorted(data["chambers"])
        overdue_alerts.append(
            {
                "study": data["study"],
                "client_label": data["client_label"],
                "count": data["count"],
                "oldest_date": data["oldest_date"],
                "chamber_label": chambers_involved[0] if len(chambers_involved) == 1 else "Varias",
            }
        )

    context = {
        "active_studies": active_studies,
        "planned_studies": planned_studies,
        "studies_in_progress_count": len(active_studies),
        "studies_in_planning_count": len(planned_studies),
        "subsamples_in_chamber_count": PlannedSubsample.objects.filter(
            located_in_chamber_filter
        ).count(),
        "withdrawals_next_30_days_count": PlannedSubsample.objects.filter(
            located_in_chamber_filter,
            planned_date__gte=today,
            planned_date__lte=next_30_days,
        ).count(),
        "active_study_rows": active_study_rows,
        "chamber_rows": chamber_rows,
        "monthly_withdrawals": monthly_withdrawals,
        "recent_deviations": recent_deviations,
        "overdue_alerts": overdue_alerts,
        "today": today,
    }
    return render(request, "web/annual_plan.html", context)


@login_required
def reports_view(request):
    low_stock_samples = Sample.objects.select_related("study", "sampling_point").filter(current_stock__lte=2).order_by("current_stock", "sample_code")
    pending_labelling = Sample.objects.select_related("study").filter(status=Sample.Status.RECEIVED).order_by("sample_code")
    pending_chamber = Sample.objects.select_related("study").filter(status=Sample.Status.LABELLED).order_by("sample_code")
    pending_extraction = Sample.objects.select_related("study", "sampling_point").filter(
        status=Sample.Status.IN_CHAMBER,
        current_stock__gt=0,
    ).order_by("sampling_point__recalculated_date", "sampling_point__target_date", "sample_code")
    receptions_with_gap = (
        SampleReception.objects.select_related("study")
        .annotate(total_created=Sum("samples__quantity"))
        .filter(quantity_expected__gt=0)
        .filter(Q(total_created__isnull=True) | ~Q(quantity_expected=F("total_created")))
        .order_by("-received_at")
    )
    recent_movements = StockMovement.objects.select_related("sample").order_by("-executed_at")[:25]
    context = {
        "low_stock_samples": low_stock_samples,
        "pending_labelling": pending_labelling,
        "pending_chamber": pending_chamber,
        "pending_extraction": pending_extraction,
        "receptions_with_gap": receptions_with_gap,
        "recent_movements": recent_movements,
        "low_stock_count": low_stock_samples.count(),
        "pending_labelling_count": pending_labelling.count(),
        "pending_chamber_count": pending_chamber.count(),
        "pending_extraction_count": pending_extraction.count(),
        "receptions_with_gap_count": receptions_with_gap.count(),
    }
    return render(request, "web/reports.html", context)


@login_required
def deviations_view(request):
    selected_chamber = request.GET.get("chamber", "").strip()
    page_size = _get_page_size(request)
    deviations = ChamberDeviation.objects.select_related("chamber").order_by("-detected_at")
    if selected_chamber:
        deviations = deviations.filter(chamber_id=selected_chamber)
    paginator = Paginator(deviations, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_numbers = []
    for page_number in range(1, paginator.num_pages + 1):
        if paginator.num_pages <= 7 or abs(page_number - page_obj.number) <= 1 or page_number in {1, paginator.num_pages}:
            page_numbers.append(page_number)
    context = {
        "deviation_form": ChamberDeviationForm(),
        "deviations": page_obj.object_list,
        "chambers": Chamber.objects.filter(is_active=True).order_by("code"),
        "selected_chamber": selected_chamber,
        "page_obj": page_obj,
        "page_numbers": page_numbers,
        "page_size": page_size,
        "query_string": urlencode({key: value for key, value in {"chamber": selected_chamber, "page_size": page_size}.items() if value not in {"", None}}),
        "total_count": paginator.count,
        "start_index": page_obj.start_index() if paginator.count else 0,
        "end_index": page_obj.end_index() if paginator.count else 0,
    }
    return render(request, "web/deviations.html", context)


@login_required
def create_deviation_web(request):
    if request.method != "POST":
        return redirect("web-deviations")
    form = ChamberDeviationForm(request.POST)
    if form.is_valid():
        deviation = form.save()
        recalculated_points = []
        if deviation.requires_recalculation:
            affected_points = (
                SamplingPoint.objects.filter(
                    samples__schedules__chamber=deviation.chamber,
                    samples__schedules__is_active=True,
                )
                .select_related("study")
                .distinct()
                .order_by("study__code", "target_date", "label")
            )
            for point in affected_points:
                previous_date = point.recalculated_date or point.target_date
                point.recalculated_date = point.target_date + timedelta(days=point.tolerance_days)
                point.save(update_fields=["recalculated_date", "updated_at"])
                recalculated_points.append(
                    {
                        "study": point.study.code,
                        "point": point.label,
                        "before": str(previous_date),
                        "after": str(point.recalculated_date),
                    }
                )
                register_audit_event(
                    point,
                    "web_recalculate_sampling_point",
                    payload={"deviation_id": deviation.id, "point": point.label, "chamber": deviation.chamber.code},
                    changes={"recalculated_date": {"before": str(previous_date), "after": str(point.recalculated_date)}},
                )
        register_audit_event(
            deviation,
            "web_create_chamber_deviation",
            payload={"chamber": deviation.chamber.code, "deviation_code": deviation.deviation_code},
            changes={"requires_recalculation": {"before": None, "after": deviation.requires_recalculation}},
        )
        if recalculated_points:
            messages.success(request, f"Desviacion registrada y {len(recalculated_points)} puntos recalculados para la camara {deviation.chamber.code}.")
        else:
            messages.success(request, "Desviacion registrada correctamente.")
    else:
        messages.error(request, "No se pudo registrar la desviacion de camara. Revisa los campos.")
    return redirect("web-deviations")


@login_required
def edit_deviation_web(request, pk):
    deviation = get_object_or_404(ChamberDeviation, pk=pk)
    if request.method != "POST":
        return redirect("web-deviations")

    before = {
        "chamber": deviation.chamber.code if deviation.chamber_id else None,
        "detected_at": deviation.detected_at.isoformat() if deviation.detected_at else None,
        "ended_at": deviation.ended_at.isoformat() if deviation.ended_at else None,
        "description": deviation.description,
        "impact_assessment": deviation.impact_assessment,
        "requires_recalculation": deviation.requires_recalculation,
    }

    form = ChamberDeviationForm(request.POST, instance=deviation)
    if form.is_valid():
        updated = form.save()
        after = {
            "chamber": updated.chamber.code if updated.chamber_id else None,
            "detected_at": updated.detected_at.isoformat() if updated.detected_at else None,
            "ended_at": updated.ended_at.isoformat() if updated.ended_at else None,
            "description": updated.description,
            "impact_assessment": updated.impact_assessment,
            "requires_recalculation": updated.requires_recalculation,
        }
        changes = {
            key: {"before": before[key], "after": after[key]}
            for key in before
            if before[key] != after[key]
        }
        register_audit_event(
            updated,
            "web_update_chamber_deviation",
            payload={"chamber": updated.chamber.code, "deviation_code": updated.deviation_code},
            changes=changes,
        )
        messages.success(request, "Desviacion actualizada correctamente.")
    else:
        messages.error(request, "No se pudo actualizar la desviacion. Revisa los campos.")
    return redirect("web-deviations")


@login_required
def delete_deviation_web(request, pk):
    deviation = get_object_or_404(ChamberDeviation, pk=pk)
    if request.method != "POST":
        return redirect("web-deviations")

    payload = {
        "chamber": deviation.chamber.code if deviation.chamber_id else None,
        "deviation_code": deviation.deviation_code,
    }
    register_audit_event(
        deviation,
        "web_delete_chamber_deviation",
        payload=payload,
        changes={"deleted": {"before": deviation.deviation_code, "after": None}},
    )
    deviation.delete()
    messages.success(request, "Desviacion eliminada correctamente.")
    return redirect("web-deviations")


@login_required
def create_sample_web(request):
    if request.method != "POST":
        return redirect("web-samples")
    form = SampleRegistrationForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        batch = resolve_batch_from_code(data["batch"])
        reception_number = (data["reception_number"] or "").strip() or generate_reception_number()
        reception = SampleReception.objects.create(
            study=data["study"],
            batch=batch,
            batch_number_text=(data["batch"] or "").strip(),
            packaging=data["packaging"],
            reception_number=reception_number,
            presentation=data["presentation"],
            batch_size=data["batch_size"] or 0,
            bulk_code=data["bulk_code"],
            api_batch=data["api_batch"],
            api_code=data["api_code"],
            primary_packing_material=data["primary_packing_material"],
            manufacture_date=data["manufacture_date"],
            received_by=data["received_by"],
            received_at=data["received_at"],
            quantity_received=data["quantity_received"],
            quantity_expected=data["quantity_expected"],
            quantity_assigned=0,
            quantity_reserved=data["quantity_reserved"],
            quantity_contingency=data["quantity_contingency"],
            discrepancy_notes=data["notes"],
            status=SampleReception.Status.RECEIVED,
            notes=data["notes"],
        )
        sample = Sample(
            study=data["study"],
            reception=reception,
            sample_code=data["sample_code"],
            quantity=data["quantity_received"] or 1,
            current_stock=data["quantity_received"] or 1,
            status=Sample.Status.RECEIVED,
            received_at=data["received_at"],
        )
        sample.save()
        StockMovement.objects.create(
            sample=sample,
            movement_type=StockMovement.MovementType.RECEPTION,
            quantity_delta=sample.quantity,
            notes="Alta inicial de muestra desde la vista web.",
        )
        register_audit_event(
            sample,
            "web_create_sample",
            payload={"sample_code": sample.sample_code},
            changes={"status": {"before": None, "after": sample.status}},
        )
        messages.success(request, f"Muestra {sample.sample_code} creada correctamente.")
    else:
        messages.error(request, "No se pudo crear la muestra. Revisa los campos obligatorios.")
    return redirect("web-samples")


@login_required
def edit_sample_web(request, pk):
    sample = get_object_or_404(Sample, pk=pk)
    if request.method != "POST":
        return redirect("web-samples")
    form = SampleRegistrationForm(request.POST, sample_instance=sample)
    if form.is_valid():
        data = form.cleaned_data
        previous_status = sample.status
        previous_stock = sample.current_stock
        previous_sample_code = sample.sample_code
        reception = sample.reception
        batch = resolve_batch_from_code(data["batch"])
        if reception is None:
            reception_number = (data["reception_number"] or "").strip() or generate_reception_number()
            reception = SampleReception.objects.create(
                study=data["study"],
                batch=batch,
                batch_number_text=(data["batch"] or "").strip(),
                packaging=data["packaging"],
                reception_number=reception_number,
                presentation=data["presentation"],
                batch_size=data["batch_size"] or 0,
                bulk_code=data["bulk_code"],
                api_batch=data["api_batch"],
                api_code=data["api_code"],
                primary_packing_material=data["primary_packing_material"],
                manufacture_date=data["manufacture_date"],
                received_by=data["received_by"],
                received_at=data["received_at"],
                quantity_received=data["quantity_received"],
                quantity_expected=data["quantity_expected"],
                quantity_assigned=0,
                quantity_reserved=data["quantity_reserved"],
                quantity_contingency=data["quantity_contingency"],
                discrepancy_notes=data["notes"],
                status=SampleReception.Status.RECEIVED,
                notes=data["notes"],
            )
            sample.reception = reception
        else:
            reception.study = data["study"]
            reception.batch = batch
            reception.batch_number_text = (data["batch"] or "").strip()
            reception.packaging = data["packaging"]
            reception.reception_number = data["reception_number"] or reception.reception_number
            reception.presentation = data["presentation"]
            reception.batch_size = data["batch_size"] or 0
            reception.bulk_code = data["bulk_code"]
            reception.api_batch = data["api_batch"]
            reception.api_code = data["api_code"]
            reception.primary_packing_material = data["primary_packing_material"]
            reception.manufacture_date = data["manufacture_date"]
            reception.received_by = data["received_by"]
            reception.received_at = data["received_at"]
            reception.quantity_received = data["quantity_received"]
            reception.quantity_expected = data["quantity_expected"]
            reception.quantity_reserved = data["quantity_reserved"]
            reception.quantity_contingency = data["quantity_contingency"]
            reception.discrepancy_notes = data["notes"]
            reception.status = SampleReception.Status.RECEIVED
            reception.notes = data["notes"]
            reception.save()

        sample.study = data["study"]
        sample.sample_code = data["sample_code"]
        sample.quantity = data["quantity_received"] or sample.quantity or 1
        sample.current_stock = data["quantity_received"] or sample.current_stock or 1
        sample.status = Sample.Status.RECEIVED
        if not sample.received_at:
            sample.received_at = data["received_at"]
        sample.save()
        if sample.sample_code != previous_sample_code:
            _refresh_sample_dependent_codes(sample)
        recalculate_reception_assigned_quantity(sample)
        register_audit_event(
            sample,
            "web_update_sample",
            payload={"sample_code": sample.sample_code},
            changes={
                "status": {"before": previous_status, "after": sample.status},
                "current_stock": {"before": previous_stock, "after": sample.current_stock},
            },
        )
        messages.success(request, f"Muestra {sample.sample_code} actualizada correctamente.")
    else:
        messages.error(request, "No se pudo actualizar la muestra. Revisa los campos obligatorios.")
    return redirect("web-samples")


@login_required
def delete_sample_web(request, pk):
    sample = get_object_or_404(Sample, pk=pk)
    if request.method == "POST":
        if sample.study.status == Study.Status.ACTIVE:
            messages.error(request, "No se pueden eliminar muestras de estudios aprobados.")
            return redirect("web-samples")
        register_audit_event(
            sample,
            "web_delete_sample",
            payload={"sample_code": sample.sample_code},
            changes={"deleted": {"before": False, "after": True}},
        )
        sample.delete()
        messages.success(request, f"Muestra {sample.sample_code} eliminada correctamente.")
    return redirect("web-samples")


@login_required
def create_sample_schedule_web(request, pk):
    sample = get_object_or_404(Sample, pk=pk)
    if request.method != "POST":
        return redirect("web-sample-schedules", pk=sample.pk)
    form = SampleScheduleForm(request.POST, sample=sample)
    wants_print = request.POST.get("submit_action") == "save_and_print"
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if form.is_valid():
        schedule = form.save(commit=False)
        schedule.sample = sample
        
        existing_count = SampleSchedule.objects.filter(
            sample=sample
        ).count()

        schedule.label = (
            f"{sample.sample_code}-F{existing_count + 1:03d}"
        )
        
        schedule.save()
        recalculate_reception_assigned_quantity(sample)
        register_audit_event(
            schedule,
            "web_create_sample_schedule",
            payload={"sample_code": sample.sample_code, "planned_date": str(schedule.planned_date)},
            changes=_schedule_audit_changes(None, schedule),
        )
        if wants_print and is_ajax:
            return JsonResponse(
                {
                    "ok": True,
                    "label_url": f"/app/labels/{sample.id}/?schedule={schedule.id}&autoprint=1",
                    "redirect_url": f"/app/samples/{sample.id}/schedules/?refresh={timezone.now().timestamp()}#add-schedule-form",
                }
            )
        messages.success(request, "Fecha de muestreo añadida correctamente.")
    else:
        messages.error(request, "No se pudo añadir la fecha de muestreo.")
    return redirect("web-sample-schedules", pk=sample.pk)


@login_required
def edit_sample_schedule_web(request, pk):
    schedule = get_object_or_404(
        SampleSchedule.objects.select_related("sample", "chamber", "chamber_location"),
        pk=pk,
    )
    if request.method != "POST":
        return redirect("web-sample-schedules", pk=schedule.sample_id)
    form = SampleScheduleEditForm(request.POST, instance=schedule)
    if form.is_valid():
        before_schedule = SampleSchedule.objects.select_related("chamber", "chamber_location").get(pk=schedule.pk)
        schedule = form.save()
        recalculate_reception_assigned_quantity(schedule.sample)
        register_audit_event(
            schedule,
            "web_update_sample_schedule",
            payload={"sample_code": schedule.sample.sample_code, "planned_date": str(schedule.planned_date)},
            changes=_schedule_audit_changes(before_schedule, schedule),
        )
        messages.success(request, "Fecha de muestreo actualizada correctamente.")
    else:
        messages.error(request, "No se pudo actualizar la fecha de muestreo.")
    return redirect("web-sample-schedules", pk=schedule.sample_id)


@login_required
def delete_sample_schedule_web(request, pk):
    schedule = get_object_or_404(SampleSchedule.objects.select_related("sample"), pk=pk)
    sample_pk = schedule.sample_id
    sample = schedule.sample
    if request.method == "POST":
        register_audit_event(
            schedule,
            "web_delete_sample_schedule",
            payload={"sample_code": schedule.sample.sample_code, "planned_date": str(schedule.planned_date)},
        )
        schedule.delete()
        recalculate_reception_assigned_quantity(sample)
        messages.success(request, "Fecha de muestreo eliminada correctamente.")
    return redirect("web-sample-schedules", pk=sample_pk)


@login_required
def withdraw_sample_schedule_web(request, pk):
    schedule = get_object_or_404(
        SampleSchedule.objects.select_related("sample", "removed_by"),
        pk=pk,
    )
    if request.method != "POST":
        return redirect("web-sample-schedules", pk=schedule.sample_id)
    if not schedule.is_active and schedule.removed_at:
        messages.info(request, "La fecha de muestreo ya estaba retirada de camara.")
        return redirect("web-sample-schedules", pk=schedule.sample_id)

    before_schedule = SampleSchedule.objects.select_related("removed_by").get(pk=schedule.pk)
    removed_at_raw = request.POST.get("removed_at") or ""
    if removed_at_raw:
        try:
            removed_at = timezone.datetime.fromisoformat(removed_at_raw)
            if timezone.is_naive(removed_at):
                removed_at = timezone.make_aware(removed_at, timezone.get_current_timezone())
        except ValueError:
            messages.error(request, "La fecha de salida no tiene un formato valido.")
            return redirect("web-sample-schedules", pk=schedule.sample_id)
    else:
        removed_at = timezone.now()

    schedule.removed_at = removed_at
    schedule.removed_by = request.user if request.user.is_authenticated else None
    schedule.is_active = False
    schedule.save(update_fields=["removed_at", "removed_by", "is_active", "updated_at"])
    recalculate_reception_assigned_quantity(schedule.sample)
    register_audit_event(
        schedule,
        "web_withdraw_sample_schedule",
        payload={
            "sample_code": schedule.sample.sample_code,
            "schedule_label": schedule.label,
            "planned_date": str(schedule.planned_date),
        },
        changes=_schedule_audit_changes(before_schedule, schedule),
    )
    messages.success(request, "Fecha de muestreo retirada de camara correctamente.")
    return redirect("web-sample-schedules", pk=schedule.sample_id)


@login_required
def create_reception(request):
    if request.method != "POST":
        return redirect("web-operations")
    form = SampleReceptionForm(request.POST)
    if form.is_valid():
        reception = form.save()
        messages.success(request, f"Recepcion {reception.reception_number} registrada correctamente.")
        register_audit_event(
            reception,
            "web_create_reception",
            payload={"reception_number": reception.reception_number},
            changes={"status": {"before": None, "after": reception.status}},
        )
    else:
        messages.error(request, "No se pudo registrar la recepcion. Revisa los campos.")
    return redirect("web-operations")


@login_required
def label_sample_web(request):
    if request.method != "POST":
        return redirect("web-operations")
    form = SampleLabelForm(request.POST)
    if form.is_valid():
        sample = form.cleaned_data["sample"]
        previous_status = sample.status
        sample.status = Sample.Status.LABELLED
        sample.qr_code = f"QR::{sample.sample_code}"
        sample.label_printed_at = timezone.now()
        sample.save(update_fields=["status", "qr_code", "label_printed_at", "updated_at"])
        StockMovement.objects.create(
            sample=sample,
            movement_type=StockMovement.MovementType.LABEL,
            quantity_delta=0,
            notes="Etiquetado realizado desde la vista web.",
        )
        register_audit_event(
            sample,
            "web_label_sample",
            payload={"qr_code": sample.qr_code},
            changes={"status": {"before": previous_status, "after": sample.status}},
        )
        messages.success(request, f"Muestra {sample.sample_code} etiquetada correctamente.")
    else:
        messages.error(request, "No se pudo etiquetar la muestra.")
    return redirect("web-operations")


@login_required
def place_sample_in_chamber_web(request):
    if request.method != "POST":
        return redirect("web-operations")
    form = ChamberPlacementForm(request.POST)
    if form.is_valid():
        sample = form.cleaned_data["sample"]
        chamber = form.cleaned_data["chamber"]
        previous_status = sample.status
        previous_chamber = sample.chamber.code if sample.chamber else None
        sample.chamber = chamber
        sample.status = Sample.Status.IN_CHAMBER
        sample.placed_in_chamber_at = timezone.now()
        sample.save(update_fields=["chamber", "status", "placed_in_chamber_at", "updated_at"])
        StockMovement.objects.create(
            sample=sample,
            movement_type=StockMovement.MovementType.CHAMBER_IN,
            quantity_delta=0,
            notes=f"Entrada en camara {chamber.code} desde la vista web.",
        )
        register_audit_event(
            sample,
            "web_place_in_chamber",
            payload={"chamber": chamber.code},
            changes={
                "status": {"before": previous_status, "after": sample.status},
                "chamber": {"before": previous_chamber, "after": chamber.code},
            },
        )
        messages.success(request, f"Muestra {sample.sample_code} enviada a la camara {chamber.code}.")
    else:
        messages.error(request, "No se pudo registrar la entrada en camara.")
    return redirect("web-operations")


@login_required
def extract_sample_web(request):
    if request.method != "POST":
        return redirect("web-operations")
    form = SampleExtractionForm(request.POST)
    if form.is_valid():
        sample = form.cleaned_data["sample"]
        quantity = form.cleaned_data["quantity"]
        if quantity > sample.current_stock:
            messages.error(request, f"No puedes extraer {quantity}. Stock disponible: {sample.current_stock}.")
            return redirect("web-operations")
        previous_stock = sample.current_stock
        previous_status = sample.status
        sample.current_stock = max(sample.current_stock - quantity, 0)
        sample.status = Sample.Status.EXTRACTED
        sample.extracted_at = timezone.now()
        sample.save(update_fields=["current_stock", "status", "extracted_at", "updated_at"])
        StockMovement.objects.create(
            sample=sample,
            movement_type=StockMovement.MovementType.EXTRACTION,
            quantity_delta=-quantity,
            notes="Extraccion realizada desde la vista web.",
        )
        if sample.current_stock <= 2:
            StabilityAlert.objects.get_or_create(
                study=sample.study,
                sample=sample,
                title=f"Stock bajo {sample.sample_code}",
                defaults={
                    "message": "La muestra ha quedado con stock bajo tras una extraccion web.",
                    "severity": StabilityAlert.Severity.WARNING,
                    "status": StabilityAlert.Status.OPEN,
                    "due_date": timezone.localdate(),
                },
            )
        register_audit_event(
            sample,
            "web_extract_sample",
            payload={"quantity": quantity},
            changes={
                "status": {"before": previous_status, "after": sample.status},
                "current_stock": {"before": previous_stock, "after": sample.current_stock},
            },
        )
        messages.success(request, f"Extraccion registrada para {sample.sample_code}.")
    else:
        messages.error(request, "No se pudo registrar la extraccion.")
    return redirect("web-operations")


@login_required
def sample_label_preview(request, pk):
    sample = get_object_or_404(
        Sample.objects.select_related(
            "study",
            "sampling_point",
            "chamber",
            "chamber__storage_condition",
            "reception",
            "reception__packaging",
            "reception__batch",
        ),
        pk=pk,
    )
    schedule = None
    schedule_id = request.GET.get("schedule")
    if schedule_id:
        schedule = get_object_or_404(
            SampleSchedule.objects.select_related(
                "chamber",
                "chamber__storage_condition",
                "chamber_location",
            ),
            pk=schedule_id,
            sample=sample,
        )
        if not schedule.schedule_qr_code:
            qr_before = schedule.schedule_qr_code or None
            schedule.schedule_qr_code = _build_schedule_qr_code(schedule)
            schedule.label_printed_at = timezone.now()
            schedule.save(update_fields=["schedule_qr_code", "label_printed_at", "updated_at"])
            register_audit_event(
                schedule,
                "web_generate_sample_schedule_label",
                payload={
                    "sample_code": sample.sample_code,
                    "schedule_label": schedule.label,
                    "planned_date": str(schedule.planned_date),
                },
                changes={
                    "schedule_qr_code": {"before": qr_before, "after": schedule.schedule_qr_code},
                    "label_printed_at": {"before": None, "after": schedule.label_printed_at.isoformat()},
                },
            )
    qr_value = schedule.schedule_qr_code if schedule and schedule.schedule_qr_code else sample.qr_code or f"QR::{sample.sample_code}"
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(qr_value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    context = {
        "sample": sample,
        "schedule": schedule,
        "qr_value": qr_value,
        "qr_image_base64": qr_image_base64,
        "autoprint": request.GET.get("autoprint") == "1",
    }
    return render(request, "web/label_preview.html", context)


@login_required
def planned_subsample_label_preview(request, pk):
    subsample = get_object_or_404(
        PlannedSubsample.objects.select_related("study", "chamber", "chamber__storage_condition", "sampling_point_template"),
        pk=pk,
    )
    _mark_planned_subsample_label_printed(subsample)
    qr_value = f"QR::{subsample.code}"
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(qr_value)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    context = {
        "subsample": subsample,
        "qr_value": qr_value,
        "qr_image_base64": qr_image_base64,
        "autoprint": request.GET.get("autoprint") == "1",
    }
    return render(request, "web/planned_subsample_label.html", context)
