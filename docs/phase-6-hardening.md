# Phase 6 — Hardening & Edge Cases

Source: `DESIGN.md` §5 (protecting records), §9 (concurrency, business-case matrix), §12, §16, §14 (Phase 6).

## Objective
Close the remaining edge cases and security gaps, polish error/empty states, and run the full manual walkthrough and invariant queries. With no automated tests (D10), this phase is the safety net.

## Scope
**In:** model guards, optional DB trigger, throttling, N+1/query review, error-message polish, accessibility pass, full manual concurrency script, security review of permissions.
**Out:** automated test suite, CI, discrepancy resolution workflow, deposit cancellation (listed as improvements unless time permits).

## Business rules enforced / verified
- Reconciled records are immutable through every path: API (no PATCH/PUT/DELETE on financial models → 405), services (state checks), model `save()/delete()` guards, Django admin read-only, optional trigger.
- Optional DB trigger: forbid `UPDATE` of amount/status columns on `APPROVED` submissions and `SETTLED` settlements outside the service path. Be candid in docs if not implemented.
- Every state change writes an audit event in the same transaction; failed operations leave no partial data.
- Lock order is fixed: loan → collections (by id) → submissions (by id) → deposit → settlement.
- Login throttling; 404 for out-of-scope objects (no enumeration); no stack traces or internals in 500 responses.

## Database changes
- Optional trigger migration(s) for immutability.
- Review all CHECK/UNIQUE constraints against DESIGN §7 and add any missing ones.
- Index review via `EXPLAIN` on seeded data.

## Backend tasks
- Add/verify model guards on `Collection`, `CashSubmission`, `CashSubmissionItem`, `BankDeposit`, `Settlement`, `AuditEvent`.
- Make financial models read-only in Django admin.
- DRF throttling on auth endpoints; tighten CORS/CSRF/cookie flags.
- Query review (`select_related`/`prefetch_related`, N+1 on list endpoints and dashboard).
- Standardise error codes and messages across modules; ensure unexpected errors carry `request_id` only.
- Write the throw-away concurrency script (outside the app) hitting repayment, submit, approve, deposit and duplicate-reference paths in parallel.

## APIs
No new endpoints. Verify for every action endpoint: allowed roles, scope, state precondition, idempotency/transaction behaviour and error codes match DESIGN §10.

## Frontend tasks
- Confirm dialogs on approve / reject / settle / void; consistent loading, empty and error states with retry.
- Accessibility pass (labels, focus, contrast, keyboard for dialogs/tables).
- Show server `details` per field; friendly messages for `OVER_COLLECTION`, `POSSIBLE_DUPLICATE`, `DUPLICATE_BANK_REFERENCE`, `INVALID_STATE`.

## Manual verification checklist
- [ ] Role × endpoint walkthrough: every role tries every action; results match the permission matrix (401/403/404).
- [ ] Parallel script: ₹6,000 ×2 on ₹10,000 loan → one success; same collection in two submissions → one success; double approve → one wins; two deposits on one submission → one wins; two deposits with same reference → one 409.
- [ ] Idempotency: same key replay, same key different amount, parallel same key → one row.
- [ ] Rollback: temporarily force an exception after partial writes in submit/approve/deposit → nothing persisted.
- [ ] Attempt to change an APPROVED submission's `received_amount` via API (405), shell/model (guard error) and admin (read-only); if trigger enabled, via raw SQL (rejected).
- [ ] Settled ₹48,500 cannot be edited; FAILED → SETTLED works once.
- [ ] 500 response contains only `code`, generic message, `request_id`.
- [ ] Login throttle triggers after repeated failures.
- [ ] All eight invariant queries from DESIGN §12 → 0 rows after the full walkthrough.

## Dependencies
Phase 5.

## Definition of done
Manual checklist from DESIGN §12 passes end to end; invariant queries return 0 rows; no write path to financial state exists outside services; UI states are consistent.

## Status
- [x] Model guards (`Collection`, `CashSubmission`, `CashSubmissionItem`, `BankDeposit`, `Settlement`, `AuditEvent`) + Django admin read-only for all financial models (`apps/common/admin.py:ReadOnlyAdmin`)
- [x] **DB immutability triggers: implemented** (`apps/integrity`, migration `0001_immutability_triggers`)
- [x] Throttling (login 10/min, refresh 60/min, per-user 600/min) + security settings review (`check --deploy` clean except the optional HSTS-preload note) + Next.js security headers
- [x] Query/N+1 review (`scripts/query_counts.py`) and explicit ordering on annotated querysets (found: `GROUP BY` dropped `Meta.ordering`, making pagination unstable)
- [x] Error codes/messages standardised: JSON 404 for any `/api/` path, JSON 500 with only `code`/`message`/`request_id`; frontend `ApiError.userMessage` maps the key codes
- [x] Verification scripts in `backend/scripts/`: `role_matrix.py`, `concurrency_check.py`, `rollback_check.py`, `query_counts.py`
- [x] Frontend: shared accessible `Modal` (labelled, Escape, focus in/trap/restore), `ReasonDialog` for void/reject/fail, error and not-found pages, table header scopes, skip link, `aria-current`, focus ring, darker placeholder/muted contrast
- [x] Full manual walkthrough + invariant queries passed (results below); in-browser click-through still to do by a human (no browser available in this environment)

## What the triggers enforce (and what they do not)
Every write path other than the service layer is refused by PostgreSQL itself (raw SQL, `QuerySet.update()`, shell, admin): `ERRCODE 23000` → `IntegrityError`.
| Table | Rule |
|---|---|
| `collections` | only `VALID → VOIDED`; amount/loan/agent/receipt/etc. never change; voided is final; no delete |
| `cash_submissions` | identity and `expected_amount` never change; `APPROVED`/`REJECTED` final, except an approved row may receive its `deposit_id` once; no delete |
| `cash_submission_items` | link and amount fixed; `is_active` only `true → false`; no delete |
| `bank_deposits` | no update, no delete |
| `settlements` | `PENDING → SETTLED/FAILED`, `FAILED → SETTLED`; `SETTLED` final; deposit link fixed; no delete |
| `loans` | principal, total, count, frequency, start date, customer fixed; only `status` changes; no delete |
| `installments`, `audit_events` | no update, no delete |

Limits, stated plainly: a database **owner/superuser can disable triggers** (that is how `reset_activity` works, and it refuses to run unless `DEBUG` is on); customers, users and branches are deliberately not frozen; the application's DB role in production should not be a superuser. These triggers make accidental or casual tampering impossible and deliberate tampering require privileged DDL, they are not a substitute for restricting DB credentials.

`python manage.py reset_activity` (DEV ONLY) wipes collections/submissions/deposits/settlements and their audit events, reopens loans and drops extra loans beyond each customer's first. Re-seed with `python manage.py seed_demo --with-activity`.

## Bugs found by this phase
1. **Same-key submit race returned 409 instead of replaying** (`submit_cash` re-checked the idempotency key only before the transaction). Fixed: replay is re-checked after the collection locks are taken, as `record_repayment` already did. Found by `concurrency_check.py`.
2. **Unstable pagination** on annotated list endpoints (loans, submissions, deposits): fixed with explicit `order_by("-id")`.
3. **Swagger generation warnings** from scoped `get_queryset()` with an anonymous user: fixed; schema now generates with zero warnings.
4. DRF renders `Decimal` as a float for non-serializer responses (fixed in Phase 5, covered by the renderer).

## Known limits (honest list)
- `/dashboard/branch-summary/` runs about 11 queries per agent (≈70 for 2 branches / 4 agents). Fine at this scale; at hundreds of agents it should become one grouped query or a materialised view.
- Discrepancy resolution and deposit cancellation workflows are not implemented (listed as improvements).
- No automated test suite or CI (decision D10): regression safety is the four scripts above plus the DB triggers/constraints.
- All UI checks so far are type/lint/page-load smoke tests; a human click-through is still needed.

## Verification results (run 2026-10-17)
- **Role × endpoint matrix** (`role_matrix.py`): 45 endpoints × 5 roles + anonymous. Every disallowed role got exactly 403, every allowed role passed the role gate, anonymous got 401, PATCH/DELETE on financial models → 405. **45 passed, 0 failed.**
- **Parallel script** (`concurrency_check.py`): over-collection race (one 201, one `OVER_COLLECTION`, outstanding ₹4,000.00); same key ×4 (one 201 + three 200 replays, one receipt); same key different amount → 422; double submit (one 409 `ALREADY_SUBMITTED`); same-key submit ×3 (one submission); void vs submit (exactly one wins); double approve (one 200, one 409, stored result equals the winner); approve vs reject (one wins); two deposits on one submission (one `SUBMISSION_NOT_ELIGIBLE`); same bank reference with case variant (one `DUPLICATE_BANK_REFERENCE`, losing submission left deposit-free); double confirm (one 409); confirm vs fail (consistent final state); SQL invariants 0. **17 passed, 0 failed.**
- **Rollback** (`rollback_check.py`): audit write forced to fail at the end of record_repayment (incl. the one that would close a loan), void, submit, approve, reject, record_deposit, confirm and fail settlement → no rows changed, loans/submissions/settlements unchanged. **9 passed, 0 failed.**
- **Immutability attempts:** API PATCH/PUT/DELETE → 405; model `save()`/`delete()` → `*_IMMUTABLE`; `QuerySet.update/delete` → `IntegrityError` from the trigger; raw SQL attacks on all tables above (amount, status, deposit re-pointing, re-activating items, settled → failed, failed → pending, audit update/delete, loan terms, installments, deletes) all blocked; legitimate void and loan close/reopen allowed; admin (even superuser) can list but add/change/delete → 403.
- **500 / 404:** a forced internal error returned only `code`, `details`, `message`, `request_id` with no exception text or stack trace; unknown `/api/…` paths return the JSON envelope.
- **Login throttle:** after repeated attempts `429 THROTTLED` with a `wait` value.
- **Query review:** list endpoints do not grow with page size; no N+1 detected.
- **Regression:** the Phase 2, 3 and 4 manual scripts re-run against the trigger-protected database with identical results; the Phase 5 dashboard still matches hand-computed numbers.
- **Invariants:** all eight from DESIGN §12 plus extra consistency checks → 0 rows, both after the parallel storm and on freshly reseeded data.
