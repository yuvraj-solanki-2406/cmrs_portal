from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.exceptions import InvalidState


class Collection(models.Model):
    """One customer repayment. Ledger row: immutable after creation except void (via service only).

    Status here is the *loan-accounting* state. Where the cash physically is (agent / branch / bank)
    is derived from submissions, deposits and settlements, never stored on this row.
    """

    class Status(models.TextChoices):
        VALID = "VALID", "Valid"
        VOIDED = "VOIDED", "Voided"

    receipt_number = models.CharField(max_length=40, unique=True)
    loan = models.ForeignKey("lending.Loan", on_delete=models.PROTECT, related_name="collections")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collections")
    # Snapshot of the agent's branch at collection time (agents can be moved later).
    branch = models.ForeignKey("accounts.Branch", on_delete=models.PROTECT, related_name="collections")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    collected_at = models.DateTimeField()
    collection_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    note = models.CharField(max_length=255, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "collections"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["loan"], name="collections_loan_idx"),
            models.Index(fields=["agent", "collection_date"], name="collections_agent_date_idx"),
            models.Index(fields=["branch", "collection_date"], name="collections_branch_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="collections_amount_positive"),
            models.UniqueConstraint(fields=["agent", "idempotency_key"], name="collections_agent_idem_uq"),
            models.CheckConstraint(condition=~Q(status="VOIDED") | ~Q(void_reason=""), name="collections_void_needs_reason"),
        ]

    def save(self, *args, **kwargs):
        # Defense in depth: only services (which set `_via_service`) may modify an existing row.
        # Note: QuerySet.update() bypasses model guards; services never use it on this table.
        if self.pk is not None and not getattr(self, "_via_service", False):
            raise InvalidState("Collections are immutable.", code="COLLECTION_IMMUTABLE")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InvalidState("Collections cannot be deleted; void them instead.", code="COLLECTION_IMMUTABLE")

    def __str__(self):
        return self.receipt_number
