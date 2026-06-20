from .context import get_audit_request
from .models import AuditTrail


def register_audit_event(instance, action, payload=None, changes=None):
    request = get_audit_request()
    user = getattr(request, "user", None) if request is not None else None
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None

    AuditTrail.objects.create(
        action=action,
        action_type=AuditTrail.ActionType.CUSTOM,
        entity_name=instance.__class__.__name__,
        entity_id=str(instance.pk),
        object_repr=str(instance),
        payload=payload or {},
        changes=changes or {},
        request_path=getattr(request, "path", "") if request is not None else "",
        request_method=getattr(request, "method", "") if request is not None else "",
        company_code=getattr(request, "company_code", "") if request is not None else "",
        contact_code=getattr(request, "contact_code", "") if request is not None else "",
        performed_by=user,
    )
