/**
 * How this works / why it is safe:
 * This module is the central HTTP API client for LedgerLine.
 * It manages authentication tokens, attaches required headers (Authorization Bearer, Idempotency-Key),
 * and standardizes error handling around the RFC JSON envelope {"error": {"code", "message", "request_id"}}.
 * On idempotent replays, it captures the Idempotent-Replayed response header so the UI can prove
 * the request did not move money twice.
 */

export interface User {
  id: string;
  email: string;
  role: "admin" | "holder" | "auditor";
  is_active: boolean;
  created_at: string;
}

export interface Account {
  id: string;
  number: string;
  name: string;
  kind: "customer" | "external" | "suspense";
  currency: string;
  balance: number; // in paise
  overdraft_limit: number; // in paise
  status: "active" | "frozen" | "closed";
  created_at: string;
}

export interface StatementItem {
  type: "posting" | "refusal";
  account_seq: number;
  at: string;
  kind: string;
  amount: number; // in paise
  balance_after?: number; // in paise (for postings)
  balance_at_attempt?: number; // in paise (for refusals)
  counterparty?: string | null;
  initiated_by: { id: string; email: string };
  journal_id?: string | null;
  reason_code?: string | null;
  request_id: string;
  prev_hash?: string | null;
  entry_hash?: string | null;
}

export interface StatementResponse {
  account_id: string;
  currency?: string;
  current_balance?: number;
  overdraft_limit?: number;
  status?: string;
  items: StatementItem[];
  has_more: boolean;
  next_after: number | null;
  next_cursor?: number | null;
}

export interface MovementResponse {
  journal_id: string;
  kind: string;
  amount: number;
  status: "posted" | "replayed";
  is_replayed?: boolean;
  entry: {
    account_id: string;
    account_seq: number;
    amount: number;
    balance_after: number;
  };
  created_at: string;
}

export interface Discrepancy {
  check: string;
  account_id?: string | null;
  account_seq?: number | null;
  expected: unknown;
  actual: unknown;
  message: string;
}

export interface AuditVerification {
  verified: boolean;
  is_valid: boolean;
  total_accounts_checked: number;
  total_entries_verified: number;
  total_journals_verified: number;
  global_balance_sum: number;
  customer_balance_sum: number;
  discrepancies: Discrepancy[];
}

export interface ReviewFlag {
  id: number;
  journal_id?: string | null;
  rule_id: string;
  severity: string;
  evidence: Record<string, unknown>;
  narrative?: string | null;
  status: "pending" | "approved" | "dismissed";
  created_at: string;
}

export class ApiError extends Error {
  code: string;
  requestId: string;
  statusCode: number;

  constructor(code: string, message: string, requestId: string, statusCode: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.requestId = requestId;
    this.statusCode = statusCode;
  }
}

const API_BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000")
    : "http://localhost:8000";

let sessionToken: string | null = null;

if (typeof window !== "undefined") {
  try {
    sessionToken = localStorage.getItem("ll_token");
  } catch {}
}

export function setToken(token: string | null) {
  sessionToken = token;
  if (typeof window !== "undefined") {
    try {
      if (token) localStorage.setItem("ll_token", token);
      else localStorage.removeItem("ll_token");
    } catch {}
  }
}

export function getToken(): string | null {
  return sessionToken;
}

async function request<T>(
  path: string,
  options: RequestInit & { idempotencyKey?: string } = {}
): Promise<{ data: T; isReplayed: boolean; requestId: string }> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (sessionToken) {
    headers["Authorization"] = `Bearer ${sessionToken}`;
  }

  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }

  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    throw new ApiError(
      "network_error",
      "Unable to connect to the LedgerLine backend server. Please check your connection.",
      "none",
      0
    );
  }

  const requestId = response.headers.get("x-request-id") || "req-unknown";
  const isReplayed = response.headers.get("idempotent-replayed") === "true";

  if (!response.ok) {
    let errBody: { error?: { code?: string; message?: string; request_id?: string } } = {};
    try {
      errBody = await response.json();
    } catch {}

    const code = errBody.error?.code || `http_${response.status}`;
    const message = errBody.error?.message || response.statusText || "Request failed.";
    const reqId = errBody.error?.request_id || requestId;

    throw new ApiError(code, message, reqId, response.status);
  }

  const data = (await response.json()) as T;
  return { data, isReplayed, requestId };
}

/* ==========================================================================
   API Operations
   ========================================================================== */

export const api = {
  // Auth
  async login(email: string, password: string): Promise<{ token: string; user: User }> {
    const { data } = await request<{ token: string; user: User; expires_at: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setToken(data.token);
    return data;
  },

  async logout(): Promise<void> {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      setToken(null);
    }
  },

  async getMe(): Promise<User> {
    const { data } = await request<User>("/auth/me");
    return data;
  },

  // Accounts
  async getAccounts(): Promise<Account[]> {
    const { data } = await request<{ accounts: Account[] }>("/accounts");
    return data.accounts;
  },

  async getAccount(id: string): Promise<Account> {
    const { data } = await request<Account>(`/accounts/${id}`);
    return data;
  },

  async getStatement(
    accountId: string,
    params: { limit?: number; after?: number; kind?: string } = {}
  ): Promise<StatementResponse> {
    const query = new URLSearchParams();
    if (params.limit) query.set("limit", params.limit.toString());
    if (params.after) query.set("after", params.after.toString());
    if (params.kind && params.kind !== "all") query.set("kind", params.kind);

    const path = `/accounts/${accountId}/statement${query.toString() ? `?${query.toString()}` : ""}`;
    const { data } = await request<StatementResponse>(path);
    return data;
  },

  // Movements (Strict Idempotency Required)
  async deposit(
    accountId: string,
    amountPaise: number,
    memo?: string,
    idempotencyKey?: string
  ): Promise<{ result: MovementResponse; isReplayed: boolean }> {
    const { data, isReplayed } = await request<MovementResponse>(`/accounts/${accountId}/deposit`, {
      method: "POST",
      body: JSON.stringify({ amount: amountPaise, memo }),
      idempotencyKey,
    });
    return { result: { ...data, is_replayed: isReplayed }, isReplayed };
  },

  async withdraw(
    accountId: string,
    amountPaise: number,
    memo?: string,
    idempotencyKey?: string
  ): Promise<{ result: MovementResponse; isReplayed: boolean }> {
    const { data, isReplayed } = await request<MovementResponse>(`/accounts/${accountId}/withdraw`, {
      method: "POST",
      body: JSON.stringify({ amount: amountPaise, memo }),
      idempotencyKey,
    });
    return { result: { ...data, is_replayed: isReplayed }, isReplayed };
  },

  async transfer(
    fromAccountId: string,
    toAccountNumber: string,
    amountPaise: number,
    memo?: string,
    idempotencyKey?: string
  ): Promise<{ result: MovementResponse; isReplayed: boolean }> {
    const { data, isReplayed } = await request<MovementResponse>("/transfers", {
      method: "POST",
      body: JSON.stringify({
        from_account_id: fromAccountId,
        to_account_number: toAccountNumber,
        amount: amountPaise,
        memo,
      }),
      idempotencyKey,
    });
    return { result: { ...data, is_replayed: isReplayed }, isReplayed };
  },

  // Admin
  async freezeAccount(id: string): Promise<Account> {
    const { data } = await request<Account>(`/admin/accounts/${id}/freeze`, { method: "POST" });
    return data;
  },

  async unfreezeAccount(id: string): Promise<Account> {
    const { data } = await request<Account>(`/admin/accounts/${id}/unfreeze`, { method: "POST" });
    return data;
  },

  async postAdjustment(
    accountId: string,
    amountPaise: number,
    reason: string,
    idempotencyKey?: string
  ): Promise<{ result: MovementResponse; isReplayed: boolean }> {
    const { data, isReplayed } = await request<MovementResponse>("/admin/adjustments", {
      method: "POST",
      body: JSON.stringify({ account_id: accountId, amount: amountPaise, reason }),
      idempotencyKey,
    });
    return { result: { ...data, is_replayed: isReplayed }, isReplayed };
  },

  // Audit
  async verifyAudit(): Promise<AuditVerification> {
    const { data } = await request<AuditVerification>("/audit/verify");
    return data;
  },

  // Review
  async getReviewFlags(): Promise<ReviewFlag[]> {
    const { data } = await request<ReviewFlag[]>("/review/flags");
    return data;
  },

  async decideReviewFlag(
    flagId: number,
    decision: "approved" | "dismissed",
    reason: string
  ): Promise<void> {
    await request(`/review/flags/${flagId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    });
  },
};
