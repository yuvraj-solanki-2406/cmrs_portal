from rest_framework import mixins, viewsets

from apps.accounts import roles
from apps.common.permissions import has_role

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only. ADMIN/FINANCE see everything; BRANCH_MANAGER sees events by users of their branch."""

    serializer_class = AuditEventSerializer
    permission_classes = [has_role(roles.ADMIN, roles.FINANCE, roles.BRANCH_MANAGER)]
    queryset = AuditEvent.objects.select_related("actor")
    filterset_fields = {"entity_type": ["exact"], "entity_id": ["exact"], "action": ["exact"],
                        "occurred_at": ["gte", "lte"]}

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, "role_code", None) == roles.BRANCH_MANAGER:
            return qs.filter(actor__branch_id=user.branch_id)
        return qs
