
    ## LedgerLine — money movement with a ledger you can prove

        Move money so the books always balance and the same request never pays twice. Any stack. Seven days.

  **

  **

        ## The situation

Every company moves money it cannot afford to get wrong. Payroll goes out to five hundred people. A vendor is paid against an invoice. An employee is reimbursed an expense. Money moves from one internal account to another. Two things go wrong, and both are expensive.

The first is that the books stop balancing. A transfer debits one account and the credit is lost on the way. A request is retried after a timeout and the payment goes out twice. Two withdrawals arrive at the same instant, both check the balance, both see enough, and both succeed — and the account is now overdrawn. Money has been created, or destroyed, or moved twice, and a real company has really lost it.

The second is that afterwards nobody can say what happened. When a balance is wrong, the first question is  *what moved, when, and who authorised it* . If the honest answer is "we are not completely sure", the money is gone and so is the trust.

You are building  **LedgerLine** : a system that moves money between accounts, where money is never created or lost, where the same request never moves money twice, and where you can prove exactly what happened.

This is an integrity and concurrency problem wearing the clothes of a CRUD application. The screens — accounts, a transfer form, a statement — are straightforward. Making them correct when two requests race, a network retries, and someone is actively trying to overdraw is not, and that is what we are marking.

---

## What it must do

1. Authentication, with at least three roles: an administrator, an account holder, and an auditor (read-only). You decide what each can do and write it down.
2. Accounts with balances. Create accounts, view a balance, view a statement.
3. Money in and out: deposits, withdrawals, and transfers between two accounts.
4. Every movement conserves money. Internal transfers net to zero; the total of all balances changes only by external deposits and withdrawals. You can state this invariant and show it holds.
5. No account goes below zero — unless you deliberately design an authorised overdraft, in which case you document the limit and enforce it server-side.
6. Idempotency. A money-moving request carries a client key; the same key submitted twice moves money once, and the second call returns the first result rather than moving it again.
7. Concurrency safety. Two money-moving requests that race cannot both succeed past the available balance, and cannot corrupt a balance or the ledger.
8. A per-account statement: every debit, every credit, and every refused attempt, each with the resulting running balance and who initiated it.
9. Authorisation per account: a user can move money only from accounts they are entitled to; who may deposit, withdraw, transfer, or adjust is decided by the server on every request.
10. Automated tests that prove it: money is conserved, a balance cannot be driven negative by concurrent requests, a replayed request does not pay twice, and one user cannot move another user's money.

That list is the floor, and it is deliberately short. Everything about *how* is yours, and so is everything the list does not mention. A week is long enough to go well past it, and what you choose to add, or deliberately leave out, is part of what we are judging.

---

## The standard it has to meet

Three things, and they are not negotiable.

**One. The books always balance.** Through any route at all — the API, a retry, two concurrent requests, a request that fails halfway — money is never created and never lost, and no account goes below the floor you defined. The server decides and enforces it atomically, every time. "The form will not let you" is not an answer. We will send two requests at once and see.

**Two. Exactly once.** A request that moves money, arriving twice — a retry after a timeout, a double-click, a replayed call — moves the money once. The second attempt returns the same answer as the first without moving anything again, and you can show us in the data which requests were duplicates.

**Three. You can prove what happened.** The ledger records every posting and every refused attempt, and it is append-only: a row cannot be quietly changed or deleted. A statement you can silently edit is not a record, and we will ask you what stops that.

---

## We are going to attack it

A judge will spend time trying to break the money, against your deployed system, using every route they can think of: two withdrawals fired at the same instant to overdraw an account, the same transfer replayed to pay a vendor twice, a transfer that moves money out of an account that is not theirs, a balance driven negative through a race, a ledger row altered to hide a payment. We are not going to tell you which they will try. Working that out is the job, and it is the part of this challenge that most separates people.

So, alongside the system, you hand in  **`THREATS.md`** : the ways you believe the money or the ledger could be broken, what you did about each, and which risks you knowingly accepted and why. An honest "I know this race is still open under this condition, and here is why I left it" is worth marks. Pretending it is closed when it is not is worth none, because we will find it.

We hold our own list. You are marked on how much of it you found and closed, and we add marks for anything you found that we had not thought of. Your automated tests should cover the cases in your own `THREATS.md`, and they must actually exercise the races and the retries — a test that calls the transfer endpoint once and checks the balance is not testing concurrency. We will take one lock or one check out of your code and run your tests; if they still pass, they were not testing anything.

---

## Where you have freedom

**The stack is entirely yours.** Any language, framework, database and host. Pick what you can defend.

Also yours, and these are the real design decisions:

* How you guarantee atomicity and isolation — database transactions, row locking, serializable isolation, an append-only event log with derived balances, something else. We will spend much of the interview here.
* How you model the ledger — double-entry with debits and credits, or single-entry with an enforced invariant. Defend it.
* How idempotency works — where the key lives, how long it is remembered, what happens to a retry that arrives while the first is still in flight.
* How far you take holds and authorisations, reversals and refunds, limits, scheduled or batch transfers, multiple currencies, and anything else you decide this product needs.
* What the administrator and the auditor can see and do, and what counts as something worth flagging.

Tell us what you chose not to build, and why. A small system whose balances are always right beats a large one that loses a rupee under load.

---

## Where AI fits, and where it must not decide

Use AI to build this. We expect it, and the marks reflect it.

If you want AI inside the product, the useful place is in review and anomaly flagging — a suggestion that a transfer looks unusual, or a reconciliation summary. **The machine must never move money on its own.** A person authorises, and both the suggestion and the decision go into the ledger.

### `PROMPTS.md`

Keep a file called `PROMPTS.md` in your repository, and  **write it as you go** . Your commit history shows us whether you did, and one file added on the last evening is worth very little.

It needs at least  **five dated entries** . Each one: what you asked the tool to do, what it produced, what was specifically wrong with it, and what you did instead, with a link to the commit where you fixed it.

**At least two of those entries must be about the money-integrity, concurrency, or idempotency logic.** That is where a confident wrong answer from an AI moves real money, and catching it is the skill we are hiring for. If you genuinely had no trouble there, say so and show us the code you checked and how you checked it. "It was all fine" is not an entry. If the file says the AI was helpful five times, it scores nothing.

---

## What you hand in

* A  **public Git repository** , with history across the week rather than one commit at the end.
* A **live URL** we can open, with seed accounts and credentials in the README for one account of each role.
* **`THREATS.md`** and  **`PROMPTS.md`** , as described above.
* **Automated tests** , including the ones that prove conservation, no-double-spend under concurrency, idempotent retries, and that one user cannot move another's money.
* **Database schema and setup scripts** , and deployment instructions that work from a clean clone.
* **API documentation** , saying for each endpoint who is allowed to call it and what it does to the money.
* A  **five-minute demo video** .
* A short  **write-up** : what you built, what you deliberately did not, your integrity and concurrency model in your own words, how you used AI and where it was wrong, and what is unfinished. Honesty about gaps scores better than hiding them.

---

## How we mark it

| Marks        | What                                                                                                                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **35** | **Integrity & security.**What a judge can break on your deployed system — overdraw, double-spend, moving another account's money, tampering with the ledger. The same attempts for everyone |
| **15** | **Threat thinking.**Your`THREATS.md`against ours, plus anything you found that we did not, plus whether your tests actually exercise the races and retries                                 |
| **15** | **Functionality.**The ten requirements, working                                                                                                                                              |
| **15** | **How you used AI.**Your`PROMPTS.md`: evidence of directing the tool and catching it being wrong. Heavy use with no example of catching an error scores near zero here                     |
| **10** | **Engineering quality.**Readable, sensibly built, errors handled                                                                                                                             |
| **10** | **Documentation, deployment and demo.**Can someone else run it, operate it and trust it                                                                                                      |

One rupee created, lost, or moved by someone who should not have moved it costs most of the first band, whatever else works. That is deliberate. A money system that does not balance is not a partially working money system.

Deploy early in the week, not on the last day. People who leave it to the end usually do not deploy at all.

---

**The interview afterwards.** Shortlisted candidates walk through their own code and make a change we pick, live. Expect to be asked exactly where the balance is checked and the debit is written, whether those happen atomically, and what happens when two of those run at the same instant or the same request arrives twice. If you cannot answer that, the rest does not help.

---

## Official Addendum & Clarifications: BalanceVault (November 2026)

> Official clarification provided by the Snovasys hiring challenge organizers (November 6 – 12, 2026).

### 1. Challenge Identity & Continuity
- **BalanceVault is the renamed LedgerLine challenge**: It is the same continuous challenge, not a new or separate one.
- **Core Financial Invariants Retained**: All original financial integrity requirements—double-entry accounting, idempotency, concurrency safety, overdraft prevention, and append-only audit ledger—remain fully applicable and evaluated under the same rubric.

### 2. Additional Mandatory Requirements
The updated problem description adds explicit emphasis on production implementation and deployment aspects. These are additional mandatory requirements (not replacements):
1. **Account Management & User Onboarding**: Self-service registration for account holders, user onboarding workflows, and administrative account management.
2. **RBAC (Role-Based Access Control)**: Rigorous server-enforced access boundaries separating `admin`, `holder`, and read-only `auditor` roles.
3. **Database Architecture**: PostgreSQL integration (with structured migrations and strict relational schemas).
4. **Redis Rate Limiting**: Redis integration for backend rate limiting across sensitive endpoints (auth, money movement, API abuse prevention).
5. **First-Admin Bootstrap Script**: A dedicated, idempotent, and secure bootstrap mechanism to provision the initial administrator without bypassing database role constraints.
6. **Database Roles & Deployment Health Checks**: Explicit database role separation (runtime app role vs schema owner/migration role) alongside unauthenticated, reliable `/health` (liveness) and `/ready` (readiness + database/cache connectivity) endpoints.

### 3. Original Deliverables Retained
All original deliverables remain strictly mandatory:
- `THREATS.md` (Threat modeling and mitigation catalog)
- `PROMPTS.md` (Dated AI interaction history with defect-catching examples)
- Automated concurrency and idempotency test suites
- Comprehensive API documentation
- 5-minute video demonstration
- Technical architectural write-up

### 4. Implementation Strategy: Extend, Do Not Rebuild
Organizers explicitly clarified: *"Please extend your existing LedgerLine implementation. You do not need to start a separate implementation. BalanceVault will be evaluated on the same rubric, with the new deployment / RBAC / Redis items added to it."*

---

### Portal Submission & Problem Context: BalanceVault
*Snovasys Fresher Hiring Challenge 2026 — VVIT (November 6 – 12, 2026)*

**Tagline**: *BalanceVault — money movement with a ledger you can prove*  
**Overview**: A secure account management platform with role-based access, user onboarding, and auditable account operations.

#### Core Problem
Managing financial accounts and their associated operations requires more than just storing account information. It also requires controlled access, secure authentication, clear onboarding, and accountability for important actions. BalanceVault brings these capabilities together: structured account management, role-based access, onboarding workflows, and auditability.

#### Required Capabilities Checklist
- [x] Responsive, fintech-grade frontend interface.
- [x] Backend API service with strict request validation and error isolation.
- [x] PostgreSQL database integration with automated migrations and relational constraints.
- [x] Dedicated database roles separating runtime app privileges from migration/owner privileges.
- [x] Authentication and role-based access control (RBAC).
- [x] Account-holder registration and account onboarding workflows.
- [x] Admin functionality for user management, account onboarding, and audit-log inspection.
- [x] Redis integration for backend rate limiting.
- [x] Backend operational health (`/health`) and readiness (`/ready`) endpoints.
- [x] Secure first-admin bootstrap script handling PostgreSQL permission nuances.

