from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum

from apps.collections.models import Collection
from apps.common.money import ZERO
from apps.common.scoping import scope_queryset

from .models import CashSubmission, CashSubmissionItem


def submissions_for(user) -> QuerySet[CashSubmission]:
    # Explicit order: GROUP BY (from the annotation) discards Meta.ordering, which would make pagination unstable.
    qs = (CashSubmission.objects.select_related("agent", "branch", "reviewed_by")
          .annotate(item_count=Count("items")).order_by("-id"))
    return scope_queryset(qs, user, branch_field="branch", agent_field="agent")


def eligible_collections(agent) -> QuerySet[Collection]:
    """Agent's VALID collections not in any live submission = cash currently held by the agent."""
    return (Collection.objects.select_related("loan", "loan__customer", "agent", "branch")
            .filter(agent=agent, status=Collection.Status.VALID)
            .exclude(submission_items__is_active=True)
            .order_by("collected_at", "id"))


def agent_cash_position(agent) -> dict[str, Decimal]:
    held = eligible_collections(agent).aggregate(t=Sum("amount"))["t"] or ZERO
    in_transit = CashSubmission.objects.filter(agent=agent, status=CashSubmission.Status.SUBMITTED).aggregate(
        t=Sum("expected_amount"))["t"] or ZERO
    shortfall = CashSubmission.objects.filter(agent=agent, status=CashSubmission.Status.APPROVED,
                                              discrepancy_amount__gt=0).aggregate(t=Sum("discrepancy_amount"))["t"] or ZERO
    return {"held": held, "in_transit": in_transit, "open_shortfall": shortfall}
