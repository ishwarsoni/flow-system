#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  FLOW Pre-Launch Security Gate
#  Run ON THE PRODUCTION SERVER after setup_production.sh.
#  Exits non-zero (blocks launch) if ANY check fails.
#
#  Usage:  sudo bash pre_launch_gate.sh <your-domain.com>
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

DOMAIN="${1:?Usage: $0 <your-domain.com>}"
BACKEND_DIR="/opt/flow/backend"
FAIL=0

pass() { echo "  ✅ PASS: $1"; }
fail() { echo "  ❌ FAIL: $1"; FAIL=1; }
section() { echo ""; echo "═══ $1 ═══"; }

# ───────────────────────────────────────────────────────────────────────────────
section "1. PORT & FIREWALL CHECK"
# ───────────────────────────────────────────────────────────────────────────────

# UFW must be active
if ufw status | grep -q "Status: active"; then
    pass "UFW firewall is active"
else
    fail "UFW firewall is NOT active"
fi

# Only 22, 80, 443 should be allowed
ALLOWED_PORTS=$(ufw status | grep "ALLOW" | grep -oP '^\S+' | sort -u)
for port in $ALLOWED_PORTS; do
    case "$port" in
        22|22/tcp|80|80/tcp|443|443/tcp|"Nginx"|"Nginx Full"|"OpenSSH") ;;
        *) fail "Unexpected UFW rule: $port" ;;
    esac
done
pass "UFW rules reviewed"

# Backend must bind to 127.0.0.1 only
if ss -tuln | grep ":8000" | grep -q "127.0.0.1"; then
    pass "Backend (8000) bound to 127.0.0.1 only"
else
    if ss -tuln | grep -q ":8000"; then
        fail "Backend (8000) is listening on 0.0.0.0 — must bind to 127.0.0.1"
    else
        fail "Backend (8000) is not running"
    fi
fi

# Redis must bind to 127.0.0.1 only
if ss -tuln | grep ":6379" | grep -q "127.0.0.1"; then
    pass "Redis (6379) bound to 127.0.0.1 only"
else
    if ss -tuln | grep -q ":6379"; then
        fail "Redis (6379) is listening on 0.0.0.0 — must bind to 127.0.0.1"
    else
        fail "Redis (6379) is not running"
    fi
fi

# No Postgres unless expected
if ss -tuln | grep -q ":5432"; then
    if ss -tuln | grep ":5432" | grep -q "127.0.0.1"; then
        pass "Postgres (5432) bound to 127.0.0.1"
    else
        fail "Postgres (5432) on 0.0.0.0 — must bind to 127.0.0.1"
    fi
else
    pass "No Postgres listening (SQLite mode — OK)"
fi

# External nmap self-scan (if nmap installed)
if command -v nmap &>/dev/null; then
    echo "  Running nmap self-scan on $DOMAIN..."
    OPEN_PORTS=$(nmap -Pn -p 1-10000 "$DOMAIN" 2>/dev/null | grep "open" | grep -v "80/tcp\|443/tcp" || true)
    if [ -z "$OPEN_PORTS" ]; then
        pass "nmap: only 80/443 open externally"
    else
        fail "nmap: unexpected open ports: $OPEN_PORTS"
    fi
else
    echo "  ⚠️  nmap not installed — install with: apt install nmap"
    echo "     Run manually: nmap -Pn -p 1-10000 $DOMAIN"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "2. SECRET ROTATION"
# ───────────────────────────────────────────────────────────────────────────────

ENV_FILE="$BACKEND_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    # SECRET_KEY must be at least 32 chars
    SK=$(grep "^SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2)
    if [ ${#SK} -ge 32 ]; then
        pass "SECRET_KEY length OK (${#SK} chars)"
    else
        fail "SECRET_KEY too short (${#SK} chars, need ≥32)"
    fi

    # No default/known-leaked keys
    if echo "$SK" | grep -q "changeme\|secret\|password\|test\|example"; then
        fail "SECRET_KEY contains a known weak pattern"
    else
        pass "SECRET_KEY doesn't match weak patterns"
    fi

    # DEBUG must be False
    DEBUG_VAL=$(grep "^DEBUG=" "$ENV_FILE" | cut -d'=' -f2)
    if [ "$DEBUG_VAL" = "False" ] || [ "$DEBUG_VAL" = "false" ]; then
        pass "DEBUG=False"
    else
        fail "DEBUG is not False (got: $DEBUG_VAL)"
    fi

    # REDIS_URL must be set
    REDIS_URL=$(grep "^REDIS_URL=" "$ENV_FILE" | cut -d'=' -f2)
    if [ -n "$REDIS_URL" ]; then
        pass "REDIS_URL is set"
    else
        fail "REDIS_URL is empty — required in production"
    fi

    # ALLOWED_ORIGINS must not contain localhost
    ORIGINS=$(grep "^ALLOWED_ORIGINS=" "$ENV_FILE" | cut -d'=' -f2-)
    if echo "$ORIGINS" | grep -q "localhost\|127.0.0.1\|192.168"; then
        fail "ALLOWED_ORIGINS contains localhost/private IPs — update for production"
    else
        pass "ALLOWED_ORIGINS has no localhost entries"
    fi

    # GROQ_API_KEY should not be the dev key in prod
    GROQ=$(grep "^GROQ_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 || true)
    if [ -n "$GROQ" ]; then
        pass "GROQ_API_KEY is set (verify it's the production key)"
    fi
else
    fail ".env file not found at $ENV_FILE"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "3. TLS & HTTPS"
# ───────────────────────────────────────────────────────────────────────────────

# Check HTTPS responds
if curl -sI "https://$DOMAIN" | head -1 | grep -q "200\|301\|302"; then
    pass "HTTPS responds on $DOMAIN"
else
    fail "HTTPS not responding on $DOMAIN"
fi

# HTTP must redirect to HTTPS
HTTP_STATUS=$(curl -sI -o /dev/null -w "%{http_code}" "http://$DOMAIN" || echo "000")
if [ "$HTTP_STATUS" = "301" ]; then
    pass "HTTP → HTTPS redirect (301)"
else
    fail "HTTP not redirecting to HTTPS (got $HTTP_STATUS)"
fi

# Check HSTS header
HSTS=$(curl -sI "https://$DOMAIN" | grep -i "strict-transport-security" || true)
if [ -n "$HSTS" ]; then
    pass "HSTS header present"
else
    fail "HSTS header missing"
fi

# Check certificate validity
CERT_EXPIRY=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN":443 2>/dev/null | openssl x509 -noout -dates 2>/dev/null | grep "notAfter" | cut -d= -f2 || true)
if [ -n "$CERT_EXPIRY" ]; then
    pass "TLS cert valid until: $CERT_EXPIRY"
else
    fail "Cannot read TLS certificate"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "4. SECURITY HEADERS"
# ───────────────────────────────────────────────────────────────────────────────

HEADERS=$(curl -sI "https://$DOMAIN/api/auth/me" 2>/dev/null || true)

check_header() {
    local name="$1"
    if echo "$HEADERS" | grep -qi "$name"; then
        pass "Header: $name"
    else
        fail "Missing header: $name"
    fi
}

check_header "X-Content-Type-Options"
check_header "X-Frame-Options"
check_header "Strict-Transport-Security"
check_header "Content-Security-Policy"
check_header "Referrer-Policy"
check_header "Permissions-Policy"
check_header "X-Permitted-Cross-Domain-Policies"

# Server header should NOT be present
if echo "$HEADERS" | grep -qi "^server: uvicorn\|^server: gunicorn\|^server: python"; then
    fail "Server identity leaked in headers"
else
    pass "No server identity leak"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "5. ENDPOINT EXPOSURE"
# ───────────────────────────────────────────────────────────────────────────────

# Docs must be disabled
for path in /docs /redoc /openapi.json; do
    STATUS=$(curl -sI -o /dev/null -w "%{http_code}" "https://$DOMAIN$path" || echo "000")
    if [ "$STATUS" = "404" ] || [ "$STATUS" = "405" ]; then
        pass "$path returns $STATUS (disabled)"
    else
        fail "$path returns $STATUS (should be 404)"
    fi
done

# Root should not leak version
ROOT_BODY=$(curl -s "https://$DOMAIN/" || true)
if echo "$ROOT_BODY" | grep -q "version"; then
    fail "Root endpoint leaks version info"
else
    pass "Root endpoint: no version leak"
fi

# Health endpoint should work
HEALTH=$(curl -s "https://$DOMAIN/health" || true)
if echo "$HEALTH" | grep -q '"db"'; then
    pass "Health endpoint reports DB status"
else
    fail "Health endpoint missing DB status"
fi
if echo "$HEALTH" | grep -q '"redis"'; then
    pass "Health endpoint reports Redis status"
else
    fail "Health endpoint missing Redis status"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "6. SCHEMA VALIDATION (extra=forbid)"
# ───────────────────────────────────────────────────────────────────────────────

SCHEMA_STATUS=$(curl -sI -o /dev/null -w "%{http_code}" -X POST "https://$DOMAIN/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@x.com","password":"x","INJECTED":"evil"}' || echo "000")
if [ "$SCHEMA_STATUS" = "422" ]; then
    pass "Unknown fields rejected (422)"
else
    fail "Unknown fields not rejected (got $SCHEMA_STATUS, expected 422)"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "7. RATE LIMITING"
# ───────────────────────────────────────────────────────────────────────────────

echo "  Sending 10 rapid login requests..."
RATE_LIMITED=0
for i in $(seq 1 10); do
    STATUS=$(curl -sI -o /dev/null -w "%{http_code}" -X POST "https://$DOMAIN/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"ratetest@x.com","password":"x"}' || echo "000")
    if [ "$STATUS" = "429" ]; then
        RATE_LIMITED=1
        break
    fi
done
if [ "$RATE_LIMITED" = "1" ]; then
    pass "Rate limiting active (429 after $i requests)"
else
    fail "Rate limiting not triggered after 10 rapid requests"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "8. DIRECT BACKEND ACCESS"
# ───────────────────────────────────────────────────────────────────────────────

# Port 8000 must not be accessible externally
DIRECT=$(curl -sI --connect-timeout 3 -o /dev/null -w "%{http_code}" "http://$DOMAIN:8000/" 2>/dev/null || echo "000")
if [ "$DIRECT" = "000" ]; then
    pass "Port 8000 not externally accessible"
else
    fail "Port 8000 is externally accessible (got $DIRECT)"
fi

# Redis port
REDIS_DIRECT=$(curl -sI --connect-timeout 3 -o /dev/null -w "%{http_code}" "http://$DOMAIN:6379/" 2>/dev/null || echo "000")
if [ "$REDIS_DIRECT" = "000" ]; then
    pass "Port 6379 (Redis) not externally accessible"
else
    fail "Port 6379 (Redis) is externally accessible!"
fi

# ───────────────────────────────────────────────────────────────────────────────
section "9. SERVICE HEALTH"
# ───────────────────────────────────────────────────────────────────────────────

# Systemd services
for svc in flow redis-server nginx; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        pass "$svc service is running"
    else
        fail "$svc service is NOT running"
    fi
done

# ═══════════════════════════════════════════════════════════════════════════════
section "FINAL VERDICT"
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "  🟢 ALL CHECKS PASSED — FLOW is safe for public exposure."
    echo ""
    exit 0
else
    echo ""
    echo "  🔴 ONE OR MORE CHECKS FAILED — LAUNCH BLOCKED."
    echo "  Fix all ❌ items above before going public."
    echo ""
    exit 1
fi
