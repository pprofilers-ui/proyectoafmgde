from django.db.models import Sum
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.models import AuditTrail
from audit.utils import register_audit_event

from .models import (
    Chamber,
    ChamberDeviation,
    ChamberLocation,
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
    StudyMode,
    StudyType,
)
from .serializers import (
    ChamberDeviationSerializer,
    ChamberLocationSerializer,
    ChamberSerializer,
    PackagingConfigurationSerializer,
    ProductBatchSerializer,
    ProductSerializer,
    SampleReceptionSerializer,
    SampleSerializer,
    SamplingPointSerializer,
    StabilityAlertSerializer,
    StockMovementSerializer,
    StorageConditionSerializer,
    StudySerializer,
    StudyModeSerializer,
    StudyTypeSerializer,
)


class CompanyScopedViewSet(viewsets.ModelViewSet):
    company_field = "company_code"

    def get_queryset(self):
        queryset = super().get_queryset()
        company_code = getattr(self.request, "company_code", None)
        if company_code and hasattr(queryset.model, self.company_field):
            queryset = queryset.filter(**{self.company_field: company_code})
        return queryset

    def _audit(self, action_name, instance, payload=None):
        register_audit_event(
            instance,
            action_name,
            payload=payload or {"repr": str(instance)},
        )

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit("update", instance)

    def perform_destroy(self, instance):
        self._audit("delete", instance)
        instance.delete()


class ProductViewSet(CompanyScopedViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ["company_code", "is_active"]
    search_fields = ["code", "name", "reference"]

    def perform_create(self, serializer):
        instance = serializer.save(company_code=self.request.company_code or serializer.validated_data.get("company_code", "AGQ"))
        self._audit("create", instance)


class PackagingConfigurationViewSet(viewsets.ModelViewSet):
    queryset = PackagingConfiguration.objects.all()
    serializer_class = PackagingConfigurationSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "name", "material"]


class ProductBatchViewSet(viewsets.ModelViewSet):
    queryset = ProductBatch.objects.select_related("product", "packaging").all()
    serializer_class = ProductBatchSerializer
    filterset_fields = ["product", "packaging"]
    search_fields = ["code", "product__name"]


class StorageConditionViewSet(viewsets.ModelViewSet):
    queryset = StorageCondition.objects.all()
    serializer_class = StorageConditionSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]


class ChamberLocationViewSet(viewsets.ModelViewSet):
    queryset = ChamberLocation.objects.all()
    serializer_class = ChamberLocationSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "name", "room", "shelf", "position"]


class StudyTypeViewSet(viewsets.ModelViewSet):
    queryset = StudyType.objects.all()
    serializer_class = StudyTypeSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]


class StudyModeViewSet(viewsets.ModelViewSet):
    queryset = StudyMode.objects.all()
    serializer_class = StudyModeSerializer
    filterset_fields = ["is_active"]
    search_fields = ["code", "name"]


class StudyViewSet(CompanyScopedViewSet):
    queryset = Study.objects.select_related("study_type", "study_mode", "client", "product", "batch", "packaging").all()
    serializer_class = StudySerializer
    filterset_fields = ["status", "company_code", "product", "study_type", "study_mode", "client", "batch"]
    search_fields = ["code", "title", "product_name", "product_code", "protocol", "specification"]
    ordering_fields = ["start_date", "created_at", "code"]

    def perform_create(self, serializer):
        instance = serializer.save(company_code=self.request.company_code or serializer.validated_data.get("company_code", "AGQ"))
        self._audit("create", instance)

    @swagger_auto_schema(tags=["Stability Studies"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(tags=["Stability Studies"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, pk=None):
        study = self.get_object()
        data = {
            "study": self.get_serializer(study).data,
            "sampling_points": SamplingPointSerializer(study.sampling_points.all(), many=True).data,
            "samples_total": study.samples.count(),
            "stock_total": sum(study.samples.values_list("current_stock", flat=True)),
            "open_alerts": study.alerts.filter(status=StabilityAlert.Status.OPEN).count(),
            "deviations": study.deviations.count(),
        }
        return Response(data)


class ChamberViewSet(viewsets.ModelViewSet):
    queryset = Chamber.objects.select_related("storage_condition", "chamber_location").all()
    serializer_class = ChamberSerializer
    filterset_fields = ["is_active", "storage_condition", "chamber_location"]
    search_fields = ["code", "name", "location"]


class SamplingPointViewSet(viewsets.ModelViewSet):
    queryset = SamplingPoint.objects.select_related("study").all()
    serializer_class = SamplingPointSerializer
    filterset_fields = ["study"]
    ordering_fields = ["target_date", "label"]

    @action(detail=True, methods=["post"], url_path="recalculate-date")
    def recalculate_date(self, request, pk=None):
        sampling_point = self.get_object()
        sampling_point.recalculated_date = sampling_point.target_date
        sampling_point.save(update_fields=["recalculated_date", "updated_at"])
        AuditTrail.objects.create(
            action="recalculate_date",
            action_type=AuditTrail.ActionType.CUSTOM,
            entity_name="SamplingPoint",
            entity_id=str(sampling_point.pk),
            object_repr=str(sampling_point),
            payload={"target_date": str(sampling_point.target_date), "recalculated_date": str(sampling_point.recalculated_date)},
            changes={"recalculated_date": {"before": None, "after": str(sampling_point.recalculated_date)}},
            request_path=request.path,
            request_method=request.method,
            company_code=getattr(request, "company_code", "") or "",
            contact_code=getattr(request, "contact_code", "") or "",
            performed_by=request.user,
        )
        return Response(self.get_serializer(sampling_point).data)


class SampleReceptionViewSet(viewsets.ModelViewSet):
    queryset = SampleReception.objects.select_related("study", "batch").all()
    serializer_class = SampleReceptionSerializer
    filterset_fields = ["study", "batch", "status"]
    search_fields = ["reception_number", "received_from", "received_by"]

    def perform_create(self, serializer):
        instance = serializer.save()
        AuditTrail.objects.create(
            action="create_reception",
            action_type=AuditTrail.ActionType.CUSTOM,
            entity_name="SampleReception",
            entity_id=str(instance.pk),
            object_repr=str(instance),
            payload={"reception_number": instance.reception_number, "quantity_received": instance.quantity_received},
            changes={"status": {"before": None, "after": instance.status}},
            request_path=self.request.path,
            request_method=self.request.method,
            company_code=getattr(self.request, "company_code", "") or "",
            contact_code=getattr(self.request, "contact_code", "") or "",
            performed_by=self.request.user if self.request.user.is_authenticated else None,
        )


class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.select_related("study", "reception", "sampling_point", "chamber").all()
    serializer_class = SampleSerializer
    filterset_fields = ["study", "status", "chamber", "sampling_point", "reception"]
    search_fields = ["sample_code", "qr_code"]
    ordering_fields = ["received_at", "sample_code", "created_at"]

    def _register_stock(self, sample, movement_type, quantity_delta, notes):
        StockMovement.objects.create(
            sample=sample,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            notes=notes,
        )

    @action(detail=True, methods=["post"], url_path="label")
    def label_sample(self, request, pk=None):
        sample = self.get_object()
        sample.status = Sample.Status.LABELLED
        sample.qr_code = f"QR::{sample.sample_code}"
        sample.label_printed_at = timezone.now()
        sample.save(update_fields=["status", "qr_code", "label_printed_at", "updated_at"])
        self._register_stock(sample, StockMovement.MovementType.LABEL, 0, "Etiquetado e impresion logica de etiqueta.")
        register_audit_event(
            sample,
            "label_sample",
            payload={"qr_code": sample.qr_code},
            changes={"status": {"before": Sample.Status.RECEIVED, "after": sample.status}},
        )
        return Response(self.get_serializer(sample).data)

    @action(detail=True, methods=["post"], url_path="place-in-chamber")
    def place_in_chamber(self, request, pk=None):
        sample = self.get_object()
        sample.status = Sample.Status.IN_CHAMBER
        sample.placed_in_chamber_at = timezone.now()
        sample.save(update_fields=["status", "placed_in_chamber_at", "updated_at"])
        self._register_stock(sample, StockMovement.MovementType.CHAMBER_IN, 0, "Entrada en camara.")
        register_audit_event(
            sample,
            "place_in_chamber",
            payload={"placed_in_chamber_at": sample.placed_in_chamber_at.isoformat()},
            changes={"status": {"before": Sample.Status.LABELLED, "after": sample.status}},
        )
        return Response(self.get_serializer(sample).data)

    @action(detail=True, methods=["post"], url_path="extract")
    def extract_sample(self, request, pk=None):
        sample = self.get_object()
        quantity_to_extract = int(request.data.get("quantity", 1))
        sample.status = Sample.Status.EXTRACTED
        sample.extracted_at = timezone.now()
        sample.current_stock = max(sample.current_stock - quantity_to_extract, 0)
        sample.save(update_fields=["status", "extracted_at", "current_stock", "updated_at"])
        self._register_stock(sample, StockMovement.MovementType.EXTRACTION, -quantity_to_extract, "Extraccion para punto de muestreo.")
        register_audit_event(
            sample,
            "extract_sample",
            payload={"quantity": quantity_to_extract},
            changes={
                "status": {"before": Sample.Status.IN_CHAMBER, "after": sample.status},
                "current_stock": {"before": sample.current_stock + quantity_to_extract, "after": sample.current_stock},
            },
        )
        if sample.current_stock == 0:
            StabilityAlert.objects.get_or_create(
                sample=sample,
                study=sample.study,
                title=f"Stock agotado {sample.sample_code}",
                defaults={
                    "message": "La muestra ha agotado su stock disponible tras la extraccion.",
                    "severity": StabilityAlert.Severity.WARNING,
                    "status": StabilityAlert.Status.OPEN,
                    "due_date": timezone.localdate(),
                },
            )
        return Response(self.get_serializer(sample).data)

    @action(detail=False, methods=["get"], url_path="stock-summary")
    def stock_summary(self, request):
        by_status = list(
            Sample.objects.values("status").annotate(total=Sum("current_stock")).order_by("status")
        )
        low_stock = Sample.objects.filter(current_stock__lte=2).count()
        return Response({"by_status": by_status, "low_stock_samples": low_stock})


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("sample").all()
    serializer_class = StockMovementSerializer
    filterset_fields = ["sample", "movement_type"]
    search_fields = ["sample__sample_code", "notes"]


class ChamberDeviationViewSet(viewsets.ModelViewSet):
    queryset = ChamberDeviation.objects.select_related("chamber").all()
    serializer_class = ChamberDeviationSerializer
    filterset_fields = ["chamber", "requires_recalculation"]
    ordering_fields = ["detected_at", "created_at"]
    permission_classes = [permissions.IsAuthenticated]


class StabilityAlertViewSet(viewsets.ModelViewSet):
    queryset = StabilityAlert.objects.select_related("study", "sample").all()
    serializer_class = StabilityAlertSerializer
    filterset_fields = ["study", "sample", "severity", "status"]
    search_fields = ["title", "message"]

    @action(detail=False, methods=["get"], url_path="master-calendar")
    def master_calendar(self, request):
        points = SamplingPoint.objects.select_related("study").all().order_by("recalculated_date", "target_date")
        alerts = StabilityAlert.objects.filter(status=StabilityAlert.Status.OPEN).order_by("due_date")
        return Response(
            {
                "sampling_calendar": [
                    {
                        "study": item.study.code,
                        "label": item.label,
                        "target_date": item.target_date,
                        "recalculated_date": item.recalculated_date,
                    }
                    for item in points
                ],
                "alerts": StabilityAlertSerializer(alerts, many=True).data,
            }
        )
