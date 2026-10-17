from django.conf import settings
from django.db import models

from apps.common.exceptions import InvalidState


class AuditEvent(models.Model):
    """Append-only record of a sensitive change. Written inside the same transaction as the change."""

    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    actor_role = models.CharField(max_length=30, blank=True)
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=40)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    request_id = models.CharField(max_length=40, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "audit_events"
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
            models.Index(fields=["occurred_at"], name="audit_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise InvalidState("Audit events are append-only.", code="AUDIT_IMMUTABLE")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InvalidState("Audit events cannot be deleted.", code="AUDIT_IMMUTABLE")
