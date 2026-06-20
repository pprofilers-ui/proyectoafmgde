from django.contrib import admin

from .models import AuditTrail


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
