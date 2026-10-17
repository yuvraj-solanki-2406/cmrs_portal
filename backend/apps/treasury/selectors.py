from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.cash.models import CashSubmission
from apps.common.scoping import scope_queryset

from .models import BankDeposit, Settlement


def deposits_for(user) -> QuerySet[BankDeposit]:
    qs = (BankDeposit.objects.select_related("branch", "created_by", "settlement", "settlement__confirmed_by")
          .annotate(submission_count=Count("submissions")).order_by("-id"))
    return scope_queryset(qs, user, branch_field="branch", agent_field=None)


def delayed_cutoff():
    return timezone.localdate() - timedelta(days=settings.SETTLEMENT_DELAY_DAYS)


def delayed_q() -> Q:
    """A deposit is delayed while its settlement is still PENDING past the allowed window (derived, not stored)."""
    return Q(settlement__status=Settlement.Status.PENDING, deposit_date__lt=delayed_cutoff())


def eligible_submissions(user) -> QuerySet[CashSubmission]:
    return (CashSubmission.objects.select_related("agent", "branch")
            .filter(branch=user.branch, status=CashSubmission.Status.APPROVED, deposit__isnull=True)
            .order_by("id"))
