
# 08_WORKFLOW_AND_COORDINATION — how to work, together, without breaking things

Audience: AI agents (two agents may work in the same repository, plus the human).

## 1. Roles (default split, the human may change it)

The human tells you at the start of a session which role you hold. If they do not say, ask before starting.

- Agent B (backend role by default): backend builder: migrations, ledger service, auth, API, backend tests, mutation script.
- Agent A (frontend role by default): frontend builder and visual verifier (use the browser/screenshot tools for UI checks), plus adversary reviewer of backend code.
- Rule: the agent that wrote money, auth or migration code never signs off its own review. The other agent reviews it as a hostile judge (file 03) before the human merges.
- Both agents may fix small obvious defects anywhere, but announce them in `.ai/HANDOFF.md`.

## 2. Avoiding collisions

- One feature branch per task: `feat/ledger-post-movement`, `feat/ui-statement`, `fix/idempotency-replay`. Branch from main, open a PR to main (even though solo, PR history shows engineering practice).
- Prefer separate git worktrees if both agents run at once (`git worktree add ../ledgerline-ui feat/ui-statement`).
- File ownership: backend directories belong to Agent B, `frontend/` to Agent A, `docs/` shared. Do not edit the other's area without recording it in HANDOFF.
- Never force-push, never rewrite history, never `git reset --hard` on shared branches, never delete branches you did not create.
- Migrations: only one agent adds a migration at a time. Announce in HANDOFF before creating it. Never edit an applied migration.

## 3. Status files (private, plain markdown)

- `.ai/STATUS.md`: Done / In progress / Blocked / Next, with dates. Update at session end.
- `.ai/HANDOFF.md`: messages to the other agent: decisions made, gotchas, files touched, open questions. Latest on top.
- `.ai/candidates.md`: mistakes and corrections (file 07).
- `.ai/security_findings.md`, `.ai/claims.md`, `.ai/WALKTHROUGH.md`.

## 4. Planning protocol

For any change touching schema, money logic, auth, or the API contract:

1. Write a short plan: goal, files, risks, tests to write first, rollback.
2. Show it to the human and wait for approval.
3. Write the failing test first, show it failing.
4. Implement, show it passing, run `make check`.
5. Update docs (API.md, THREATS.md row, ARCHITECTURE.md if semantics changed).
6. Commit.
   For small safe changes (copy, styling, lint, refactor inside a function with tests), proceed without asking.

## 5. Git conventions

- Conventional commits: `feat(ledger): ...`, `fix(idempotency): ...`, `test(race): ...`, `docs(api): ...`, `chore(ci): ...`, `refactor(auth): ...`.
- Commit at least every logical unit; target 5+ commits per working day. The history must show a week of work.
- Commit message body explains WHY for integrity-related changes.
- Never commit secrets, `.env`, `node_modules`, build output, or `docs/agent/`.
- Never back-date commits or alter timestamps.

## 6. Definition of done (every task)

Types and lint clean; hostile test written first and passing; mutation check updated if a protection was added or changed; API docs and THREATS row updated; no TODOs on money paths; evidence (command output) shown to the human; committed; STATUS updated.

## 7. Explainability for the interview

- Maintain `.ai/WALKTHROUGH.md`: for each of ledger service, idempotency, locking, append-only layers, authorisation, hash chain, BFF auth, a plain-language explanation (what it does, the exact line numbers, the failure it prevents, what happens under two concurrent requests, what happens on retry).
- Include Q&A pairs for the likely interview questions: where is the balance checked and the debit written; are they atomic; what happens when two run at once; what happens when the same request arrives twice; what stops editing a ledger row; what if you are the DB superuser; how deadlocks are avoided; which line stops user X moving user Y's money.
- Include 5 "live change" exercises with solutions: add a per-account daily withdrawal limit; add a new role; add an `overdraft_limit` admin endpoint; change the idempotency retention; add a new refusal reason. Each with the files to touch and the test to add.
- When the human asks you to explain, teach step by step, then ask them to explain it back and correct gaps.

## 8. Engineering quality standards

- Readable over clever. Small functions, clear names, comments for why.
- Errors are handled deliberately: typed app errors, mapped status codes, structured logs, no silent catches.
- No dead code, no commented-out code, no TODO without an issue note in UNFINISHED.md.
- Consistent formatting via ruff/prettier, enforced in CI.
- Dependencies pinned (uv.lock, pnpm-lock.yaml). Every dependency justified.
- Performance is secondary to correctness, but avoid N+1 queries on statements and keep indexes on `(account_id, account_seq)`, `(initiated_by, idempotency_key)`, and foreign keys.

## 9. When to stop and ask the human

- A document conflict, or a rule you think is wrong.
- Any need for a permission broader than the documented grants.
- Any schema, API contract or role-matrix change.
- A failing test you cannot explain after two honest attempts.
- Anything that could touch the deployed database or other people's systems.
- Time pressure making you want to skip a test, a constraint, or a check. Say so; do not skip.

## 10. Prohibited actions

- Disabling, weakening, or deleting tests, constraints, triggers, grants or CI checks to get green.
- Running destructive commands (`DROP`, `TRUNCATE`, `rm -rf`, `git reset --hard`, force-push) without explicit human approval in this session.
- Writing to the production database or production secrets.
- Copying code from other candidates or from public solutions to this challenge.
- Inventing results, test output, benchmarks, or PROMPTS entries.
- Leaving the repository in a state where `make check` is red at the end of a session without telling the human.
