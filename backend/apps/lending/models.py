from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Customer(models.Model):
    customer_code = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    branch = models.ForeignKey("accounts.Branch", on_delete=models.PROTECT, related_name="customers")
    assigned_agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                       related_name="assigned_customers")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customers"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["assigned_agent"], name="customers_agent_idx"),
            models.Index(fields=["branch"], name="customers_branch_idx"),
        ]

    def __str__(self):
        return f"{self.customer_code} {self.full_name}"


class Loan(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Every 3 months"
        HALF_YEARLY = "HALF_YEARLY", "Every 6 months"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    loan_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="loans")
    principal = models.DecimalField(max_digits=14, decimal_places=2)
    # Principal + interest, fixed at creation (assumption A3). Outstanding is derived, never stored.
    total_payable = models.DecimalField(max_digits=14, decimal_places=2)
    installment_count = models.PositiveIntegerField()
    frequency = models.CharField(max_length=12, choices=Frequency.choices)
    start_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "loans"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["customer"], name="loans_customer_idx"),
            models.Index(fields=["status"], name="loans_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(principal__gt=0), name="loans_principal_positive"),
            models.CheckConstraint(condition=Q(total_payable__gte=F("principal")), name="loans_total_gte_principal"),
            models.CheckConstraint(condition=Q(installment_count__gt=0), name="loans_installments_positive"),
        ]

    def __str__(self):
        return self.loan_number


class Installment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="installments")
    installment_no = models.PositiveIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "installments"
        ordering = ["loan_id", "installment_no"]
        indexes = [
            models.Index(fields=["due_date"], name="installments_due_idx"),
            models.Index(fields=["loan", "due_date"], name="installments_loan_due_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["loan", "installment_no"], name="installments_loan_no_uq"),
            models.CheckConstraint(condition=Q(amount_due__gt=0), name="installments_amount_positive"),
        ]
