# Phase 2 — Collections (Repayments & Receipts)

Source: `DESIGN.md` §6 (collections), §7, §8-A, §9, §10, §14 (Phase 2).

## Objective
Agents record customer repayments (partial allowed) safely under retries and concurrency; each repayment gets a unique receipt; agents see daily collections.

## Scope
**In:** record repayment, receipt numbers, idempotency, over-collection guard, soft duplicate guard, daily/own views, void (by manager, before submission).
**Out:** cash submission (Phase 3), payment gateway, post-submission adjustments.

## Business rules enforced
- `0 < amount ≤ outstanding`; larger amount → 400 `OVER_COLLECTION` stating the max allowed [A2].
- Agent must be assigned to the customer; loan must be ACTIVE.
- Loan row is locked (`select_for_update`) while outstanding is recomputed and the collection inserted.
- Idempotency: `UNIQUE(agent_id, idempotency_key)`; same key + same payload → original receipt; same key + different payload → 422 `IDEMPOTENCY_KEY_REUSED`.
- Soft duplicate: same agent + loan + amount within 10 min requires `confirm_duplicate=true` (new-key human double entry).
- Loan becomes CLOSED when outstanding reaches ₹0 inside the same locked transaction; a void reopens it.
- Collections are immutable; void only by BRANCH_MANAGER, with reason, only if no active submission item.
- Recording a repayment does not mean cash reached the branch.

## Database changes
| Item | Details |
|---|---|
| `collections` | `receipt_number` UQ, `loan_id`, `agent_id`, `branch_id` (snapshot), `amount` NUMERIC(14,2), `collected_at`, `collection_date` (IST), `status` (VALID/VOIDED), `idempotency_key` UUID, `request_hash`, `note`, `voided_by`, `voided_at`, `void_reason` |
| Constraints | CHECK `amount > 0`; UQ `(agent_id, idempotency_key)`; CHECK `status='VOIDED' ⇒ void_reason NOT NULL` |
| Indexes | `(loan_id)`, `(agent_id, collection_date)`, `(branch_id, collection_date)` |
| Sequence | `receipt_seq` via migration `RunSQL`; format `RCP-<branchcode>-<YYYYMMDD>-<6-digit seq>`; gaps after rollback acceptable |

## Backend tasks
- `collections/services.py`: `record_repayment` (atomic: replay check → lock loan → validate → `nextval` → insert → close loan if 0 → audit); catch `IntegrityError` on key race, re-read winner, compare `request_hash`.
- `void_collection` (atomic, locks collection, checks no active item, reopens loan if needed, audit).
- `collections/selectors.py`: daily collections per agent/branch, repayment history per loan.
- Model `save()/delete()` guard for VALID rows; serializer read-only on state/amount.
- Audit: `COLLECTION_RECORDED`, `COLLECTION_VOIDED`.

## APIs
| Method + URL | Roles | Txn / idempotent | Validations / errors |
|---|---|---|---|
| `POST /collections/` | AGENT | atomic + **Idempotency-Key required** + loan lock | 400 `OVER_COLLECTION`, `LOAN_NOT_ACTIVE`; 404 unassigned customer; 409 `POSSIBLE_DUPLICATE`; 422 key reused; 200 + `Idempotent-Replay: true` on replay |
| `GET /collections/` | AGENT own; MANAGER branch; FINANCE/ADMIN all | no | filters `agent`, `branch`, `status`, `date_from`, `date_to` |
| `GET /collections/{id}/` | scoped | no | receipt payload |
| `POST /collections/{id}/void/` | MANAGER | atomic + lock | 400 reason required; 409 `INVALID_STATE` if submitted |
| `GET /loans/{id}/repayments/` | scoped | no | history |

## Frontend tasks
- Agent "Today" list with due customers and quick "Record".
- Record-repayment form (amount string, note); idempotency key generated once per form mount and reused on retry; receipt confirmation screen; handle `OVER_COLLECTION` / `POSSIBLE_DUPLICATE` with a confirm dialog.
- Loan detail: repayment history and updated schedule statuses.
- "My daily collections" with date filter; manager's agent-collections list with void dialog.

## Manual verification checklist
- [ ] Loan ₹10,000: pay ₹3,000 then ₹2,500 → outstanding ₹4,500; installments show PARTIAL where applicable.
- [ ] Pay ₹4,501 when outstanding is ₹4,500 → 400 `OVER_COLLECTION` (max ₹4,500.00).
- [ ] Same Idempotency-Key replayed → same receipt, still one row; same key with ₹2,600 → 422.
- [ ] Two parallel ₹6,000 requests (different keys) on a ₹10,000 loan via one throw-away script → exactly one succeeds, outstanding ₹4,000.
- [ ] Receipt numbers unique and increasing; formatted per branch/date.
- [ ] Repeating the same ₹2,000 within 10 min without confirm → 409; with confirm → recorded.
- [ ] Agent cannot record for another agent's customer; manager cannot POST `/collections/` (403).
- [ ] Void ₹2,500 → outstanding returns to ₹7,000; voiding a submitted collection (after Phase 3) → 409.
- [ ] Final payment bringing outstanding to ₹0 closes the loan.

## Dependencies
Phase 1 (loans, outstanding, installments).

## Definition of done
Partial repayments work end-to-end; receipts unique; retries and races do not double-count; loan auto-closes/reopens; invariant queries 1–2 from DESIGN §12 return 0 rows.

## Status
- [x] `collections` model, constraints, `receipt_seq` (app label `collections`, module `apps.collections`; `startapp` rejects the bare name, files created by hand)
- [x] `record_repayment` with lock + idempotency (replay checked before and after the loan lock; `IntegrityError` on the `(agent, key)` unique index re-reads the winner)
- [x] Soft duplicate guard (10 minutes, `confirm_duplicate`)
- [x] Void service (manager, reason required, reopens loan); hook `is_in_active_submission()` returns False until Phase 3
- [x] Collections APIs + OpenAPI (`/collections/`, `/collections/summary/`, `/collections/{id}/void/`, `/loans/{id}/repayments/`; `GET /loans/?has_due=true` and `due_now` added for the agent's Today list)
- [x] Frontend: Today, Record repayment (key per attempt, receipt, over-collection and duplicate handling), My/All Collections with date filter, summary and void dialog, repayment history on loan detail; lint, tsc, build pass
- [x] Manual checklist (API) passed incl. parallel-request script; in-browser click-through still to do
- [ ] Phase 3 must replace `collections.selectors.is_in_active_submission`

## Design notes
- `lending` reads repayments through the `Loan.collections` reverse relation by name (no import), so the dependency still points `collections → lending`.
- Model guard: `Collection.save()` rejects updates unless a service sets `_via_service`; `delete()` always raises. `QuerySet.update()` bypasses model guards, so services never use it on this table.
- The key is per attempt in the UI: reused on retry of the same payload, renewed when amount/note change (same key + different payload is a 422) and after success.

## Verification results (API, run 2026-10-17)
- ₹10,000 loan: pay ₹3,000 then ₹2,500 → outstanding ₹4,500.00; receipts `RCP-MUM01-20261017-000001`, `-000002`.
- ₹4,501 when ₹4,500 outstanding → 400 `OVER_COLLECTION`, `max_allowed 4500.00`.
- Same key replayed → 200 + `Idempotent-Replay: true`, same receipt; same key with a different amount → 422; missing key → 400.
- Same ₹2,000 again within 10 min → 409 `POSSIBLE_DUPLICATE`; with `confirm_duplicate` → 201.
- Other agent → 404; manager/finance POST → 403.
- Void: empty reason → 400; other-branch manager → 404; agent → 403; ₹3,000 void raises outstanding by ₹3,000; voiding twice → 409; final payment closes the loan, further payment → `LOAN_NOT_ACTIVE`; voiding the last payment reopens it.
- Parallel ₹6,000 × 2 (different keys) on a ₹10,000 loan → one 201, one 400 `OVER_COLLECTION`, outstanding ₹4,000.00.
- Parallel × 4 with the same key → one 201 and three 200 replays, one receipt, one ₹300 recorded.
- Invariant SQL (overpaid loans, schedule mismatch, closed-but-outstanding, active-but-paid) → 0 rows each.
