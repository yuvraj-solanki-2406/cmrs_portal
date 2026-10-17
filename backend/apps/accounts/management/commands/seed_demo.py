import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts import roles
from apps.accounts.models import Branch, Role, User

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Cmrs@12345")  # demo-only default; documented in README as test credentials

BRANCHES = [("MUM01", "Mumbai Central"), ("DEL01", "Delhi North")]
USERS = [
    # username, full name, role, branch code
    ("admin", "System Admin", roles.ADMIN, None),
    ("finance1", "Fatima Finance", roles.FINANCE, None),
    ("manager_mum", "Meena Manager", roles.BRANCH_MANAGER, "MUM01"),
    ("manager_del", "Deepak Manager", roles.BRANCH_MANAGER, "DEL01"),
    ("agent_mum1", "Ravi Agent", roles.AGENT, "MUM01"),
    ("agent_mum2", "Sunita Agent", roles.AGENT, "MUM01"),
    ("agent_del1", "Karan Agent", roles.AGENT, "DEL01"),
    ("agent_del2", "Pooja Agent", roles.AGENT, "DEL01"),
]


# branch code -> [(customer name, phone, agent username, principal, total payable, installments, frequency)]
CUSTOMERS = {
    "MUM01": [
        ("Anil Sharma", "9800000001", "agent_mum1", "10000.00", "12000.00", 12, "MONTHLY"),
        ("Bhavna Patel", "9800000002", "agent_mum1", "20000.00", "22000.00", 10, "WEEKLY"),
        ("Chetan Rao", "9800000003", "agent_mum2", "15000.00", "16500.00", 3, "MONTHLY"),
        ("Divya Nair", "9800000004", "agent_mum2", "8000.00", "9000.00", 6, "WEEKLY"),
    ],
    "DEL01": [
        ("Esha Verma", "9811000001", "agent_del1", "25000.00", "28000.00", 14, "WEEKLY"),
        ("Farhan Khan", "9811000002", "agent_del1", "12000.00", "13200.00", 6, "MONTHLY"),
        ("Gita Singh", "9811000003", "agent_del2", "18000.00", "19800.00", 9, "WEEKLY"),
        ("Harish Gupta", "9811000004", "agent_del2", "30000.00", "33000.00", 10, "MONTHLY"),
    ],
}


class Command(BaseCommand):
    help = "Seed demo branches, users, customers and loans. Idempotent. --with-activity adds a sample cash lifecycle."

    def add_arguments(self, parser):
        parser.add_argument("--users-only", action="store_true",
                            help="Create only branches and users (no customers, loans or activity).")
        parser.add_argument("--with-activity", action="store_true",
                            help="Also create sample collections, submissions, deposits and settlements (skipped if collections exist).")

    @transaction.atomic
    def handle(self, *args, **options):
        branches = {c: Branch.objects.get_or_create(code=c, defaults={"name": n})[0] for c, n in BRANCHES}
        created = 0
        for username, full_name, role_code, branch_code in USERS:
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={"full_name": full_name, "role": Role.objects.get(code=role_code),
                          "branch": branches.get(branch_code), "is_staff": role_code == roles.ADMIN,
                          "is_superuser": role_code == roles.ADMIN},
            )
            if was_created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seed: {created} users created."))
        if options["users_only"]:
            return
        self._seed_lending(branches)
        if options["with_activity"]:
            self._seed_activity()

    def _seed_lending(self, branches):
        from datetime import date, timedelta
        from decimal import Decimal

        from apps.lending import services
        from apps.lending.models import Customer

        today = date.today()
        made = 0
        for branch_code, rows in CUSTOMERS.items():
            manager = User.objects.get(role__code=roles.BRANCH_MANAGER, branch=branches[branch_code])
            for name, phone, agent_name, principal, total, count, freq in rows:
                if Customer.objects.filter(branch=branches[branch_code], full_name=name).exists():
                    continue
                customer = services.create_customer(actor=manager, full_name=name, phone=phone,
                                                    assigned_agent=User.objects.get(username=agent_name))
                services.create_loan_with_schedule(
                    actor=manager, customer=customer, principal=Decimal(principal), total_payable=Decimal(total),
                    installment_count=count, frequency=freq, start_date=today - timedelta(days=14))
                made += 1
        self.stdout.write(self.style.SUCCESS(f"Seed: {made} customers with loans created."))

    def _seed_activity(self):
        """Sample lifecycle built through the real services, so every rule and audit event applies.
        Hand-checkable totals: collected 36,000 · held 4,300 · in transit 7,500 · received 23,700 ·
        deposited 23,500 · settled 14,500 · discrepancy 500 · deposit variance 200 · delayed 1."""
        import uuid
        from datetime import date, timedelta
        from decimal import Decimal

        from apps.cash import services as cash
        from apps.collections import services as coll
        from apps.collections.models import Collection
        from apps.lending.models import Loan
        from apps.treasury import services as treasury

        if Collection.objects.exists():
            self.stdout.write("Activity seed skipped: collections already exist.")
            return
        u = lambda name: User.objects.get(username=name)
        today = date.today()
        # The scenario assumes the seeded agent assignments; restore any that were changed (via the service, audited).
        from apps.lending import services as lending
        from apps.lending.models import Customer
        for branch_code, rows in CUSTOMERS.items():
            for name, _phone, agent_name, *_ in rows:
                customer = Customer.objects.select_related("assigned_agent").get(branch__code=branch_code, full_name=name)
                if customer.assigned_agent is None or customer.assigned_agent.username != agent_name:
                    lending.assign_agent(actor=User.objects.get(role__code=roles.BRANCH_MANAGER, branch__code=branch_code),
                                         customer=customer, agent=u(agent_name))
                    self.stdout.write(f"Restored seeded assignment: {name} -> {agent_name}")

        def pay(agent, customer, amount):
            loan = Loan.objects.filter(customer__full_name=customer).order_by("id").first()
            c, _ = coll.record_repayment(actor=u(agent), loan_id=loan.pk, amount=Decimal(amount), idempotency_key=uuid.uuid4())
            return c.pk

        def submit(agent, ids):
            sub, _ = cash.submit_cash(actor=u(agent), collection_ids=ids, idempotency_key=uuid.uuid4())
            return sub.pk

        # Mumbai — agent_mum1: ₹15,000 collected; counted ₹14,500 (₹500 short); deposited and settled.
        ids = [pay("agent_mum1", "Anil Sharma", a) for a in ("2000", "1000")] + \
              [pay("agent_mum1", "Bhavna Patel", a) for a in ("5000", "4000", "3000")]
        sub = submit("agent_mum1", ids)
        cash.approve_submission(actor=u("manager_mum"), submission_id=sub, received_amount=Decimal("14500"),
                                discrepancy_reason="Counted 14,500 against 15,000; two notes missing")
        dep = treasury.record_deposit(actor=u("manager_mum"), submission_ids=[sub], bank_name="HDFC", amount=Decimal("14500"),
                                      deposit_date=today - timedelta(days=1), reference_number="UTR-MUM-0001")
        treasury.confirm_settlement(actor=u("finance1"), deposit_id=dep.pk, settled_amount=Decimal("14500"), settled_on=today,
                                    bank_credit_reference="CR-MUM-0001")
        pay("agent_mum1", "Anil Sharma", "1500")  # still held by the agent
        # Mumbai — agent_mum2: ₹7,500 submitted and waiting for the manager; ₹800 still held.
        submit("agent_mum2", [pay("agent_mum2", "Chetan Rao", "6000"), pay("agent_mum2", "Divya Nair", "1500")])
        pay("agent_mum2", "Divya Nair", "800")
        # Delhi — agent_del1: ₹6,200 approved exactly; deposited ₹6,000 five days ago (variance, still pending = delayed).
        sub = submit("agent_del1", [pay("agent_del1", "Esha Verma", "4000"), pay("agent_del1", "Farhan Khan", "2200")])
        cash.approve_submission(actor=u("manager_del"), submission_id=sub, received_amount=Decimal("6200"))
        treasury.record_deposit(actor=u("manager_del"), submission_ids=[sub], bank_name="ICICI", amount=Decimal("6000"),
                                deposit_date=today - timedelta(days=5), reference_number="UTR-DEL-0001",
                                variance_note="Rs 200 retained for branch stationery, to be confirmed")
        # Delhi — agent_del2: one submission rejected (collections return to the agent), one deposited then failed.
        sub = submit("agent_del2", [pay("agent_del2", "Gita Singh", "2000")])
        cash.reject_submission(actor=u("manager_del"), submission_id=sub, reason="Notes were not bundled; recount at branch")
        sub = submit("agent_del2", [pay("agent_del2", "Harish Gupta", "3000")])
        cash.approve_submission(actor=u("manager_del"), submission_id=sub, received_amount=Decimal("3000"))
        dep = treasury.record_deposit(actor=u("manager_del"), submission_ids=[sub], bank_name="SBI", amount=Decimal("3000"),
                                      deposit_date=today - timedelta(days=3), reference_number="UTR-DEL-0002")
        treasury.fail_settlement(actor=u("finance1"), deposit_id=dep.pk, reason="Credit not found in bank statement")
        self.stdout.write(self.style.SUCCESS("Seed: sample cash lifecycle created."))
