
# 05_DEPLOYMENT — environments, hosting, CI, fresh-clone verification

Audience: AI agents. Deploy a skeleton on DAY 1 and redeploy daily. People who leave deployment to the last day usually fail to deploy at all, and the live URL is worth 30 marks of reachability.

Free-tier behaviours and limits change. Before relying on any provider-specific behaviour below, check the provider's current documentation and tell the human what you verified.

## 1. Targets

- Database: Neon PostgreSQL (or Supabase). Direct endpoint for migrations, pooled endpoint optional for the app (see Postgres directive section 5).
- Backend: Render web service (Python) or Fly.io. Single uvicorn worker.
- Frontend: Vercel (Next.js).
- Frontend to backend: server-side BFF calls (`API_BASE_URL`). The raw API is also public for judges.

## 2. Environment variables

Backend (Render):

| Var                              | Notes                                              |
| -------------------------------- | -------------------------------------------------- |
| `ENV=prod`                     |                                                    |
| `DATABASE_URL_APP`             | runtime role, `sslmode=require`                  |
| `ALLOWED_ORIGINS`              | the exact Vercel production origin(s), no wildcard |
| `SESSION_TTL_MINUTES`          | e.g. 480                                           |
| `MAX_AMOUNT_PAISE`             | e.g. 10000000000                                   |
| `LLM_ENABLED`, `LLM_API_KEY` | optional                                           |

Migrations and seeding (run by the human from a trusted machine, not by agents against production):

- `DATABASE_URL_OWNER` direct endpoint, `alembic upgrade head`, then `python -m app.seed`.

Frontend (Vercel): `API_BASE_URL` (server-only), `NEXT_PUBLIC_DEMO_MODE` (true for demo credentials panel).

`.env.example` lists every variable with fake values. Real `.env` files are gitignored. Never commit secrets. Run `gitleaks` before the repo becomes public.

## 3. Backend start command

`uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips='*'`
Build: `uv sync --frozen --no-dev` (or pip with a locked requirements file). Health check path: `/health`. Readiness: `/ready`.
Optional `Dockerfile` (multi-stage, non-root user, no dev dependencies) so deployment is reproducible; keep native and Docker instructions both working or document only one.

## 4. Keep-alive and cold starts

- Free web services may sleep after inactivity. Add an external uptime ping or a scheduled GitHub Actions workflow hitting `/health` every ~10 minutes, and say so honestly in the README.
- Clients retry with the SAME idempotency key after timeouts; the system is built for that.
- Before any judging window, hit `/ready` and run a smoke test.

## 5. CI (GitHub Actions)

- Workflow `ci.yml` on push and PR: start a Postgres 16 service container, run migrations as owner, run `make check` (ruff, mypy, bandit, pip-audit, pytest including concurrency tests), frontend `pnpm lint`, `pnpm tsc --noEmit`, `pnpm test`.
- Separate scheduled/manual workflow for `scripts/mutation_check.sh` (slower).
- Optional keep-alive workflow `ping.yml` on a cron.
- A red CI is the human's first priority. Do not mask failures.

## 6. Deployment procedure

1. Merge to main only when `make check` is green locally.
2. Backend deploys from main. Frontend deploys from main.
3. The human runs migrations against Neon (direct URL) BEFORE the new backend goes live when a migration is included.
4. Smoke test the deployed system (script `scripts/smoke.sh`): login for each seed role, view an account, deposit, replay the same key (expect identical response), attempt cross-user access (expect denied), call `/audit/verify` (expect clean).
5. Record the commit hash and date of each production deploy in `docs/agent/DEPLOY_LOG.md` (private).

## 7. Fresh-clone verification (run Wednesday and Thursday morning)

1. New empty directory, `git clone` the repo, follow README commands EXACTLY (no extra knowledge).
2. Local: `docker compose up -d db`, create env files from `.env.example`, `make setup`, `make migrate`, `make seed`, `make dev`; open the frontend; log in as each role.
3. `make check` passes on the clean clone.
4. Fix the README until a stranger could do it. Any step that needed unwritten knowledge is a README bug.

## 8. Seed data and credentials

- One account per role is required in the README: admin, holder (two holders exist), auditor. Use demo-only passwords that are never reused elsewhere.
- The seed script is idempotent, and production seed data is created by the human.
- Provide the judges with: live frontend URL, live API base URL, OpenAPI docs URL, curl examples for login and a withdrawal with an idempotency key.

## 9. Operational limits to document honestly

Single region, single database, no HA, free-tier cold starts, single worker, in-memory rate limiting. None of these can create or lose money; they can only reduce availability. State it.

## 10. Release checklist (Thursday)

- [ ] 09:00 final deploy of backend and frontend, migrations applied
- [ ] Smoke test passes; `/audit/verify` clean on production
- [ ] `attack.py` against production passes all scenarios
- [ ] Incognito window: live URL opens and each role can log in
- [ ] README commands verified from a fresh clone
- [ ] `gitleaks` clean; no secrets in history
- [ ] Repo public (only now, per the organiser's rule) and the live URL still works
- [ ] Demo video link works in incognito
- [ ] Form filled, "I am done" ticked by 16:00 (not 17:59)
