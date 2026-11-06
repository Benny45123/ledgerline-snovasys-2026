
# 03_SECURITY — threat hunting and hardening procedure

Audience: AI agents, especially whichever agent is acting as the ADVERSARY. Your job is to break this system before the judges do, honestly report what you find, and never pretend a hole is closed.

## 1. Scope and safety rules

- Attack only: localhost, the test database, and the human's own deployment, and only when the human says the deployed target may be attacked.
- Never attack the organiser's site, other candidates, or any third party. Never scan the internet. Never exfiltrate secrets.
- Never run destructive commands against a deployed database. Attack scripts must create their own users/accounts and tolerate a shared deployment.
- Keep attack code in `scripts/attack/`. It is a legitimate part of the submission (shows threat thinking) and must be clean and documented.

## 2. Adversary procedure (run after every milestone)

1. Read only `backend/app`, `backend/migrations` and the API docs. List every route, every table, every trust boundary.
2. For each route, ask: who can call it, what does it do to money, what if called twice, what if called concurrently, what if the body is malformed, what if the IDs belong to someone else?
3. For each table: who can write, who can update/delete, what constraint keeps it honest?
4. Produce findings as rows: `ID | attack (exact request or SQL) | result on current code | which test covers it | verdict (BLOCKED / VULNERABLE / UNTESTED)`.
5. Anything VULNERABLE: report to the human immediately with a proposed fix and a failing test. Anything UNTESTED: write the test.
6. Add every new threat to THREATS.md with an honest status.

## 3. Hostile checklist (must all be attempted and recorded)

### Money and concurrency

- 20 to 50 parallel withdrawals larger than the combined balance: exact success count, no 5xx, final balance right.
- Parallel transfers from one source to many destinations, and many sources to one destination.
- Opposite transfers A to B and B to A in tight loops (deadlock hunt).
- Deposit and withdraw racing on the same account.
- Amount abuse: 0, -1, 1.5, "100", true, null, 1e3, huge ints, 2^63, strings with unicode digits, missing field, extra fields.
- Source equals destination. Unknown destination. Frozen/closed accounts. Currency fields supplied by client.
- Crash injection: force an exception after the debit insert and before commit; verify nothing persisted and the key is reusable.
- Lock timeout: hold a lock in another connection; the API must return 503 without partial effects.

### Exactly once

- Same key sequentially, simultaneously (50 parallel), after server restart, after a refusal, with different body, with different user (must not collide), with key of edge-case lengths/characters, with missing key.
- Prove duplicates in data: `idempotency_replays` rows exist, exactly one journal exists.

### Authorisation

- For every account-scoped route, use holder2's token on holder1's account ids (IDOR). Expected: 404 or 403 as designed, no side effects, a security event recorded.
- Mass assignment: send `user_id`, `role`, `owner_id`, `balance`, `status` in bodies. Must be rejected.
- Auditor token on every write route. Holder token on admin routes. No token and malformed tokens on everything.
- Expired and revoked tokens. Token reuse after logout. Token from another environment.
- Admin cannot spend a holder's money except through logged adjustments.
- HTTP verb tunnelling, trailing-slash and case variations of routes, double-encoded path segments.

### Ledger integrity

- As the runtime role: UPDATE, DELETE, TRUNCATE, DROP, ALTER, GRANT on ledger tables must fail.
- As owner in a TEST database: edit a ledger row, delete a row, reorder rows; `/audit/verify` must report the discrepancy and name the account and sequence.
- Balance cache edited directly: verify and the deferred trigger must catch it.
- Insert an unbalanced journal: commit must fail.
- Sequence gaps or duplicate `account_seq`: must be impossible/detected.

### Application and platform

- SQL injection in every string field (memo, names, account numbers, query params), including second-order cases.
- Oversized body, wrong content type, deeply nested JSON, invalid UTF-8, huge headers.
- Error shape leaks: stack traces, SQL text, internal ids, framework versions.
- CORS: preflight from an untrusted origin must not be allowed. CSRF against the BFF: cross-origin form POST must be rejected.
- Rate limiting and login brute force behaviour; confirm no hard lockout of seeded users.
- Dependency audit (`pip-audit`, `npm audit`), secret scan (`gitleaks`), static analysis (`bandit`, optionally `semgrep`).
- Docs endpoints (`/docs`, `/openapi.json`): decide deliberately (keeping them is fine and useful for judges; ensure they leak nothing sensitive) and record the decision.

### AI feature

- Prompt injection through memo; verify the LLM output cannot trigger any write; verify the review module cannot import the posting service.

## 4. Secure coding rules (apply when writing code too)

- Parameterised SQL only. No string-built SQL, no f-strings with user data.
- Validate at the edge (Pydantic strict), validate again in the service.
- Principle of least privilege: runtime DB role, no owner rights, read-only inspection roles for agents.
- Defence in depth for each invariant: code check + DB constraint + test + mutation check.
- Constant-time comparison for secrets; random tokens from `secrets`; never `random`.
- Do not log secrets, tokens, passwords, full account numbers or request bodies on sensitive routes.
- Fail closed: if authorisation cannot be determined, deny.
- Time and ordering come from the database (`now()`, sequences, triggers), not from the client.

## 5. Reporting

- Maintain `.ai/security_findings.md` with dated findings, reproduction commands, status.
- Tell the human plainly about anything you could not close and why. Honest "still open under condition X" is worth marks; claiming closed when it is not is worth none and the judges will find it.
- When you are unsure whether something is exploitable, write a test that tries to exploit it. If the test cannot be written, say so.
