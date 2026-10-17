from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.common.exceptions import InvalidState


class CashSubmission(models.Model):
    """Agent → branch hand-over of cash. Also carries the branch reconciliation outcome (1:1 with the count)."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    reference_no = models.CharField(max_length=40, unique=True)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cash_submissions")
    branch = models.ForeignKey("accounts.Branch", on_delete=models.PROTECT, related_name="cash_submissions")
    submitted_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    # Server-computed snapshot: sum of the items at submission time.
    expected_amount = models.DecimalField(max_digits=14, decimal_places=2)
    received_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # expected - received: positive = shortfall, negative = surplus.
    discrepancy_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    discrepancy_reason = models.CharField(max_length=255, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    # Set by treasury.record_deposit; a deposit covers whole APPROVED submissions (assumption A7).
    deposit = models.ForeignKey("treasury.BankDeposit", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="submissions")
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "cash_submissions"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["branch", "status"], name="cash_sub_branch_status_idx"),
            models.Index(fields=["agent", "submitted_at"], name="cash_sub_agent_time_idx"),
            models.Index(fields=["deposit"], name="cash_sub_deposit_idx"),
            models.Index(fields=["status", "reviewed_at"], name="cash_sub_status_reviewed_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["agent", "idempotency_key"], name="cash_sub_agent_idem_uq"),
            models.CheckConstraint(condition=Q(expected_amount__gt=0), name="cash_sub_expected_positive"),
            models.CheckConstraint(condition=Q(received_amount__isnull=True) | Q(received_amount__gte=0),
                                   name="cash_sub_received_nonneg"),
            models.CheckConstraint(
                name="cash_sub_approved_fields",
                condition=~Q(status="APPROVED") | (
                    Q(received_amount__isnull=False, discrepancy_amount__isnull=False,
                      reviewed_by__isnull=False, reviewed_at__isnull=False)
                    & Q(discrepancy_amount=F("expected_amount") - F("received_amount"))
                    & (Q(discrepancy_amount=0) | ~Q(discrepancy_reason=""))
                ),
            ),
            models.CheckConstraint(
                name="cash_sub_rejected_fields",
                condition=~Q(status="REJECTED") | (
                    ~Q(rejection_reason="") & Q(received_amount__isnull=True,
                                                reviewed_by__isnull=False, reviewed_at__isnull=False)
                ),
            ),
            models.CheckConstraint(condition=Q(deposit__isnull=True) | Q(status="APPROVED"),
                                   name="cash_sub_deposit_needs_approved"),
            models.CheckConstraint(condition=Q(reviewed_by__isnull=True) | ~Q(reviewed_by=F("agent")),
                                   name="cash_sub_reviewer_not_agent"),
        ]

    def save(self, *args, **kwargs):
        # Terminal rows (and any change to an existing row) only via services that set `_via_service`.
        if self.pk is not None and not getattr(self, "_via_service", False):
            raise InvalidState("Reconciled submissions are immutable.", code="SUBMISSION_IMMUTABLE")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InvalidState("Submissions cannot be deleted.", code="SUBMISSION_IMMUTABLE")

    def __str__(self):
        return self.reference_no


class CashSubmissionItem(models.Model):
    submission = models.ForeignKey(CashSubmission, on_delete=models.PROTECT, related_name="items")
    collection = models.ForeignKey("collections.Collection", on_delete=models.PROTECT, related_name="submission_items")
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # snapshot of the collection amount
    # False after the submission is rejected: row is kept for history, collection becomes submittable again.
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "cash_submission_items"
        ordering = ["id"]
        indexes = [models.Index(fields=["submission"], name="cash_item_submission_idx")]
        constraints = [
            # A collection can sit in at most one live submission, enforced by the database.
            models.UniqueConstraint(fields=["collection"], condition=Q(is_active=True), name="cash_item_one_active_uq"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="cash_item_amount_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None and not getattr(self, "_via_service", False):
            raise InvalidState("Submission items are immutable.", code="SUBMISSION_ITEM_IMMUTABLE")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InvalidState("Submission items cannot be deleted.", code="SUBMISSION_ITEM_IMMUTABLE")
