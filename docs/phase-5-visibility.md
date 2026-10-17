# Phase 5 — Visibility: Dashboards, Reports & Lifecycle Trace

Source: `DESIGN.md` §6 (reporting, audit), §10, §11 (KPI definitions), §14 (Phase 5).

## Objective
Role-appropriate dashboards with all required metrics and filters, plus traceability from any receipt, submission or deposit to its full chain.

## Scope
**In:** dashboard summary, branch summary, discrepancy and mismatch reports, lifecycle trace, audit viewer, CSV export, index tuning.
**Out:** materialized views, scheduled reports, charts beyond simple bars/tiles.

## Business rules enforced
- All figures computed on read from ledger tables (no stored balances).
- Scoping: Agent = own, Manager = branch, Finance/Admin = all; filters cannot widen scope.
- KPI definitions (shown in tooltips): *Expected* = Σ `installments.amount_due` due in range; *Collected* = Σ VALID collections; *Held by agents* = valid collections with no active item; *In transit* = Σ SUBMITTED expected; *Received at branch* = Σ `received_amount` of APPROVED; *Deposited* = Σ deposits; *Settled* = Σ `settled_amount` SETTLED; *Outstanding* = Σ loan outstanding; *Discrepancies* = Σ |discrepancy| of APPROVED + count; *Gaps* = Σ deposit/settlement variance.
- Funnel consistency: stage amounts use actual cash (submission `received_amount`), not collection amounts.

## Database changes
No new tables. Add/tune indexes based on dashboard queries (e.g. `cash_submissions(status, reviewed_at)`, `bank_deposits(deposit_date)`, `settlements(status)`); verify with `EXPLAIN` on seeded data.

## Backend tasks
- `reporting/selectors.py`: aggregate queries using `SUM(...) FILTER (...)` / `GROUP BY`; filter parser (date range, branch, agent, status) shared across endpoints.
- Lifecycle trace builder: Receipt/Submission/Deposit → linked chain with actors, amounts, timestamps, audit events.
- Delayed-settlement flag using `SETTLEMENT_DELAY_DAYS`.
- CSV export for lists (collections, submissions, deposits, discrepancies).
- Audit read endpoint with scoping (manager: own branch).

## APIs
| Method + URL | Roles | Txn / idempotent | Validations / errors |
|---|---|---|---|
| `GET /dashboard/summary/` | all (scoped) | read-only | filters `date_from`, `date_to`, `branch`, `agent`, `status`; 400 bad range |
| `GET /dashboard/branch-summary/` | MANAGER, FINANCE, ADMIN | read-only | per-branch/agent breakdown |
| `GET /reports/discrepancies/` | MANAGER, FINANCE, ADMIN | read-only | shortfalls/surpluses with reasons |
| `GET /reports/mismatches/` | MANAGER, FINANCE, ADMIN | read-only | deposit vs reconciled, settled vs deposit |
| `GET /reports/lifecycle/{type}/{id}/` | scoped | read-only | `type` ∈ collection/submission/deposit; 404 out of scope |
| `GET /audit-events/` | MANAGER (branch), FINANCE, ADMIN | read-only | `entity_type`, `entity_id` |
| `GET .../export.csv` | scoped | read-only | same filters as list |

## Frontend tasks
- Role-specific dashboards: KPI tiles (8 metrics), funnel (Expected → Collected → Branch Received → Deposited → Settled), filter bar (date range, branch, agent, status) synced to URL.
- Branch summary table; discrepancy and mismatch report pages; delayed-settlement badge/filter.
- Lifecycle trace timeline page (Receipt → Submission → Deposit → Settlement); admin/finance audit log viewer.
- Loading/empty/error states on every widget; CSV download buttons.

## Manual verification checklist
- [ ] Seed: Branch A — agent collects ₹50,000, submission approved at ₹48,500, deposited ₹48,500, settled ₹48,500. Dashboard shows Collected 50,000 · Received 48,500 · Deposited 48,500 · Settled 48,500 · Discrepancy 1,500.
- [ ] Add a pending submission of ₹10,000 → "In transit" ₹10,000; "Held by agents" unchanged.
- [ ] Hand-compute Outstanding for 3 loans and compare to dashboard.
- [ ] Filters by branch/agent/date/status change numbers correctly; manager cannot widen to another branch.
- [ ] Lifecycle trace from a receipt shows all linked submission/deposit/settlement records and audit events.
- [ ] Deposit ₹48,000 vs reconciled ₹48,500 appears in mismatch report.
- [ ] CSV export row count matches list count.
- [ ] Run all eight invariant queries from DESIGN §12 → 0 rows.

## Dependencies
Phase 4 (full lifecycle data).

## Definition of done
All 8 required metrics and 4 filters are correct against hand-computed seed data; funnel is consistent; trace works from receipt, submission and deposit.

## Status
- [x] Filter parser + aggregate selectors (`apps/reporting`: filters never widen scope, out-of-scope branch/agent → 403 `FILTER_OUT_OF_SCOPE`; each metric uses its own event date)
- [x] Dashboard + branch summary APIs (`/dashboard/summary/`, `/dashboard/records/` for the stage drill-down, `/dashboard/branch-summary/`)
- [x] Discrepancy / mismatch reports (`/reports/discrepancies/`, `/reports/mismatches/`: deposit≠reconciled, settled≠deposit, failed, delayed)
- [x] Lifecycle trace API (`/reports/lifecycle/{collection|submission|deposit}/{id}/`; agents get a limited deposit view)
- [x] Audit viewer endpoint (existing `/audit-events/`, manager scoped to branch) + page
- [x] CSV export (collections, submissions, deposits, discrepancies, mismatches; formula-injection guard)
- [x] Dashboards, filters (URL-synced), trace timeline, audit UI, CSV buttons; lint, tsc and page smoke tests pass
- [x] Index tuning (`EXPLAIN`): `cash_sub_status_reviewed_idx`, `deposits_date_idx`, `settlements_status_settled_idx`
- [x] Manual checklist (API) passed; in-browser click-through still to do

## Design notes
- **"Status" filter** is the cash-pipeline stage (Collected / Held / In transit / Received at branch / Deposited / Settled); choosing one lists the underlying records. The assignment does not define "status" for the dashboard, so this is an assumption.
- **Agent attribution:** deposits are branch-level. For an agent (or an agent filter) *Deposited* / *Settled* are that agent's approved cash whose submission was banked / whose deposit settled (`attribution: "submission"`). Branch/finance views sum the deposits themselves.
- **Date semantics:** Expected = installment due date; Collected = collection date; In transit = submitted time; Received & discrepancy = review time; Deposited = deposit date; Settled = settlement date; Outstanding is current (not date-filtered). With no date range, Expected means "due up to today".
- Date ranges on timestamp columns are converted to `[start, next-day)` ranges so the column indexes are usable.
- All money in raw-dict responses is rendered as strings by `MoneySafeJSONRenderer` (DRF's default turns Decimal into float for non-serializer data; caught during this phase).
- `/agents/` is now readable by FINANCE (filter dropdowns).
- `seed_demo --with-activity` builds a hand-checkable lifecycle through the real services.

## Verification results (API, seeded with `seed_demo --with-activity`)
Hand-computed vs dashboard (finance, no filters): Expected 15,800 · Collected 36,000 · Held 4,300 · In transit 7,500 · Received 23,700 · Deposited 23,500 · Settled 14,500 · Outstanding 117,500 · Discrepancy 500 (1 case) · Deposit variance 200 · Delayed 1 · Pending settlement 6,000. All matched exactly, and collected = held + (submitted live) holds.
- Manager Mumbai: collected 24,800 · held 2,300 · in transit 7,500 · received 14,500; manager Delhi: collected 11,200 · received 9,200 · deposited 9,000 · delayed 1. Agent `agent_mum1`: collected 16,500 · received 14,500 · settled 14,500 · shortfall 500.
- Scope: manager `?branch=` another branch → 403; agent `?agent=` another → 403; bad date range → 400; `stage` missing/invalid → 400.
- Date semantics: "yesterday" shows only the deposit dated yesterday (14,500); "today" shows collected/received/settled and no deposits.
- Reports: discrepancy report 1 row (₹15,000 vs ₹14,500); mismatch report: deposit ₹6,000 vs ₹6,200 (−200), failed ₹3,000, delayed ₹6,000; Mumbai manager sees none, Delhi manager sees 3.
- Trace: submission chain (5 collections → submission → deposit → settlement with 9 audit events); other agent / other-branch manager → 404; agent hitting a deposit trace → 404; an agent tracing their own collection sees no deposit amounts.
- CSV row counts equal list counts for collections (13), submissions (5), deposits (3); filters and scope apply; agent → 403 on deposits CSV; formula-injection cells are prefixed, negative numbers untouched.
- Audit: manager sees only own-branch events; agent → 403.
- Invariant SQL (all eight from DESIGN §12 plus two extra consistency checks) → 0 rows each.
