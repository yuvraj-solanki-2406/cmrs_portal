"""Forced-failure checks: break the audit write at the END of each operation (after every other write) and
assert nothing was persisted. Run: python manage.py shell < scripts/rollback_check.py
Creates its own data through the services; leaves only the setup rows behind."""
import uuid
from datetime import date
from decimal import Decimal
from unittest import mock

from apps.accounts.models import User
from apps.cash import services as cash
from apps.cash.models import CashSubmission, CashSubmissionItem
from apps.collections import services as coll
from apps.collections.models import Collection
from apps.lending import services as lending
from apps.lending.models import Customer, Loan
from apps.treasury import services as treasury
from apps.treasury.models import BankDeposit, Settlement

agent, mgr, fin = (User.objects.get(username=u) for u in ("agent_mum1", "manager_mum", "finance1"))
cust = Customer.objects.get(full_name="Bhavna Patel")
loan = lending.create_loan_with_schedule(actor=mgr, customer=cust, principal=Decimal("100000"), total_payable=Decimal("100000"),
                                         installment_count=4, frequency="WEEKLY", start_date=date.today())
passed = failed = 0


def boom(**kwargs):
    raise RuntimeError("forced failure at end of operation")


def snapshot():
    return (Collection.objects.count(), CashSubmission.objects.count(), CashSubmissionItem.objects.count(),
            BankDeposit.objects.count(), Settlement.objects.count(), Loan.objects.filter(status="CLOSED").count())


def expect_rollback(label, module, fn, extra=lambda: True):
    global passed, failed
    before = snapshot()
    with mock.patch.object(module, "audit_record", boom):
        try:
            fn()
            ok, why = False, "no exception raised"
        except RuntimeError:
            ok, why = snapshot() == before and extra(), "state changed"
    passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else ' — ' + why}")


def pay(amount):
    c, _ = coll.record_repayment(actor=agent, loan_id=loan.pk, amount=Decimal(amount), idempotency_key=uuid.uuid4())
    return c


def submitted():
    c = pay(str(1000 + Collection.objects.count()))
    s, _ = cash.submit_cash(actor=agent, collection_ids=[c.pk], idempotency_key=uuid.uuid4())
    return s


def approved():
    s = submitted()
    cash.approve_submission(actor=mgr, submission_id=s.pk, received_amount=s.expected_amount)
    s.refresh_from_db()
    return s


expect_rollback("record_repayment", coll, lambda: coll.record_repayment(actor=agent, loan_id=loan.pk, amount=Decimal("123.45"), idempotency_key=uuid.uuid4()))
small = lending.create_loan_with_schedule(actor=mgr, customer=cust, principal=Decimal("500"), total_payable=Decimal("500"),
                                          installment_count=2, frequency="WEEKLY", start_date=date.today())
expect_rollback("record_repayment that would CLOSE the loan (loan stays ACTIVE)", coll,
                lambda: coll.record_repayment(actor=agent, loan_id=small.pk, amount=Decimal("500"), idempotency_key=uuid.uuid4()),
                lambda: Loan.objects.get(pk=small.pk).status == "ACTIVE")
c = pay("777.00")
expect_rollback("void_collection (collection stays VALID)", coll, lambda: coll.void_collection(actor=mgr, collection_id=c.pk, reason="x"),
                lambda: Collection.objects.get(pk=c.pk).status == "VALID")
c2 = pay("888.00")
expect_rollback("submit_cash", cash, lambda: cash.submit_cash(actor=agent, collection_ids=[c2.pk], idempotency_key=uuid.uuid4()))
s = submitted()
expect_rollback("approve_submission (stays SUBMITTED)", cash, lambda: cash.approve_submission(actor=mgr, submission_id=s.pk, received_amount=s.expected_amount),
                lambda: CashSubmission.objects.get(pk=s.pk).status == "SUBMITTED")
expect_rollback("reject_submission (items stay active)", cash, lambda: cash.reject_submission(actor=mgr, submission_id=s.pk, reason="x"),
                lambda: CashSubmission.objects.get(pk=s.pk).status == "SUBMITTED" and s.items.filter(is_active=True).count() == s.items.count())
a = approved()
expect_rollback("record_deposit (no deposit, no settlement, submission unlinked)", treasury,
                lambda: treasury.record_deposit(actor=mgr, submission_ids=[a.pk], bank_name="HDFC", amount=a.received_amount, deposit_date=date.today(), reference_number="RB-" + uuid.uuid4().hex[:6]),
                lambda: CashSubmission.objects.get(pk=a.pk).deposit_id is None)
dep = treasury.record_deposit(actor=mgr, submission_ids=[a.pk], bank_name="HDFC", amount=a.received_amount, deposit_date=date.today(), reference_number="RB-" + uuid.uuid4().hex[:6])
expect_rollback("confirm_settlement (stays PENDING)", treasury, lambda: treasury.confirm_settlement(actor=fin, deposit_id=dep.pk, settled_amount=dep.amount, settled_on=date.today()),
                lambda: Settlement.objects.get(deposit=dep).status == "PENDING")
expect_rollback("fail_settlement (stays PENDING)", treasury, lambda: treasury.fail_settlement(actor=fin, deposit_id=dep.pk, reason="x"),
                lambda: Settlement.objects.get(deposit=dep).status == "PENDING")
print(f"\n{passed} passed, {failed} failed")
