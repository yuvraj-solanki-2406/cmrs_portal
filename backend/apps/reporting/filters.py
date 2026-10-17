"""Shared filter parsing. Filters can narrow a user's scope but never widen it."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.accounts import roles
from apps.accounts.models import Branch, User
from apps.common.exceptions import NotAllowed

STAGES = ["COLLECTED", "HELD", "IN_TRANSIT", "BRANCH_RECEIVED", "DEPOSITED", "SETTLED"]


class FilterParamsSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    branch = serializers.IntegerField(required=False)
    agent = serializers.IntegerField(required=False)
    stage = serializers.ChoiceField(choices=STAGES, required=False)

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to") and attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_to": ["Must not be before date_from."]})
        return attrs


@dataclass(frozen=True)
class Filters:
    date_from: date | None
    date_to: date | None
    branch_id: int | None
    agent_id: int | None
    stage: str | None
    agent_scoped: bool  # True when figures must be attributed per agent (agent role or agent filter)

    def datetime_kwargs(self, field: str) -> dict:
        """Day range -> timestamp range in the local timezone, so a plain index on the column is usable
        (a `__date` cast would force a per-row conversion)."""
        tz = timezone.get_current_timezone()
        out = {}
        if self.date_from:
            out[f"{field}__gte"] = timezone.make_aware(datetime.combine(self.date_from, time.min), tz)
        if self.date_to:
            out[f"{field}__lt"] = timezone.make_aware(datetime.combine(self.date_to + timedelta(days=1), time.min), tz)
        return out

    def date_kwargs(self, field: str) -> dict:
        out = {}
        if self.date_from:
            out[f"{field}__gte"] = self.date_from
        if self.date_to:
            out[f"{field}__lte"] = self.date_to
        return out


def resolve_filters(user, params) -> Filters:
    data = FilterParamsSerializer(data=params)
    data.is_valid(raise_exception=True)
    v = data.validated_data
    branch_id, agent_id = v.get("branch"), v.get("agent")
    role = user.role_code
    if role == roles.AGENT:
        if agent_id not in (None, user.pk) or branch_id not in (None, user.branch_id):
            raise NotAllowed("Agents can only view their own figures.", code="FILTER_OUT_OF_SCOPE")
        branch_id, agent_id = user.branch_id, user.pk
    elif role == roles.BRANCH_MANAGER:
        if branch_id not in (None, user.branch_id):
            raise NotAllowed("You can only view your own branch.", code="FILTER_OUT_OF_SCOPE")
        branch_id = user.branch_id
    if agent_id is not None:
        agent = User.objects.filter(pk=agent_id, role__code=roles.AGENT).first()
        if agent is None or (branch_id is not None and agent.branch_id != branch_id):
            raise NotAllowed("Agent is outside the selected scope.", code="FILTER_OUT_OF_SCOPE")
        branch_id = agent.branch_id
    if branch_id is not None and not Branch.objects.filter(pk=branch_id).exists():
        raise NotAllowed("Unknown branch.", code="FILTER_OUT_OF_SCOPE")
    return Filters(v.get("date_from"), v.get("date_to"), branch_id, agent_id, v.get("stage"), agent_id is not None)
