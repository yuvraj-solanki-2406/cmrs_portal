from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", default=None, read_only=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "occurred_at", "actor", "actor_role", "action", "entity_type", "entity_id",
                  "before", "after", "reason", "request_id"]
        read_only_fields = fields
