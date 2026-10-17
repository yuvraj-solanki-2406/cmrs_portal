# Phase 7 — Ship: Deployment, Documentation & Video

Source: `DESIGN.md` §4 (deliverables), §13, §14 (Phase 7), §17.

## Objective
Publicly hosted, documented application plus a GitHub repository and a ≤5-minute explanation video meeting every submission requirement.

## Scope
**In:** production settings, Dockerfile, hosting of frontend/backend/database, seed data, README, API docs, test credentials, video.
**Out:** CI/CD pipelines (decision D10), payment-gateway sandbox (optional, only if time remains).

## Business rules / non-functional requirements
- No secrets in the repo; `DEBUG=False`; HTTPS; secure cookies (`Secure`, httpOnly refresh); HSTS and SSL redirect.
- Same-origin proxy (`/api/*` rewrite) so cookies work across hosted domains.
- Migrations run on release; `receipt_seq` and constraints created by migrations; `seed_demo` is idempotent.
- Money remains `Decimal`/`NUMERIC`; JSON amounts remain strings.

## Database / deployment changes
- Managed PostgreSQL (Render/Railway/Fly/Neon); `DATABASE_URL` supplied via env.
- Run `migrate` + `seed_demo` as release/start step; backups per provider defaults.

## Backend tasks
- Production Dockerfile (gunicorn, WhiteNoise for static); `/healthz`.
- Env vars: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_HOURS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` (if not proxying), `SETTLEMENT_DELAY_DAYS`, `SENTRY_DSN` (optional).
- Structured logging with request-id; Swagger at `/api/docs/`, schema at `/api/schema/`.
- Seed realistic demo data covering normal, discrepancy, rejected, deposit-mismatch, failed and delayed-settlement cases.

## APIs
No new endpoints. Confirm `/healthz`, `/api/docs/`, `/api/schema/` reachable in production.

## Frontend tasks
- Deploy Next.js (Vercel/Netlify) with `BACKEND_URL` server env and rewrites; no secrets in `NEXT_PUBLIC_*`.
- Production smoke test of every role's main journey.

## Documentation tasks
- **README** (required): overview, architecture diagram, setup (docker-compose + manual), env var table, DB schema/ER diagram, API docs link, assumptions (A1–A13), hosted URL, **test credentials for each role** (agent, branch manager, finance, admin), known limitations, improvements (including "no automated tests").
- Keep `docs/DESIGN.md` and phase docs as the design record; export diagrams if needed.
- **Video (≤ 5 min)** outline: problem & two lifecycles (0:30) · architecture & tech choices (0:45) · database design incl. derived balances and constraints (1:00) · live demo: repayment → submission with ₹1,500 discrepancy → approval → deposit → settlement, plus a rejected submission (1:30) · business rules & concurrency (0:45) · trade-offs, challenges, improvements (0:30).

## Manual verification checklist (on the hosted URL)
- [ ] Public URL loads; login works for all four roles using README credentials.
- [ ] Agent records ₹3,000 repayment → receipt issued; replaying the request does not duplicate it.
- [ ] Agent submits ₹50,000; manager approves at ₹48,500 with reason → discrepancy ₹1,500.
- [ ] Manager deposits ₹48,500 (unique ref); same reference again → 409.
- [ ] Finance confirms settlement; dashboard figures match; lifecycle trace shows the full chain.
- [ ] Cookies are `Secure` + httpOnly; no tokens in localStorage; HTTP redirects to HTTPS.
- [ ] `/api/docs/` loads; `/healthz` returns OK.
- [ ] Fresh clone follows README setup successfully (docker-compose).
- [ ] Submission checklist complete: GitHub repo (code, README, setup, env docs, schema info, API docs), hosted URL, credentials in README, video ≤ 5 min covering all ten required topics.

## Dependencies
Phase 6.

## Definition of done
Public URL works with seeded credentials per role; README complete; OpenAPI published; repository pushed to GitHub; video recorded within 5 minutes.

## Status
- [x] Production settings + Dockerfile (PORT-aware gunicorn, `/healthz` exempt from SSL redirect, Render host auto-allowed, `seed_demo --users-only`, `DEMO_PASSWORD`); verified locally with `DEBUG=false` on an empty Postgres
- [x] Render blueprint `render.yaml` (DB + API, `preDeployCommand` = migrate + users-only seed) — **needs you to create it on Render**
- [ ] Backend deployed (`/healthz`, `/api/docs/`)
- [ ] Frontend deployed with `/api` rewrite
- [ ] Seed data covers all edge cases
- [x] README with env vars, credentials, deployment section (hosted URL placeholder; ER diagram/assumption list still to add)
- [ ] Hosted smoke test passed
- [ ] GitHub repo pushed
- [ ] Video recorded (≤ 5 min)
- [ ] (Optional) Payment-gateway sandbox
