from django.contrib import admin

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
)


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


@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ("code", "product", "packaging", "manufactured_at", "expiry_date", "quantity_released")
    list_filter = ("product", "packaging")
    search_fields = ("code", "product__name")


@admin.register(StorageCondition)
class StorageConditionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "temperature_set_point", "humidity_set_point", "light_condition", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(ChamberLocation)
class ChamberLocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "room", "shelf", "position", "is_active")
    list_filter = ("is_active", "room")
    search_fields = ("code", "name", "room")


@admin.register(Study)
class StudyAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "product_name", "batch_number", "company_code", "status", "start_date", "end_date")
    list_filter = ("status", "company_code")
    search_fields = ("code", "title", "product_name", "batch_number")


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


@admin.register(SamplingPoint)
class SamplingPointAdmin(admin.ModelAdmin):
    list_display = ("study", "label", "target_date", "tolerance_days", "recalculated_date")
    list_filter = ("study",)
    search_fields = ("label", "study__code", "study__title")


@admin.register(SampleReception)
class SampleReceptionAdmin(admin.ModelAdmin):
    list_display = ("reception_number", "study", "batch", "received_from", "received_at", "quantity_received", "status")
    list_filter = ("status", "study")
    search_fields = ("reception_number", "received_from")


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sample_code", "study", "reception", "sampling_point", "chamber", "quantity", "current_stock", "status")
    list_filter = ("status", "chamber", "study")
    search_fields = ("sample_code", "study__code", "qr_code")


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
