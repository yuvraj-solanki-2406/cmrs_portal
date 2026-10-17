"""Agent → branch cash submission and branch reconciliation. One atomic transaction + audit per operation."""
import hashlib
import json
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.models import User
from apps.audit.services import record as audit_record
from apps.collections.models import Collection
from apps.common.exceptions import Conflict, DomainError, InvalidState, NotFound, ValidationFailed
from apps.common.money import ZERO
from apps.common.sequences import next_value

from .models import CashSubmission, CashSubmissionItem


class AlreadySubmitted(Conflict):
    code = "ALREADY_SUBMITTED"


class IneligibleCollections(ValidationFailed):
    code = "INELIGIBLE_COLLECTIONS"


class IdempotencyKeyReused(DomainError):
    status_code = 422
    code = "IDEMPOTENCY_KEY_REUSED"


def _fingerprint(ids: list[int], note: str) -> str:
    return hashlib.sha256(json.dumps({"ids": sorted(ids), "note": note.strip()}).encode()).hexdigest()


def _replay(agent: User, key: uuid.UUID, fingerprint: str) -> CashSubmission | None:
    existing = CashSubmission.objects.filter(agent=agent, idempotency_key=key).first()
    if existing is None:
        return None
    if existing.request_hash != fingerprint:
        raise IdempotencyKeyReused("This Idempotency-Key was already used with a different request.")
    return existing


def submit_cash(*, actor: User, collection_ids: list[int], idempotency_key: uuid.UUID,
                note: str = "") -> tuple[CashSubmission, bool]:
    """Returns (submission, replayed)."""
    ids = sorted(set(collection_ids))
    if not ids:
        raise ValidationFailed("Select at least one collection to submit.",
                               details={"fields": {"collection_ids": ["Required."]}})
    fingerprint = _fingerprint(ids, note)
    if (hit := _replay(actor, idempotency_key, fingerprint)) is not None:
        return hit, True
    try:
        return _submit_tx(actor, ids, idempotency_key, note.strip(), fingerprint)
    except IntegrityError:
        # Either a same-key race (return the winner) or the partial unique index caught a double submit.
        if (hit := _replay(actor, idempotency_key, fingerprint)) is not None:
            return hit, True
        raise AlreadySubmitted("One or more collections were just submitted by another request.")


@transaction.atomic
def _submit_tx(actor, ids, key, note, fingerprint) -> tuple[CashSubmission, bool]:
    # Lock in id order (consistent order prevents deadlocks between concurrent submitters).
    locked = list(Collection.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    # A same-key request may have committed while we waited for the locks: replay it, don't conflict.
    if (hit := _replay(actor, key, fingerprint)) is not None:
        return hit, True
    if len(locked) != len(ids):
        raise IneligibleCollections("Some collections do not exist.")
    bad = [c.receipt_number for c in locked
           if c.agent_id != actor.pk or c.status != Collection.Status.VALID or c.branch_id != actor.branch_id]
    if bad:
        raise IneligibleCollections("Only your own valid collections can be submitted.", details={"receipts": bad})
    already = list(CashSubmissionItem.objects.filter(collection_id__in=ids, is_active=True)
                   .values_list("collection__receipt_number", flat=True))
    if already:
        raise AlreadySubmitted("Some collections are already part of a cash submission.", details={"receipts": already})
    expected = sum((c.amount for c in locked), ZERO)  # server-computed, never client-supplied
    now = timezone.now()
    submission = CashSubmission.objects.create(
        reference_no=f"SUB-{actor.branch.code}-{timezone.localdate(now):%Y%m%d}-{next_value('submission_seq'):06d}",
        agent=actor, branch=actor.branch, submitted_at=now, expected_amount=expected,
        idempotency_key=key, request_hash=fingerprint, note=note,
    )
    CashSubmissionItem.objects.bulk_create(
        [CashSubmissionItem(submission=submission, collection=c, amount=c.amount) for c in locked])
    audit_record(actor=actor, action="SUBMISSION_CREATED", entity=submission,
                 after={"reference": submission.reference_no, "expected": str(expected),
                        "collections": [c.receipt_number for c in locked]})
    return submission, False


def _lock_reviewable(actor: User, submission_id: int) -> CashSubmission:
    submission = CashSubmission.objects.select_for_update().filter(pk=submission_id).first()
    # Wrong role / other branch looks like a nonexistent record.
    if (submission is None or actor.role_code != roles.BRANCH_MANAGER or submission.branch_id != actor.branch_id
            or submission.agent_id == actor.pk):
        raise NotFound("Submission not found.")
    if submission.status != CashSubmission.Status.SUBMITTED:
        raise InvalidState(f"Submission is already {submission.status.lower()} and cannot be changed.")
    return submission


@transaction.atomic
def approve_submission(*, actor: User, submission_id: int, received_amount: Decimal,
                       discrepancy_reason: str = "") -> CashSubmission:
    submission = _lock_reviewable(actor, submission_id)
    if received_amount < 0:
        raise ValidationFailed("Received amount cannot be negative.",
                               details={"fields": {"received_amount": ["Must be 0 or more."]}})
    reason = discrepancy_reason.strip()
    discrepancy = submission.expected_amount - received_amount  # + shortfall, - surplus
    if discrepancy != 0 and not reason:
        raise ValidationFailed("A reason is required when received differs from expected.",
                               code="DISCREPANCY_REASON_REQUIRED",
                               details={"fields": {"discrepancy_reason": ["Required when there is a difference."]},
                                        "expected": str(submission.expected_amount), "discrepancy": str(discrepancy)})
    submission.status = CashSubmission.Status.APPROVED
    submission.received_amount, submission.discrepancy_amount = received_amount, discrepancy
    submission.discrepancy_reason = reason if discrepancy != 0 else ""
    submission.reviewed_by, submission.reviewed_at = actor, timezone.now()
    submission._via_service = True
    submission.save()
    audit_record(actor=actor, action="SUBMISSION_APPROVED", entity=submission, reason=submission.discrepancy_reason,
                 before={"status": "SUBMITTED"},
                 after={"status": "APPROVED", "expected": str(submission.expected_amount),
                        "received": str(received_amount), "discrepancy": str(discrepancy)})
    return submission


@transaction.atomic
def reject_submission(*, actor: User, submission_id: int, reason: str) -> CashSubmission:
    submission = _lock_reviewable(actor, submission_id)
    reason = reason.strip()
    if not reason:
        raise ValidationFailed("A rejection reason is required.", details={"fields": {"reason": ["Required."]}})
    submission.status = CashSubmission.Status.REJECTED
    submission.rejection_reason = reason
    submission.reviewed_by, submission.reviewed_at = actor, timezone.now()
    submission._via_service = True
    submission.save()
    # Release the collections: items stay for history but stop blocking resubmission.
    submission.items.filter(is_active=True).update(is_active=False)
    audit_record(actor=actor, action="SUBMISSION_REJECTED", entity=submission, reason=reason,
                 before={"status": "SUBMITTED"}, after={"status": "REJECTED", "expected": str(submission.expected_amount)})
    return submission
