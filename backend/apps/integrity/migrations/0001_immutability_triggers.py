"""Database-level immutability for financial records (see docs/phase-6-hardening.md)."""
from django.db import migrations

FORWARD = r'''
-- Defense in depth: the service layer is the only legitimate writer; these triggers make the database refuse
-- every other write path (raw SQL, QuerySet.update(), shell, admin) to financial state.
-- ERRCODE 23000 maps to django.db.IntegrityError.

CREATE OR REPLACE FUNCTION cmrs_block_delete() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Financial records cannot be deleted (table %)', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation';
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cmrs_block_update() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'Records in % are immutable', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation';
END; $$ LANGUAGE plpgsql;

-- collections: only VALID -> VOIDED (with void metadata); nothing else ever changes.
CREATE OR REPLACE FUNCTION cmrs_collections_guard() RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'VOIDED' THEN
    RAISE EXCEPTION 'A voided collection is final' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF (NEW.id, NEW.receipt_number, NEW.loan_id, NEW.agent_id, NEW.branch_id, NEW.amount, NEW.collected_at,
      NEW.collection_date, NEW.idempotency_key, NEW.request_hash, NEW.note)
     IS DISTINCT FROM
     (OLD.id, OLD.receipt_number, OLD.loan_id, OLD.agent_id, OLD.branch_id, OLD.amount, OLD.collected_at,
      OLD.collection_date, OLD.idempotency_key, OLD.request_hash, OLD.note) THEN
    RAISE EXCEPTION 'Collections are immutable (only voiding is allowed)' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- cash_submissions: identity/expected never change; APPROVED/REJECTED are final except that an APPROVED
-- submission may receive its deposit link exactly once.
CREATE OR REPLACE FUNCTION cmrs_submissions_guard() RETURNS trigger AS $$
BEGIN
  IF (NEW.id, NEW.reference_no, NEW.agent_id, NEW.branch_id, NEW.submitted_at, NEW.expected_amount,
      NEW.idempotency_key, NEW.request_hash, NEW.note)
     IS DISTINCT FROM
     (OLD.id, OLD.reference_no, OLD.agent_id, OLD.branch_id, OLD.submitted_at, OLD.expected_amount,
      OLD.idempotency_key, OLD.request_hash, OLD.note) THEN
    RAISE EXCEPTION 'Submission identity and expected amount are immutable' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF OLD.status IN ('APPROVED', 'REJECTED') THEN
    IF OLD.status = 'APPROVED' AND OLD.deposit_id IS NULL AND NEW.deposit_id IS NOT NULL
       AND (NEW.status, NEW.received_amount, NEW.discrepancy_amount, NEW.discrepancy_reason, NEW.reviewed_by_id,
            NEW.reviewed_at, NEW.rejection_reason)
           IS NOT DISTINCT FROM
           (OLD.status, OLD.received_amount, OLD.discrepancy_amount, OLD.discrepancy_reason, OLD.reviewed_by_id,
            OLD.reviewed_at, OLD.rejection_reason) THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'A reconciled submission cannot be modified' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- cash_submission_items: link and snapshot amount fixed; is_active may only go true -> false.
CREATE OR REPLACE FUNCTION cmrs_items_guard() RETURNS trigger AS $$
BEGIN
  IF (NEW.id, NEW.submission_id, NEW.collection_id, NEW.amount) IS DISTINCT FROM (OLD.id, OLD.submission_id, OLD.collection_id, OLD.amount)
     OR (OLD.is_active = FALSE AND NEW.is_active = TRUE) THEN
    RAISE EXCEPTION 'Submission items are immutable (they can only be released)' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- settlements: PENDING -> SETTLED|FAILED, FAILED -> SETTLED; SETTLED is final; the deposit link never changes.
CREATE OR REPLACE FUNCTION cmrs_settlements_guard() RETURNS trigger AS $$
BEGIN
  IF NEW.id IS DISTINCT FROM OLD.id OR NEW.deposit_id IS DISTINCT FROM OLD.deposit_id THEN
    RAISE EXCEPTION 'Settlement identity is immutable' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF OLD.status = 'SETTLED' THEN
    RAISE EXCEPTION 'A settled settlement is final' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF NOT ((OLD.status = 'PENDING' AND NEW.status IN ('SETTLED', 'FAILED')) OR (OLD.status = 'FAILED' AND NEW.status = 'SETTLED')) THEN
    RAISE EXCEPTION 'Illegal settlement transition % -> %', OLD.status, NEW.status USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- loans: money and schedule fields are fixed at creation; only status (ACTIVE <-> CLOSED) changes.
CREATE OR REPLACE FUNCTION cmrs_loans_guard() RETURNS trigger AS $$
BEGIN
  IF (NEW.id, NEW.loan_number, NEW.customer_id, NEW.principal, NEW.total_payable, NEW.installment_count,
      NEW.frequency, NEW.start_date, NEW.created_by_id)
     IS DISTINCT FROM
     (OLD.id, OLD.loan_number, OLD.customer_id, OLD.principal, OLD.total_payable, OLD.installment_count,
      OLD.frequency, OLD.start_date, OLD.created_by_id) THEN
    RAISE EXCEPTION 'Loan terms are fixed at creation' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER collections_guard BEFORE UPDATE ON collections FOR EACH ROW EXECUTE FUNCTION cmrs_collections_guard();
CREATE TRIGGER submissions_guard BEFORE UPDATE ON cash_submissions FOR EACH ROW EXECUTE FUNCTION cmrs_submissions_guard();
CREATE TRIGGER items_guard BEFORE UPDATE ON cash_submission_items FOR EACH ROW EXECUTE FUNCTION cmrs_items_guard();
CREATE TRIGGER settlements_guard BEFORE UPDATE ON settlements FOR EACH ROW EXECUTE FUNCTION cmrs_settlements_guard();
CREATE TRIGGER loans_guard BEFORE UPDATE ON loans FOR EACH ROW EXECUTE FUNCTION cmrs_loans_guard();
CREATE TRIGGER deposits_no_update BEFORE UPDATE ON bank_deposits FOR EACH ROW EXECUTE FUNCTION cmrs_block_update();
CREATE TRIGGER installments_no_update BEFORE UPDATE ON installments FOR EACH ROW EXECUTE FUNCTION cmrs_block_update();
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events FOR EACH ROW EXECUTE FUNCTION cmrs_block_update();

CREATE TRIGGER collections_no_delete BEFORE DELETE ON collections FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER submissions_no_delete BEFORE DELETE ON cash_submissions FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER items_no_delete BEFORE DELETE ON cash_submission_items FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER deposits_no_delete BEFORE DELETE ON bank_deposits FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER settlements_no_delete BEFORE DELETE ON settlements FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER installments_no_delete BEFORE DELETE ON installments FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
CREATE TRIGGER loans_no_delete BEFORE DELETE ON loans FOR EACH ROW EXECUTE FUNCTION cmrs_block_delete();
'''

REVERSE = r'''
DROP TRIGGER IF EXISTS collections_guard ON collections;
DROP TRIGGER IF EXISTS submissions_guard ON cash_submissions;
DROP TRIGGER IF EXISTS items_guard ON cash_submission_items;
DROP TRIGGER IF EXISTS settlements_guard ON settlements;
DROP TRIGGER IF EXISTS loans_guard ON loans;
DROP TRIGGER IF EXISTS deposits_no_update ON bank_deposits;
DROP TRIGGER IF EXISTS installments_no_update ON installments;
DROP TRIGGER IF EXISTS audit_no_update ON audit_events;
DROP TRIGGER IF EXISTS collections_no_delete ON collections;
DROP TRIGGER IF EXISTS submissions_no_delete ON cash_submissions;
DROP TRIGGER IF EXISTS items_no_delete ON cash_submission_items;
DROP TRIGGER IF EXISTS deposits_no_delete ON bank_deposits;
DROP TRIGGER IF EXISTS settlements_no_delete ON settlements;
DROP TRIGGER IF EXISTS audit_no_delete ON audit_events;
DROP TRIGGER IF EXISTS installments_no_delete ON installments;
DROP TRIGGER IF EXISTS loans_no_delete ON loans;
DROP FUNCTION IF EXISTS cmrs_block_delete(), cmrs_block_update(), cmrs_collections_guard(), cmrs_submissions_guard(),
  cmrs_items_guard(), cmrs_settlements_guard(), cmrs_loans_guard();
'''


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_seed_roles"),
        ("audit", "0001_initial"),
        ("lending", "0001_initial"),
        ("collections", "0001_initial"),
        ("cash", "0003_cashsubmission_cash_sub_status_reviewed_idx"),
        ("treasury", "0002_bankdeposit_deposits_date_idx_and_more"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
