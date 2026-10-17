# Phase 3 — Cash Submission & Branch Reconciliation

Source: `DESIGN.md` §6 (cash), §7, §8-B/C, §9, §10, §14 (Phase 3).

## Objective
Agents submit collected cash to their branch; branch managers verify the received amount, record discrepancies, and approve or reject.

## Scope
**In:** submit cash, reconciliation (approve with/without discrepancy, reject), resubmission after rejection, pending queue, agent "cash held" view.
**Out:** discrepancy resolution/write-off workflow (improvement), post-approval adjustments.

## Business rules enforced
- Only the agent's own VALID collections with no active submission item can be submitted; at least one item.
- `expected_amount` is server-computed (sum of items), never client-supplied.
- Approve: row-locked, status must be `SUBMITTED`; approver is in same branch and ≠ submitter; `received ≥ 0`; `discrepancy = expected − received` (+ shortfall, − surplus); reason mandatory if discrepancy ≠ 0.
- Approved-with-shortfall: received amount is branch cash; shortfall is an open discrepancy attributed to the agent [A6]; collections remain credited to customers.
- Reject: reason mandatory; items set `is_active=false`, collections return to the agent, who may resubmit as a new submission.
- APPROVED and REJECTED are terminal; no edit endpoints.
- Double submit of the same collection impossible (lock + partial unique index).

## Database changes
| Item | Details |
|---|---|
| `cash_submissions` | `reference_no` UQ, `agent_id`, `branch_id`, `submitted_at`, `status` (SUBMITTED/APPROVED/REJECTED), `expected_amount`, `received_amount`, `discrepancy_amount`, `discrepancy_reason`, `reviewed_by`, `reviewed_at`, `rejection_reason`, `deposit_id` (added in Phase 4), `idempotency_key` |
| `cash_submission_items` | `submission_id`, `collection_id`, `amount` (snapshot), `is_active` |
| Constraints | APPROVED ⇒ received, discrepancy, reviewed_by, reviewed_at NOT NULL and `discrepancy = expected − received`; REJECTED ⇒ rejection_reason NOT NULL, received NULL; discrepancy ≠ 0 ⇒ reason NOT NULL; UQ `(agent_id, idempotency_key)`; **partial UQ `(collection_id) WHERE is_active`** |
| Indexes | `(branch_id, status)`, `(agent_id, submitted_at)`, `(submission_id)` |

## Backend tasks
- `cash/services.py`: `submit_cash` (atomic; lock collections `ORDER BY id`; create submission + items; idempotent), `approve_submission` (lock submission, validations, discrepancy math, audit), `reject_submission` (release items, audit).
- `cash/selectors.py`: collections available to submit, pending queue per branch, agent cash-held totals.
- Model guards: reject updates to terminal submissions outside services.
- Audit: `SUBMISSION_CREATED`, `SUBMISSION_APPROVED`, `SUBMISSION_REJECTED`.

## APIs
| Method + URL | Roles | Txn / idempotent | Validations / errors |
|---|---|---|---|
| `GET /submissions/pending-collections/` | AGENT | no | collections eligible to submit + total |
| `POST /submissions/` | AGENT | atomic + Idempotency-Key + row locks | 400 empty/ineligible ids; 409 `ALREADY_SUBMITTED` |
| `GET /submissions/`, `GET /submissions/{id}/` | AGENT own; MANAGER branch; FINANCE/ADMIN all | no | filters `agent`, `branch`, `status`, dates |
| `POST /submissions/{id}/approve/` | MANAGER | atomic + lock | body `received_amount`, `discrepancy_reason?`; 400 reason required / negative; 403 own submission or other branch; 409 `INVALID_STATE` |
| `POST /submissions/{id}/reject/` | MANAGER | atomic + lock | body `reason`; 400 missing; 409 `INVALID_STATE` |
| `PATCH/PUT/DELETE /submissions/{id}/` | — | not routed (405) | state is changed only via actions |

## Frontend tasks
- Agent: "Cash I'm holding" (selectable collections, running total) → Submit; "My submissions" with status and rejection reason.
- Manager: pending queue → Reconcile screen (expected, counted input, live difference, discrepancy reason, Approve/Reject with confirm dialogs); agent collections view; branch summary stub.
- `StatusBadge` for SUBMITTED / APPROVED / REJECTED; discrepancy highlight.

## Manual verification checklist
- [ ] Agent holds 5 collections totalling ₹50,000 → submission expected ₹50,000.00.
- [ ] Manager approves with received ₹48,500 and no reason → 400; with reason → APPROVED, discrepancy ₹1,500.00.
- [ ] Received ₹51,000 → discrepancy −₹1,000.00 (surplus), reason required.
- [ ] Reject with reason → collections reappear in agent's "cash held"; new submission succeeds; old one stays REJECTED.
- [ ] Re-approve or reject an APPROVED submission → 409; PATCH → 405.
- [ ] Submitting the same collection in two parallel requests → one succeeds, one 409.
- [ ] Manager approving own submission or another branch's → 403/404.
- [ ] Forced failure mid-submit (e.g. temporarily raising after items insert) leaves no submission/items.
- [ ] Voiding a collection in a SUBMITTED submission → 409.
- [ ] Invariant queries 3–5 (DESIGN §12) return 0 rows.

## Dependencies
Phase 2 (collections).

## Definition of done
The ₹50,000 vs ₹48,500 flow works end-to-end through the UI; rejection/resubmission works; approved submissions are immutable; no double-submission possible.

## Status
- [x] Models, constraints, partial unique index (`cash_item_one_active_uq`; CHECKs for approved/rejected field sets, discrepancy arithmetic, reviewer ≠ agent; `submission_seq`)
- [x] `submit_cash` service (collections locked in id order; replay before and after; `IntegrityError` mapped to replay or `ALREADY_SUBMITTED`)
- [x] `approve_submission` / `reject_submission` services (row lock, same-branch manager, never the submitter; reason required for any difference, shortfall or surplus)
- [x] Submission APIs + OpenAPI (`pending-collections`, create, list/detail, approve, reject; PATCH/PUT/DELETE → 405)
- [x] Agent frontend: Cash Holding (select, running total, confirm, per-attempt idempotency key), My Submissions, submission detail with rejection reason
- [x] Manager frontend: Reconciliation queue (default filter SUBMITTED), Reconcile panel with live difference, reason field, Approve/Reject dialogs
- [x] Manual checklist (API) passed; in-browser click-through still to do
- [x] `collections.selectors.is_in_active_submission` now checks `submission_items` (voiding a submitted collection → 409)
- [ ] Phase 4 adds `cash_submissions.deposit_id` (the model guard already allows service-set updates)

## Design notes
- Money-state view for an agent (`pending-collections`): *held* = valid collections with no live item; *in transit* = SUBMITTED expected totals; *open shortfall* = Σ positive discrepancy of APPROVED submissions (resolution workflow is out of scope, assumption A6).
- Manager checks use 404 (not 403) for other branches so records cannot be enumerated; an agent hitting approve gets 403 from the role gate.
- `tsconfig` target raised to ES2020 for BigInt paise math in the reconcile screen (display only; the server is authoritative).

## Verification results (API, run 2026-10-17)
- Five collections ₹10,000 + ₹12,000 + ₹8,000 + ₹15,000 + ₹5,000 → pending ₹50,000.00 → submission expected ₹50,000.00 with 5 items.
- Same key replay → 200 + `Idempotent-Replay`; same key different ids → 422; same ids with a new key → 409 `ALREADY_SUBMITTED`; empty → 400; manager submit → 403; another agent → `INELIGIBLE_COLLECTIONS`.
- Voiding a submitted collection → 409.
- Approve ₹48,500 without reason → 400 `DISCREPANCY_REASON_REQUIRED` (discrepancy 1500.00); with reason → APPROVED, discrepancy ₹1,500.00; negative amount → 400; other-branch manager → 404; agent → 403.
- Re-approve or reject an APPROVED submission → 409 `INVALID_STATE`; PATCH/DELETE → 405.
- Agent position after approval: held 0, open shortfall ₹1,500.00.
- Reject without reason → 400; reject with reason → REJECTED, 3 collections back in Cash Holding, resubmission → 201, old stays REJECTED.
- Surplus ₹6,500 vs ₹6,000 → reason required; approved with discrepancy −₹500.00.
- Parallel double submit of one collection → one 201, one 409 `ALREADY_SUBMITTED`.
- Forced failure after items insert (audit patched to raise) → no submission/items left; the collection stayed submittable.
- Direct SQL attempts to break status/field rules and reviewer = agent → blocked by CHECK constraints; model guard raises `SUBMISSION_IMMUTABLE` on edits.
- Invariant SQL (duplicate active items, expected ≠ Σ items, bad discrepancy, rejected-but-active items) → 0 rows each.
