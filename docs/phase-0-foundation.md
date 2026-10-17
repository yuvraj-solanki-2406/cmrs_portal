# Phase 0 — Foundation

Source: `DESIGN.md` §5, §6, §7 (roles/users/branches/audit), §10, §11, §14 (Phase 0), §17.

## Objective
Repo, tooling and an authenticated, role-aware skeleton (backend + frontend) that runs with one command and can be deployed early.

## Scope
**In:** repo layout, docker-compose, Django project, `common` / `accounts` / `audit` apps, JWT auth with httpOnly refresh cookie, permission classes, branch-scoping mixin, error envelope, request-id logging, drf-spectacular, `seed_demo`, Next.js login + role-aware shell + `/api` rewrite.
**Out:** any lending/collection/cash logic, dashboards, automated tests, CI (decisions D10).

## Repo layout
```
task/
  backend/   (manage.py, config/, common/, accounts/, audit/)
  frontend/  (Next.js App Router, TypeScript, Tailwind)
  docs/
  docker-compose.yml   # postgres + api
  .env.example  .gitignore  README.md (stub)
```

## Business rules enforced
- Agent and Branch Manager must belong to a branch; Finance/Admin have no branch (service-layer check, cross-table).
- Deactivated users cannot log in. Admin cannot perform financial actions (enforced later via permission classes defined now).
- Audit events are append-only (model forbids updating an existing row; no update/delete endpoints).

## Database changes
| Table | Notes |
|---|---|
| `branches` | `code` UQ, `name`, `is_active` |
| `roles` | `code` UQ (`AGENT`,`BRANCH_MANAGER`,`FINANCE`,`ADMIN`), `name`, `description`; seeded via data migration |
| `users` | custom `AbstractUser`; `role_id` FK→roles NOT NULL (PROTECT); `branch_id` FK→branches nullable; index `(branch_id, role_id)`; **create before first migration** (`AUTH_USER_MODEL`) |
| `audit_events` | `occurred_at`, `actor_id`, `actor_role`, `action`, `entity_type`, `entity_id`, `before`/`after` JSONB, `reason`, `request_id`, `ip`; indexes `(entity_type, entity_id)`, `(occurred_at)` |

## Backend tasks
- Settings split by env (`DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, JWT lifetimes); `ATOMIC_REQUESTS=False`; timezone `Asia/Kolkata`.
- `common`: `DomainError` hierarchy (`ValidationFailed`, `PermissionDenied`, `NotFound`, `InvalidState`, `Conflict`), DRF exception handler → `{code, message, details, request_id}`, `Money` helpers (Decimal, 2dp), pagination (`page_size ≤ 100`), request-id middleware + structured logging, base permission classes (`HasRole`, role constants).
- `accounts`: Role/User/Branch models; services `create_user`, `deactivate_user`; SimpleJWT login/refresh/logout (access in JSON, rotating refresh in httpOnly Secure SameSite=Lax cookie, blacklist on logout); `GET /auth/me`; `BranchScopedQuerysetMixin`; login throttling.
- `audit`: `record(actor, action, entity, before, after, reason)` helper, read-only admin registration.
- drf-spectacular at `/api/docs/`, `/api/schema/`; `/healthz`.
- `seed_demo` (idempotent): 2 branches, 1 manager each, 2 agents, 1 finance, 1 admin.

## APIs
| Method + URL | Roles | Txn / idempotent | Notes |
|---|---|---|---|
| `POST /api/v1/auth/login/` | public | no | 400 invalid payload, 401 bad credentials / inactive user |
| `POST /api/v1/auth/refresh/` | cookie | no | 401 expired/blacklisted |
| `POST /api/v1/auth/logout/` | authenticated | no | blacklists refresh, clears cookie |
| `GET /api/v1/auth/me/` | authenticated | no | id, name, role code, branch |
| `users/`, `branches/` CRUD | ADMIN | atomic writes | 403 for other roles |
| `GET /api/v1/audit-events/` | FINANCE, ADMIN (manager: own branch later) | no | filters `entity_type`, `entity_id` |

## Frontend tasks
- Next.js + TypeScript + Tailwind/shadcn scaffold; `next.config` rewrite `/api/*` → `BACKEND_URL`.
- `lib/apiClient.ts` (bearer, refresh-on-401 once, error-envelope parsing); `AuthProvider` (access token in memory).
- `middleware.ts` redirects unauthenticated users to `/login`; role route guard.
- Screens: `/login`, `(app)` shell with sidebar built from role, placeholder dashboard per role, 403/404 pages.
- Shared UI stubs: `DataTable`, `StatusBadge`, `MoneyText`, `ConfirmDialog`, `EmptyState`, `ErrorState`.

## Manual verification checklist
- [ ] `docker compose up` starts Postgres + API; migrations apply; `seed_demo` runs twice without duplicates.
- [ ] Login as each of the 4 seeded roles succeeds; wrong password → 401 with envelope; deactivated user → 401.
- [ ] Refresh token is httpOnly (not visible to JS); access token not in localStorage; logout invalidates refresh.
- [ ] Agent calling an ADMIN endpoint (`GET /users/`) → 403; unauthenticated → 401.
- [ ] Create a user with role AGENT and no branch → 400 `VALIDATION_FAILED`.
- [ ] Editing an `audit_events` row via admin/shell is rejected.
- [ ] Swagger loads at `/api/docs/`; each response carries a request id that appears in logs.
- [ ] Frontend: sidebar differs per role; direct URL to another role's page redirects/403s.

## Dependencies
None. (Deploy a "login works" skeleton on a public URL at the end of this phase.)

## Definition of done
- One command brings up DB + API; frontend runs against it.
- All four seeded roles log in through the UI and see role-specific navigation.
- RBAC and scoping primitives exist and are used by the first endpoints.
- Swagger available; README stub lists env vars and seeded credentials.

## Status
- [x] Repo layout, `.env.example`, `.gitignore`, docker-compose
- [x] Django project + settings per env
- [x] `common` (errors, handler, money, pagination, request-id)
- [x] `accounts` (Role, User, Branch, roles data migration)
- [x] JWT login/refresh/logout with httpOnly cookie (+ `cmrs_session` presence cookie for the Next.js `proxy.ts` guard)
- [x] Permission classes + scoping mixin
- [x] `audit` app + `record()`
- [x] drf-spectacular + `/healthz`
- [x] `seed_demo` command
- [x] Next.js scaffold, `/api` rewrite, login, role-aware shell, admin users/branches pages (production build + lint + tsc pass)
- [ ] Skeleton deployed to a public URL (deferred to Phase 7 unless you want it earlier)
- [~] Manual checklist: API/RBAC/cookie/rotation/Docker checks passed via curl; **in-browser click-through of the UI still to be done by you** (browser extension was unavailable)

## Implementation notes
- Next.js 16 renamed `middleware` to `proxy` (`src/proxy.ts`).
- The refresh cookie is scoped to `/api/v1/auth/`, so page routes cannot see it; Django also sets a `cmrs_session` flag cookie (path `/`) used only for the redirect guard.
- Next rewrite needs an explicit `/api/:path*/` rule, otherwise the trailing slash Django requires is dropped.
- Local Postgres runs in Docker on port **5433** (credentials `cmrs/cmrs`) to avoid clashing with a system Postgres.
