"""Money-moving operations for repayments. Every function is one atomic transaction with audit."""
import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.models import User
from apps.audit.services import record as audit_record
from apps.common.exceptions import Conflict, DomainError, InvalidState, NotAllowed, NotFound, ValidationFailed
from apps.common.sequences import next_value
from apps.lending.models import Loan
from apps.lending.selectors import paid_total

from .models import Collection

DUPLICATE_WINDOW = timedelta(minutes=10)


class OverCollection(ValidationFailed):
    code = "OVER_COLLECTION"


class LoanNotActive(ValidationFailed):
    code = "LOAN_NOT_ACTIVE"


class PossibleDuplicate(Conflict):
    code = "POSSIBLE_DUPLICATE"


class IdempotencyKeyReused(DomainError):
    status_code = 422
    code = "IDEMPOTENCY_KEY_REUSED"


def request_fingerprint(loan_id: int, amount: Decimal, note: str) -> str:
    payload = json.dumps({"loan": loan_id, "amount": str(amount), "note": note.strip()}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _replay(agent: User, key: uuid.UUID, fingerprint: str) -> Collection | None:
    existing = Collection.objects.filter(agent=agent, idempotency_key=key).first()
    if existing is None:
        return None
    if existing.request_hash != fingerprint:
        raise IdempotencyKeyReused("This Idempotency-Key was already used with a different request.")
    return existing


def _receipt_number(branch_code: str) -> str:
    return f"RCP-{branch_code}-{timezone.localdate():%Y%m%d}-{next_value('receipt_seq'):06d}"


def record_repayment(*, actor: User, loan_id: int, amount: Decimal, idempotency_key: uuid.UUID, note: str = "",
                     confirm_duplicate: bool = False) -> tuple[Collection, bool]:
    """Returns (collection, replayed). Lock order: loan row first."""
    fingerprint = request_fingerprint(loan_id, amount, note)
    if (hit := _replay(actor, idempotency_key, fingerprint)) is not None:
        return hit, True
    try:
        return _record_repayment_tx(actor, loan_id, amount, idempotency_key, note.strip(), confirm_duplicate, fingerprint)
    except IntegrityError:
        # Lost a race on UNIQUE(agent, idempotency_key): the winner's row is the answer.
        hit = _replay(actor, idempotency_key, fingerprint)
        if hit is None:
            raise
        return hit, True


@transaction.atomic
def _record_repayment_tx(actor, loan_id, amount, key, note, confirm_duplicate, fingerprint) -> tuple[Collection, bool]:
    # 1. Authorization: the loan's customer must be assigned to this agent. Anything else looks nonexistent.
    visible = Loan.objects.filter(pk=loan_id, customer__assigned_agent=actor).exists()
    if not visible:
        raise NotFound("Loan not found.")
    # 2. Serialize all payments on this loan. `of=("self",)` locks only the loans row.
    loan = Loan.objects.select_for_update(of=("self",)).select_related("customer").get(pk=loan_id)
    # 3. Re-check replay now that we hold the lock (a same-key request may have just committed).
    if (hit := _replay(actor, key, fingerprint)) is not None:
        return hit, True
    if loan.status != Loan.Status.ACTIVE:
        raise LoanNotActive("Loan is closed; no further repayments are accepted.")
    # 4. Over-collection guard against the freshly computed outstanding.
    outstanding = loan.total_payable - paid_total(loan.pk)
    if amount > outstanding:
        raise OverCollection(
            f"Amount exceeds the outstanding balance. Maximum allowed is {outstanding}.",
            details={"max_allowed": str(outstanding), "outstanding": str(outstanding)},
        )
    # 5. Soft duplicate guard (human double-entry with a fresh key).
    if not confirm_duplicate and Collection.objects.filter(
        agent=actor, loan=loan, amount=amount, status=Collection.Status.VALID,
        collected_at__gte=timezone.now() - DUPLICATE_WINDOW,
    ).exists():
        raise PossibleDuplicate(
            "The same amount was recorded for this loan in the last 10 minutes. Confirm to record it again.",
            details={"confirm_duplicate_required": True},
        )
    now = timezone.now()
    collection = Collection.objects.create(
        receipt_number=_receipt_number(actor.branch.code), loan=loan, agent=actor, branch=actor.branch,
        amount=amount, collected_at=now, collection_date=timezone.localdate(now), idempotency_key=key,
        request_hash=fingerprint, note=note,
    )
    if outstanding - amount == 0:
        loan.status = Loan.Status.CLOSED
        loan.save(update_fields=["status"])
    audit_record(actor=actor, action="COLLECTION_RECORDED", entity=collection,
                 after={"receipt": collection.receipt_number, "loan": loan.loan_number, "amount": str(amount),
                        "outstanding_after": str(outstanding - amount)})
    return collection, False


@transaction.atomic
def void_collection(*, actor: User, collection_id: int, reason: str) -> Collection:
    reason = reason.strip()
    if not reason:
        raise ValidationFailed("A reason is required.", details={"fields": {"reason": ["Required."]}})
    # Lock order is loan first (same as record_repayment), then the collection.
    loan_id = Collection.objects.filter(pk=collection_id).values_list("loan_id", flat=True).first()
    if loan_id is None:
        raise NotFound("Collection not found.")
    loan = Loan.objects.select_for_update(of=("self",)).get(pk=loan_id)
    collection = Collection.objects.select_for_update().get(pk=collection_id)
    if actor.role_code != roles.BRANCH_MANAGER or collection.branch_id != actor.branch_id:
        raise NotFound("Collection not found.")
    if collection.status != Collection.Status.VALID:
        raise InvalidState("Collection is already voided.")
    from .selectors import is_in_active_submission
    if is_in_active_submission(collection):
        raise InvalidState("This collection is part of a cash submission and can no longer be voided.",
                           code="COLLECTION_SUBMITTED")
    collection.status = Collection.Status.VOIDED
    collection.voided_by, collection.voided_at, collection.void_reason = actor, timezone.now(), reason
    collection._via_service = True
    collection.save()
    if loan.status == Loan.Status.CLOSED:  # outstanding is positive again
        loan.status = Loan.Status.ACTIVE
        loan.save(update_fields=["status"])
    audit_record(actor=actor, action="COLLECTION_VOIDED", entity=collection, reason=reason,
                 before={"status": "VALID"}, after={"status": "VOIDED", "amount": str(collection.amount),
                                                    "loan": loan.loan_number})
    return collection
