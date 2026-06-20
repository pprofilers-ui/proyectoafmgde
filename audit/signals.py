from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.db import connection

from .context import get_audit_request
from .models import AuditTrail


AUDIT_EXCLUDED_MODELS = {"AuditTrail"}
AUDIT_EXCLUDED_APP_LABELS = {"audit", "contenttypes", "sessions"}


def _should_skip_sender(sender):
    app_label = getattr(sender._meta, "app_label", "")
    db_table = getattr(sender._meta, "db_table", "")
    if sender.__name__ in AUDIT_EXCLUDED_MODELS:
        return True
    if app_label in AUDIT_EXCLUDED_APP_LABELS:
        return True
    if db_table == "django_migrations":
        return True
    return False


def _audit_table_ready():
    return AuditTrail._meta.db_table in connection.introspection.table_names()


def _serialize_instance(instance):
    data = model_to_dict(instance)
    serialized = {}
    for key, value in data.items():
        if hasattr(value, "isoformat"):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def _get_request_metadata():
    request = get_audit_request()
    if request is None:
        return {
            "performed_by": None,
            "request_path": "",
            "request_method": "",
            "company_code": "",
            "contact_code": "",
        }
    user = getattr(request, "user", None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return {
        "performed_by": user,
        "request_path": getattr(request, "path", ""),
        "request_method": getattr(request, "method", ""),
        "company_code": getattr(request, "company_code", "") or "",
        "contact_code": getattr(request, "contact_code", "") or "",
    }


def _build_changes(before, after):
    changes = {}
    keys = set(before.keys()) | set(after.keys())
    for key in keys:
        if before.get(key) != after.get(key):
            changes[key] = {
                "before": before.get(key),
                "after": after.get(key),
            }
    return changes


@receiver(pre_save)
def capture_previous_state(sender, instance, **kwargs):
    if _should_skip_sender(sender):
        return
    if not hasattr(instance, "pk") or not instance.pk:
        instance._audit_previous_state = None
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
        instance._audit_previous_state = _serialize_instance(previous)
    except sender.DoesNotExist:
        instance._audit_previous_state = None


@receiver(post_save)
def log_create_or_update(sender, instance, created, **kwargs):
    if _should_skip_sender(sender) or not _audit_table_ready():
        return

    metadata = _get_request_metadata()
    after = _serialize_instance(instance)

    if created:
        AuditTrail.objects.create(
            action="create",
            action_type=AuditTrail.ActionType.CREATE,
            entity_name=sender.__name__,
            entity_id=str(instance.pk),
            object_repr=str(instance),
            payload={"after": after},
            changes=after,
            **metadata,
        )
        return

    before = getattr(instance, "_audit_previous_state", None) or {}
    changes = _build_changes(before, after)
    if not changes:
        return

    AuditTrail.objects.create(
        action="update",
        action_type=AuditTrail.ActionType.UPDATE,
        entity_name=sender.__name__,
        entity_id=str(instance.pk),
        object_repr=str(instance),
        payload={"before": before, "after": after},
        changes=changes,
        **metadata,
    )


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if _should_skip_sender(sender) or not _audit_table_ready():
        return

    metadata = _get_request_metadata()
    snapshot = _serialize_instance(instance)

    AuditTrail.objects.create(
        action="delete",
        action_type=AuditTrail.ActionType.DELETE,
        entity_name=sender.__name__,
        entity_id=str(instance.pk),
        object_repr=str(instance),
        payload={"before": snapshot},
        changes=snapshot,
        **metadata,
    )
