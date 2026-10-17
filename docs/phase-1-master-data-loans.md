# Phase 1 — Master Data & Loans

Source: `DESIGN.md` §6 (lending), §7 (customers/loans/installments), §10, §11, §14 (Phase 1).

## Objective
Branch managers can create customers and loans with a generated repayment schedule; anyone authorised can see outstanding amounts; agents see only their assigned customers.

## Scope
**In:** customer and loan CRUD, schedule generation, outstanding calculation, installment status waterfall, agent assignment, repayment-history endpoint (empty until Phase 2).
**Out:** recording repayments (Phase 2), interest accrual, late fees, loan disbursement workflow.

## Business rules enforced
- Customer's assigned agent must belong to the same branch (service-level).
- Loan: `total_payable ≥ principal > 0`, `installment_count > 0`; `total_payable` fixed at creation [A3].
- Schedule: equal installments, last installment absorbs rounding; `Σ amount_due = total_payable` (Decimal, base rounded **down** to paise so the last installment is never smaller; no floats).
- `outstanding = total_payable − Σ(VALID collections)`; never stored.
- Principal/schedule cannot change after the first collection exists.
- Manager acts only within own branch; Agent read-only on assigned customers; out-of-scope objects return 404.

## Database changes
| Table | Key fields / constraints / indexes |
|---|---|
| `customers` | `customer_code` UQ, `branch_id`, `assigned_agent_id` (nullable), `is_active`; indexes `(assigned_agent_id)`, `(branch_id)` |
| `loans` | `loan_number` UQ, `customer_id`, `principal`, `total_payable` NUMERIC(14,2), `installment_count`, `frequency` (WEEKLY/MONTHLY), `start_date`, `status` (ACTIVE/CLOSED); CHECK `total_payable >= principal AND principal > 0`, `installment_count > 0`; indexes `(customer_id)`, `(status)` |
| `installments` | `loan_id`, `installment_no`, `due_date`, `amount_due`; UQ `(loan_id, installment_no)`; CHECK `amount_due > 0`; indexes `(due_date)`, `(loan_id, due_date)` |

## Backend tasks
- Models + migrations; `lending/services.py`: `create_customer`, `assign_agent`, `create_loan_with_schedule` (atomic), `get_outstanding(loan)`.
- `lending/selectors.py`: customers visible to user (role/branch/agent scoping), installment statuses via oldest-first waterfall (PAID / PARTIAL / PENDING / OVERDUE).
- Audit events: `CUSTOMER_CREATED`, `AGENT_ASSIGNED`, `LOAN_CREATED`.
- Read-only serializers for computed fields (`outstanding`, `paid`, installment status).

## APIs
| Method + URL | Roles | Txn / idempotent | Validations / errors |
|---|---|---|---|
| `GET/POST /customers/` | MANAGER (branch), ADMIN; AGENT read assigned | POST atomic | 400 agent not in branch; 404 out of scope |
| `GET/PATCH /customers/{id}/` | same | atomic | PATCH excludes `assigned_agent` |
| `POST /customers/{id}/assign-agent/` | MANAGER, ADMIN | atomic + audit | 400 `AGENT_BRANCH_MISMATCH` |
| `GET/POST /loans/` | MANAGER, ADMIN; others read | POST atomic (loan + installments) | 400 amounts; schedule sum check |
| `GET /loans/{id}/` | scoped | no | includes outstanding |
| `GET /loans/{id}/installments/` | scoped | no | status per waterfall |
| `GET /loans/{id}/outstanding/` | scoped | no | `{total_payable, paid, outstanding}` as strings |
| `GET /loans/{id}/repayments/` | scoped | no | empty until Phase 2 |

## Frontend tasks
- Customers list (search, pagination, agent filter) and detail with loans.
- Loan create form (principal, total payable, count, frequency, start date) with schedule preview from the server response.
- Loan detail: outstanding, schedule table with status badges, repayment history placeholder.
- Assign-agent dialog (manager). Agent view: "My customers".

## Manual verification checklist
- [ ] Loan ₹10,000 over 3 installments → ₹3,333.33 / ₹3,333.33 / ₹3,333.34; sum equals ₹10,000.
- [ ] Loan ₹12,000 monthly ×12 → 12 installments of ₹1,000.00 with correct monthly due dates.
- [ ] `outstanding` shows ₹10,000.00 for a new loan; amounts appear as strings in JSON.
- [ ] Manager of Branch A cannot see/modify Branch B customers (404).
- [ ] Assigning an agent from another branch → 400.
- [ ] Agent sees only own customers; cannot POST `/loans/` (403).
- [ ] `total_payable` < `principal` is rejected (400 and DB CHECK).

## Dependencies
Phase 0 (users, roles, branches, scoping, audit).

## Definition of done
Manager creates customer + loan end-to-end in the UI; schedule sums exactly; agent sees only assigned customers; seed data extended with customers and loans for later phases.

## Status
- [x] Models + migrations (customers, loans, installments; `customer_code_seq`, `loan_number_seq` sequences)
- [x] Schedule generation service (`schedule.py`: first due date = start_date + 1 period; monthly dates anchored to start day, clamped to month end)
- [x] Outstanding + waterfall selectors (`paid_total` / `annotate_paid` return 0 until Phase 2 — the only place to change)
- [x] Assign-agent service + audit (`CUSTOMER_CREATED`, `CUSTOMER_UPDATED`, `AGENT_ASSIGNED`, `LOAN_CREATED`)
- [x] Lending APIs + OpenAPI (+ `GET /agents/` for managers/admin, search/ordering filters enabled globally)
- [x] Frontend customers/loans screens (list+filters, detail, assign-agent dialog, loan form with server schedule, loan detail); lint, tsc, build pass
- [x] `seed_demo` extended (8 customers with loans, 4 per branch, 2 per agent)
- [~] Manual checklist: all API checks passed by script (see below); in-browser click-through still to do

## Verification results (API, run 2026-10-17)
- ₹10,000 / 3 monthly from 31 Jan → ₹3,333.33, ₹3,333.33, ₹3,333.34 due 28 Feb, 31 Mar, 30 Apr.
- Seeded ₹12,000 × 12 monthly → 12 × ₹1,000.00, due 3 Nov 2026 … 3 Oct 2027.
- New loan: outstanding ₹10,000.00, amounts are JSON strings.
- Branch B manager: GET Branch A customer → 404; create loan for it → 404.
- Assign agent from another branch → 400 `AGENT_BRANCH_MISMATCH`.
- Agent sees only own 2 customers; agent POST `/loans/` → 403; PATCH loan → 405.
- total_payable < principal → 400 `TOTAL_LT_PRINCIPAL`; direct SQL update also rejected by `loans_total_gte_principal`.
