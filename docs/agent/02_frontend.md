
# 02_FRONTEND — Next.js, TypeScript, Tailwind, three.js standards

Audience: AI agents. The UI must look senior-level and be safe with money. The server is the authority; the UI only renders it.

## 1. Stack and setup

- Next.js (latest stable, App Router), React, TypeScript `strict: true` plus `noUncheckedIndexedAccess`, Tailwind CSS, shadcn/ui (install real components through its CLI/MCP, do not hand-roll lookalikes), Framer Motion, `three`, `@react-three/fiber`, `@react-three/drei`, `zod`, `@tanstack/react-query`, `sonner` for toasts, `lucide-react` icons.
- Lint/format: ESLint (next config) + Prettier. `tsc --noEmit` clean. No `any` without a comment explaining why.
- Use the frontend-design skill and Context7 docs when available. Do not use deprecated Next.js APIs; check current docs.

## 2. Structure

```
frontend/src/
  app/
    (public)/login/page.tsx            # + marketing hero with LedgerChain3D
    (app)/layout.tsx                   # auth gate + shell (sidebar/topbar)
    (app)/dashboard/page.tsx
    (app)/accounts/[id]/page.tsx       # balance + statement
    (app)/move-money/page.tsx          # tabs: Deposit | Withdraw | Transfer
    (app)/admin/{users,accounts,adjustments,flags}/page.tsx
    (app)/audit/{verify,ledger,replays,security}/page.tsx   # auditor + admin
    api/[...path]/route.ts             # BFF proxy to backend (see 3)
  components/ui/ (shadcn)  components/ledger/ (StatementTable, MoneyInput, BalanceCard, RefusalRow, VerifyPanel)
  components/three/LedgerChain3D.tsx
  lib/{api.ts,money.ts,idempotency.ts,schemas.ts,auth.ts,format.ts}
  styles/tokens.css
```

Role-based navigation is a UX nicety only; the backend enforces everything.

## 3. Auth and API access (BFF pattern)

- The browser never holds the API token in JavaScript. Login goes through `app/api/auth/login` (route handler) which calls the backend, then sets an `httpOnly; Secure; SameSite=Lax` cookie containing the opaque session token.
- `app/api/[...path]/route.ts` proxies browser requests to the backend, reads the cookie server-side, adds `Authorization: Bearer`, forwards `Idempotency-Key`, and uses an allow-list of backend path prefixes. On non-GET requests it rejects when the `Origin` header does not equal the site's own origin (CSRF defence).
- `API_BASE_URL` is a server-only env var (not `NEXT_PUBLIC_`). Never expose secrets to the client bundle.
- Session expiry (401) redirects to login and clears the cookie.
- The raw backend API stays directly usable with Bearer tokens (judges will use curl); the README documents both.

## 4. Money handling in the UI (strict)

- Money is integer paise everywhere in state and in API calls. `lib/money.ts` provides: `parseRupeesToPaise(input: string): bigint | null` using a regex (`^\d+(\.\d{1,2})?$`) and integer arithmetic only (never `parseFloat`), `formatPaise(paise)` using `Intl.NumberFormat('en-IN')` on a whole-rupee and paise split, and unit tests for edge cases (0.1, 0.01, 1e3, "١٢٣", negative, empty, 3 decimals, huge).
- Show amounts in tabular numerals, right-aligned, with a clear Dr/Cr treatment (credit in accent, debit neutral, refusal in red with an icon, never colour alone).
- NO optimistic updates for money. Show a pending state, then the server-confirmed result.
- Idempotency: create the key with `crypto.randomUUID()` when the form is first opened for an intent. Reuse it if the user retries the same submit (network error, timeout, double-click). Generate a new key only after success or when the user edits amount/destination. Disable the submit button while a request is in flight. Show the "Replayed (not charged again)" badge when the response has `Idempotent-Replayed: true`.
- Display refusal reasons in plain language and never imply money moved. Announce results in an `aria-live` region.
- Never compute eligibility in the UI (balance checks, ownership). Server decides; UI renders server messages.

## 5. Visual design direction

Goal: a fintech product a judge screenshots. Precise, calm, trustworthy, with one memorable element (the 3D chain).

- Dark theme default, light theme supported via CSS variables. Tokens in `tokens.css`:
  - Background ink `#0B0F14`, surface `#111823`, elevated `#162030`, border `#1F2B3D`.
  - Text `#E6EDF5`, muted `#8FA1B8`.
  - Accent (one only) mint `#6CF5B0`; danger `#FF6B6B` (refusals, tamper); warning `#FFC857` (AI flags); info `#6AA9FF` sparingly.
  - Radius 12px cards, 8px controls; spacing on a 4px grid; subtle 1px borders instead of heavy shadows.
- Typography: Geist Sans for UI, Geist Mono for ids/hashes, tabular numerals for amounts (`font-variant-numeric: tabular-nums`). Clear hierarchy: one large balance number per page, small caps labels.
- Motion: Framer Motion for page transitions and list entry (150 to 250 ms, ease-out), number tick on balance change after server confirmation, skeleton loaders for every async block. Respect `prefers-reduced-motion` everywhere.
- Layout: left sidebar on desktop, bottom bar on mobile (390 px). No horizontal scroll at 390 px. Max content width 1200 px.
- Empty, loading and error states for every screen. Error toasts show the server's error code and request id (small, copyable) for debuggability.
- Do not use generic gradient hero clichés, stock illustrations or emoji as icons. Use lucide icons and the 3D chain.

## 6. LedgerChain3D (three.js, with purpose)

- Renders an account's last N ledger entries (or a sample on the landing page) as linked glass blocks along a curved path. Each block shows seq and the first 6 hex chars of its hash; links show prev_hash relationship.
- States: idle (slow drift), verifying (a pulse travels along the chain), verified (all blocks glow mint), tampered (the affected block and everything after it turns red, camera eases toward it).
- Implementation: `@react-three/fiber` Canvas, `drei` helpers, instanced meshes where possible, `frameloop="demand"` when idle, DPR capped at 2, no postprocessing heavy passes, a single directional light plus environment. Total added JS must stay lazy: `next/dynamic(() => import(...), { ssr: false })`.
- Fallbacks: if WebGL unavailable, `prefers-reduced-motion`, or low-power device, render a static SVG of the same chain. The component takes data as props and never calls the API itself.
- The component is decorative-plus-informative: the same verify result is always shown as text/table beside it (accessibility).

## 7. Screens (acceptance criteria)

1. Login: email/password, clear errors (generic "invalid credentials"), throttling message on 429, optional demo-credentials panel behind `NEXT_PUBLIC_DEMO_MODE=true`.
2. Dashboard: accounts the user can see, balances (large, tabular), last activity, quick actions. Admin/auditor see an all-accounts table with search.
3. Account detail + Statement: header balance, status badge (active/frozen), filter by type (posting/refusal) and date, keyset "Load more". Each row shows running balance, counterparty (masked), initiator, request id (copy). Refused attempts are visually distinct with the reason code.
4. Move Money: tabs Deposit, Withdraw, Transfer. Account picker only lists the user's own accounts as sources. Review-then-confirm step showing amount, from, to. Result panel shows journal id, new balance, and replay badge when applicable. Duplicate-click protection demonstrated in Playwright.
5. Admin: create users and accounts, assign owners, freeze/unfreeze, post adjustments (reason required, confirmation dialog), reverse a journal, AI flag queue with approve/dismiss and mandatory reason.
6. Audit (auditor and admin): Verify page with the 3D chain and a results table (chain OK, balance cache, zero-sum, global sum, customer total vs deposits minus withdrawals), ledger explorer with filters, replay log, security events. Auditor sees no action buttons.
7. Errors: 401 to login, 403 page, 404 page, global error boundary with request id.

## 8. Quality bar

- Accessibility: keyboard navigation, visible focus rings, labelled inputs, AA contrast, semantic table markup for statements, `aria-live` for results.
- Performance: Lighthouse (desktop) 90+ for Performance and Accessibility on the dashboard and login; three.js chunk lazy-loaded; no layout shift on balances (reserve space).
- Security: strict CSP via middleware with a nonce (`default-src 'self'`, `connect-src 'self'`, `img-src 'self' data:`, `frame-ancestors 'none'`, inline styles allowed only as needed by Tailwind/Framer), `X-Content-Type-Options`, `Referrer-Policy`, no `dangerouslySetInnerHTML`, user text always rendered as text.
- Tests: Vitest for `money.ts` and `idempotency.ts`; Playwright e2e for login per role, transfer success, refused transfer display, double-click submit (exactly one journal), auditor has no action buttons, session expiry. Screenshots at 390 px and 1440 px saved to `frontend/e2e/screenshots/` during design review.
- After each screen, take Playwright screenshots, critique against this file, and fix before moving on.
