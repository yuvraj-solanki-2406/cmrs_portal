from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

TABLES = ["customers", "collections", "cash_submission_items", "cash_submissions", "bank_deposits", "settlements", "audit_events", "loans", "installments"]
ACTIVITY_ENTITIES = ("Collection", "CashSubmission", "BankDeposit", "Settlement", "Loan")


class Command(BaseCommand):
    help = ("DEV ONLY: wipe collections, submissions, deposits, settlements and their audit events, reopen loans and drop "
            "extra loans beyond each customer's first. Users, branches, customers and the first loans/schedules are kept. Refuses to run unless DEBUG is on.")

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true",
                            help="Also delete customers, loans and installments (keeps only users, roles and branches).")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("reset_activity only runs with DJANGO_DEBUG=true (it bypasses immutability triggers).")
        with connection.cursor() as cur:
            for table in TABLES:  # triggers are table-level DDL; owner privilege suffices, re-enabled below
                cur.execute(f'ALTER TABLE "{table}" DISABLE TRIGGER USER')
            cur.execute("DELETE FROM audit_events WHERE entity_type = ANY(%s)", [list(ACTIVITY_ENTITIES)])
            cur.execute("TRUNCATE collections, cash_submission_items, cash_submissions, bank_deposits, settlements RESTART IDENTITY CASCADE")
            if options["all"]:
                cur.execute("DELETE FROM audit_events WHERE entity_type = ANY(%s)", [["Customer", "Loan", "Installment"]])
                cur.execute("TRUNCATE installments, loans, customers RESTART IDENTITY CASCADE")
                for seq in ("receipt_seq", "submission_seq", "deposit_seq"):
                    cur.execute(f"ALTER SEQUENCE {seq} RESTART")
                cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
                for table in TABLES:
                    cur.execute(f'ALTER TABLE "{table}" ENABLE TRIGGER USER')
                self.stdout.write(self.style.SUCCESS("All business data cleared; users, roles and branches kept."))
                return
            # Keep each customer's first (seeded) loan; drop extra loans that experiments/scripts added.
            keep = "(SELECT MIN(id) FROM loans GROUP BY customer_id)"
            cur.execute(f"DELETE FROM audit_events WHERE entity_type = 'Loan' AND entity_id::bigint NOT IN {keep}")
            cur.execute(f"DELETE FROM installments WHERE loan_id NOT IN {keep}")
            cur.execute(f"DELETE FROM loans WHERE id NOT IN {keep}")
            cur.execute("UPDATE loans SET status = 'ACTIVE'")
            for seq in ("receipt_seq", "submission_seq", "deposit_seq"):
                cur.execute(f"ALTER SEQUENCE {seq} RESTART")
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")  # run pending FK checks before touching trigger DDL
            for table in TABLES:
                cur.execute(f'ALTER TABLE "{table}" ENABLE TRIGGER USER')
        self.stdout.write(self.style.SUCCESS("Activity data cleared. Re-seed with: python manage.py seed_demo --with-activity"))
