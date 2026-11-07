#!/usr/bin/env bash
# ==============================================================================
# Universal Zero-Trust Network Confinement Verification Script
# Runs inside the isolated container to confirm network boundaries.
# Zero external package dependencies (no 'nc' or 'netcat' required).
# Uses native Bash /dev/tcp with Python 3 socket fallback.
# ==============================================================================
set -u

PROXY_IP="${PROXY_IP:-172.28.0.1}"
PROXY_PORT="${PROXY_PORT:-8888}"
TIMEOUT_SEC=2

TOTAL_TESTS=4
PASSED_TESTS=0
FAILED_TESTS=0

echo "=========================================================="
echo "      Zero-Trust Container Confinement Verification       "
echo "=========================================================="
echo "Target Proxy: ${PROXY_IP}:${PROXY_PORT}"
echo ""

# Portable TCP connection checker without netcat
test_tcp_connection() {
    local host="$1"
    local port="$2"
    local timeout_val="${3:-2}"

    if command -v timeout >/dev/null 2>&1; then
        timeout "${timeout_val}" bash -c "exec 3<>/dev/tcp/${host}/${port}" 2>/dev/null
        return $?
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "import socket; s = socket.socket(); s.settimeout(${timeout_val}); s.connect(('${host}', int(${port}))); s.close()" 2>/dev/null
        return $?
    else
        # Subshell background with kill fallback
        ( exec 3<>/dev/tcp/"${host}"/"${port}" ) 2>/dev/null &
        local pid=$!
        local count=0
        while kill -0 "${pid}" 2>/dev/null; do
            sleep 0.2
            count=$((count + 1))
            if [ "${count}" -ge $((timeout_val * 5)) ]; then
                kill "${pid}" 2>/dev/null || true
                return 1
            fi
        done
        wait "${pid}" 2>/dev/null
        return $?
    fi
}

# ------------------------------------------------------------------------------
# Test 1: Direct WAN Egress (Must Fail)
# ------------------------------------------------------------------------------
echo -n "[1/4] Testing direct external WAN egress (https://1.1.1.1)... "
if curl -s -k --connect-timeout "${TIMEOUT_SEC}" --max-time "${TIMEOUT_SEC}" https://1.1.1.1 >/dev/null 2>&1; then
    echo "FAILED! (CRITICAL LEAK: Direct internet egress is allowed)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
else
    echo "PASSED (Egress blocked by iptables)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# ------------------------------------------------------------------------------
# Test 2: External DNS Port 53 Egress (Must Fail)
# ------------------------------------------------------------------------------
echo -n "[2/4] Testing external DNS port 53 query (8.8.8.8:53)... "
if test_tcp_connection 8.8.8.8 53 "${TIMEOUT_SEC}"; then
    echo "FAILED! (CRITICAL LEAK: Port 53 DNS accessible outside proxy)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
else
    echo "PASSED (Port 53 blocked by iptables)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# ------------------------------------------------------------------------------
# Test 3: Host SSH Port 22 Access (Must Fail)
# ------------------------------------------------------------------------------
echo -n "[3/4] Testing host SSH access (${PROXY_IP}:22)... "
if test_tcp_connection "${PROXY_IP}" 22 "${TIMEOUT_SEC}"; then
    echo "FAILED! (SECURITY HAZARD: Host SSH port 22 reachable from container)"
    FAILED_TESTS=$((FAILED_TESTS + 1))
else
    echo "PASSED (Host SSH blocked by iptables)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
fi

# ------------------------------------------------------------------------------
# Test 4: Local MITM Proxy Endpoint (Must Succeed)
# ------------------------------------------------------------------------------
echo -n "[4/4] Testing MITM forward proxy endpoint (${PROXY_IP}:${PROXY_PORT})... "
if test_tcp_connection "${PROXY_IP}" "${PROXY_PORT}" "${TIMEOUT_SEC}"; then
    echo "PASSED (Proxy reachable)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "WARNING (Proxy port ${PROXY_PORT} closed on host or proxy daemon not yet listening)"
fi

echo ""
echo "=========================================================="
echo "Verification Summary: ${PASSED_TESTS}/${TOTAL_TESTS} security boundaries enforced."
if [ "${FAILED_TESTS}" -gt 0 ]; then
    echo "[!] VERIFICATION FAILED: Egress leaks detected."
    exit 1
else
    echo "[✓] VERIFICATION PASSED: Zero-trust containment verified."
    exit 0
fi
