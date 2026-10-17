from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyAdmin):
    list_display = ("occurred_at", "actor", "action", "entity_type", "entity_id")
    list_filter = ("action", "entity_type")
