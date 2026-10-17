from apps.common.middleware import get_request_id

from .models import AuditEvent


def _snapshot(value):
    return value if value is None or isinstance(value, (dict, list)) else str(value)


def record(*, actor, action: str, entity, before=None, after=None, reason: str = "", ip: str | None = None) -> AuditEvent:
    """Append an audit event. Call inside the caller's transaction.atomic() so it rolls back with it."""
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        actor_role=actor.role.code if getattr(actor, "pk", None) else "",
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        before=_snapshot(before),
        after=_snapshot(after),
        reason=reason,
        request_id=get_request_id() if get_request_id() != "-" else "",
        ip=ip,
    )
