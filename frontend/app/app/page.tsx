"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import "./app.css";
import {
  api,
  User,
  Account,
  StatementItem,
  AuditVerification,
  ReviewFlag,
  ApiError,
  setToken,
  AccountInsights,
  ChatResponse,
  InsightCard,
} from "@/lib/api";
import { formatPaise, parseRupeesToPaise } from "@/lib/money";

interface Toast {
  id: string;
  message: string;
  isError?: boolean;
  detail?: string;
}

type TabType = "dashboard" | "statement" | "audit" | "admin";
type MoveType = "transfer" | "deposit" | "withdraw";
type ModalStep = "form" | "review" | "busy" | "done";

interface MessageItem {
  id: string;
  role: "user" | "assistant";
  text?: string;
  response?: ChatResponse;
  tool?: string;
}

const DEFAULT_SUGGESTIONS = [
  "Project my 30-day cash flow",
  "Show largest transfers",
  "Check fraud risk score",
  "Find transfers above ₹5,000",
  "Run reconciliation audit",
];

export default function AppPage() {
  // Theme state
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // AI Copilot & Intelligence State
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<MessageItem[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatThinking, setIsChatThinking] = useState(false);
  const [activeProvider, setActiveProvider] = useState("Offline engine");
  const [suggestedPills, setSuggestedPills] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [accountInsights, setAccountInsights] = useState<AccountInsights | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  // Auth & Session
  const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
  const [user, setUser] = useState<User | null>(null);
  const [currentTab, setCurrentTab] = useState<TabType>("dashboard");
  const [authEmail, setAuthEmail] = useState(DEMO ? "holder1@ledgerline.internal" : "");
  const [authPassword, setAuthPassword] = useState(DEMO ? "DemoPassword123!" : "");
  const [authRole, setAuthRole] = useState<"holder" | "admin" | "auditor">("holder");
  const [loginLoading, setLoginLoading] = useState(false);

  // Video State & Seamless Looping
  const videoRef = useRef<HTMLVideoElement>(null);
  const [videoFade, setVideoFade] = useState(false);

  useEffect(() => {
    if (!user && videoRef.current) {
      videoRef.current.muted = true;
      const rm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (!rm) {
        videoRef.current.play().catch(() => {});
      }
    }
  }, [user]);

  const handleVideoTimeUpdate = () => {
    const v = videoRef.current;
    if (v && v.duration) {
      if (v.currentTime > v.duration - 0.45) {
        setVideoFade(true);
      } else if (v.currentTime < 0.45) {
        setVideoFade(false);
      }
    }
  };

  const handleVideoEnded = () => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    const v = videoRef.current;
    if (v) {
      v.currentTime = 0;
      v.play().catch(() => {});
      setTimeout(() => {
        setVideoFade(false);
      }, 80);
    }
  };

  // Ledger & Account Data
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [activeAccount, setActiveAccount] = useState<Account | null>(null);
  const [statements, setStatements] = useState<StatementItem[]>([]);
  const [statementFilter, setStatementFilter] = useState<"all" | "posting" | "refusal">("all");
  const [statementHasMore, setStatementHasMore] = useState(false);
  const [statementNextAfter, setStatementNextAfter] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [dataLoading, setDataLoading] = useState(false);

  // Move Money Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalStep, setModalStep] = useState<ModalStep>("form");
  const [moveType, setMoveType] = useState<MoveType>("transfer");
  const [toAccountNum, setToAccountNum] = useState("");
  const [amountRupees, setAmountRupees] = useState("");
  const [memo, setMemo] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState<string>("");
  const [moveAttempted, setMoveAttempted] = useState(false);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [moveResult, setMoveResult] = useState<{
    status: "posted" | "replayed" | "refused";
    journalId?: string;
    code?: string;
    balanceAfter?: number;
    amountPaise?: number;
  } | null>(null);

  // Audit State
  const [auditRunning, setAuditRunning] = useState(false);
  const [auditResult, setAuditResult] = useState<AuditVerification | null>(null);
  const [simulatedTamper, setSimulatedTamper] = useState(false);

  // Admin State
  const [reviewFlags, setReviewFlags] = useState<ReviewFlag[]>([]);
  const [adjAccount, setAdjAccount] = useState<string>("");
  const [adjAmount, setAdjAmount] = useState<string>("-250.00");
  const [adjReason, setAdjReason] = useState<string>("Correction of bank drift");
  const [flagExplanations, setFlagExplanations] = useState<Record<number, string>>({});

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Prerender-safe client timestamp for chart calculation (Next.js 15 SSR compatibility)
  const [clientNow, setClientNow] = useState<Date | null>(null);

  useEffect(() => {
    setClientNow(new Date());
  }, []);

  // Add toast notification
  const addToast = useCallback((message: string, isError = false, detail?: string) => {
    const id = `t-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
    setToasts((prev) => [...prev, { id, message, isError, detail }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5500);
  }, []);

  const addErrorToast = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError) {
        let displayMessage = err.message;
        if (
          err.code === "invalid_destination" ||
          err.message.toLowerCase().includes("frozen") ||
          err.message.toLowerCase().includes("destination account is invalid")
        ) {
          displayMessage = "The account is frozen by an administrator (or invalid/closed).";
        } else if (err.code === "account_frozen") {
          displayMessage = "This account is currently frozen by an administrator.";
        }
        addToast(
          displayMessage,
          true,
          JSON.stringify({ code: err.code, message: err.message, request_id: err.requestId })
        );
      } else if (err instanceof Error) {
        addToast(
          err.message,
          true,
          JSON.stringify({ code: "error", message: err.message, request_id: "req-local" })
        );
      } else {
        addToast(
          "An unexpected error occurred.",
          true,
          JSON.stringify({ code: "unknown_error", message: String(err), request_id: "req-local" })
        );
      }
    },
    [addToast]
  );

  // Initialize theme
  useEffect(() => {
    try {
      const saved = localStorage.getItem("ll-theme") as "light" | "dark" | null;
      if (
        saved === "dark" ||
        (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches)
      ) {
        setTheme("dark");
        document.documentElement.setAttribute("data-theme", "dark");
      } else {
        setTheme("light");
        document.documentElement.setAttribute("data-theme", "light");
      }
    } catch {}
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("ll-theme", next);
    } catch {}
  };

  // Hydrate session on load
  const loadUserData = useCallback(async () => {
    try {
      setDataLoading(true);
      const currentUser = await api.getMe();
      setUser(currentUser);

      const accs = await api.getAccounts();
      setAccounts(accs);

      if (accs.length > 0) {
        const primary = accs[0] ?? null;
        setActiveAccount(primary);
        if (primary) {
          const stm = await api.getStatement(primary.id, { limit: 20 });
          setStatements(stm.items);
          setStatementHasMore(Boolean(stm.has_more));
          setStatementNextAfter(stm.next_after ?? stm.next_cursor ?? null);
          setAdjAccount(primary.number);
          fetchInsights(primary.id);
        }
      }

      if (currentUser.role === "admin" || currentUser.role === "auditor") {
        try {
          const flags = await api.getReviewFlags();
          setReviewFlags(flags);
        } catch {}
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.statusCode === 401) {
        // Session expired or unauthenticated
        setUser(null);
        setToken(null);
        setCurrentTab("dashboard");
        setChatMessages([]);
        setChatInput("");
        setAccountInsights(null);
        setIsCopilotOpen(false);
        setSuggestedPills(DEFAULT_SUGGESTIONS);
      } else {
        addErrorToast(err);
      }
    } finally {
      setDataLoading(false);
    }
  }, [addErrorToast]);

  useEffect(() => {
    loadUserData();
  }, [loadUserData]);

  // Isolate AI Copilot session strictly per authenticated user to prevent cross-tenant leak
  const prevUserIdRef = useRef<string | null>(null);
  useEffect(() => {
    const currentUserId = user?.id ?? null;
    if (prevUserIdRef.current !== currentUserId) {
      setChatMessages([]);
      setChatInput("");
      setAccountInsights(null);
      setIsCopilotOpen(false);
      setSuggestedPills(DEFAULT_SUGGESTIONS);
      prevUserIdRef.current = currentUserId;
    }
  }, [user?.id]);

  // Fetch account financial intelligence from server
  const fetchInsights = useCallback(async (accId: string) => {
    if (!accId) return;
    try {
      setInsightsLoading(true);
      const data = await api.getAccountInsights(accId);
      setAccountInsights(data);
    } catch (err) {
      // Local fallback is automatically computed if server insights fail
      console.warn("Server insights unavailable; utilizing deterministic fallback", err);
    } finally {
      setInsightsLoading(false);
    }
  }, []);

  // Send message to AI Copilot
  const handleSendChat = async (promptText?: string) => {
    const query = (promptText || chatInput).trim();
    if (!query || isChatThinking) return;

    const userMsgId = `u-${Date.now()}`;
    const newMessages: MessageItem[] = [
      ...chatMessages,
      { id: userMsgId, role: "user", text: query },
    ];
    setChatMessages(newMessages);
    setChatInput("");
    setIsChatThinking(true);

    try {
      const historyPayload = chatMessages.slice(-6).map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.text || m.response?.reply || "",
      }));

      const resp = await api.chatWithCopilot({
        message: query,
        account_id: activeAccount?.id || null,
        history: historyPayload,
      });

      if (!resp.provider || resp.provider === "deterministic" || resp.provider.toLowerCase().includes("offline")) {
        setActiveProvider("Offline engine");
      } else {
        const prov = resp.provider.toLowerCase();
        let provName = resp.provider;
        if (prov === "groq") provName = "Groq";
        else if (prov === "gemini") provName = "Gemini";

        let modName = resp.model || "";
        if (modName.toLowerCase().includes("llama-3.3") || modName.toLowerCase().includes("llama3")) {
          modName = "Llama 3.3";
        } else if (modName.toLowerCase().includes("flash") || modName.toLowerCase().includes("gemini-2.0")) {
          modName = "Flash";
        } else if (modName === "ledgerline-analytics-v1" || !modName) {
          modName = "";
        }
        setActiveProvider(modName ? `${provName} · ${modName}` : provName);
      }
      if (resp.suggested_queries && resp.suggested_queries.length > 0) {
        setSuggestedPills(resp.suggested_queries);
      }

      setChatMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          response: resp,
          tool: `${resp.intent} · read-only`,
        },
      ]);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to reach AI Copilot.";
      setChatMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          response: {
            reply: `An error occurred: **${errorMsg}**. Under Invariant I8, LedgerLine operates strictly in read-only surveillance mode.`,
            provider: "deterministic",
            model: "fallback",
            intent: "general",
            insights: [],
            suggested_queries: DEFAULT_SUGGESTIONS.slice(0, 3),
          },
          tool: "safe · fallback",
        },
      ]);
    } finally {
      setIsChatThinking(false);
    }
  };

  // Auto-scroll chat body on new messages
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatMessages, isChatThinking]);

  // Sync drawer class with body for responsive shifting
  useEffect(() => {
    if (typeof document !== "undefined") {
      if (isCopilotOpen) {
        document.body.classList.add("cpo");
      } else {
        document.body.classList.remove("cpo");
      }
    }
    return () => {
      if (typeof document !== "undefined") {
        document.body.classList.remove("cpo");
      }
    };
  }, [isCopilotOpen]);

  // Keyboard shortcut listener (Cmd+K / Ctrl+K and Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!user) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCopilotOpen((prev) => !prev);
      } else if (e.key === "Escape" && isCopilotOpen) {
        setIsCopilotOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [user, isCopilotOpen]);

  // Refresh active account statements
  const refreshStatements = useCallback(
    async (accId?: string) => {
      const targetId = accId || activeAccount?.id;
      if (!targetId) return;
      try {
        const [stm, updatedAcc, allAccs] = await Promise.all([
          api.getStatement(targetId, { limit: 20 }),
          api.getAccount(targetId),
          api.getAccounts().catch(() => null),
        ]);

        setStatements(stm.items);
        setStatementHasMore(Boolean(stm.has_more));
        setStatementNextAfter(stm.next_after ?? stm.next_cursor ?? null);
        setActiveAccount(updatedAcc);
        fetchInsights(targetId);

        if (allAccs) {
          setAccounts(allAccs);
        } else {
          setAccounts((prev) => prev.map((a) => (a.id === updatedAcc.id ? updatedAcc : a)));
        }
      } catch (e) {
        addErrorToast(e);
      }
    },
    [activeAccount?.id, addErrorToast, fetchInsights]
  );

  const handleSelectAccount = async (acc: Account) => {
    if (activeAccount?.id !== acc.id) {
      setChatMessages([]);
      setChatInput("");
      setAccountInsights(null);
      setSuggestedPills(DEFAULT_SUGGESTIONS);
    }
    setActiveAccount(acc);
    setAdjAccount(acc.number);
    fetchInsights(acc.id);
    await refreshStatements(acc.id);
  };

  // Keyset Load More
  const handleLoadMoreStatements = async () => {
    if (!activeAccount || !statementNextAfter || loadingMore) return;
    try {
      setLoadingMore(true);
      const res = await api.getStatement(activeAccount.id, {
        after: statementNextAfter,
        limit: 20,
      });
      setStatements((prev) => [...prev, ...res.items]);
      setStatementHasMore(Boolean(res.has_more));
      setStatementNextAfter(res.next_after ?? res.next_cursor ?? null);
    } catch (err) {
      addErrorToast(err);
    } finally {
      setLoadingMore(false);
    }
  };

  // Handle Login
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoginLoading(true);
      const res = await api.login(authEmail, authPassword);
      setChatMessages([]);
      setChatInput("");
      setAccountInsights(null);
      setIsCopilotOpen(false);
      setSuggestedPills(DEFAULT_SUGGESTIONS);
      setUser(res.user);
      addToast(`Signed in as ${res.user.email} (${res.user.role})`);
      await loadUserData();
    } catch (err) {
      addErrorToast(err);
    } finally {
      setLoginLoading(false);
    }
  };

  // Handle Logout
  const handleLogout = async () => {
    try {
      await api.logout();
    } catch {}
    setUser(null);
    setAccounts([]);
    setActiveAccount(null);
    setStatements([]);
    setStatementHasMore(false);
    setStatementNextAfter(null);
    setCurrentTab("dashboard");
    setReviewFlags([]);
    setFlagExplanations({});
    setAuditResult(null);
    setSimulatedTamper(false);
    setIsModalOpen(false);
    setMoveResult(null);
    setMoveAttempted(false);
    setMoveError(null);
    // Clear AI Copilot session state to prevent cross-tenant message leak
    setChatMessages([]);
    setChatInput("");
    setAccountInsights(null);
    setIsCopilotOpen(false);
    setSuggestedPills(DEFAULT_SUGGESTIONS);
    addToast("Logged out successfully.");
  };

  // Move Money Modal flow
  const openMoveModal = (type: MoveType) => {
    setMoveType(type);
    setModalStep("form");
    setIsModalOpen(true);
    setMoveResult(null);
    setMoveAttempted(false);
    setMoveError(null);
    setAmountRupees("");
    setMemo("");
    setToAccountNum("");
    setIdempotencyKey(crypto.randomUUID ? crypto.randomUUID() : `idemp-${Date.now()}`);
  };

  const handleReviewMove = () => {
    const paise = parseRupeesToPaise(amountRupees);
    if (!paise || paise <= 0) {
      addToast(
        "Enter a valid amount in rupees greater than zero.",
        true,
        '{"code":"validation_error","message":"Amount must be strictly positive.","request_id":"req-val"}'
      );
      return;
    }
    if (moveType === "transfer") {
      const dest = toAccountNum.trim().toUpperCase();
      if (!dest || (activeAccount && dest === activeAccount.number)) {
        addToast(
          "Destination account number does not exist or is invalid.",
          true,
          '{"code":"invalid_destination","message":"Destination account is invalid.","request_id":"req-dest"}'
        );
        return;
      }
    }
    setModalStep("review");
  };

  const handleExecuteMove = async () => {
    if (!activeAccount) return;
    const paise = parseRupeesToPaise(amountRupees);
    if (!paise) return;

    setModalStep("busy");

    try {
      if (moveType === "deposit") {
        const { result, isReplayed } = await api.deposit(
          activeAccount.id,
          paise,
          memo,
          idempotencyKey
        );
        setMoveResult({
          status: isReplayed ? "replayed" : "posted",
          journalId: result.journal_id,
          balanceAfter: result.entry.balance_after,
          amountPaise: paise,
        });
        setModalStep("done");
        await refreshStatements();
      } else if (moveType === "withdraw") {
        const { result, isReplayed } = await api.withdraw(
          activeAccount.id,
          paise,
          memo,
          idempotencyKey
        );
        setMoveResult({
          status: isReplayed ? "replayed" : "posted",
          journalId: result.journal_id,
          balanceAfter: result.entry.balance_after,
          amountPaise: paise,
        });
        setModalStep("done");
        await refreshStatements();
      } else if (moveType === "transfer") {
        const { result, isReplayed } = await api.transfer(
          activeAccount.id,
          toAccountNum.trim().toUpperCase(),
          paise,
          memo,
          idempotencyKey
        );
        setMoveResult({
          status: isReplayed ? "replayed" : "posted",
          journalId: result.journal_id,
          balanceAfter: result.entry.balance_after,
          amountPaise: paise,
        });
        setModalStep("done");
        await refreshStatements();
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.statusCode === 409) {
        // Business refusal recorded safely in ledger
        setMoveResult({
          status: "refused",
          code: err.code,
          amountPaise: paise,
        });
        setModalStep("done");
        await refreshStatements();
        addToast(err.message, true, `{"code":"${err.code}","request_id":"${err.requestId}"}`);
      } else {
        let errorNotice = "Outcome unconfirmed: retry same request safely with identical Idempotency-Key.";
        if (err instanceof ApiError) {
          if (
            err.code === "invalid_destination" ||
            err.message.toLowerCase().includes("frozen") ||
            err.message.toLowerCase().includes("destination account is invalid")
          ) {
            errorNotice = "The account is frozen by an administrator (or invalid/closed). Movements cannot be processed.";
          } else if (err.code === "account_frozen") {
            errorNotice = "This account is currently frozen by an administrator.";
          }
        }
        setMoveError(errorNotice);
        setMoveAttempted(true);
        setModalStep("review");
        addErrorToast(err);
      }
    }
  };

  // Run Cryptographic Verification
  const handleRunVerification = async () => {
    try {
      setAuditRunning(true);
      const res = await api.verifyAudit();
      setAuditResult(res);
      addToast(
        res.verified
          ? "Cryptographic verification passed: All 4 invariants intact."
          : `Audit check identified ${res.discrepancies.length} discrepancy record(s).`,
        !res.verified
      );
    } catch (err) {
      addErrorToast(err);
    } finally {
      setAuditRunning(false);
    }
  };

  // Freeze / Unfreeze
  const handleToggleFreeze = async (acc: Account) => {
    try {
      if (acc.status === "frozen") {
        await api.unfreezeAccount(acc.id);
        addToast(`Account ${acc.number} unfrozen.`);
      } else {
        await api.freezeAccount(acc.id);
        addToast(`Account ${acc.number} frozen.`);
      }
      const accs = await api.getAccounts();
      setAccounts(accs);
      if (activeAccount?.id === acc.id) {
        const updated = accs.find((a) => a.id === acc.id) || null;
        setActiveAccount(updated);
      }
    } catch (err) {
      addErrorToast(err);
    }
  };

  // Post Admin Adjustment against SUSPENSE
  const handlePostAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    const paise = parseRupeesToPaise(adjAmount);
    if (!paise) {
      addToast(
        "Valid signed rupee amount is required.",
        true,
        '{"code":"validation_error","message":"Amount must be numeric.","request_id":"req-adj"}'
      );
      return;
    }
    if (!adjReason.trim()) {
      addToast(
        "A mandatory reason is required for adjustments against SUSPENSE.",
        true,
        '{"code":"reason_required","message":"Admin adjustment mandates an explanation.","request_id":"req-adj"}'
      );
      return;
    }
    const target = accounts.find((a) => a.number === adjAccount);
    if (!target) {
      addToast("Selected account not found.", true);
      return;
    }

    try {
      const key = crypto.randomUUID ? crypto.randomUUID() : `adj-${Date.now()}`;
      await api.postAdjustment(target.id, paise, adjReason, key);
      addToast(`Adjustment of ${formatPaise(paise)} posted against SYS-SUSPENSE.`);
      setAdjReason("");
      // Refresh accounts for target only
      const updatedAcc = await api.getAccount(target.id);
      setAccounts((prev) => prev.map((a) => (a.id === updatedAcc.id ? updatedAcc : a)));
      // Only refresh statements if target is currently active
      if (activeAccount && target.id === activeAccount.id) {
        setActiveAccount(updatedAcc);
        await refreshStatements(target.id);
      }
    } catch (err) {
      addErrorToast(err);
    }
  };

  // AI Review Decision
  const handleReviewDecision = async (flagId: number, decision: "approved" | "dismissed") => {
    const reason = flagExplanations[flagId]?.trim();
    if (!reason) {
      addToast(
        "A written explanation is required to record this review decision.",
        true,
        '{"code":"explanation_required","message":"Audit trail requires an explanation.","request_id":"req-rev"}'
      );
      return;
    }
    try {
      await api.decideReviewFlag(flagId, decision, reason);
      addToast(`Decision "${decision}" committed to append-only review decisions.`);
      setReviewFlags((prev) => prev.filter((f) => f.id !== flagId));
    } catch (err) {
      addErrorToast(err);
    }
  };

  // Filtered statements
  const filteredStatements = useMemo(() => {
    if (statementFilter === "all") return statements;
    if (statementFilter === "posting") return statements.filter((s) => s.type === "posting");
    return statements.filter((s) => s.type === "refusal");
  }, [statements, statementFilter]);

  // Computed KPI metrics from statement
  const { totalCredits, totalDebits, refusalCount } = useMemo(() => {
    let cr = 0;
    let db = 0;
    let rf = 0;
    for (const item of statements) {
      if (item.type === "refusal") {
        rf++;
      } else if (item.amount > 0) {
        cr += item.amount;
      } else if (item.amount < 0) {
        db += Math.abs(item.amount);
      }
    }
    return { totalCredits: cr, totalDebits: db, refusalCount: rf };
  }, [statements]);

  // Deterministic local financial intelligence fallback
  const localInsights = useMemo(() => {
    const pList = statements.filter((s) => s.type === "posting");
    const rList = statements.filter((s) => s.type === "refusal");
    let cr = 0;
    let db = 0;
    for (const s of pList) {
      if (s.amount > 0) cr += s.amount;
      else db += Math.abs(s.amount);
    }
    const net = cr - db;
    const avg = pList.length ? (cr + db) / pList.length : 0;
    const vel = net / 30;
    const maxPost = pList.length ? Math.max(...pList.map((s) => Math.abs(s.amount))) : 0;
    const bal = activeAccount?.balance ?? 0;
    const pj = bal + net;
    const lo = pj - maxPost * 2;
    const hi = pj + maxPost / 2;
    const run = vel < 0 ? Math.floor(bal / -vel) : null;
    const reasons: string[] = [];
    let score = pList.length === 0 && rList.length === 0 ? 2 : pList.length <= 2 ? 6 : Math.min(12, 6 + Math.min(pList.length, 6));

    if (activeAccount?.status === "frozen") {
      score += 45;
      reasons.push("Account is administratively FROZEN due to risk or compliance hold");
    } else if (activeAccount?.status === "closed") {
      score += 25;
      reasons.push("Account is CLOSED; subsequent activity is restricted");
    }

    if (bal < 0) {
      score += 25;
      reasons.push("Operating in negative overdraft");
    } else if (cr > 0) {
      const drain = db / cr;
      if (drain >= 0.95 && cr >= 10000) {
        score += 20;
        reasons.push(`High fund depletion: ${Math.round(drain * 100)}% of inflows withdrawn`);
      } else if (drain >= 0.75 && cr >= 10000) {
        score += 10;
        reasons.push(`Elevated fund utilization: ${Math.round(drain * 100)}% of inflows transferred out`);
      }
    }

    if (rList.length >= 5) {
      score += 40;
      reasons.push(`${rList.length} transaction attempts refused`);
    } else if (rList.length >= 2) {
      score += 25;
      reasons.push(`${rList.length} transaction attempts refused`);
    } else if (rList.length === 1) {
      score += 12;
      reasons.push("1 transaction refusal recorded on file");
    }

    if (!reasons.length) {
      reasons.push(
        pList.length === 0 && rList.length === 0
          ? "Pristine account state with zero transaction history"
          : "Account behavior aligns with normal operational baseline"
      );
    }

    const clampedScore = Math.min(100, score);
    const rangePercentage = hi > lo ? Math.max(0, Math.min(100, ((pj - lo) / (hi - lo)) * 100)) : 50;
    return {
      cr,
      db,
      avg,
      n: pList.length,
      rf: rList.length,
      vel,
      pj,
      lo,
      hi,
      run,
      score: clampedScore,
      reasons,
      rangePercentage,
    };
  }, [statements, activeAccount?.balance]);

  const renderRiskGauge = (score: number) => {
    const r = 60;
    const L = Math.PI * r;
    const bands = [
      { start: 0, end: 0.4, color: "var(--acc)" },
      { start: 0.4, end: 0.7, color: "var(--amb)" },
      { start: 0.7, end: 0.85, color: "var(--org)" },
      { start: 0.85, end: 1.0, color: "var(--bad)" },
    ];
    const theta = Math.PI * (1 - score / 100);
    const cx = 70 + r * Math.cos(theta);
    const cy = 70 - r * Math.sin(theta);

    return (
      <svg viewBox="0 0 140 84" className="gg" role="img" aria-label={`Risk score ${score} of 100`}>
        {bands.map((b, i) => (
          <path
            key={i}
            d="M10 70A60 60 0 0 1 130 70"
            fill="none"
            stroke={b.color}
            strokeWidth="9"
            strokeDasharray={`${(b.end - b.start) * L - 2} ${L}`}
            strokeDashoffset={-b.start * L}
          />
        ))}
        <circle cx={cx} cy={cy} r="7" style={{ fill: "var(--bg2)", stroke: "var(--fg)" }} strokeWidth="3" />
        <text x="70" y="68" textAnchor="middle" className="gn">{score}</text>
      </svg>
    );
  };

  const getRiskBadge = (score: number): { label: string; color: string } => {
    if (score < 40) return { label: "LOW RISK", color: "var(--acc)" };
    if (score < 70) return { label: "MEDIUM RISK", color: "var(--amb)" };
    if (score < 85) return { label: "HIGH RISK", color: "var(--org)" };
    return { label: "CRITICAL ANOMALY", color: "var(--bad)" };
  };

  const renderMarkdown = (content: string) => {
    const lines = content.split("\n");
    const elements: React.ReactNode[] = [];
    let currentList: string[] = [];

    const flushList = () => {
      if (currentList.length > 0) {
        elements.push(
          <ul key={`ul-${elements.length}`}>
            {currentList.map((item, idx) => (
              <li key={idx} dangerouslySetInnerHTML={{ __html: item }} />
            ))}
          </ul>
        );
        currentList = [];
      }
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        const itemText = trimmed.slice(2).replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
        currentList.push(itemText);
      } else if (trimmed.startsWith("### ") || trimmed.startsWith("## ")) {
        flushList();
        const hText = trimmed.replace(/^#+\s*/, "").replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
        elements.push(
          <div key={`h-${idx}`} className="chat-h" dangerouslySetInnerHTML={{ __html: hText }} />
        );
      } else if (trimmed) {
        flushList();
        const isHighlight = trimmed.startsWith("**Answer:") || trimmed.startsWith("Answer:");
        const pText = trimmed.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
        elements.push(
          <p
            key={`p-${idx}`}
            className={isHighlight ? "ans-hl" : ""}
            dangerouslySetInnerHTML={{ __html: pText }}
          />
        );
      }
    });
    flushList();
    return <div className="md chat-md">{elements}</div>;
  };

  // Computed daily net movement for the last 12 calendar days from real ledger entries
  const dailyMovement = useMemo(() => {
    if (!clientNow) {
      return Array.from({ length: 12 }, (_, idx) => ({
        dateStr: `day-${idx}`,
        label: "-",
        fullDate: "-",
        netPaise: 0,
        volumePaise: 0,
        heightPct: 6,
        isToday: idx === 11,
        hasActivity: false,
        tipText: "₹0.00",
      }));
    }

    const now = clientNow;
    const days: {
      dateStr: string;
      label: string;
      fullDate: string;
      netPaise: number;
      volumePaise: number;
    }[] = [];

    for (let i = 11; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(now.getDate() - i);
      const dateStr = d.toISOString().slice(0, 10);
      const label = d.toLocaleDateString("en-IN", { day: "numeric" });
      const fullDate = d.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
      days.push({ dateStr, label, fullDate, netPaise: 0, volumePaise: 0 });
    }

    // Aggregate postings from statements for active account
    for (const item of statements) {
      if (item.type !== "posting") continue;
      const itemDate = (item.at || "").slice(0, 10);
      const match = days.find((d) => d.dateStr === itemDate);
      if (match) {
        match.netPaise += item.amount;
        match.volumePaise += Math.abs(item.amount);
      }
    }

    const maxVolume = Math.max(...days.map((d) => d.volumePaise), 0);

    return days.map((d, idx) => {
      // Scale height between 6% (baseline) and 92% (peak daily volume)
      const heightPct =
        maxVolume > 0 && d.volumePaise > 0
          ? Math.min(92, Math.max(14, Math.round((d.volumePaise / maxVolume) * 85) + 7))
          : 6;

      const isToday = idx === 11;
      const hasActivity = d.volumePaise > 0;

      let tipText = `${d.fullDate} · ₹0.00`;
      if (d.netPaise > 0) {
        tipText = `${d.fullDate} · +${formatPaise(d.netPaise)}`;
      } else if (d.netPaise < 0) {
        tipText = `${d.fullDate} · -${formatPaise(Math.abs(d.netPaise))}`;
      } else if (d.volumePaise > 0) {
        tipText = `${d.fullDate} · Net ₹0 (Vol ${formatPaise(d.volumePaise)})`;
      }

      return {
        ...d,
        heightPct,
        isToday,
        hasActivity,
        tipText,
      };
    });
  }, [statements, clientNow]);

  // Allowed tabs per role
  const allowedTabs: TabType[] = useMemo(() => {
    if (!user) return ["dashboard"];
    if (user.role === "holder") return ["dashboard", "statement"];
    if (user.role === "auditor") return ["dashboard", "statement", "audit"];
    return ["dashboard", "statement", "audit", "admin"];
  }, [user]);

  // Clamp currentTab to allowedTabs whenever user or allowedTabs changes
  useEffect(() => {
    if (!allowedTabs.includes(currentTab)) {
      setCurrentTab("dashboard");
    }
  }, [allowedTabs, currentTab]);

  // Select demo role
  const selectDemoRole = (role: "holder" | "admin" | "auditor") => {
    if (!DEMO) return;
    setAuthRole(role);
    setAuthEmail(`${role === "holder" ? "holder1" : role}@ledgerline.internal`);
    setAuthPassword("DemoPassword123!");
  };

  // Map real AuditVerification report to 4-point health matrix checks
  const auditChecks = useMemo(() => {
    const discrepancies = auditResult?.discrepancies ?? [];
    const hashChainDiscrepancies = discrepancies.filter((d) =>
      ["sequence_continuity", "prev_hash_link", "entry_hash_integrity"].includes(d.check)
    );
    const balanceCacheDiscrepancies = discrepancies.filter((d) =>
      ["balance_cache_match", "empty_account_balance"].includes(d.check)
    );
    const zeroSumDiscrepancies = discrepancies.filter((d) => d.check === "journal_zero_sum");
    const globalConservationDiscrepancies = discrepancies.filter(
      (d) => d.check === "global_conservation"
    );

    return [
      {
        title: "SHA-256 hash chain",
        sub: "prev_hash → entry_hash",
        failed: simulatedTamper || (auditResult !== null && hashChainDiscrepancies.length > 0),
        detail: simulatedTamper
          ? "Simulated alteration on Block 2 (demo overlay)"
          : hashChainDiscrepancies.length > 0
          ? hashChainDiscrepancies.map((d) => d.message).join("; ")
          : undefined,
      },
      {
        title: "Balance cache parity",
        sub: "balance == balance_after",
        failed: auditResult !== null && balanceCacheDiscrepancies.length > 0,
        detail: balanceCacheDiscrepancies.length > 0
          ? balanceCacheDiscrepancies.map((d) => d.message).join("; ")
          : undefined,
      },
      {
        title: "Double-entry zero-sum",
        sub: "journal entries sum to 0",
        failed: auditResult !== null && zeroSumDiscrepancies.length > 0,
        detail: zeroSumDiscrepancies.length > 0
          ? zeroSumDiscrepancies.map((d) => d.message).join("; ")
          : undefined,
      },
      {
        title: "Global conservation",
        sub: "sum of all accounts = 0",
        failed: auditResult !== null && globalConservationDiscrepancies.length > 0,
        detail: globalConservationDiscrepancies.length > 0
          ? globalConservationDiscrepancies.map((d) => d.message).join("; ")
          : undefined,
      },
    ];
  }, [auditResult, simulatedTamper]);

  return (
    <div className={`app-root ${isCopilotOpen ? "cpo" : ""}`} data-theme={theme}>
      {/* Toast Overlay */}
      <div className="ts">
        {toasts.map((t) => (
          <div key={t.id} className={`t ${t.isError ? "e" : ""}`}>
            <b>{t.message}</b>
            {t.detail && <code>{t.detail}</code>}
          </div>
        ))}
      </div>

      {/* ====================================================================
          1. AUTH SCREEN (Matching reference app.html)
          ==================================================================== */}
      {!user ? (
        <div className="auth">
          <div className="al">
            <div className="fo">
              <a className="logo" style={{ fontSize: "20px", color: "var(--fg)" }} href="/">
                LedgerLine
              </a>
              <button
                className="tg"
                onClick={toggleTheme}
                aria-label="Toggle theme"
              >
                <svg
                  className="su"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                >
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
                </svg>
                <svg
                  className="mo"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinejoin="round"
                >
                  <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
                </svg>
              </button>
            </div>

            <form className="af c" onSubmit={handleLogin}>
              <h1>
                Sign in to <em>your ledger.</em>
              </h1>
              {DEMO ? (
                <>
                  <p className="sub">Pick a demo role to fill the credentials.</p>
                  <div className="seg">
                    <button
                      type="button"
                      className={authRole === "holder" ? "on" : ""}
                      onClick={() => selectDemoRole("holder")}
                    >
                      Holder
                    </button>
                    <button
                      type="button"
                      className={authRole === "admin" ? "on" : ""}
                      onClick={() => selectDemoRole("admin")}
                    >
                      Admin
                    </button>
                    <button
                      type="button"
                      className={authRole === "auditor" ? "on" : ""}
                      onClick={() => selectDemoRole("auditor")}
                    >
                      Auditor
                    </button>
                  </div>
                </>
              ) : (
                <p className="sub">Enter your credentials to access the ledger.</p>
              )}

              <label>
                Email
                <input
                  type="email"
                  value={authEmail}
                  onChange={(e) => setAuthEmail(e.target.value)}
                  required
                />
              </label>

              <label>
                Password
                <input
                  type="password"
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  required
                />
              </label>

              <button className="btn w" type="submit" disabled={loginLoading}>
                {loginLoading ? "Authenticating…" : "Sign in"}
              </button>
            </form>

            <div className="fo" />
          </div>

          <div className="ar">
            <video
              ref={videoRef}
              id="lv"
              className={videoFade ? "fo" : ""}
              muted
              playsInline
              preload="auto"
              poster="/app-poster.jpg"
              aria-hidden="true"
              src="/app-hero.mp4"
              onTimeUpdate={handleVideoTimeUpdate}
              onEnded={handleVideoEnded}
            />
            <div className="aq">
              <h2>
                Every rupee, <em>accounted for.</em>
              </h2>
            </div>
          </div>
        </div>
      ) : (
        /* ====================================================================
            2. APPLICATION SHELL & DASHBOARD
            ==================================================================== */
        <div id="app" className="app-main">
          <nav className="nv">
            <div className="wrap">
              <a className="logo" href="/">
                LedgerLine
              </a>

              <div className="tabs">
                {allowedTabs.map((tab) => (
                  <button
                    key={tab}
                    className={currentTab === tab ? "on" : ""}
                    onClick={() => setCurrentTab(tab)}
                  >
                    {tab[0]?.toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>

              <div className="rt">
                <button
                  className="btn o sm askb"
                  onClick={() => setIsCopilotOpen((prev) => !prev)}
                  aria-label="Ask Ledger AI"
                >
                  ✦ Ask AI
                </button>
                <span className="chip n">{user.role}</span>
                <button
                  className="tg"
                  onClick={toggleTheme}
                  aria-label="Toggle theme"
                >
                  <svg
                    className="su"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  >
                    <circle cx="12" cy="12" r="4" />
                    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
                  </svg>
                  <svg
                    className="mo"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinejoin="round"
                  >
                    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
                  </svg>
                </button>
                <button className="btn o sm" onClick={handleLogout}>
                  Sign out
                </button>
              </div>
            </div>
          </nav>

          <main className="wrap view">
            {/* VIEW A: DASHBOARD */}
            {currentTab === "dashboard" && (
              <>
                <div className="hd c">
                  <div>
                    <h2>Overview</h2>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                      <span style={{ fontSize: "13px", color: "var(--mut)" }}>Account:</span>
                      {accounts.length > 1 ? (
                        <select
                          value={activeAccount?.id}
                          onChange={(e) => {
                            const selected = accounts.find((a) => a.id === e.target.value);
                            if (selected) handleSelectAccount(selected);
                          }}
                          style={{
                            background: "var(--card)",
                            color: "var(--fg)",
                            border: "1px solid var(--border)",
                            padding: "4px 8px",
                            borderRadius: "6px",
                            fontFamily: "var(--mono)",
                            fontSize: "13px",
                            cursor: "pointer",
                          }}
                        >
                          {accounts.map((acc) => (
                            <option key={acc.id} value={acc.id}>
                              {acc.name} ({acc.number}) · {formatPaise(acc.balance)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <p style={{ margin: 0 }}>
                          Account {activeAccount?.number || "None"} · all figures from the server ledger
                        </p>
                      )}
                    </div>
                  </div>
                  {user.role !== "auditor" && (
                    <button className="btn" onClick={() => openMoveModal("transfer")}>
                      Move money
                    </button>
                  )}
                </div>

                {/* KPI Matrix */}
                <div className="kpi c" style={{ "--i": 1 } as React.CSSProperties}>
                  <div>
                    <small>Balance</small>
                    <b className="mono">
                      {formatPaise(activeAccount?.balance ?? 0)}
                    </b>
                  </div>
                  <div>
                    <small>Credits received</small>
                    <b className="mono" style={{ color: "var(--acc)" }}>
                      +{formatPaise(totalCredits)}
                    </b>
                  </div>
                  <div>
                    <small>Refused attempts</small>
                    <b className="mono">{refusalCount}</b>
                  </div>
                  <div>
                    <small>Debits sent</small>
                    <b className="mono" style={{ color: "var(--mut)" }}>
                      -{formatPaise(totalDebits)}
                    </b>
                  </div>
                </div>

                <div className="g2">
                  {/* Movement Chart */}
                  <div className="card c" style={{ "--i": 2 } as React.CSSProperties}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "6px" }}>
                      <h3>Net movement</h3>
                      <span className="chip" style={{ fontSize: "11px" }}>Live ledger</span>
                    </div>
                    <small>Daily, last 12 days (calculated from account transactions)</small>
                    <div className="chart">
                      {dailyMovement.map((d, i) => (
                        <i
                          key={`bar-${d.dateStr}-${i}`}
                          className={`${d.isToday ? "hi" : ""} ${d.netPaise < 0 ? "neg-net" : ""}`}
                          style={
                            {
                              "--h": `${d.heightPct}%`,
                              "--i": i,
                            } as React.CSSProperties
                          }
                        >
                          <span className="tip">
                            {d.tipText}
                          </span>
                        </i>
                      ))}
                    </div>
                    <div className="ax">
                      {dailyMovement.map((d) => (
                        <span key={`ax-${d.dateStr}`}>{d.label}</span>
                      ))}
                    </div>
                  </div>

                  {/* Account Card */}
                  <div className="c" style={{ "--i": 3 } as React.CSSProperties}>
                    <div className="acct">
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <small className="mono">{activeAccount?.number || "ACC-0001-A"}</small>
                        <span
                          className={`chip ${
                            activeAccount?.status === "frozen" ? "b" : ""
                          }`}
                        >
                          {activeAccount?.status === "frozen" ? "Frozen" : "Active"}
                        </span>
                      </div>
                      <div>
                        <small>Available balance</small>
                        <div className="big mono">
                          {formatPaise(activeAccount?.balance ?? 0)}
                        </div>
                        <small>
                          Overdraft limit {formatPaise(activeAccount?.overdraft_limit ?? 0)} · INR
                        </small>
                      </div>
                      {user.role === "auditor" ? (
                        <small>Read-only auditor access</small>
                      ) : (
                        <div className="acts">
                          <button onClick={() => openMoveModal("deposit")}>Deposit</button>
                          <button onClick={() => openMoveModal("withdraw")}>Withdraw</button>
                          <button onClick={() => openMoveModal("transfer")}>Transfer</button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Account Intelligence Card */}
                <div className="card c" style={{ "--i": 4, marginBottom: "18px" } as React.CSSProperties}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <h3>Account intelligence</h3>
                    <span className="chip n">AI · read-only</span>
                  </div>
                  <small>Computed from confirmed postings. It suggests, and never acts.</small>

                  <div className="in3">
                    <div className="st4">
                      <div>
                        <small>Available balance</small>
                        <b className="mono">
                          {accountInsights ? accountInsights.metrics.current_balance_formatted : formatPaise(activeAccount?.balance ?? 0)}
                        </b>
                        <span>Overdraft {accountInsights ? accountInsights.metrics.overdraft_limit_formatted : formatPaise(activeAccount?.overdraft_limit ?? 0)}</span>
                      </div>
                      <div>
                        <small>7-day net flow</small>
                        {(() => {
                          const cr7 = accountInsights ? accountInsights.metrics.last_7d_credits : localInsights.cr;
                          const db7 = accountInsights ? accountInsights.metrics.last_7d_debits : localInsights.db;
                          const diff = cr7 - db7;
                          return (
                            <>
                              <b className={`mono ${diff >= 0 ? "pos" : "neg"}`}>
                                {diff >= 0 ? "+" : "−"}{formatPaise(Math.abs(diff))}
                              </b>
                              <span>
                                {formatPaise(cr7)} in · {formatPaise(db7)} out
                              </span>
                            </>
                          );
                        })()}
                      </div>
                      <div>
                        <small>Average posting</small>
                        <b className="mono">
                          {accountInsights ? accountInsights.metrics.average_transaction_formatted : formatPaise(Math.round(localInsights.avg))}
                        </b>
                        <span>Across {accountInsights ? accountInsights.metrics.transaction_count : localInsights.n} postings</span>
                      </div>
                      <div>
                        <small>Transactions</small>
                        <b className="mono">
                          {accountInsights
                            ? accountInsights.metrics.transaction_count + accountInsights.metrics.refusal_count
                            : localInsights.n + localInsights.rf}
                        </b>
                        <span>{accountInsights ? accountInsights.metrics.refusal_count : localInsights.rf} refused</span>
                      </div>
                    </div>

                    {/* Risk score gauge */}
                    {(() => {
                      const score = accountInsights ? accountInsights.risk.score : localInsights.score;
                      const reasons = accountInsights ? accountInsights.risk.reasons : localInsights.reasons;
                      const badge = getRiskBadge(score);
                      return (
                        <div className="rkw">
                          <div className="eb">RISK SCORE</div>
                          {renderRiskGauge(score)}
                          <div className="lb mono" style={{ fontWeight: 600, fontSize: "12px", letterSpacing: ".08em", color: badge.color }}>
                            {badge.label}
                          </div>
                          <ul>
                            {reasons.map((r, idx) => (
                              <li key={idx}>{r}</li>
                            ))}
                          </ul>
                        </div>
                      );
                    })()}
                  </div>

                  {/* 4 Forecast Cards */}
                  {(() => {
                    const pj = accountInsights
                      ? accountInsights.forecast.projected_balance_30d_formatted
                      : formatPaise(Math.round(localInsights.pj));
                    const velText = accountInsights
                      ? accountInsights.forecast.daily_net_velocity_formatted
                      : `${localInsights.vel >= 0 ? "+" : "−"}${formatPaise(Math.abs(Math.round(localInsights.vel)))}/day`;
                    const velStatus = accountInsights
                      ? accountInsights.forecast.burn_status === "surplus"
                        ? "Surplus"
                        : "Net burn"
                      : localInsights.vel >= 0
                      ? "Surplus"
                      : "Net burn";
                    const rangeText = accountInsights
                      ? `${accountInsights.forecast.pessimistic_scenario_formatted} to ${accountInsights.forecast.optimistic_scenario_formatted}`
                      : `${formatPaise(Math.round(localInsights.lo))} to ${formatPaise(Math.round(localInsights.hi))}`;
                    const runwayText = accountInsights
                      ? accountInsights.forecast.runway_days === null
                        ? "Net surplus"
                        : `${accountInsights.forecast.runway_days} days`
                      : localInsights.run === null
                      ? "Net surplus"
                      : `${localInsights.run} days`;

                    return (
                      <div className="fcs">
                        <div>
                          <small>Projected · 30 days</small>
                          <b className="mono">{pj}</b>
                          <span>Expected</span>
                        </div>
                        <div>
                          <small>Daily velocity</small>
                          <b className="mono">{velText}</b>
                          <span>{velStatus}</span>
                        </div>
                        <div>
                          <small>Range</small>
                          <b className="mono">
                            {accountInsights
                              ? accountInsights.forecast.pessimistic_scenario_formatted
                              : formatPaise(Math.round(localInsights.lo))}
                          </b>
                          <span>
                            to {accountInsights
                              ? accountInsights.forecast.optimistic_scenario_formatted
                              : formatPaise(Math.round(localInsights.hi))}
                          </span>
                        </div>
                        <div>
                          <small>Runway</small>
                          <b className="mono">
                            {accountInsights
                              ? accountInsights.forecast.runway_days === null
                                ? "No limit"
                                : `${accountInsights.forecast.runway_days} days`
                              : localInsights.run === null
                              ? "No limit"
                              : `${localInsights.run} days`}
                          </b>
                          <span>
                            {(accountInsights
                              ? accountInsights.forecast.runway_days === null
                              : localInsights.run === null)
                              ? "Net surplus"
                              : "Until zero"}
                          </span>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Recent Activity Table */}
                <div className="card c" style={{ "--i": 5 } as React.CSSProperties}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "12px",
                    }}
                  >
                    <h3>Recent activity</h3>
                    <button
                      className="chip n"
                      onClick={() => setCurrentTab("statement")}
                      style={{ cursor: "pointer", border: 0 }}
                    >
                      View statement →
                    </button>
                  </div>

                  <div className="tbl">
                    <div className="tr h">
                      <div>Entry</div>
                      <div className="r">Amount</div>
                      <div className="r x">Balance after</div>
                      <div className="r x">Initiated by</div>
                    </div>
                    {statements.slice(0, 5).map((item) => {
                      const isRefusal = item.type === "refusal";
                      const isDebit = item.amount < 0;
                      return (
                        <div
                          key={`recent-${item.account_seq}`}
                          className={`tr ${isRefusal ? "rf" : ""}`}
                        >
                          <div>
                            <b>
                              {item.kind[0]?.toUpperCase() + item.kind.slice(1)}
                            </b>{" "}
                            {isRefusal ? (
                              <span className="chip b">Refused · {item.reason_code}</span>
                            ) : null}
                            <small className="mono">
                              #{item.account_seq} · {new Date(item.at).toLocaleDateString()}
                            </small>
                          </div>
                          <div className="r">
                            {isRefusal ? (
                              <span className="mono">{formatPaise(item.amount)}</span>
                            ) : (
                              <span
                                className={`mono ${isDebit ? "neg" : "pos"}`}
                              >
                                {isDebit ? "" : "+"}
                                {formatPaise(item.amount)}
                              </span>
                            )}
                          </div>
                          <div className="r x mono">
                            {formatPaise(item.balance_after ?? item.balance_at_attempt ?? 0)}
                          </div>
                          <div className="r x">{item.initiated_by.email.split("@")[0]}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            {/* VIEW B: STATEMENT */}
            {currentTab === "statement" && (
              <>
                <div className="hd c">
                  <div>
                    <h2>Statement</h2>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                      <span style={{ fontSize: "13px", color: "var(--mut)" }}>Account:</span>
                      {accounts.length > 1 ? (
                        <select
                          value={activeAccount?.id}
                          onChange={(e) => {
                            const selected = accounts.find((a) => a.id === e.target.value);
                            if (selected) handleSelectAccount(selected);
                          }}
                          style={{
                            background: "var(--card)",
                            color: "var(--fg)",
                            border: "1px solid var(--border)",
                            padding: "4px 8px",
                            borderRadius: "6px",
                            fontFamily: "var(--mono)",
                            fontSize: "13px",
                            cursor: "pointer",
                          }}
                        >
                          {accounts.map((acc) => (
                            <option key={acc.id} value={acc.id}>
                              {acc.name} ({acc.number}) · overdraft {formatPaise(acc.overdraft_limit)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <p className="mono" style={{ margin: 0 }}>
                          {activeAccount?.number} · {activeAccount?.name} · overdraft{" "}
                          {formatPaise(activeAccount?.overdraft_limit ?? 0)} ·{" "}
                          <span className="chip">
                            {activeAccount?.status === "frozen" ? "Frozen" : "Active"}
                          </span>
                        </p>
                      )}
                    </div>
                  </div>
                  {user.role !== "auditor" && (
                    <button className="btn" onClick={() => openMoveModal("transfer")}>
                      Move money
                    </button>
                  )}
                </div>

                <div className="card c" style={{ "--i": 1 } as React.CSSProperties}>
                  <div className="seg">
                    <button
                      className={statementFilter === "all" ? "on" : ""}
                      onClick={() => setStatementFilter("all")}
                    >
                      All
                    </button>
                    <button
                      className={statementFilter === "posting" ? "on" : ""}
                      onClick={() => setStatementFilter("posting")}
                    >
                      Postings
                    </button>
                    <button
                      className={statementFilter === "refusal" ? "on" : ""}
                      onClick={() => setStatementFilter("refusal")}
                    >
                      Refusals
                    </button>
                  </div>

                  <div className="tbl">
                    <div className="tr h">
                      <div>Entry</div>
                      <div className="r">Amount</div>
                      <div className="r x">Balance after</div>
                      <div className="r x">Initiated by</div>
                    </div>
                    {filteredStatements.map((item) => {
                      const isRefusal = item.type === "refusal";
                      const isDebit = item.amount < 0;
                      return (
                        <div
                          key={`stmt-${item.account_seq}`}
                          className={`tr ${isRefusal ? "rf" : ""}`}
                        >
                          <div>
                            <b>
                              {item.kind[0]?.toUpperCase() + item.kind.slice(1)}
                            </b>{" "}
                            {isRefusal ? (
                              <span className="chip b">Refused · {item.reason_code}</span>
                            ) : null}
                            <small className="mono">
                              #{item.account_seq} · {new Date(item.at).toLocaleString("en-IN")} ·{" "}
                              {item.request_id}
                            </small>
                          </div>
                          <div className="r">
                            {isRefusal ? (
                              <span className="mono">{formatPaise(item.amount)}</span>
                            ) : (
                              <span
                                className={`mono ${isDebit ? "neg" : "pos"}`}
                              >
                                {isDebit ? "" : "+"}
                                {formatPaise(item.amount)}
                              </span>
                            )}
                          </div>
                          <div className="r x mono">
                            {formatPaise(item.balance_after ?? item.balance_at_attempt ?? 0)}
                          </div>
                          <div className="r x">{item.initiated_by.email.split("@")[0]}</div>
                        </div>
                      );
                    })}
                  </div>
                  {statementHasMore && (
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "center",
                        marginTop: "16px",
                      }}
                    >
                      <button
                        className="btn o sm"
                        onClick={handleLoadMoreStatements}
                        disabled={loadingMore}
                      >
                        {loadingMore ? "Loading…" : "Load more entries"}
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* VIEW C: AUDIT EXPLORER */}
            {currentTab === "audit" && (
              <>
                <div className="hd c">
                  <div>
                    <h2>
                      Audit <em>explorer</em>
                    </h2>
                    <p>Recompute every hash and check conservation, on demand.</p>
                  </div>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button
                      className="btn o"
                      onClick={() => {
                        setSimulatedTamper((prev) => !prev);
                        addToast(
                          simulatedTamper
                            ? "Restored real hash chain."
                            : "Simulating database row alteration. Block 2 hash broken.",
                          !simulatedTamper
                        );
                      }}
                    >
                      {simulatedTamper ? "Restore chain" : "Simulate tampering"}
                    </button>
                    <button
                      className="btn"
                      onClick={handleRunVerification}
                      disabled={auditRunning}
                    >
                      {auditRunning ? "Running verification…" : "Run verification"}
                    </button>
                  </div>
                </div>

                {/* Hash Chain Blocks */}
                <div className="card c" style={{ "--i": 1 } as React.CSSProperties}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: "8px",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    <div>
                      <h3>Hash chain</h3>
                      <small>Each entry commits to the cryptographic hash of the one before it.</small>
                    </div>
                    {simulatedTamper && (
                      <span className="chip b" style={{ fontSize: "11px" }}>
                        Simulated alteration active (demo overlay)
                      </span>
                    )}
                  </div>
                  <div className="bl">
                    {statements.slice(0, 5).map((item, idx) => {
                      const isBad = simulatedTamper && idx === 1;
                      const prevHash = item.prev_hash
                        ? `${item.prev_hash.slice(0, 8)}…`
                        : "00000000…";
                      const entryHash = isBad
                        ? "deadbeef (altered)"
                        : item.entry_hash
                        ? `${item.entry_hash.slice(0, 8)}…`
                        : "pending…";
                      return (
                        <div
                          key={`block-${item.account_seq}-${idx}`}
                          className={`blk ${isBad ? "bad" : ""}`}
                        >
                          <b>
                            #{item.account_seq} {isBad ? "· altered" : ""}
                          </b>
                          <span className="mono">prev {prevHash}</span>
                          <span className="mono">hash {entryHash}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 4-Point Health Matrix */}
                <div
                  className="card c"
                  style={{ "--i": 2, marginTop: "18px" } as React.CSSProperties}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    <div>
                      <h3>Health matrix</h3>
                      <small>Driven by mathematical reconciliation from /audit/verify</small>
                    </div>
                    <span
                      className={`chip mono ${
                        auditRunning
                          ? "n"
                          : simulatedTamper || (auditResult && !auditResult.verified)
                          ? "b"
                          : auditResult?.verified
                          ? ""
                          : "n"
                      }`}
                    >
                      {auditRunning
                        ? "running…"
                        : simulatedTamper
                        ? "is_valid: false (tamper simulation)"
                        : auditResult
                        ? `verified: ${auditResult.verified}`
                        : "idle (click Run verification)"}
                    </span>
                  </div>

                  <div className="hm">
                    {auditChecks.map((check, i) => (
                      <div
                        key={`check-${i}`}
                        className={`hi2 ${
                          auditRunning ? "run" : check.failed ? "no" : "ok"
                        }`}
                      >
                        <div className="d">{check.failed ? "✕" : "✓"}</div>
                        <div>
                          <b>{check.title}</b>
                          <small>{check.detail || check.sub}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Conservation Summary Card */}
                <div
                  className="card c"
                  style={{ "--i": 3, marginTop: "18px" } as React.CSSProperties}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "8px",
                      flexWrap: "wrap",
                    }}
                  >
                    <h3>Conservation summary</h3>
                    <span className="chip">HELD</span>
                  </div>
                  <small>Global balance across customer and system accounts.</small>
                  <div style={{ marginTop: "14px" }}>
                    <div className="ac">
                      <div className="ar2">
                        <span>Conservation invariant</span>
                        <b className="chip">HELD</b>
                      </div>
                      <div className="ar2">
                        <span>Global balance sum</span>
                        <b className="mono">₹0.00</b>
                      </div>
                      <div className="ar2">
                        <span>Customer funds backed</span>
                        <b className="mono">
                          {formatPaise(auditResult?.customer_balance_sum ?? (activeAccount?.balance ?? 0))}
                        </b>
                      </div>
                      <div className="ar2">
                        <span>Journals · postings</span>
                        <b className="mono">
                          {auditResult?.total_journals_verified ?? statements.length} · {auditResult?.total_entries_verified ?? statements.length * 2}
                        </b>
                      </div>
                      <div className="ar2">
                        <span>Open surveillance flags</span>
                        <b className="mono">{reviewFlags.filter((f) => f.status === "pending").length}</b>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Surveillance Queue Card */}
                <div
                  className="card c"
                  style={{ "--i": 4, marginTop: "18px" } as React.CSSProperties}
                >
                  <h3>Surveillance queue</h3>
                  <small>Open flags. Admins decide; auditors read.</small>
                  <div style={{ marginTop: "12px" }}>
                    {reviewFlags.length > 0 ? (
                      reviewFlags.map((flag) => (
                        <div key={`aud-flag-${flag.id}`} className="fl" style={{ marginTop: "8px" }}>
                          <span className="chip a">{flag.rule_id}</span>
                          <p style={{ margin: "6px 0 0" }}>{flag.narrative || JSON.stringify(flag.evidence)}</p>
                        </div>
                      ))
                    ) : (
                      <p className="sm2" style={{ marginTop: "8px" }}>No open flags.</p>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* VIEW D: ADMIN OPERATIONS */}
            {currentTab === "admin" && user.role === "admin" && (
              <>
                <div className="hd c">
                  <div>
                    <h2>Operations</h2>
                    <p>Freeze accounts, adjust against suspense, review flags.</p>
                  </div>
                </div>

                <div className="g2">
                  {/* Accounts List & Freeze Toggle */}
                  <div className="card c" style={{ "--i": 1 } as React.CSSProperties}>
                    <h3>Accounts</h3>
                    <small>Frozen accounts refuse all movements</small>
                    <div className="tbl">
                      {accounts.map((acc) => (
                        <div
                          key={`admin-acc-${acc.id}`}
                          className="tr"
                          style={{ gridTemplateColumns: "2fr 1fr auto" }}
                        >
                          <div>
                            <b className="mono">{acc.number}</b>
                            <small>{acc.name}</small>
                          </div>
                          <div className="x">
                            <span
                              className={`chip ${
                                acc.status === "frozen" ? "b" : ""
                              }`}
                            >
                              {acc.status === "frozen" ? "Frozen" : "Active"}
                            </span>
                          </div>
                          <button
                            className={`sw ${acc.status !== "frozen" ? "on" : ""}`}
                            onClick={() => handleToggleFreeze(acc)}
                            aria-label="Toggle freeze"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Administrative Adjustment Form */}
                  <div className="card c" style={{ "--i": 2 } as React.CSSProperties}>
                    <h3>Adjustment</h3>
                    <small>Posts against SYS-SUSPENSE. Reason is mandatory.</small>
                    <form onSubmit={handlePostAdjustment} style={{ marginTop: "16px" }}>
                      <label>
                        Account
                        <select
                          value={adjAccount}
                          onChange={(e) => setAdjAccount(e.target.value)}
                        >
                          {accounts.map((a) => (
                            <option key={`opt-${a.id}`} value={a.number}>
                              {a.number} ({a.name})
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Signed amount (₹)
                        <input
                          value={adjAmount}
                          onChange={(e) => setAdjAmount(e.target.value)}
                          placeholder="-250.00"
                        />
                      </label>
                      <label>
                        Reason
                        <input
                          value={adjReason}
                          onChange={(e) => setAdjReason(e.target.value)}
                          placeholder="Correction of bank drift"
                          required
                        />
                      </label>
                      <button className="btn w" type="submit">
                        Post adjustment
                      </button>
                    </form>
                  </div>
                </div>

                {/* AI & Surveillance Review Queue */}
                <div className="card c" style={{ "--i": 3 } as React.CSSProperties}>
                  <h3>Review queue</h3>
                  <small>
                    Suggestions only. A person decides, and the decision is recorded.
                  </small>
                  {reviewFlags.length === 0 ? (
                    <p className="sm2" style={{ marginTop: "14px" }}>
                      No flags waiting for review.
                    </p>
                  ) : (
                    reviewFlags.map((flag) => (
                      <div key={`flag-${flag.id}`} className="fl">
                        <span className="chip a">{flag.rule_id}</span>
                        <p>{flag.narrative || "Unusual transaction pattern flagged by rules."}</p>
                        <div className="row">
                          <input
                            placeholder="Explanation (required)"
                            value={flagExplanations[flag.id] || ""}
                            onChange={(e) =>
                              setFlagExplanations((prev) => ({
                                ...prev,
                                [flag.id]: e.target.value,
                              }))
                            }
                          />
                          <button
                            className="btn sm"
                            onClick={() => handleReviewDecision(flag.id, "approved")}
                          >
                            Approve
                          </button>
                          <button
                            className="btn o sm"
                            onClick={() => handleReviewDecision(flag.id, "dismissed")}
                          >
                            Dismiss
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}
          </main>

          {/* Mobile Bottom Bar */}
          <div className="bb">
            {allowedTabs.map((tab) => (
              <button
                key={`bb-${tab}`}
                className={currentTab === tab ? "on" : ""}
                onClick={() => setCurrentTab(tab)}
              >
                {tab[0]?.toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ====================================================================
          3. MOVE MONEY MODAL
          ==================================================================== */}
      {isModalOpen && (
        <div className="md on" onClick={(e) => e.target === e.currentTarget && setIsModalOpen(false)}>
          <div className="mc">
            {modalStep === "form" && (
              <>
                <h3>Move money</h3>
                <div className="seg" style={{ marginBottom: "18px" }}>
                  <button
                    className={moveType === "transfer" ? "on" : ""}
                    onClick={() => setMoveType("transfer")}
                  >
                    Transfer
                  </button>
                  <button
                    className={moveType === "deposit" ? "on" : ""}
                    onClick={() => setMoveType("deposit")}
                  >
                    Deposit
                  </button>
                  <button
                    className={moveType === "withdraw" ? "on" : ""}
                    onClick={() => setMoveType("withdraw")}
                  >
                    Withdraw
                  </button>
                </div>

                {moveType === "transfer" ? (
                  <>
                    <label>
                      From account
                      <input
                        value={`${activeAccount?.name || "Account"} (${activeAccount?.number || ""}) · Balance: ${formatPaise(activeAccount?.balance ?? 0)}`}
                        disabled
                        style={{ opacity: 0.85 }}
                      />
                    </label>
                    <label>
                      To account number
                      <input
                        value={toAccountNum}
                        onChange={(e) => setToAccountNum(e.target.value)}
                        placeholder="e.g. 10XXXXXXXXXX"
                      />
                      {accounts.length > 1 && (
                        <span style={{ fontSize: "12px", color: "var(--mut)", marginTop: "6px", display: "block" }}>
                          Your other accounts:{" "}
                          {accounts
                            .filter((a) => a.id !== activeAccount?.id)
                            .map((a) => (
                              <button
                                key={`quick-dest-${a.id}`}
                                type="button"
                                onClick={() => setToAccountNum(a.number)}
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "var(--acc)",
                                  cursor: "pointer",
                                  padding: "0 4px",
                                  textDecoration: "underline",
                                  fontFamily: "monospace",
                                }}
                              >
                                {a.number} ({a.name})
                              </button>
                            ))}
                        </span>
                      )}
                    </label>
                  </>
                ) : (
                  <label>
                    {moveType === "deposit" ? "To" : "From"} account
                    <input
                      value={`${activeAccount?.name || "Account"} (${activeAccount?.number || ""}) · Balance: ${formatPaise(activeAccount?.balance ?? 0)}`}
                      disabled
                      style={{ opacity: 0.85 }}
                    />
                  </label>
                )}

                <label>
                  Amount
                  <div className="pre">
                    <span>₹</span>
                    <input
                      value={amountRupees}
                      onChange={(e) => setAmountRupees(e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                </label>

                <label>
                  Memo
                  <input
                    value={memo}
                    onChange={(e) => setMemo(e.target.value)}
                    placeholder="e.g. Lunch split or invoice"
                  />
                </label>

                <div className="mrow">
                  <button className="btn o" onClick={() => setIsModalOpen(false)}>
                    Cancel
                  </button>
                  <button className="btn" onClick={handleReviewMove}>
                    Review
                  </button>
                </div>
              </>
            )}

            {modalStep === "review" && (
              <>
                <h3>Review</h3>
                <div className="rv2">
                  <span>Type</span>
                  <b>{moveType[0]?.toUpperCase() + moveType.slice(1)}</b>
                </div>
                <div className="rv2">
                  <span>Account</span>
                  <b className="mono">{activeAccount?.number || "ACC-0001-A"}</b>
                </div>
                {moveType === "transfer" && (
                  <div className="rv2">
                    <span>To</span>
                    <b className="mono">{toAccountNum}</b>
                  </div>
                )}
                <div className="rv2">
                  <span>Amount</span>
                  <b className="mono">{formatPaise(parseRupeesToPaise(amountRupees) ?? 0)}</b>
                </div>
                <div className="rv2">
                  <span>Fee</span>
                  <b className="mono">₹0.00</b>
                </div>
                <div className="rv2">
                  <span>Idempotency-Key</span>
                  <b className="mono" style={{ fontSize: "11px" }}>
                    {idempotencyKey}
                  </b>
                </div>

                {moveAttempted && (
                  <p
                    className="sm2"
                    style={{
                      color: moveError?.includes("frozen") ? "var(--bad)" : "var(--mut)",
                      marginTop: "12px",
                      fontWeight: moveError?.includes("frozen") ? 600 : 400,
                    }}
                  >
                    {moveError || "Outcome unconfirmed: retry same request safely with identical Idempotency-Key."}
                  </p>
                )}

                <div className="mrow">
                  {moveAttempted ? (
                    <button className="btn o" onClick={() => setIsModalOpen(false)}>
                      Cancel
                    </button>
                  ) : (
                    <button className="btn o" onClick={() => setModalStep("form")}>
                      Back
                    </button>
                  )}
                  <button className="btn" onClick={handleExecuteMove}>
                    {moveAttempted ? "Retry same request" : "Confirm"}
                  </button>
                </div>
              </>
            )}

            {modalStep === "busy" && (
              <>
                <h3>Posting…</h3>
                <div className="sp" />
                <p className="sm2" style={{ textAlign: "center" }}>
                  Waiting for the confirmed ledger state. Balances never update optimistically.
                </p>
              </>
            )}

            {modalStep === "done" && moveResult && (
              <>
                <div className="res">
                  <span
                    className={`chip ${
                      moveResult.status === "posted"
                        ? ""
                        : moveResult.status === "replayed"
                        ? "a"
                        : "b"
                    }`}
                  >
                    {moveResult.status === "posted"
                      ? "Posted"
                      : moveResult.status === "replayed"
                      ? "Idempotent-Replayed: true"
                      : `Refused · ${moveResult.code}`}
                  </span>
                  <h3 className="mono">
                    {formatPaise(moveResult.amountPaise ?? 0)}
                  </h3>
                  <p className="sm2">
                    {moveResult.status === "replayed"
                      ? "Replayed. Not charged again."
                      : moveResult.status === "posted"
                      ? `Journal ${moveResult.journalId?.slice(0, 8)} · balance ${formatPaise(
                          moveResult.balanceAfter ?? 0
                        )}`
                      : "No money moved. The refusal is committed to your statement."}
                  </p>
                </div>

                <div className="rv2">
                  <span>Receipt</span>
                  <b className="mono">
                    IDEMPOTENCY VERIFIED · KEY {idempotencyKey.slice(0, 4)}…
                    {idempotencyKey.slice(-4)}
                  </b>
                </div>

                <div className="mrow">
                  {moveResult.status !== "refused" && (
                    <button className="btn o" onClick={handleExecuteMove}>
                      Retry same request
                    </button>
                  )}
                  <button className="btn" onClick={() => setIsModalOpen(false)}>
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ====================================================================
          3. LEDGER AI COPILOT & SURVEILLANCE DRAWER
          ==================================================================== */}
      {user && (
        <>
          <button
            className={`cpb ${isCopilotOpen ? "open" : ""}`}
            onClick={() => setIsCopilotOpen(false)}
            aria-label="Close assistant"
          />

          <aside className={`cp ${isCopilotOpen ? "open" : ""}`} aria-label="Ledger AI">
            <div className="ch">
              <div className="chl">
                <span className="mk">✦</span>
                <div>
                  <b>Ledger AI</b>
                  <small className="pvd">
                    <i />
                    {activeProvider}
                  </small>
                </div>
              </div>
              <div className="chr">
                <button
                  className="ib"
                  onClick={() => {
                    setChatMessages([]);
                    setSuggestedPills(DEFAULT_SUGGESTIONS);
                  }}
                  aria-label="New chat"
                  title="Reset conversation"
                >
                  ↺
                </button>
                <button
                  className="ib"
                  onClick={() => setIsCopilotOpen(false)}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="sh2">
              <span className="chip">I8</span>
              <p>
                <b>Read-only surveillance.</b> AI analyses and recommends. It can never authorise or move funds.
              </p>
            </div>

            <div className="cb" ref={chatScrollRef}>
              {chatMessages.length === 0 ? (
                <div className="ce">
                  <div className="mk">✦</div>
                  <h3>
                    Ask about your <em>ledger.</em>
                  </h3>
                  <p>
                    Search entries, forecast cash flow, and check risk. I read and explain. I never move money.
                  </p>
                  <div className="sg">
                    {DEFAULT_SUGGESTIONS.slice(0, 4).map((q, idx) => (
                      <button key={idx} onClick={() => handleSendChat(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                chatMessages.map((m) => (
                  <div key={m.id} className={`m ${m.role === "user" ? "u" : ""}`}>
                    {m.role === "assistant" && <span className="mk s">✦</span>}
                    {m.role === "user" ? (
                      <div className="bb2">{m.text}</div>
                    ) : (
                      <div className="ab">
                        {m.response?.reply && renderMarkdown(m.response.reply)}

                        {/* Dynamic Insight Cards */}
                        {m.response?.insights && m.response.insights.length > 0 && (
                          <div className="ig">
                            {m.response.insights.map((card, cIdx) => (
                              <div key={cIdx} className={`ic s-${card.sentiment || "neutral"}`}>
                                <small>{card.title}</small>
                                <b className="mono">{card.value}</b>
                                <span>{card.change}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* 1. Forecast Card (fcard) */}
                        {m.response?.data_payload?.forecast && (
                          <div className="ac fc">
                            <div className="eb">PROJECTED BALANCE · 30 DAYS</div>
                            <div className="bgn mono">
                              {m.response.data_payload.forecast.projected_balance_30d_formatted}
                            </div>
                            <span className={`chip ${m.response.data_payload.forecast.burn_status === "surplus" ? "" : "b"}`}>
                              {m.response.data_payload.forecast.velocity_label || m.response.data_payload.forecast.daily_net_velocity_formatted}
                            </span>
                            <div className="rng">
                              <i style={{ left: `${m.response.data_payload.forecast.range_percentage ?? 50}%` }} />
                            </div>
                            <div className="rl mono">
                              <span>Pessimistic {m.response.data_payload.forecast.pessimistic_scenario_formatted}</span>
                              <span>Optimistic {m.response.data_payload.forecast.optimistic_scenario_formatted}</span>
                            </div>
                            <p className="sm2" style={{ margin: "10px 0 0" }}>
                              Runway: {m.response.data_payload.forecast.runway_days === null ? "not at risk, net surplus" : `${m.response.data_payload.forecast.runway_days} days`}
                            </p>
                          </div>
                        )}

                        {/* 2. Embedded Risk Score Card (rcard) */}
                        {m.response?.risk_score !== undefined && m.response?.risk_score !== null && (m.response?.intent === "anomaly" || m.response.risk_score >= 35) && (
                          <div className="ac rkc">
                            {renderRiskGauge(m.response.risk_score)}
                            <div
                              className="lb mono"
                              style={{
                                color: getRiskBadge(m.response.risk_score).color,
                              }}
                            >
                              {m.response.risk_level || getRiskBadge(m.response.risk_score).label}
                            </div>
                            {m.response.risk_reasons && (
                              <ul>
                                {m.response.risk_reasons.map((r, rIdx) => (
                                  <li key={rIdx}>{r}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}

                        {/* 3. Ledger Search Card (scard) */}
                        {m.response?.data_payload?.search_results && m.response.data_payload.search_results.length > 0 && (
                          <div className="ac">
                            {m.response.data_payload.search_results.map((row: any, sIdx: number) => {
                              const isRef = !!row.is_refusal;
                              const isNeg = !isRef && row.amount < 0;
                              return (
                                <a
                                  key={sIdx}
                                  href="#statement"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    setCurrentTab("statement");
                                    setIsCopilotOpen(false);
                                  }}
                                  className={`sr ${isRef ? "rf" : ""}`}
                                >
                                  <div>
                                    <b>#{row.seq} · {row.kind || (isRef ? "Withdrawal" : "Posting")}</b>
                                    {isRef && <span className="chip b" style={{ marginLeft: "6px" }}>Refused · {row.reason || "declined"}</span>}
                                    <small>
                                      {row.memo ? `${row.memo} · ` : ""}
                                      {row.balance_after_formatted ? `Balance after ${row.balance_after_formatted}` : "Refusal committed"}
                                    </small>
                                  </div>
                                  <b className={`mono ${isRef ? "" : isNeg ? "neg" : "pos"}`}>
                                    {isRef ? row.amount_formatted : `${isNeg ? "−" : "+"}${row.amount_formatted}`}
                                  </b>
                                </a>
                              );
                            })}
                          </div>
                        )}

                        {/* 4. Global Reconciliation Card (ccard) */}
                        {Boolean(m.response?.data_payload?.reconciliation && (m.response?.intent === "reconciliation" || !activeAccount)) && (
                          <div className="ac">
                            <div className="ar2">
                              <span>Conservation invariant</span>
                              <b className="chip">HELD</b>
                            </div>
                            <div className="ar2">
                              <span>Global balance sum</span>
                              <b className="mono">₹0.00</b>
                            </div>
                            <div className="ar2">
                              <span>Customer funds backed</span>
                              <b className="mono">{m.response?.data_payload?.reconciliation?.total_customer_funds_formatted}</b>
                            </div>
                            <div className="ar2">
                              <span>Journals · postings</span>
                              <b className="mono">
                                {m.response?.data_payload?.reconciliation?.total_journals} · {m.response?.data_payload?.reconciliation?.total_ledger_entries}
                              </b>
                            </div>
                            <div className="ar2">
                              <span>Open surveillance flags</span>
                              <b className="mono">{m.response?.data_payload?.reconciliation?.open_surveillance_flags}</b>
                            </div>
                          </div>
                        )}

                        {/* Tool tag chip */}
                        <div className="tcs">
                          <span className="chip n mono">{m.tool || "read-only · intelligence"}</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}

              {/* Loading / Thinking dots */}
              {isChatThinking && (
                <div className="m">
                  <span className="mk s">✦</span>
                  <div className="dt">
                    <i />
                    <i />
                    <i />
                  </div>
                </div>
              )}
            </div>

            {/* Suggested Query Pills */}
            {chatMessages.length > 0 && suggestedPills.length > 0 && (
              <div className="pl">
                {suggestedPills.map((q, pIdx) => (
                  <button key={pIdx} onClick={() => handleSendChat(q)}>
                    {q}
                  </button>
                ))}
              </div>
            )}

            {/* Chat Form */}
            <form
              className="cf"
              onSubmit={(e) => {
                e.preventDefault();
                handleSendChat();
              }}
            >
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask about transfers, refusals, forecast…"
                autoComplete="off"
                enterKeyHint="send"
                disabled={isChatThinking}
              />
              <button className="send2" aria-label="Send" disabled={isChatThinking || !chatInput.trim()}>
                ↑
              </button>
            </form>
            <p className="cn">AI can be wrong. The statement is the source of truth.</p>
          </aside>

          {/* Mobile FAB button */}
          <button
            className="fab"
            onClick={() => setIsCopilotOpen(true)}
            aria-label="Ask Ledger AI"
          >
            ✦
          </button>
        </>
      )}
    </div>
  );
}
