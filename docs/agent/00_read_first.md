
# 00_READ_FIRST — entry point for every AI agent on LedgerLine

Audience: any AI coding agent working in this repository. Private working instructions. Never copy this text into committed docs.

## 1. Precedence (highest first)

1. The human's live instruction in this session.
2. `docs/agent/AGENT_POSTGRES_DIRECTIVE.md` (database rules).
3. `AGENTS.md` (invariants, money, idempotency, ledger rules).
4. `docs/ARCHITECTURE.md` (schema, algorithm, roles, API).
5. The numbered files in `docs/agent/` (01 to 08).
6. Your own defaults.
   If two files conflict, stop and ask the human. Do not choose silently.

## 2. Reading order and purpose

| File                                           | Read it when                                                 |
| ---------------------------------------------- | ------------------------------------------------------------ |
| `AGENTS.md`                                  | Always, first                                                |
| `docs/ARCHITECTURE.md`                       | Any schema, ledger, auth or API work                         |
| `docs/agent/AGENT_POSTGRES_DIRECTIVE.md`     | Any database work                                            |
| `docs/agent/01_BACKEND.md`                   | Writing or reviewing Python code                             |
| `docs/agent/02_FRONTEND.md`                  | Any UI work                                                  |
| `docs/agent/03_SECURITY.md`                  | Reviewing, attacking, hardening                              |
| `docs/agent/04_TESTING.md`                   | Writing tests, mutation checks, load tests                   |
| `docs/agent/05_DEPLOYMENT.md`                | Deploying, env vars, CI, fresh-clone checks                  |
| `docs/agent/06_DOCS_AND_SUBMISSION.md`       | README, API docs, write-up, final submission                 |
| `docs/agent/07_AI_FEATURE_AND_HONESTY.md`    | The review/flagging feature, PROMPTS evidence, honesty rules |
| `docs/agent/08_WORKFLOW_AND_COORDINATION.md` | Git, planning, two-agent coordination, status files          |
| `docs/agent/BUILD_PLAN.md`                   | Deciding what to do today                                    |

## 3. Project facts

- Challenge: Snovasys Fresher Hiring Challenge 2026, "LedgerLine, money movement with a ledger you can prove". One human, individual assessment.
- Deadline: Thursday 12 November 2026, 18:00 IST. Code freeze Thursday 12:00. Work started Friday 6 November 2026.
- Stack: Python 3.12 + FastAPI + PostgreSQL 16 backend; Next.js (App Router) + TypeScript strict + Tailwind + shadcn/ui + Framer Motion + three.js (react-three-fiber) frontend.
- Marks: 35 integrity and security, 15 threat thinking (THREATS.md and tests that can fail), 15 functionality (ten requirements), 15 AI usage evidence (PROMPTS.md), 10 engineering quality, 10 documentation, deployment and demo.
- A judge will attack the DEPLOYED system: parallel withdrawals, replayed transfers, cross-user transfers, negative balances via races, ledger tampering. One rupee wrong costs most of the 35.
- Shortlisted candidates are interviewed on their own code and must change it live. The human must be able to explain everything you write.
- Production quality is the bar, not prototype quality. Working code delivered as files, root cause explained when something breaks.

## 4. Competition integrity (non-negotiable)

- The work must be the human's, directed by you. Do not search for, fetch, or reuse other people's solutions to this challenge. Documentation of libraries and frameworks is fine.
- Do not attack anything except localhost and the human's own deployment. Never probe other candidates' or the organiser's systems.
- Never hide AI use. PROMPTS.md and the README disclose the tools and the real mistakes. You do not write PROMPTS.md entries as if they were the human's experience; see file 07.
- Never claim a feature works unless you ran it and saw it work. Never write docs for features that do not exist.

## 5. Session start protocol

1. `git status`, `git log --oneline -10`, read `.ai/STATUS.md` and `.ai/HANDOFF.md` if present.
2. Run `make check` (lint, types, tests). Report the result before starting new work.
3. State today's task in one sentence and the files you expect to touch.

## 6. Session end protocol

1. Run `make check`. Commit with a conventional message (small, focused commits during the session, not one at the end).
2. Update `.ai/STATUS.md` (done, in progress, blocked, next) and `.ai/HANDOFF.md` (anything the other agent must know).
3. If the human corrected you or you found your own mistake, append an entry to `.ai/candidates.md` (format in file 07).
4. Tell the human, in at most six lines: what changed, evidence (command output), risks, next step.

## 7. Talking to the human

- Be concise, direct, and honest. Lead with the result, then evidence.
- When something fails, give the root cause, not just the fix.
- Ask before: schema changes, new dependencies, anything touching money or auth semantics, deleting files, changing any rule in these docs.
- Do not ask for permission for routine work (formatting, adding tests, refactoring inside a file you own, fixing lint).
- When the human asks "explain", teach at the level of a strong CS student: simple sentences, concrete examples, the exact line and why it is safe.

## 7b. Kickoff prompt the human will paste

The human may simply say "start from AGENTS.md". That means do exactly the following.

> Read docs/agent/00_READ_FIRST.md and every file it lists, then AGENTS.md and docs/ARCHITECTURE.md. Do not write code yet. Summarise the invariants in your own words, list the three riskiest parts of the build, list any conflicts or ambiguities between the documents, and propose the first day's plan from docs/agent/BUILD_PLAN.md. Wait for my approval.
