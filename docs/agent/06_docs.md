
# 06_DOCS_AND_SUBMISSION — what to write, how to keep it honest, how to submit

Audience: AI agents. Documentation is 10 marks, but dishonest documentation is grounds for rejection. Every claim must be provable with a command.

## 1. Claims register

Maintain `.ai/claims.md` (private working file): each README/write-up/demo claim, the exact command or test that proves it, and the date last verified. Before the final submission, re-run every proof. Delete any claim that fails.

## 2. Files to produce (committed unless marked private)

| File                                            | Content                                                                                                                                                                                           | Rule                                                                                    |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `README.md`                                   | Overview; live URLs; seed credentials (admin, holder, auditor); architecture and invariants in the human's own words; run from clean clone; tests; links to docs; not-built list; unfinished list | Only features that exist                                                                |
| `docs/ARCHITECTURE.md`                        | Schema, algorithm, roles, decisions and defence                                                                                                                                                   | Keep in sync with code                                                                  |
| `docs/API.md`                                 | For EVERY endpoint: method + path, who may call it, request body, responses, effect on money, idempotency requirements, example curl                                                              | Generated from OpenAPI plus hand-written effect notes; verified by the schemathesis run |
| `THREATS.md`                                  | See THREATS seed; statuses honest                                                                                                                                                                 | Every CLOSED row has a real test and a mutation that kills it                           |
| `PROMPTS.md`                                  | Real entries only (file 07)                                                                                                                                                                       | Written by the human, from `.ai/candidates.md`                                        |
| `docs/MUTATION_REPORT.md`                     | Output of the mutation script                                                                                                                                                                     | Generated                                                                               |
| `docs/UNFINISHED.md`                          | Everything not done, known bugs, accepted risks and why                                                                                                                                           | Honest gaps score; false claims disqualify                                              |
| `docs/DESIGN_DECISIONS.md`                    | Why Postgres, double-entry, locking, idempotency model, hash chain, scope cuts                                                                                                                    | The human's voice; agents draft, human edits                                            |
| `docs/DB_SCHEMA.md` + `backend/migrations/` | Schema reference and setup scripts                                                                                                                                                                | Setup must work from a clean clone                                                      |
| `.ai/WALKTHROUGH.md` (private)                | Study notes for the interview                                                                                                                                                                     | See file 08                                                                             |

## 3. README structure

1. What it is (3 sentences) and the three laws: books balance, exactly once, provable history.
2. Live demo: frontend URL, API URL, docs URL, demo credentials table (role, email, password), what each role can do.
3. Try the attacks yourself: curl examples for a withdrawal with an `Idempotency-Key`, replaying it, a cross-user attempt, and `/audit/verify`.
4. Architecture in brief: ledger model, atomicity and isolation, idempotency, tamper-proofing, authorisation (link to ARCHITECTURE.md).
5. Running locally from a clean clone: exact commands.
6. Tests: commands, what each file proves, the mutation report, the load-test result.
7. AI usage: tools used, where AI was wrong (link PROMPTS.md).
8. Not built (with reasons) and unfinished (link UNFINISHED.md).
   Rules: no marketing claims, no unmeasured numbers, no screenshots of features that do not exist.

## 4. Short write-up (the challenge asks for it)

Sections: what was built; what was deliberately not built and why; the integrity and concurrency model in the human's own words (lock, check, debit, commit; idempotency claim; refusals as records; append-only layers); how AI was used and where it was wrong; what is unfinished. 600 to 900 words. Agents draft from the claims register; the human rewrites in their own voice and must be able to defend every sentence.

## 5. The six form questions (mapping)

1. Problem solved: three-law summary in plain words.
2. What works now: copy from the claims register, with test names and counts.
3. How to run: the exact README commands, verified from a fresh clone.
4. AI tools used: list tools, models, and for what (planning, code, review, tests).
5. What the AI got wrong (25 of 100 marks per the instructions): the specific bugs and rejected approaches, from PROMPTS.md. Name the bug it introduced, the approach rejected, and what the human did instead.
6. Not finished: from UNFINISHED.md, specific and honest.

## 6. Demo video (5 minutes)

Follow the script in `docs/agent/BUILD_PLAN.md`. Rules: record against the deployed system; show only things that work; narrate the lock, the idempotency claim, and the hash-chain verify; show a real parallel-attack result and the replay log rows; show the tamper-detection moment; end with what is unfinished. Upload so it plays in an incognito window.

## 7. Repository hygiene

- History across the week: small commits with conventional messages. Never rewrite or squash history, never back-date. If a mistake is committed (secret, large file), fix forward and rotate the secret.
- `.gitignore`: env files, `node_modules`, `__pycache__`, `.venv`, build outputs, agent-private docs (`docs/agent/`).
- No secrets, no real personal data. Run `gitleaks` before going public.
- Repository must be PUBLIC at submission time. The organiser asks candidates not to publish before the deadline; make it public on Thursday morning and keep the live URL working. If anything is unclear the human should ask their placement cell.
- Include a LICENSE only if the human wants one (not required).

## 8. Final submission checklist

- [ ] Profile on the hiring site complete (human)
- [ ] Repo public, history spans the week
- [ ] Live URL works in incognito for a stranger, seed credentials for admin/holder/auditor in README
- [ ] THREATS.md, PROMPTS.md (5+ dated entries, at least two on money/idempotency and two on authorisation/audit trail, each with commit links), tests, schema and setup scripts, API docs, write-up, demo video link
- [ ] All six form boxes filled from verified material
- [ ] "I am done" ticked before Thursday 18:00 IST (aim for 16:00)
