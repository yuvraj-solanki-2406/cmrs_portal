# Phase 4 — Bank Deposit & Settlement

Source: `DESIGN.md` §6 (treasury), §7, §8-D/E, §9, §10, §14 (Phase 4).

## Objective
Branch managers deposit approved cash at the bank; Finance confirms or fails settlement; differences between reconciled and bank-settled amounts are visible.

## Scope
**In:** record deposit against approved submissions, settlement (1:1, created PENDING), confirm/fail/retry, variance flags, derived "delayed" status.
**Out:** deposit cancellation/release (P3 improvement), splitting a submission across deposits [A7], bank feed integration.

## Business rules enforced
- A deposit covers whole submissions that are APPROVED, belong to the manager's branch, and have `deposit_id IS NULL` (locked `FOR UPDATE ORDER BY id`).
- `reconciled_amount = Σ received_amount`; `variance = amount − reconciled`; variance ≠ 0 requires `variance_note` (allowed and flagged) [A8].
- Bank reference globally unique after `UPPER(TRIM())` [A9]; duplicate → 409 `DUPLICATE_BANK_REFERENCE`.
- Deposit date cannot be in the future; amount > 0.
- Settlement created PENDING in the same transaction as the deposit; only FINANCE may confirm/fail.
- Confirm: `settled_amount`, `settled_on` required; short/over credit → SETTLED with variance + note [A10]. FAILED requires reason; FAILED → SETTLED allowed; SETTLED is terminal.
- Recording a deposit is not settlement; deposits are not editable.
- "Delayed" = PENDING older than `SETTLEMENT_DELAY_DAYS` (default 2), derived at query time.

## Database changes
| Item | Details |
|---|---|
| `bank_deposits` | `deposit_no` UQ, `branch_id`, `bank_name` (fixed list), `amount`, `deposit_date`, `reference_number`, `reconciled_amount`, `variance_amount`, `variance_note`, `created_by`, `created_at` |
| `settlements` | `deposit_id` **UNIQUE FK**, `status` (PENDING/SETTLED/FAILED), `settled_amount`, `settled_on`, `bank_credit_reference`, `variance_amount`, `variance_note`, `failure_reason`, `confirmed_by`, `confirmed_at` |
| `cash_submissions.deposit_id` | new FK → `bank_deposits`; CHECK `deposit_id IS NOT NULL ⇒ status='APPROVED'`; index `(deposit_id)` |
| Constraints | UQ on `UPPER(TRIM(reference_number))`; CHECK `amount > 0`; variance ≠ 0 ⇒ note; SETTLED ⇒ settled_amount/settled_on/confirmed_by NOT NULL; FAILED ⇒ failure_reason NOT NULL |
| Indexes | `bank_deposits(branch_id, deposit_date)`, `settlements(status)` |

## Backend tasks
- `treasury/services.py`: `record_deposit` (atomic; lock submissions; compute totals/variance; insert deposit + PENDING settlement; set `deposit_id`; audit), `confirm_settlement`, `fail_settlement` (lock settlement, state check, variance math, audit).
- `treasury/selectors.py`: eligible submissions per branch, settlement queue (pending / delayed / failed), mismatch lists.
- Map `IntegrityError` on reference to friendly 409.
- Audit: `DEPOSIT_RECORDED`, `SETTLEMENT_CONFIRMED`, `SETTLEMENT_FAILED`.

## APIs
| Method + URL | Roles | Txn / idempotent | Validations / errors |
|---|---|---|---|
| `GET /deposits/eligible-submissions/` | MANAGER | no | approved, un-deposited, own branch |
| `POST /deposits/` | MANAGER | atomic + locks | body `submission_ids`, `bank_name`, `amount`, `deposit_date`, `reference_number`, `variance_note?`; 400 variance note missing / future date; 409 `DUPLICATE_BANK_REFERENCE`, `SUBMISSION_NOT_ELIGIBLE` |
| `GET /deposits/`, `GET /deposits/{id}/` | MANAGER branch; FINANCE/ADMIN all | no | filters `branch`, `status`, dates, `delayed=true` |
| `POST /deposits/{id}/settlement/confirm/` | FINANCE | atomic + lock | body `settled_amount`, `settled_on`, `variance_note?`; 409 `INVALID_STATE` if already SETTLED |
| `POST /deposits/{id}/settlement/fail/` | FINANCE | atomic + lock | body `reason`; 409 if SETTLED |

## Frontend tasks
- Manager: create-deposit screen (select approved submissions, auto reconciled total, entered amount, live variance, bank, date, reference); deposits list.
- Finance: settlement queue tabs (Pending / Delayed / Failed / Settled), confirm and fail dialogs showing variance.
- Status badges (PENDING / SETTLED / FAILED / DELAYED) and variance chips.

## Manual verification checklist
- [ ] Approved submission with received ₹48,500 → deposit ₹48,500 ref `UTR998877` → settlement PENDING, no variance.
- [ ] Deposit ₹48,000 against ₹48,500 reconciled → variance −₹500 requires note.
- [ ] Same reference `utr998877 ` (case/space variant) → 409.
- [ ] Deposit including a REJECTED / other-branch / already-deposited submission → rejected.
- [ ] Two parallel deposits for the same submission → one succeeds.
- [ ] Finance confirms ₹48,500 → SETTLED; confirming ₹48,000 → variance ₹500 flagged with note.
- [ ] Fail with reason → FAILED; later confirm → SETTLED; confirm again → 409.
- [ ] Branch manager calling settlement confirm → 403; PENDING deposit older than 2 days shows DELAYED.
- [ ] Invariant queries 6–7 return 0 rows.

## Dependencies
Phase 3 (approved submissions).

## Definition of done
Full lifecycle Customer → Collection → Submission → Reconciliation → Deposit → Settlement works through the UI; mismatches and failures are visible.

## Status
- [x] Models, constraints, `deposit_id` migration (treasury 0001 → cash 0002; `deposit_seq`; functional unique index `UPPER(TRIM(reference_number))`; CHECKs for variance math, SETTLED/FAILED field sets, deposit ⇒ APPROVED)
- [x] `record_deposit` service (submissions locked in id order; other-branch ids look nonexistent; unique violation caught in a savepoint and mapped to `DUPLICATE_BANK_REFERENCE`)
- [x] `confirm_settlement` / `fail_settlement` (settlement row locked; FAILED → SETTLED retry; SETTLED terminal)
- [x] Deposit/settlement APIs + OpenAPI (`eligible-submissions`, create, list/detail with `status`, `delayed`, date filters, `settlement/confirm`, `settlement/fail`; PATCH/DELETE → 405)
- [x] Manager frontend: New deposit (select submissions, auto reconciled total, live variance, note), Deposits list
- [x] Finance frontend: Settlements queue with tabs All / Pending / Delayed / Failed / Settled, detail page with confirm (live variance) and fail dialogs
- [x] Manual checklist (API) passed; in-browser click-through still to do

## Design notes
- A deposit has no status of its own; its fate is the 1:1 `Settlement` (created PENDING in the same transaction). "Delayed" is derived (PENDING and `deposit_date` older than `SETTLEMENT_DELAY_DAYS`).
- Two variances are tracked: `deposit.variance = deposited − reconciled` (branch side) and `settlement.variance = deposited − credited` (bank side). `gap_amount = reconciled − settled` is the end-to-end difference the assignment asks to identify.
- `settled_on` must lie between the deposit date and today; `settled_amount` must be positive (nothing credited = Fail).
- Admin gets read-only access; FINANCE alone can confirm/fail, MANAGER alone can record deposits (others get 403, other-branch managers 404).
- `cash` now has a schema dependency on `treasury` (the `deposit` FK, assumption A7); services still depend one way (`treasury → cash`).

## Verification results (API, run 2026-10-17)
- Submission received ₹48,500 (expected ₹50,000) → deposit ₹48,500 ref `UTR998877` → settlement PENDING, variance ₹0.00.
- `utr998877 `, `UTR998877`, ` utr998877` → 409 `DUPLICATE_BANK_REFERENCE`; the submission stayed eligible. Raw SQL with a case/space variant is blocked by `deposits_reference_uq`.
- Deposit ₹2,500 vs ₹3,000 reconciled without note → 400 `VARIANCE_NOTE_REQUIRED` (variance −500.00); with note → 201.
- Rejected / pending / already-deposited submissions → 409 `SUBMISSION_NOT_ELIGIBLE`; other-branch manager → 404; agent and finance → 403; future date, empty list, unknown bank → 400.
- Parallel deposits for one submission → one 201, one 409; parallel deposits with the same reference → one 201, one 409 `DUPLICATE_BANK_REFERENCE`.
- Settlement: manager and admin confirm → 403; settled date before deposit date or in the future → 400; confirm exact → SETTLED (gap 0.00); confirm ₹2,400 vs ₹2,500 without note → 400, with note → SETTLED variance ₹100.00 and reconciled−settled gap ₹600.00; confirm/fail after SETTLED → 409.
- Fail without reason → 400; fail → FAILED; fail again → 409; later confirm → SETTLED with the failure reason kept as history.
- A deposit dated 5 days ago with PENDING settlement → `is_delayed` true; `delayed=true` returns it, `delayed=false` excludes it.
- PATCH/DELETE on deposits → 405; model guards raise `DEPOSIT_IMMUTABLE` / `SETTLEMENT_IMMUTABLE`; CHECK constraints block variance math errors, SETTLED without fields, FAILED without reason, and a deposit link on a REJECTED submission.
- Invariant SQL (reconciled ≠ Σ received, deposit without exactly one settlement, deposited-but-not-approved, settled variance wrong) → 0 rows each.
- Audit: `DEPOSIT_RECORDED`, `SETTLEMENT_CONFIRMED`, `SETTLEMENT_FAILED` present.
