from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Trim, Upper

from apps.common.exceptions import InvalidState


class BankName(models.TextChoices):
    HDFC = "HDFC", "HDFC Bank"
    ICICI = "ICICI", "ICICI Bank"
    SBI = "SBI", "State Bank of India"
    AXIS = "AXIS", "Axis Bank"
    KOTAK = "KOTAK", "Kotak Mahindra Bank"
    PNB = "PNB", "Punjab National Bank"
    OTHER = "OTHER", "Other"


class BankDeposit(models.Model):
    """Cash banked by a branch against whole APPROVED submissions. Never edited after creation.
    Its fate (settled / failed) lives in the 1:1 Settlement row, never on the deposit itself."""

    deposit_no = models.CharField(max_length=40, unique=True)
    branch = models.ForeignKey("accounts.Branch", on_delete=models.PROTECT, related_name="deposits")
    bank_name = models.CharField(max_length=10, choices=BankName.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    deposit_date = models.DateField()
    reference_number = models.CharField(max_length=60)
    # Snapshots: sum of the covered submissions' received amounts, and amount - reconciled.
    reconciled_amount = models.DecimalField(max_digits=14, decimal_places=2)
    variance_amount = models.DecimalField(max_digits=14, decimal_places=2)
    variance_note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_deposits"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["branch", "deposit_date"], name="deposits_branch_date_idx"),
            models.Index(fields=["deposit_date"], name="deposits_date_idx"),
        ]
        constraints = [
            # Case/whitespace-insensitive: "utr998877 " collides with "UTR998877", even under a race.
            models.UniqueConstraint(Upper(Trim("reference_number")), name="deposits_reference_uq"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="deposits_amount_positive"),
            models.CheckConstraint(condition=Q(variance_amount=F("amount") - F("reconciled_amount")),
                                   name="deposits_variance_math"),
            models.CheckConstraint(condition=Q(variance_amount=0) | ~Q(variance_note=""),
                                   name="deposits_variance_needs_note"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise InvalidState("Bank deposits cannot be edited.", code="DEPOSIT_IMMUTABLE")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InvalidState("Bank deposits cannot be deleted.", code="DEPOSIT_IMMUTABLE")

    def __str__(self):
        return self.deposit_no


class Settlement(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SETTLED = "SETTLED", "Settled"
        FAILED = "FAILED", "Failed"

    deposit = models.OneToOneField(BankDeposit, on_delete=models.PROTECT, related_name="settlement")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    settled_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    settled_on = models.DateField(null=True, blank=True)
    bank_credit_reference = models.CharField(max_length=60, blank=True)
    # deposit.amount - settled_amount: positive = bank credited less than deposited.
    variance_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    variance_note = models.CharField(max_length=255, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "settlements"
        indexes = [
            models.Index(fields=["status"], name="settlements_status_idx"),
            models.Index(fields=["status", "settled_on"], name="settlements_status_settled_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                name="settlements_settled_fields",
                condition=~Q(status="SETTLED") | Q(settled_amount__isnull=False, settled_on__isnull=False,
                                                   confirmed_by__isnull=False, variance_amount__isnull=False),
            ),
            models.CheckConstraint(condition=~Q(status="FAILED") | ~Q(failure_reason=""),
                                   name="settlements_failed_needs_reason"),
            models.CheckConstraint(condition=Q(variance_amount__isnull=True) | Q(variance_amount=0) | ~Q(variance_note=""),
                                   name="settlements_variance_needs_note"),
            models.CheckConstraint(condition=Q(settled_amount__isnull=True) | Q(settled_amount__gt=0),
                                   name="settlements_settled_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None and not getattr(self, "_via_service", False):
            raise InvalidState("Settlements change only through confirm/fail operations.", code="SETTLEMENT_IMMUTABLE")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InvalidState("Settlements cannot be deleted.", code="SETTLEMENT_IMMUTABLE")
