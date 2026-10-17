"""Bank deposit and settlement operations. One atomic transaction + audit per operation.
Lock order: submissions (by id) for deposits; the settlement row for confirm/fail."""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.models import User
from apps.audit.services import record as audit_record
from apps.cash.models import CashSubmission
from apps.common.exceptions import Conflict, InvalidState, NotFound, ValidationFailed
from apps.common.money import ZERO
from apps.common.sequences import next_value

from .models import BankDeposit, Settlement


class DuplicateBankReference(Conflict):
    code = "DUPLICATE_BANK_REFERENCE"


class SubmissionNotEligible(Conflict):
    code = "SUBMISSION_NOT_ELIGIBLE"


def normalize_reference(reference: str) -> str:
    return " ".join(reference.split()).strip()


@transaction.atomic
def record_deposit(*, actor: User, submission_ids: list[int], bank_name: str, amount: Decimal, deposit_date: date,
                   reference_number: str, variance_note: str = "") -> BankDeposit:
    ids = sorted(set(submission_ids))
    if not ids:
        raise ValidationFailed("Select at least one approved submission.",
                               details={"fields": {"submission_ids": ["Required."]}})
    reference = normalize_reference(reference_number)
    if not reference:
        raise ValidationFailed("Bank reference is required.", details={"fields": {"reference_number": ["Required."]}})
    if deposit_date > timezone.localdate():
        raise ValidationFailed("Deposit date cannot be in the future.", code="DEPOSIT_DATE_IN_FUTURE",
                               details={"fields": {"deposit_date": ["Cannot be in the future."]}})
    # Lock the submissions in id order so two deposits cannot both claim the same one.
    locked = list(CashSubmission.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    if len(locked) != len(ids) or any(s.branch_id != actor.branch_id for s in locked):
        raise NotFound("Submission not found.")  # other branches look nonexistent
    problems = [s.reference_no for s in locked
                if s.status != CashSubmission.Status.APPROVED or s.deposit_id is not None]
    if problems:
        raise SubmissionNotEligible("Only approved submissions that are not yet deposited can be banked.",
                                    details={"submissions": problems})
    reconciled = sum((s.received_amount for s in locked), ZERO)
    variance = amount - reconciled
    note = variance_note.strip()
    if variance != 0 and not note:
        raise ValidationFailed("A note is required when the deposit differs from the reconciled cash.",
                               code="VARIANCE_NOTE_REQUIRED",
                               details={"fields": {"variance_note": ["Required when amounts differ."]},
                                        "reconciled": str(reconciled), "variance": str(variance)})
    try:
        with transaction.atomic():  # savepoint so a unique violation can be translated, not leaked
            deposit = BankDeposit.objects.create(
                deposit_no=f"DEP-{actor.branch.code}-{timezone.localdate():%Y%m%d}-{next_value('deposit_seq'):06d}",
                branch=actor.branch, bank_name=bank_name, amount=amount, deposit_date=deposit_date,
                reference_number=reference, reconciled_amount=reconciled, variance_amount=variance,
                variance_note=note if variance != 0 else "", created_by=actor)
    except IntegrityError as exc:
        if "deposits_reference_uq" in str(exc):
            raise DuplicateBankReference("This bank reference has already been recorded.",
                                         details={"fields": {"reference_number": ["Already used."]}}) from exc
        raise
    Settlement.objects.create(deposit=deposit)  # PENDING, same transaction as the deposit
    for submission in locked:
        submission.deposit = deposit
        submission._via_service = True
        submission.save(update_fields=["deposit"])
    audit_record(actor=actor, action="DEPOSIT_RECORDED", entity=deposit, reason=deposit.variance_note,
                 after={"deposit_no": deposit.deposit_no, "bank": bank_name, "reference": reference,
                        "amount": str(amount), "reconciled": str(reconciled), "variance": str(variance),
                        "submissions": [s.reference_no for s in locked]})
    return deposit


def _lock_settlement(actor: User, deposit_id: int) -> Settlement:
    if actor.role_code != roles.FINANCE:
        raise NotFound("Deposit not found.")
    settlement = Settlement.objects.select_for_update(of=("self",)).select_related("deposit").filter(deposit_id=deposit_id).first()
    if settlement is None:
        raise NotFound("Deposit not found.")
    return settlement


@transaction.atomic
def confirm_settlement(*, actor: User, deposit_id: int, settled_amount: Decimal, settled_on: date,
                       variance_note: str = "", bank_credit_reference: str = "") -> Settlement:
    settlement = _lock_settlement(actor, deposit_id)
    if settlement.status == Settlement.Status.SETTLED:
        raise InvalidState("This deposit is already settled and cannot be changed.")
    deposit = settlement.deposit
    if settled_amount <= 0:
        raise ValidationFailed("Settled amount must be greater than zero (use Fail if nothing was credited).",
                               details={"fields": {"settled_amount": ["Must be positive."]}})
    if settled_on > timezone.localdate() or settled_on < deposit.deposit_date:
        raise ValidationFailed("Settlement date must be between the deposit date and today.",
                               details={"fields": {"settled_on": ["Out of range."]}})
    variance = deposit.amount - settled_amount  # + bank credited less, - bank credited more
    note = variance_note.strip()
    if variance != 0 and not note:
        raise ValidationFailed("A note is required when the bank credit differs from the deposit.",
                               code="VARIANCE_NOTE_REQUIRED",
                               details={"fields": {"variance_note": ["Required when amounts differ."]},
                                        "deposit_amount": str(deposit.amount), "variance": str(variance)})
    before = {"status": settlement.status}
    settlement.status = Settlement.Status.SETTLED
    settlement.settled_amount, settlement.settled_on = settled_amount, settled_on
    settlement.variance_amount = variance
    settlement.variance_note = note if variance != 0 else ""
    settlement.bank_credit_reference = bank_credit_reference.strip()
    settlement.confirmed_by, settlement.confirmed_at = actor, timezone.now()
    settlement._via_service = True
    settlement.save()
    audit_record(actor=actor, action="SETTLEMENT_CONFIRMED", entity=settlement, reason=settlement.variance_note,
                 before=before, after={"status": "SETTLED", "deposit": deposit.deposit_no, "settled": str(settled_amount),
                                       "deposit_amount": str(deposit.amount), "variance": str(variance)})
    return settlement


@transaction.atomic
def fail_settlement(*, actor: User, deposit_id: int, reason: str) -> Settlement:
    settlement = _lock_settlement(actor, deposit_id)
    if settlement.status != Settlement.Status.PENDING:
        raise InvalidState(f"Only a pending settlement can be marked failed (current: {settlement.status.lower()}).")
    reason = reason.strip()
    if not reason:
        raise ValidationFailed("A failure reason is required.", details={"fields": {"reason": ["Required."]}})
    settlement.status = Settlement.Status.FAILED
    settlement.failure_reason = reason
    settlement.confirmed_by, settlement.confirmed_at = actor, timezone.now()
    settlement._via_service = True
    settlement.save()
    audit_record(actor=actor, action="SETTLEMENT_FAILED", entity=settlement, reason=reason,
                 before={"status": "PENDING"}, after={"status": "FAILED", "deposit": settlement.deposit.deposit_no})
    return settlement
