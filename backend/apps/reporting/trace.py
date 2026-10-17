"""Lifecycle trace: collection ⇄ submission(s) ⇄ deposit ⇄ settlement, plus audit events, all scope-checked.
Agents see only their own collections/submissions and a limited deposit summary (no sibling cash)."""
from django.db.models import Q

from apps.accounts import roles
from apps.audit.models import AuditEvent
from apps.cash.models import CashSubmission, CashSubmissionItem
from apps.cash.selectors import submissions_for
from apps.collections.models import Collection
from apps.collections.selectors import collections_for
from apps.common.exceptions import NotFound
from apps.treasury.models import BankDeposit
from apps.treasury.selectors import deposits_for, delayed_cutoff

KINDS = ("collection", "submission", "deposit")


def _collection(c: Collection) -> dict:
    return {"id": c.pk, "receipt_number": c.receipt_number, "amount": c.amount, "status": c.status,
            "collected_at": c.collected_at, "agent": c.agent.username, "customer": c.loan.customer.full_name,
            "loan_number": c.loan.loan_number, "void_reason": c.void_reason}


def _submission(s: CashSubmission) -> dict:
    return {"id": s.pk, "reference_no": s.reference_no, "status": s.status, "agent": s.agent.username,
            "submitted_at": s.submitted_at, "expected_amount": s.expected_amount, "received_amount": s.received_amount,
            "discrepancy_amount": s.discrepancy_amount, "discrepancy_reason": s.discrepancy_reason,
            "reviewed_by": s.reviewed_by.username if s.reviewed_by else None, "reviewed_at": s.reviewed_at,
            "rejection_reason": s.rejection_reason, "deposit_id": s.deposit_id}


def _deposit(d: BankDeposit, *, limited: bool) -> dict:
    s = d.settlement
    base = {"id": d.pk, "deposit_no": d.deposit_no, "bank_name": d.bank_name, "deposit_date": d.deposit_date,
            "settlement_status": s.status, "is_delayed": s.status == "PENDING" and d.deposit_date < delayed_cutoff(),
            "settled_on": s.settled_on}
    if limited:  # an agent must not learn the amounts of other agents' cash banked in the same deposit
        return base
    return {**base, "reference_number": d.reference_number, "amount": d.amount, "reconciled_amount": d.reconciled_amount,
            "variance_amount": d.variance_amount, "variance_note": d.variance_note,
            "settled_amount": s.settled_amount, "settlement_variance": s.variance_amount,
            "settlement_variance_note": s.variance_note, "failure_reason": s.failure_reason,
            "confirmed_by": s.confirmed_by.username if s.confirmed_by else None}


def build(user, kind: str, pk: int) -> dict:
    if kind not in KINDS:
        raise NotFound("Unknown trace type.")
    limited = user.role_code == roles.AGENT
    visible_collections = collections_for(user)
    visible_submissions = submissions_for(user)
    visible_deposits = deposits_for(user)

    if kind == "collection":
        root = visible_collections.filter(pk=pk).first()
        sub_ids = CashSubmissionItem.objects.filter(collection_id=pk).values_list("submission_id", flat=True)
        subs = list(visible_submissions.filter(pk__in=sub_ids).order_by("id"))
        cols = [root] if root else []
    elif kind == "submission":
        root = visible_submissions.filter(pk=pk).first()
        subs = [root] if root else []
        col_ids = CashSubmissionItem.objects.filter(submission_id=pk).values_list("collection_id", flat=True)
        cols = list(visible_collections.filter(pk__in=col_ids).order_by("id"))
    else:
        root = visible_deposits.filter(pk=pk).first()
        subs = list(visible_submissions.filter(deposit_id=pk).order_by("id")) if root else []
        col_ids = CashSubmissionItem.objects.filter(submission__in=subs, is_active=True).values_list("collection_id", flat=True)
        cols = list(visible_collections.filter(pk__in=col_ids).order_by("id"))
    if root is None:
        raise NotFound("Record not found.")

    if kind != "deposit":
        dep_ids = {s.deposit_id for s in subs if s.deposit_id}
        deps = list(BankDeposit.objects.filter(pk__in=dep_ids).select_related("settlement", "settlement__confirmed_by"))
    else:
        deps = list(BankDeposit.objects.filter(pk=pk).select_related("settlement", "settlement__confirmed_by"))

    q = Q()
    if cols: q |= Q(entity_type="Collection", entity_id__in=[str(c.pk) for c in cols])
    if subs: q |= Q(entity_type="CashSubmission", entity_id__in=[str(s.pk) for s in subs])
    if deps:
        q |= Q(entity_type="BankDeposit", entity_id__in=[str(d.pk) for d in deps])
        q |= Q(entity_type="Settlement", entity_id__in=[str(d.settlement.pk) for d in deps])
    events = AuditEvent.objects.select_related("actor").filter(q).exclude(action__in=["LOGIN"]).order_by("occurred_at", "id") if q else []
    timeline = [{"at": e.occurred_at, "action": e.action, "actor": e.actor.username if e.actor else None,
                 "actor_role": e.actor_role, "entity_type": e.entity_type, "entity_id": e.entity_id,
                 "reason": e.reason, "details": e.after} for e in events]
    return {
        "root": {"type": kind, "id": pk},
        "collections": [_collection(c) for c in cols],
        "submissions": [_submission(s) for s in subs],
        "deposits": [_deposit(d, limited=limited) for d in deps],
        "timeline": timeline,
    }
