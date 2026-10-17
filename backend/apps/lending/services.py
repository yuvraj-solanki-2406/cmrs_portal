from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.accounts import roles
from apps.accounts.models import Branch, User
from apps.audit.services import record as audit_record
from apps.common.exceptions import NotAllowed, ValidationFailed
from apps.common.sequences import next_value

from .models import Customer, Installment, Loan
from .schedule import build_schedule


def _ensure_agent_for_branch(agent: User | None, branch: Branch):
    if agent is None:
        return
    if agent.role_code != roles.AGENT or not agent.is_active:
        raise ValidationFailed("Selected user is not an active agent.", code="NOT_AN_AGENT",
                               details={"fields": {"assigned_agent": ["Must be an active agent."]}})
    if agent.branch_id != branch.pk:
        raise ValidationFailed("Agent belongs to a different branch.", code="AGENT_BRANCH_MISMATCH",
                               details={"fields": {"assigned_agent": ["Agent must belong to the customer's branch."]}})


def _resolve_branch(actor: User, branch: Branch | None) -> Branch:
    if actor.role_code == roles.BRANCH_MANAGER:
        if branch is not None and branch.pk != actor.branch_id:
            raise NotAllowed("You can only manage your own branch.")
        return actor.branch
    if branch is None:
        raise ValidationFailed("Branch is required.", details={"fields": {"branch": ["Required."]}})
    return branch


def _assert_can_manage(actor: User, customer: Customer):
    if actor.role_code == roles.BRANCH_MANAGER and customer.branch_id != actor.branch_id:
        raise NotAllowed("Customer belongs to another branch.")


@transaction.atomic
def create_customer(*, actor: User, full_name: str, phone: str = "", address: str = "",
                    branch: Branch | None = None, assigned_agent: User | None = None) -> Customer:
    branch = _resolve_branch(actor, branch)
    _ensure_agent_for_branch(assigned_agent, branch)
    customer = Customer.objects.create(
        customer_code=f"CUST-{next_value('customer_code_seq'):06d}",
        full_name=full_name.strip(), phone=phone.strip(), address=address.strip(),
        branch=branch, assigned_agent=assigned_agent,
    )
    audit_record(actor=actor, action="CUSTOMER_CREATED", entity=customer,
                 after={"code": customer.customer_code, "branch": branch.code,
                        "agent": assigned_agent.username if assigned_agent else None})
    return customer


@transaction.atomic
def update_customer(*, actor: User, customer: Customer, **fields) -> Customer:
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    _assert_can_manage(actor, customer)
    before = {k: getattr(customer, k) for k in fields}
    for name, value in fields.items():
        setattr(customer, name, value.strip() if isinstance(value, str) else value)
    customer.save(update_fields=list(fields))
    audit_record(actor=actor, action="CUSTOMER_UPDATED", entity=customer, before=before,
                 after={k: getattr(customer, k) for k in fields})
    return customer


@transaction.atomic
def assign_agent(*, actor: User, customer: Customer, agent: User | None) -> Customer:
    customer = Customer.objects.select_for_update().select_related("branch").get(pk=customer.pk)
    _assert_can_manage(actor, customer)
    _ensure_agent_for_branch(agent, customer.branch)
    previous = customer.assigned_agent.username if customer.assigned_agent_id else None
    customer.assigned_agent = agent
    customer.save(update_fields=["assigned_agent"])
    audit_record(actor=actor, action="AGENT_ASSIGNED", entity=customer, before={"agent": previous},
                 after={"agent": agent.username if agent else None})
    return customer


@transaction.atomic
def create_loan_with_schedule(*, actor: User, customer: Customer, principal: Decimal, total_payable: Decimal,
                              installment_count: int, frequency: str, start_date: date) -> Loan:
    _assert_can_manage(actor, customer)
    if not customer.is_active:
        raise ValidationFailed("Customer is inactive.", details={"fields": {"customer": ["Inactive customer."]}})
    if total_payable < principal:
        raise ValidationFailed("Total payable cannot be less than principal.", code="TOTAL_LT_PRINCIPAL",
                               details={"fields": {"total_payable": ["Must be at least the principal."]}})
    schedule = build_schedule(total_payable, installment_count, frequency, start_date)
    loan = Loan.objects.create(
        loan_number=f"LN-{next_value('loan_number_seq'):06d}", customer=customer, principal=principal,
        total_payable=total_payable, installment_count=installment_count, frequency=frequency,
        start_date=start_date, created_by=actor,
    )
    Installment.objects.bulk_create(
        [Installment(loan=loan, installment_no=n, due_date=d, amount_due=a) for n, d, a in schedule]
    )
    audit_record(actor=actor, action="LOAN_CREATED", entity=loan,
                 after={"loan_number": loan.loan_number, "customer": customer.customer_code,
                        "principal": str(principal), "total_payable": str(total_payable),
                        "installments": installment_count, "frequency": frequency})
    return loan
