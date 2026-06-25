import base64
from io import BytesIO
from datetime import timedelta
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
import qrcode

from audit.utils import register_audit_event

from .models import Chamber, ChamberDeviation, LabelTemplate, ProductBatch, Sample, SampleReception, SampleSchedule, SamplingPoint, StabilityAlert, StockMovement, Study
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


def generate_reception_number():
    year = timezone.localdate().year
    prefix = f"REC-{year}-"
    existing = SampleReception.objects.filter(reception_number__startswith=prefix).values_list(
        "reception_number",
        flat=True,
    )
    seq = _next_sequence(existing)
    return RECEPTION_CODE_PATTERN.format(year=year, seq=seq)


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
    assigned_total = (
        sample.schedules.filter(is_active=True).aggregate(total=Sum("quantity")).get("total") or 0
    )
    if reception.quantity_assigned != assigned_total:
        reception.quantity_assigned = assigned_total
        reception.save(update_fields=["quantity_assigned", "updated_at"])
    return assigned_total


def ensure_study_sampling_points(study):
    created_points = []
    if study.sampling_points.exists():
        return created_points

    for label, days_offset in DEFAULT_SAMPLING_SCHEDULE:
        point = SamplingPoint.objects.create(
            study=study,
            label=label,
            target_date=study.start_date + timedelta(days=days_offset),
            tolerance_days=3,
        )
        created_points.append(point)
    return created_points


class AppLoginView(LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True


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
    studies = Study.objects.select_related("study_type", "client", "product").order_by("-created_at")
    return render(request, "web/studies.html", {"studies": studies, "study_form": StudyCreateForm()})


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
        study.save()
        created_points = ensure_study_sampling_points(study)
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
    form = StudyEditForm(request.POST, instance=study)
    if form.is_valid():
        previous_status = study.status
        updated_study = form.save(commit=False)
        if not updated_study.code:
            updated_study.code = study.code
        if updated_study.product and not updated_study.product_code:
            updated_study.product_code = updated_study.product.code
        if updated_study.product and not updated_study.product_name:
            updated_study.product_name = updated_study.product.name
        updated_study.save()
        register_audit_event(
            updated_study,
            "web_update_study",
            payload={"code": updated_study.code, "title": updated_study.title},
            changes={"status": {"before": previous_status, "after": updated_study.status}},
        )
        messages.success(request, f"Estudio {updated_study.code} actualizado correctamente.")
    else:
        messages.error(request, "No se pudo actualizar el estudio. Revisa los campos obligatorios.")
    return redirect("web-studies")


@login_required
def delete_study_web(request, pk):
    study = get_object_or_404(Study, pk=pk)
    if request.method == "POST":
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
    samples = Sample.objects.select_related("study", "sampling_point", "chamber", "reception", "reception__packaging", "reception__batch")
    
    if study_id:
        samples = samples.filter(study_id=study_id)

    samples = list(samples.order_by("-created_at"))
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
def alerts_list(request):
    alerts = StabilityAlert.objects.select_related("study", "sample").order_by("status", "due_date")
    return render(request, "web/alerts.html", {"alerts": alerts})


@login_required
def operations_hub(request):
    selected_chamber = request.GET.get("chamber", "").strip()
    selected_study = request.GET.get("study", "").strip()
    show_history = request.GET.get("show") == "all"
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
        "chamber_contents": chamber_contents.order_by("chamber__code", "planned_date", "sample__sample_code", "id"),
        "chamber_summary": chamber_summary,
        "active_count": chamber_contents.filter(is_active=True).count() if show_history else chamber_contents.count(),
        "retired_count": chamber_contents.filter(is_active=False).count() if show_history else 0,
    }
    return render(request, "web/operations.html", context)


@login_required
def annual_plan_view(request):
    active_studies = Study.objects.filter(status=Study.Status.ACTIVE).order_by("start_date", "code")
    planned_studies = Study.objects.filter(status=Study.Status.DRAFT).order_by("start_date", "code")
    closed_studies = Study.objects.filter(status=Study.Status.CLOSED).order_by("-updated_at", "code")
    upcoming_points = SamplingPoint.objects.select_related("study").order_by("recalculated_date", "target_date")[:20]
    upcoming_entries = Sample.objects.select_related("study").filter(
        status__in=[Sample.Status.RECEIVED, Sample.Status.LABELLED]
    ).order_by("created_at")[:20]
    upcoming_extractions = Sample.objects.select_related("study", "sampling_point").filter(
        sampling_point__isnull=False,
        current_stock__gt=0,
    ).order_by("sampling_point__recalculated_date", "sampling_point__target_date")[:20]
    chamber_load = Chamber.objects.annotate(sample_count=Count("samples")).order_by("-sample_count", "code")
    open_alerts = StabilityAlert.objects.filter(status=StabilityAlert.Status.OPEN).order_by("due_date", "severity")[:20]
    deviations = ChamberDeviation.objects.select_related("chamber", "study").order_by("-detected_at")[:20]
    context = {
        "active_studies": active_studies,
        "planned_studies": planned_studies,
        "closed_studies": closed_studies,
        "upcoming_points": upcoming_points,
        "upcoming_entries": upcoming_entries,
        "upcoming_extractions": upcoming_extractions,
        "chamber_load": chamber_load,
        "open_alerts": open_alerts,
        "deviations": deviations,
        "today": timezone.localdate(),
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
    }
    return render(request, "web/reports.html", context)


@login_required
def deviations_view(request):
    selected_chamber = request.GET.get("chamber", "").strip()
    deviations = ChamberDeviation.objects.select_related("chamber").order_by("-detected_at")
    if selected_chamber:
        deviations = deviations.filter(chamber_id=selected_chamber)
    context = {
        "deviation_form": ChamberDeviationForm(),
        "deviations": deviations,
        "chambers": Chamber.objects.filter(is_active=True).order_by("code"),
        "selected_chamber": selected_chamber,
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
        sample_code = generate_sample_code(data["study"])
        sample = Sample(
            study=data["study"],
            reception=reception,
            sample_code=sample_code,
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
    form = SampleRegistrationForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        previous_status = sample.status
        previous_stock = sample.current_stock
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
        sample.quantity = data["quantity_received"] or sample.quantity or 1
        sample.current_stock = data["quantity_received"] or sample.current_stock or 1
        sample.status = Sample.Status.RECEIVED
        if not sample.received_at:
            sample.received_at = data["received_at"]
        if not sample.sample_code:
            sample.sample_code = generate_sample_code(data["study"])
        sample.save()
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
