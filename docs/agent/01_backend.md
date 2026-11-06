# 01_BACKEND — Python/FastAPI standards for LedgerLine

Audience: AI agents. Read with AGENTS.md, docs/ARCHITECTURE.md and the Postgres directive.

## 1. Layout

```
backend/
  pyproject.toml  uv.lock  alembic.ini  Dockerfile  .env.example
  app/
    main.py            # app factory, middleware, exception handlers, router mounting
    config.py          # pydantic-settings; fail fast on missing/weak secrets
    logging.py         # structlog JSON, request_id binding, redaction
    errors.py          # AppError hierarchy + error codes + handlers
    deps.py            # request_id, current_user, require_role, db session deps
    db/engine.py       # engine + session factory (see Postgres directive)
    auth/              # passwords.py sessions.py throttle.py routes.py schemas.py
    ledger/            # service.py (post_movement ONLY writer), hashing.py, queries.py (read-only), schemas.py, errors.py
    accounts/          # routes.py schemas.py service.py (create, freeze, membership)
    audit/             # routes.py verify.py (hash chain + reconciliation)
    review/            # rules.py narrative.py routes.py (never imports ledger.service)
    seed/              # idempotent seed script using post_movement()
  migrations/          # Alembic
  tests/               # see 04_TESTING.md
```

Layering rules (enforced by an import-linter test):

- Routers are thin: parse input, call a service function, shape output. No SQL in routers.
- Services own transactions. `app.ledger.service.post_movement` is the only code that writes ledger tables or `accounts.balance/next_seq/last_hash`.
- `app.ledger.queries` and other read paths use SELECT only.
- `app.review` must not import `app.ledger.service`.

## 2. Code standards (production bar)

- Python 3.12, full type hints, `mypy --strict` clean on `app/ledger`, `app/auth`, `app/accounts`; `ruff` (lint + format) clean everywhere; `bandit` clean.
- No global mutable state except the engine and settings. No business logic at import time.
- Functions do one thing. Money-path functions are short enough to read top to bottom in one screen. Comment the WHY (lock order, why check after lock), not the what.
- Every public function in `ledger/` and `auth/` has a docstring stating its invariants and failure modes.
- Use `Enum`/`Literal` for kinds, statuses and reason codes. No magic strings scattered around.
- Dependencies: keep few and well known (fastapi, uvicorn, sqlalchemy, psycopg, alembic, pydantic, pydantic-settings, argon2-cffi, structlog, httpx, pytest stack). Ask the human before adding any other.

## 3. Configuration

- `pydantic-settings`, environment only. Required: `DATABASE_URL_APP`, `ENV` (`dev|test|prod`), `SESSION_TTL_MINUTES`, `ALLOWED_ORIGINS`, `MAX_AMOUNT_PAISE`. Optional: `LLM_ENABLED`, `LLM_API_KEY`.
- In `prod`: refuse to start if SSL is not used for the database, if `ALLOWED_ORIGINS` contains `*`, or if debug/docs flags are on that should not be.
- `MAX_AMOUNT_PAISE` default `10_000_000_000` (Rs 10 crore). Keep all balances inside JavaScript's safe integer range so the UI never loses precision. Document the cap.

## 4. API conventions

- JSON only on writes (`Content-Type: application/json`, else 415). Request body limit 16 KB.
- Pydantic request models: `ConfigDict(extra="forbid", strict=True)`.
- IDs are UUIDs; invalid UUID path params return 404 (not 422, not 500) to avoid leaking structure.
- Pagination: keyset (`?limit=50&after=<account_seq>`), `limit` max 200.
- Error envelope for every non-2xx: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`. Never include stack traces, SQL or internal ids.
- Status codes:
  - 200 success (also for idempotent replay, with header `Idempotent-Replayed: true`)
  - 400 missing/invalid `Idempotency-Key`
  - 401 unauthenticated, 403 authenticated but role not allowed for the route
  - 404 unknown OR not-yours account (uniform)
  - 409 refused by business rule: `insufficient_funds`, `account_frozen`, `account_closed`
  - 415 wrong content type, 413 body too large
  - 422 validation errors and `idempotency_key_reuse` (same key, different body) and `invalid_destination`
  - 429 rate limited, 503 lock timeout or pool exhaustion (with `Retry-After`)
  - 500 unexpected (rolled back)
- A refusal (409) is a successful write of a refusal record. Replaying its key returns the same 409.

### Money endpoints (exact contracts)

- `POST /accounts/{id}/deposit`, `POST /accounts/{id}/withdraw`: `{"amount": <int paise>, "memo": <str ≤140, optional>}`.
- `POST /transfers`: `{"from_account_id": <uuid>, "to_account_number": <str>, "amount": <int>, "memo": <optional>}`. Unknown, frozen or closed destination all return the same 422 `invalid_destination` (no enumeration).
- All require `Idempotency-Key`.
- Success body: `{"journal_id", "kind", "amount", "status": "posted", "entry": {"account_id", "account_seq", "amount", "balance_after"}, "created_at"}`. Return ONLY the caller's own account entry. Never return the counterparty's balance.
- Statement item: `{"type": "posting"|"refusal", "account_seq", "at", "kind", "amount", "balance_after" | "balance_at_attempt", "counterparty": "****1234", "initiated_by": {"id","display_name"}, "journal_id"|null, "reason_code"|null, "request_id"}`. Ordered by `account_seq`, so postings and refusals interleave in true order with the running balance.

## 5. AuthN implementation

- Passwords: Argon2id via argon2-cffi with sane parameters; on unknown email still perform a dummy verify to equalise timing.
- Sessions: `secrets.token_urlsafe(32)` returned once on login; only `sha256(token)` stored. TTL 8h, sliding not required. Logout revokes. Compare with `hmac.compare_digest` where comparing secrets.
- `Authorization: Bearer <token>` for API clients (judges will use curl).
- Login throttle: count recent `login_failed` security events by (email) and by (ip); apply progressive delay and 429 beyond thresholds. No permanent lockout (seed users are shared with judges). Every failure and success is a `security_events` row.
- Deploy a single uvicorn worker so in-memory rate limits are coherent; money safety must never depend on rate limits.
- Never log: passwords, tokens, Authorization headers, full request bodies on auth routes.

## 6. AuthZ implementation

- Dependency `require_role("admin")` etc. on every route. Routes without one are a bug (a test enumerates all routes and fails if a route lacks an explicit role declaration or a documented `public` marker).
- Account-scoped routes verify access inside the service using DB state, after the lock for money moves. Deny by default, 404 for unrelated accounts.
- Roles and capabilities: ARCHITECTURE.md section 6. The auditor never gets a write route; the test iterates over every non-GET route as auditor.

## 7. Money-path coding rules (re-stated because they matter most)

- One function writes money: `post_movement()`. It is the exact algorithm in ARCHITECTURE.md section 4.
- Inputs are validated again inside the service (defence in depth): amount int, positive, within cap; accounts distinct for transfers; kinds known.
- No `try/except` that swallows a database error. Catch only the specific errors listed in the Postgres directive, convert them to `AppError`, and let everything else roll back and become 500.
- `created_at` and hashes come from the database (defaults/triggers), not from the client or from Python clocks, so they cannot be forged by request data.
- Never read a balance in one transaction and write in another.

## 8. Health and operations

- `GET /health` (process up, no DB), `GET /ready` (DB reachable, migrations at head, db-check conditions pass). Both unauthenticated and free of internals.
- Structured logs: `request_id`, route, status, duration, user id (never email), error code.
- Startup logs the schema version and the runtime role.

## 9. Seed script

- `python -m app.seed` is idempotent (safe to run twice) and creates: 1 admin, 2 holders (`holder1`, `holder2` so cross-user attacks can be tested), 1 auditor, EXTERNAL and SUSPENSE system accounts, 2 accounts per holder with opening balances posted through `post_movement()` as deposits with deterministic idempotency keys.
- Passwords come from env or are generated and printed once. The README lists demo credentials for deployment (demo data only, never reused elsewhere).
