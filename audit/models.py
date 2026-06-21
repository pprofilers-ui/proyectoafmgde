from django.db import models

from users.models import User


class AuditTrail(models.Model):
    class ActionType(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        CUSTOM = "custom", "Custom"

    action = models.CharField(max_length=100)
    action_type = models.CharField(max_length=20, choices=ActionType.choices, default=ActionType.CUSTOM)
    entity_name = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=50)
    object_repr = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    request_path = models.CharField(max_length=255, blank=True)
    request_method = models.CharField(max_length=20, blank=True)
    company_code = models.CharField(max_length=50, blank=True)
    contact_code = models.CharField(max_length=50, blank=True)
    performed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-performed_at']
        verbose_name = "Traza de Auditoría"
        verbose_name_plural = "Trazas de Auditoría"
    
    def __str__(self):
        return f'{self.entity_name}:{self.entity_id} - {self.action}'
