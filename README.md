# CMRS — Cash Management & Reconciliation System

Tracks loan-repayment cash from customer → agent → branch → bank → company account.
Design: [`docs/DESIGN.md`](docs/DESIGN.md) · Phase plans: `docs/phase-*.md`.

**Stack:** Next.js (TypeScript, Tailwind) · Django + DRF · PostgreSQL · JWT (access in memory, refresh in httpOnly cookie).

## Quick start (local)

```bash
# 1. Database (port 5433) — and optionally the API container
docker compose up -d db

# 2. Backend
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo                 # add --with-activity for a sample cash lifecycle
python manage.py runserver 8000        # Swagger: http://localhost:8000/api/docs/

# 3. Frontend (new terminal)
cd frontend
cp .env.example .env.local
npm install
npm run dev                            # http://localhost:3000
```

Or run DB + API in Docker: `docker compose up --build` (API on :8000, migrations + seed run on start).

## Verification scripts (no automated test suite by design)

With the API running on :8000 and seeded data (`seed_demo --with-activity`):

```bash
cd backend && . .venv/bin/activate
python scripts/role_matrix.py                      # every role x every endpoint vs the permission matrix
python scripts/concurrency_check.py                # parallel races: repayment, submit, approve, deposit, settlement
python manage.py shell < scripts/rollback_check.py # forced failures leave nothing behind
python manage.py shell < scripts/query_counts.py   # list endpoints do not grow per row
python manage.py reset_activity                    # DEV ONLY: wipe demo activity, then: seed_demo --with-activity
```

Financial records are protected in depth: no edit endpoints, service-layer state checks, model guards, read-only Django admin, and PostgreSQL triggers (`apps/integrity`) that refuse updates/deletes outside the legal state transitions. See `docs/phase-6-hardening.md`.

## Test credentials (demo data from `seed_demo`)

All passwords: `Cmrs@12345`

| Role | Username | Branch |
|---|---|---|
| Admin | `admin` | — |
| Finance | `finance1` | — |
| Branch Manager | `manager_mum`, `manager_del` | MUM01, DEL01 |
| Agent | `agent_mum1`, `agent_mum2`, `agent_del1`, `agent_del2` | MUM01 / DEL01 |

## Deployment

Hosted on Vercel (frontend) + Render (API + PostgreSQL). Steps, blueprint and smoke test: [`docs/deployment.md`](docs/deployment.md). Blueprint: [`render.yaml`](render.yaml).

- **Hosted URL:** _to be filled after deploy_
- **API docs (Swagger):** `<api-url>/api/docs/` · **Health:** `<api-url>/healthz`
- The hosted database is seeded with branches and users only (`seed_demo --users-only`); create customers/loans through the UI. Set `DEMO_PASSWORD` on Render to change the demo password (then update the credentials table).

## Environment variables

Backend (`backend/.env`): `DJANGO_DEBUG`, `DJANGO_SECRET_KEY` (required when debug is off), `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `CSRF_TRUSTED_ORIGINS`, `JWT_ACCESS_MINUTES` (15), `JWT_REFRESH_HOURS` (8), `REFRESH_COOKIE_SECURE`, `LOGIN_THROTTLE_RATE` (10/min), `SETTLEMENT_DELAY_DAYS` (2), `LOG_LEVEL`, `DEMO_PASSWORD` (seed only), `PORT`/`WEB_CONCURRENCY` (container), `RENDER_EXTERNAL_HOSTNAME` (set by Render).

Frontend (`frontend/.env.local`): `BACKEND_URL` — server-side target of the `/api/*` proxy.

## Status

Phases 0–6 are implemented and verified through the API: foundation, customers/loans, repayments, cash submission & reconciliation, deposits & settlement, dashboards/reports/trace, and hardening. Phase 7 (deploy & document): deployment config and guide are ready and the production image was verified locally; the hosted deploy, README URL and video need your accounts — see `docs/phase-7-ship.md`.
