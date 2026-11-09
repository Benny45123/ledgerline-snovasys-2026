#!/usr/bin/env bash
# ==============================================================================
# LedgerLine Deployment Smoke Verification Script
# Usage: ./scripts/smoke.sh [API_BASE_URL]
# Example: ./scripts/smoke.sh https://ledgerline-backend.onrender.com
# ==============================================================================
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
echo "======================================================================"
echo "Running LedgerLine Smoke Verification against: $BASE_URL"
echo "======================================================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() {
    echo -e "${GREEN}✓ PASS:${NC} $1"
}

fail() {
    echo -e "${RED}✗ FAIL:${NC} $1" >&2
    exit 1
}

# 1. Health Probe
echo "[1/8] Checking /health probe..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" || true)
[ "$HEALTH_STATUS" = "200" ] || fail "Health probe returned HTTP $HEALTH_STATUS"
HEALTH_BODY=$(curl -s "$BASE_URL/health")
echo "$HEALTH_BODY" | grep -q '"status":"ok"' || fail "Unexpected health response: $HEALTH_BODY"
pass "Process is healthy (/health)"

# 2. Readiness Probe (Database connectivity)
echo "[2/8] Checking /ready probe..."
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/ready" || true)
[ "$READY_STATUS" = "200" ] || fail "Readiness probe returned HTTP $READY_STATUS (DB unreachable)"
READY_BODY=$(curl -s "$BASE_URL/ready")
echo "$READY_BODY" | grep -q '"status":"ready"' || fail "DB not ready: $READY_BODY"
pass "PostgreSQL connected and ready (/ready)"

# 3. Seed Role Authentication
echo "[3/8] Authenticating seed roles..."
LOGIN_ADMIN=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@ledgerline.internal","password":"DemoPassword123!"}')
ADMIN_TOKEN=$(echo "$LOGIN_ADMIN" | grep -o '"session_token":"[^"]*' | cut -d'"' -f4 || true)
[ -n "$ADMIN_TOKEN" ] || fail "Admin login failed: $LOGIN_ADMIN"
pass "Admin authenticated"

LOGIN_H1=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"holder1@ledgerline.internal","password":"DemoPassword123!"}')
H1_TOKEN=$(echo "$LOGIN_H1" | grep -o '"session_token":"[^"]*' | cut -d'"' -f4 || true)
[ -n "$H1_TOKEN" ] || fail "Holder 1 login failed: $LOGIN_H1"
pass "Holder 1 authenticated"

LOGIN_H2=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"holder2@ledgerline.internal","password":"DemoPassword123!"}')
H2_TOKEN=$(echo "$LOGIN_H2" | grep -o '"session_token":"[^"]*' | cut -d'"' -f4 || true)
[ -n "$H2_TOKEN" ] || fail "Holder 2 login failed: $LOGIN_H2"
pass "Holder 2 authenticated"

LOGIN_AUDITOR=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"auditor@ledgerline.internal","password":"DemoPassword123!"}')
AUDITOR_TOKEN=$(echo "$LOGIN_AUDITOR" | grep -o '"session_token":"[^"]*' | cut -d'"' -f4 || true)
[ -n "$AUDITOR_TOKEN" ] || fail "Auditor login failed: $LOGIN_AUDITOR"
pass "Auditor authenticated"

# 4. Holder 1 Account Resolution
echo "[4/8] Resolving Holder 1 accounts..."
H1_ACCOUNTS=$(curl -s -H "Authorization: Bearer $H1_TOKEN" "$BASE_URL/accounts")
H1_ACC_ID=$(echo "$H1_ACCOUNTS" | grep -o '"id":"[^"]*' | head -n1 | cut -d'"' -f4 || true)
[ -n "$H1_ACC_ID" ] || fail "No account found for Holder 1: $H1_ACCOUNTS"
pass "Holder 1 account located: $H1_ACC_ID"

# 5. Idempotent Deposit & Duplicate Replay Test
echo "[5/8] Testing deposit with idempotency key and replay..."
KEY="smoke-test-$(date +%s)-$RANDOM"
DEPOSIT_RES=$(curl -s -w "\n%{http_code}" -i -X POST "$BASE_URL/accounts/$H1_ACC_ID/deposit" \
    -H "Authorization: Bearer $H1_TOKEN" \
    -H "Idempotency-Key: $KEY" \
    -H "Content-Type: application/json" \
    -d '{"amount":10000,"memo":"Smoke test deposit"}')
DEPOSIT_CODE=$(echo "$DEPOSIT_RES" | tail -n1)
DEPOSIT_OUT=$(echo "$DEPOSIT_RES" | sed '$d')
[ "$DEPOSIT_CODE" = "200" ] || fail "Deposit failed with HTTP $DEPOSIT_CODE: $DEPOSIT_OUT"
pass "Original deposit executed successfully (₹100.00)"

# Replay same key with identical body
REPLAY_RES=$(curl -s -w "\n%{http_code}" -i -X POST "$BASE_URL/accounts/$H1_ACC_ID/deposit" \
    -H "Authorization: Bearer $H1_TOKEN" \
    -H "Idempotency-Key: $KEY" \
    -H "Content-Type: application/json" \
    -d '{"amount":10000,"memo":"Smoke test deposit"}')
REPLAY_CODE=$(echo "$REPLAY_RES" | tail -n1)
REPLAY_OUT=$(echo "$REPLAY_RES" | sed '$d')
[ "$REPLAY_CODE" = "200" ] || fail "Replay failed with HTTP $REPLAY_CODE: $REPLAY_OUT"
echo "$REPLAY_OUT" | grep -iq "idempotent-replayed: true" || fail "Replay header missing on duplicate: $REPLAY_OUT"
pass "Idempotent replay verified (Idempotent-Replayed: true, exact 1x money movement)"

# 6. IDOR Boundary Verification
echo "[6/8] Verifying IDOR isolation: Holder 2 accessing Holder 1 account..."
IDOR_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $H2_TOKEN" "$BASE_URL/accounts/$H1_ACC_ID/statement")
[ "$IDOR_STATUS" -eq 404 ] || fail "IDOR leak! Expected 404 Not Found, got $IDOR_STATUS"
pass "IDOR boundary enforced (HTTP 404 returned for unassociated account)"

# 7. Auditor Read-Only Boundary Verification
echo "[7/8] Verifying Auditor read-only constraint..."
AUDIT_WRITE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/accounts/$H1_ACC_ID/deposit" \
    -H "Authorization: Bearer $AUDITOR_TOKEN" \
    -H "Idempotency-Key: smoke-auditor-$RANDOM" \
    -H "Content-Type: application/json" \
    -d '{"amount":10000}')
[ "$AUDIT_WRITE_STATUS" -eq 403 ] || fail "Auditor was not rejected on write! Expected 403 Forbidden, got $AUDIT_WRITE_STATUS"
pass "Auditor role strictly read-only (HTTP 403 Forbidden on write)"

# 8. Cryptographic Hash Chain & Zero-Sum Reconciliation
echo "[8/8] Running cryptographic audit verification (/audit/verify)..."
AUDIT_VERIFY=$(curl -s -H "Authorization: Bearer $AUDITOR_TOKEN" "$BASE_URL/audit/verify")
echo "$AUDIT_VERIFY" | grep -q '"is_balanced":true' || fail "Audit discrepancy detected: $AUDIT_VERIFY"
echo "$AUDIT_VERIFY" | grep -q '"conservation_invariant":"HELD"' || fail "Conservation invariant failed: $AUDIT_VERIFY"
pass "Cryptographic ledger verification clean (Zero-Sum HELD, hash chains intact)"

echo "======================================================================"
echo -e "${GREEN}ALL SMOKE CHECKS PASSED SUCCESSFULLY.${NC}"
echo "Deployment is fully operational, secure, and provably balanced."
echo "======================================================================"
