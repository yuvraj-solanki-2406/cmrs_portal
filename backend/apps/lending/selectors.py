"""Read-side queries for lending. `paid_total` / `annotate_paid` are the ONLY places that know how
repayments reduce a loan balance; Phase 2 (collections) swaps their bodies, nothing else changes."""
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.common.money import ZERO
from apps.common.scoping import scope_queryset

from .models import Customer, Installment, Loan


def customers_for(user) -> QuerySet[Customer]:
    qs = Customer.objects.select_related("branch", "assigned_agent")
    return scope_queryset(qs, user, branch_field="branch", agent_field="assigned_agent")


_MONEY = DecimalField(max_digits=14, decimal_places=2)


def annotate_paid(queryset: QuerySet[Loan]) -> QuerySet[Loan]:
    """Annotate `paid_amount` (sum of VALID collections) and `due_to_date` (sum of installments due so far).
    Uses the `Loan.collections` reverse relation by name, so lending does not import the collections app."""
    due = (Installment.objects.filter(loan=OuterRef("pk"), due_date__lte=date.today())
           .values("loan").annotate(total=Sum("amount_due")).values("total"))
    return queryset.annotate(
        paid_amount=Coalesce(Sum("collections__amount", filter=Q(collections__status="VALID")), Value(ZERO), output_field=_MONEY),
        due_to_date=Coalesce(Subquery(due, output_field=_MONEY), Value(ZERO), output_field=_MONEY),
    )


def loans_for(user) -> QuerySet[Loan]:
    qs = Loan.objects.select_related("customer", "customer__branch")
    qs = scope_queryset(qs, user, branch_field="customer__branch", agent_field="customer__assigned_agent")
    return annotate_paid(qs).order_by("-id")


def paid_total(loan_id: int) -> Decimal:
    """Paid amount of one loan from the ledger. Call while holding the loan row lock when it guards a write."""
    total = Loan.objects.filter(pk=loan_id).aggregate(
        t=Sum("collections__amount", filter=Q(collections__status="VALID")))["t"]
    return total or ZERO


def loan_summary(loan: Loan) -> dict[str, Decimal]:
    paid = getattr(loan, "paid_amount", None)
    if paid is None:
        paid = paid_total(loan.pk)
    summary = {"total_payable": loan.total_payable, "paid": paid, "outstanding": loan.total_payable - paid}
    due_to_date = getattr(loan, "due_to_date", None)
    if due_to_date is not None:
        summary["due_now"] = max(due_to_date - paid, ZERO)
    return summary


def installment_statuses(loan: Loan, *, today: date | None = None) -> list[dict]:
    """Oldest-first waterfall of total paid over installments. Derived on read, never stored."""
    today = today or date.today()
    remaining = loan_summary(loan)["paid"]
    rows = []
    for inst in Installment.objects.filter(loan=loan).order_by("installment_no"):
        allocated = min(remaining, inst.amount_due)
        remaining -= allocated
        if allocated == inst.amount_due:
            status = "PAID"
        elif inst.due_date < today:
            status = "OVERDUE"
        elif allocated > 0:
            status = "PARTIAL"
        else:
            status = "PENDING"
        rows.append({"id": inst.pk, "installment_no": inst.installment_no, "due_date": inst.due_date,
                     "amount_due": inst.amount_due, "amount_paid": allocated,
                     "amount_remaining": inst.amount_due - allocated, "status": status})
    return rows
