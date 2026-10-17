"""Read-only aggregate queries over the ledger tables. Nothing here is stored; everything is computed on read."""
from datetime import date

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Abs, Coalesce
from django.utils import timezone

from apps.accounts.models import Branch, User
from apps.cash.models import CashSubmission
from apps.collections.models import Collection
from apps.common.money import ZERO
from apps.lending.models import Installment, Loan
from apps.treasury.models import BankDeposit, Settlement
from apps.treasury.selectors import delayed_cutoff, delayed_q

from .filters import Filters


def _sum(qs: QuerySet, field: str):
    return qs.aggregate(t=Coalesce(Sum(field), ZERO))["t"]


def _scope(qs, f: Filters, *, branch: str | None, agent: str | None = None):
    if f.branch_id is not None and branch:
        qs = qs.filter(**{branch: f.branch_id})
    if f.agent_id is not None and agent:
        qs = qs.filter(**{agent: f.agent_id})
    return qs


# ---- base querysets (all honour branch/agent scope; date handled per metric) -----------------

def valid_collections(f: Filters, *, dated=True) -> QuerySet[Collection]:
    qs = _scope(Collection.objects.filter(status=Collection.Status.VALID), f, branch="branch_id", agent="agent_id")
    return qs.filter(**f.date_kwargs("collection_date")) if dated else qs


def submissions(f: Filters) -> QuerySet[CashSubmission]:
    return _scope(CashSubmission.objects.all(), f, branch="branch_id", agent="agent_id")


def held_collections(f: Filters) -> QuerySet[Collection]:
    return valid_collections(f).exclude(submission_items__is_active=True)


def in_transit_submissions(f: Filters) -> QuerySet[CashSubmission]:
    return submissions(f).filter(status=CashSubmission.Status.SUBMITTED, **f.datetime_kwargs("submitted_at"))


def approved_submissions(f: Filters) -> QuerySet[CashSubmission]:
    return submissions(f).filter(status=CashSubmission.Status.APPROVED, **f.datetime_kwargs("reviewed_at"))


def deposited_submissions(f: Filters) -> QuerySet[CashSubmission]:
    """Agent attribution: the agent's approved cash that has been banked (by the deposit's date)."""
    return submissions(f).filter(deposit__isnull=False, **f.date_kwargs("deposit__deposit_date"))


def settled_submissions(f: Filters) -> QuerySet[CashSubmission]:
    return submissions(f).filter(deposit__settlement__status=Settlement.Status.SETTLED,
                                 **f.date_kwargs("deposit__settlement__settled_on"))


def deposits(f: Filters) -> QuerySet[BankDeposit]:
    return _scope(BankDeposit.objects.all(), f, branch="branch_id").filter(**f.date_kwargs("deposit_date"))


def settled_settlements(f: Filters) -> QuerySet[Settlement]:
    qs = _scope(Settlement.objects.filter(status=Settlement.Status.SETTLED), f, branch="deposit__branch_id")
    return qs.filter(**f.date_kwargs("settled_on"))


def expected_installments(f: Filters) -> QuerySet[Installment]:
    qs = _scope(Installment.objects.all(), f, branch="loan__customer__branch_id", agent="loan__customer__assigned_agent_id")
    if f.date_from or f.date_to:
        return qs.filter(**f.date_kwargs("due_date"))
    return qs.filter(due_date__lte=timezone.localdate())  # no range given: expected to date


def active_loans(f: Filters) -> QuerySet[Loan]:
    return _scope(Loan.objects.filter(status=Loan.Status.ACTIVE), f, branch="customer__branch_id",
                  agent="customer__assigned_agent_id")


def outstanding_total(f: Filters):
    loans = active_loans(f)
    total = _sum(loans, "total_payable")
    paid = _sum(Collection.objects.filter(status=Collection.Status.VALID, loan__in=loans), "amount")
    return total - paid


# ---- dashboard ----------------------------------------------------------------------------

def summary(f: Filters) -> dict:
    appr = approved_submissions(f)
    disc = appr.exclude(discrepancy_amount=0).aggregate(
        count=Count("id"), total=Coalesce(Sum(Abs("discrepancy_amount")), ZERO),
        shortfall=Coalesce(Sum("discrepancy_amount", filter=Q(discrepancy_amount__gt=0)), ZERO),
        surplus=Coalesce(Sum(Abs("discrepancy_amount"), filter=Q(discrepancy_amount__lt=0)), ZERO))
    if f.agent_scoped:
        deposited, settled = _sum(deposited_submissions(f), "received_amount"), _sum(settled_submissions(f), "received_amount")
        dep_gap = {"count": 0, "total": ZERO}
        set_gap = {"count": 0, "total": ZERO}
        delayed = pending_amount = None
        attribution = "submission"
    else:
        dq = deposits(f)
        deposited, settled = _sum(dq, "amount"), _sum(settled_settlements(f), "settled_amount")
        dep_gap = dq.exclude(variance_amount=0).aggregate(count=Count("id"), total=Coalesce(Sum(Abs("variance_amount")), ZERO))
        set_gap = settled_settlements(f).exclude(variance_amount=0).aggregate(
            count=Count("id"), total=Coalesce(Sum(Abs("variance_amount")), ZERO))
        pending = _scope(Settlement.objects.filter(status=Settlement.Status.PENDING), f, branch="deposit__branch_id")
        delayed = _scope(BankDeposit.objects.filter(delayed_q()), f, branch="branch_id").count()
        pending_amount = _sum(pending, "deposit__amount")
        attribution = "deposit"
    m = {
        "expected": _sum(expected_installments(f), "amount_due"),
        "collected": _sum(valid_collections(f), "amount"),
        "held_by_agents": _sum(held_collections(f), "amount"),
        "in_transit": _sum(in_transit_submissions(f), "expected_amount"),
        "received_at_branch": _sum(appr, "received_amount"),
        "deposited": deposited,
        "settled": settled,
        "outstanding": outstanding_total(f),
        "discrepancy_total": disc["total"], "discrepancy_count": disc["count"],
        "shortfall_total": disc["shortfall"], "surplus_total": disc["surplus"],
        "deposit_variance_total": dep_gap["total"], "deposit_variance_count": dep_gap["count"],
        "settlement_variance_total": set_gap["total"], "settlement_variance_count": set_gap["count"],
        "delayed_settlements": delayed, "pending_settlement_amount": pending_amount,
    }
    funnel = [{"stage": s, "label": label, "amount": m[k]} for s, label, k in [
        ("EXPECTED", "Expected", "expected"), ("COLLECTED", "Collected", "collected"),
        ("BRANCH_RECEIVED", "Branch received", "received_at_branch"), ("DEPOSITED", "Deposited", "deposited"),
        ("SETTLED", "Settled", "settled")]]
    return {"metrics": m, "funnel": funnel, "attribution": attribution}


def stage_records(f: Filters, limit: int = 100) -> dict:
    """Records behind one pipeline stage, honouring the same filters (drill-down for the `stage` filter)."""
    stage = f.stage
    rows: list[dict] = []
    if stage in ("COLLECTED", "HELD"):
        qs = (valid_collections(f) if stage == "COLLECTED" else held_collections(f)).select_related(
            "agent", "branch", "loan", "loan__customer").order_by("-collected_at")
        total = qs.count()
        rows = [{"kind": "collection", "id": c.pk, "reference": c.receipt_number, "date": c.collected_at,
                 "branch": c.branch.code, "agent": c.agent.username, "party": c.loan.customer.full_name,
                 "amount": c.amount, "status": "HELD" if stage == "HELD" else "VALID"} for c in qs[:limit]]
    elif stage in ("IN_TRANSIT", "BRANCH_RECEIVED"):
        qs = (in_transit_submissions(f) if stage == "IN_TRANSIT" else approved_submissions(f)).select_related(
            "agent", "branch").order_by("-submitted_at")
        total = qs.count()
        rows = [{"kind": "submission", "id": s.pk, "reference": s.reference_no, "date": s.submitted_at,
                 "branch": s.branch.code, "agent": s.agent.username, "party": "",
                 "amount": s.expected_amount if stage == "IN_TRANSIT" else s.received_amount, "status": s.status}
                for s in qs[:limit]]
    elif stage in ("DEPOSITED", "SETTLED"):
        qs = (deposits(f) if stage == "DEPOSITED" else BankDeposit.objects.filter(
            pk__in=settled_settlements(f).values("deposit_id"))).select_related("branch", "settlement").order_by("-deposit_date", "-id")
        if stage == "SETTLED":
            qs = _scope(qs, f, branch="branch_id")
        total = qs.count()
        rows = [{"kind": "deposit", "id": d.pk, "reference": d.deposit_no, "date": d.deposit_date, "branch": d.branch.code,
                 "agent": "", "party": f"{d.bank_name} {d.reference_number}",
                 "amount": d.amount if stage == "DEPOSITED" else d.settlement.settled_amount,
                 "status": d.settlement.status} for d in qs[:limit]]
    else:
        total = 0
    return {"stage": stage, "total": total, "truncated": total > limit, "rows": rows}


def branch_summary(f: Filters) -> list[dict]:
    branches = Branch.objects.filter(is_active=True)
    if f.branch_id is not None:
        branches = branches.filter(pk=f.branch_id)
    out = []
    for branch in branches.order_by("code"):
        bf = Filters(f.date_from, f.date_to, branch.pk, None, None, False)
        s = summary(bf)["metrics"]
        agents = []
        for agent in User.objects.filter(branch=branch, role__code="AGENT", is_active=True).order_by("username"):
            af = Filters(f.date_from, f.date_to, branch.pk, agent.pk, None, True)
            am = summary(af)["metrics"]
            agents.append({"agent": {"id": agent.pk, "username": agent.username, "full_name": agent.full_name},
                           **{k: am[k] for k in ("collected", "held_by_agents", "in_transit", "received_at_branch",
                                                 "shortfall_total", "outstanding")}})
        out.append({"branch": {"id": branch.pk, "code": branch.code, "name": branch.name},
                    **{k: s[k] for k in ("expected", "collected", "held_by_agents", "in_transit", "received_at_branch",
                                         "deposited", "settled", "outstanding", "discrepancy_total", "delayed_settlements")},
                    "agents": agents})
    return out


# ---- reports ------------------------------------------------------------------------------

def discrepancy_rows(f: Filters) -> QuerySet[CashSubmission]:
    return (approved_submissions(f).exclude(discrepancy_amount=0).select_related("agent", "branch", "reviewed_by")
            .order_by("-reviewed_at"))


def mismatch_rows(f: Filters) -> list[dict]:
    """Deposit vs reconciled, settled vs deposited, plus failed settlements."""
    rows = []
    dq = (_scope(BankDeposit.objects.all(), f, branch="branch_id").filter(**f.date_kwargs("deposit_date"))
          .select_related("branch", "settlement", "settlement__confirmed_by").order_by("-deposit_date", "-id"))
    for d in dq:
        s = d.settlement
        if d.variance_amount != 0:
            rows.append({"type": "DEPOSIT_VS_RECONCILED", "deposit_id": d.pk, "deposit_no": d.deposit_no, "branch": d.branch.code,
                         "date": d.deposit_date, "expected": d.reconciled_amount, "actual": d.amount,
                         "difference": d.variance_amount, "reason": d.variance_note, "settlement_status": s.status})
        if s.status == Settlement.Status.SETTLED and s.variance_amount != 0:
            rows.append({"type": "SETTLED_VS_DEPOSITED", "deposit_id": d.pk, "deposit_no": d.deposit_no, "branch": d.branch.code,
                         "date": s.settled_on, "expected": d.amount, "actual": s.settled_amount,
                         "difference": s.variance_amount, "reason": s.variance_note, "settlement_status": s.status})
        if s.status == Settlement.Status.FAILED:
            rows.append({"type": "SETTLEMENT_FAILED", "deposit_id": d.pk, "deposit_no": d.deposit_no, "branch": d.branch.code,
                         "date": d.deposit_date, "expected": d.amount, "actual": None, "difference": None,
                         "reason": s.failure_reason, "settlement_status": s.status})
        if s.status == Settlement.Status.PENDING and d.deposit_date < delayed_cutoff():
            rows.append({"type": "SETTLEMENT_DELAYED", "deposit_id": d.pk, "deposit_no": d.deposit_no, "branch": d.branch.code,
                         "date": d.deposit_date, "expected": d.amount, "actual": None, "difference": None,
                         "reason": f"Pending since {d.deposit_date}", "settlement_status": s.status})
    return rows
