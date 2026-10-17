# Deployment guide (Vercel + Render)

```
Browser ──HTTPS──► Vercel (Next.js) ── /api/* rewrite ──► Render web service (Django + gunicorn, Docker)
                                                              │
                                                              └──► Render PostgreSQL
```

The browser only ever talks to the Vercel domain. Next.js forwards `/api/*` to Django, so the httpOnly refresh cookie is first-party and CORS is not needed.

## 1. Push the code to GitHub
The repository root is the project folder (`backend/`, `frontend/`, `render.yaml`, `docs/`). Secrets are never committed (`.env*` is git-ignored; only `*.example` files are tracked).

## 2. Backend + database on Render
1. Render dashboard → **New → Blueprint** → select the GitHub repo. Render reads `render.yaml` and creates `cmrs-db` (PostgreSQL) and `cmrs-api` (Docker web service built from `backend/Dockerfile`).
2. Environment values are set by the blueprint: `DATABASE_URL` (from the database), `DJANGO_SECRET_KEY` (generated), `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS=.onrender.com`, `SETTLEMENT_DELAY_DAYS=2`.
3. In the `cmrs-api` service add:
   - `DEMO_PASSWORD` — the password for all demo users (optional; the default `Cmrs@12345` is public in the README).
   - `CSRF_TRUSTED_ORIGINS` — `https://<your-app>.vercel.app` once you know it (only needed for the Django admin; the JSON API uses bearer tokens).
4. Every deploy runs, before traffic switches: `python manage.py migrate --noinput && python manage.py seed_demo --users-only` (both idempotent). This creates the schema, triggers, sequences, 4 roles, 2 branches and 8 users, and **no** customers or activity.
5. Check: `https://<api>.onrender.com/healthz` → `ok`, `/api/docs/` → Swagger UI.

Free-plan note: the free web service sleeps after inactivity, so the first request can take ~30–60 s; the free database expires after a limited period. Use a paid plan for anything beyond a demo.

## 3. Frontend on Vercel
1. **Add New → Project** → import the repo → set **Root Directory = `frontend`** (framework auto-detects Next.js).
2. Environment variable (Production): `BACKEND_URL = https://<api>.onrender.com` (no trailing slash, server-side only; never `NEXT_PUBLIC_`).
3. Deploy. The rewrites in `frontend/next.config.ts` forward `/api/*` to `BACKEND_URL`.

## 4. Smoke test on the hosted URL
Run the checklist in `docs/phase-7-ship.md`. Quick path with the demo users:
1. `manager_mum` → Customers → New customer (10-digit mobile) → assign `agent_mum1` → New loan (start date ≥ 1 period ago so it is due).
2. `agent_mum1` → Today → Record repayment → Cash Holding → Submit.
3. `manager_mum` → Reconciliation → approve with a different counted amount + reason → Deposits → New deposit.
4. `finance1` → Settlements → Confirm. Check the Dashboard and the lifecycle trace.
5. Browser dev tools → Application → Cookies: `cmrs_refresh` is `HttpOnly` + `Secure`; Local Storage holds no tokens.

## Verified locally before deploying
The backend image was built and run with `DJANGO_DEBUG=false` against an empty PostgreSQL: migrations and the seed ran (and re-ran without duplicates), `check --deploy` clean apart from the optional HSTS-preload note, `/healthz` answers 200 over plain HTTP (platform health check), every other plain-HTTP request gets a 301, requests with `X-Forwarded-Proto: https` work, an unknown `Host` gets 400, login sets `HttpOnly; Secure` cookies and HSTS, and `/api/docs/` + `/api/schema/` load. The frontend also passes `next build` (19 routes, TypeScript clean). Neither has been run on Render/Vercel from this environment: that needs your accounts.

## Operating notes
- Rollback: redeploy the previous commit; migrations are forward-only, so do not roll back across a migration without a plan.
- `reset_activity` refuses to run when `DJANGO_DEBUG` is false (it bypasses the immutability triggers), so it cannot wipe the hosted database.
- In production the application's DB role must not be a superuser (triggers can be disabled by an owner/superuser).
