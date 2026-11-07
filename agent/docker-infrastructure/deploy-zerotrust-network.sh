#!/usr/bin/env bash
# ==============================================================================
# Universal Zero-Trust Ephemeral Playwright Network Configuration
# Supported Distros: Ubuntu, Debian, RHEL, CentOS, Rocky Linux, AlmaLinux, Arch, Alpine
# Supported Runtimes: Docker, Podman
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configurable Parameters & Defaults (Overridable via Environment)
# ------------------------------------------------------------------------------
NETWORK_NAME="${NETWORK_NAME:-playwright-net}"
BRIDGE_IF="${BRIDGE_IF:-br-playwright}"
SUBNET="${SUBNET:-172.28.0.0/16}"
GATEWAY_IP="${GATEWAY_IP:-172.28.0.1}"
PROXY_PORT="${PROXY_PORT:-8888}"

# Interface name validation (Linux IFNAMSIZ is 16 chars including null byte)
if [[ ${#BRIDGE_IF} -gt 15 ]]; then
    echo "[!] Error: BRIDGE_IF '${BRIDGE_IF}' exceeds Linux maximum of 15 characters." >&2
    exit 1
fi

# Require root privileges for firewall configuration
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "[!] Error: This script must be executed as root (or with sudo)." >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Container Runtime Detection (Docker / Podman)
# ------------------------------------------------------------------------------
RUNTIME=""
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    RUNTIME="docker"
elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    RUNTIME="podman"
else
    echo "[!] Error: No active container runtime detected. Please start Docker or Podman." >&2
    exit 1
fi
echo "[+] Detected active container runtime: ${RUNTIME}"

# ------------------------------------------------------------------------------
# 3. Create Isolated Container Bridge Network
# ------------------------------------------------------------------------------
echo "[+] Step 1: Configuring isolated bridge network: ${NETWORK_NAME} (${BRIDGE_IF})..."

if "${RUNTIME}" network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
    echo "    - Network '${NETWORK_NAME}' already exists. Reusing existing network."
else
    if [[ "${RUNTIME}" == "docker" ]]; then
        docker network create \
            --driver bridge \
            --subnet "${SUBNET}" \
            --gateway "${GATEWAY_IP}" \
            --opt "com.docker.network.bridge.name=${BRIDGE_IF}" \
            --opt "com.docker.network.bridge.enable_icc=false" \
            "${NETWORK_NAME}"
    else
        # Podman syntax
        podman network create \
            --driver bridge \
            --subnet "${SUBNET}" \
            --gateway "${GATEWAY_IP}" \
            --opt "isolate=true" \
            "${NETWORK_NAME}"
    fi
    echo "    - Successfully created '${NETWORK_NAME}'."
fi

# ------------------------------------------------------------------------------
# 4. Firewall Tool & Backend Detection
# ------------------------------------------------------------------------------
IPTABLES_BIN=""
if command -v iptables >/dev/null 2>&1; then
    IPTABLES_BIN="iptables"
elif command -v iptables-nft >/dev/null 2>&1; then
    IPTABLES_BIN="iptables-nft"
elif command -v iptables-legacy >/dev/null 2>&1; then
    IPTABLES_BIN="iptables-legacy"
else
    echo "[!] Error: 'iptables' binary not found. Please install iptables / iptables-nft." >&2
    exit 1
fi

IPTABLES_VER=$("${IPTABLES_BIN}" -V 2>/dev/null || echo "unknown")
echo "[+] Using firewall binary: ${IPTABLES_BIN} (${IPTABLES_VER})"

# ------------------------------------------------------------------------------
# 5. Apply Zero-Trust Host Isolation Rules (INPUT Chain)
# Ephemeral containers can ONLY reach the MITM proxy on $GATEWAY_IP:$PROXY_PORT.
# All host services (SSH 22, host DNS 53, local daemons) are strictly dropped.
# ------------------------------------------------------------------------------
echo "[+] Step 2: Applying zero-trust firewall isolation rules..."

"${IPTABLES_BIN}" -N PLAYWRIGHT-HOST 2>/dev/null || "${IPTABLES_BIN}" -F PLAYWRIGHT-HOST
"${IPTABLES_BIN}" -D INPUT -i "${BRIDGE_IF}" -j PLAYWRIGHT-HOST 2>/dev/null || true
"${IPTABLES_BIN}" -I INPUT 1 -i "${BRIDGE_IF}" -j PLAYWRIGHT-HOST

# Allow established and related connections
"${IPTABLES_BIN}" -A PLAYWRIGHT-HOST -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
"${IPTABLES_BIN}" -A PLAYWRIGHT-HOST -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true

# Allow exclusively the local MITM proxy port on the host gateway
"${IPTABLES_BIN}" -A PLAYWRIGHT-HOST -p tcp -d "${GATEWAY_IP}" --dport "${PROXY_PORT}" -j ACCEPT

# Block host DNS resolution attempts
"${IPTABLES_BIN}" -A PLAYWRIGHT-HOST -p udp --dport 53 -j DROP
"${IPTABLES_BIN}" -A PLAYWRIGHT-HOST -p tcp --dport 53 -j DROP

# Drop all remaining traffic destined for the host
"${IPTABLES_BIN}" -A PLAYWRIGHT-HOST -j DROP

# ------------------------------------------------------------------------------
# 6. Apply Zero-Trust Egress Rules (DOCKER-USER or FORWARD Chain)
# Block all external DNS lookups (53) and drop all outbound internet traffic.
# ------------------------------------------------------------------------------
"${IPTABLES_BIN}" -N PLAYWRIGHT-EGRESS 2>/dev/null || "${IPTABLES_BIN}" -F PLAYWRIGHT-EGRESS

# Determine target forwarding chain (DOCKER-USER for Docker, FORWARD for Podman / bare netfilter)
EGRESS_TARGET_CHAIN="FORWARD"
if "${IPTABLES_BIN}" -L DOCKER-USER -n >/dev/null 2>&1; then
    EGRESS_TARGET_CHAIN="DOCKER-USER"
fi
echo "    - Attaching egress containment to '${EGRESS_TARGET_CHAIN}' chain."

"${IPTABLES_BIN}" -D "${EGRESS_TARGET_CHAIN}" -i "${BRIDGE_IF}" -j PLAYWRIGHT-EGRESS 2>/dev/null || true
"${IPTABLES_BIN}" -I "${EGRESS_TARGET_CHAIN}" 1 -i "${BRIDGE_IF}" -j PLAYWRIGHT-EGRESS

# Block external DNS attempts
"${IPTABLES_BIN}" -A PLAYWRIGHT-EGRESS -p udp --dport 53 -j DROP
"${IPTABLES_BIN}" -A PLAYWRIGHT-EGRESS -p tcp --dport 53 -j DROP

# Drop ALL outbound internet egress from this bridge
"${IPTABLES_BIN}" -A PLAYWRIGHT-EGRESS -j DROP

# ------------------------------------------------------------------------------
# 7. Cross-Distribution Persistence
# ------------------------------------------------------------------------------
echo "[+] Step 3: Configuring rule persistence across reboots..."
PERSISTED=false

# Debian / Ubuntu with netfilter-persistent
if command -v netfilter-persistent >/dev/null 2>&1; then
    netfilter-persistent save >/dev/null 2>&1 || true
    echo "    - Rules persisted via netfilter-persistent."
    PERSISTED=true
fi

# Standard /etc/iptables (Debian, Ubuntu, Arch)
if [[ -d /etc/iptables ]]; then
    "${IPTABLES_BIN}-save" > /etc/iptables/rules.v4 2>/dev/null || true
    PERSISTED=true
fi

# RHEL / Rocky / Alma / CentOS (/etc/sysconfig/iptables)
if [[ -d /etc/sysconfig ]] && [[ -f /etc/sysconfig/iptables || -w /etc/sysconfig ]]; then
    "${IPTABLES_BIN}-save" > /etc/sysconfig/iptables 2>/dev/null || true
    PERSISTED=true
fi

# Alpine Linux (OpenRC)
if [[ -d /etc/iptables ]] && command -v rc-service >/dev/null 2>&1; then
    "${IPTABLES_BIN}-save" > /etc/iptables/rules-save 2>/dev/null || true
    PERSISTED=true
fi

# Fallback: create a systemd restore service if systemd is active
if [[ -d /etc/systemd/system ]] && command -v systemctl >/dev/null 2>&1 && [[ "${PERSISTED}" == false ]]; then
    mkdir -p /etc/iptables
    "${IPTABLES_BIN}-save" > /etc/iptables/zerotrust.v4
    cat << 'EOF' > /etc/systemd/system/zerotrust-firewall.service
[Unit]
Description=Restore Zero-Trust Container Firewall Rules
Before=network.target docker.service

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables/zerotrust.v4

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable zerotrust-firewall.service >/dev/null 2>&1 || true
    echo "    - Rules persisted via custom systemd service (zerotrust-firewall.service)."
    PERSISTED=true
fi

echo "[✓] Zero-Trust Network & Firewall Configuration Complete."
echo "    - Runtime:       ${RUNTIME}"
echo "    - Network:       ${NETWORK_NAME}"
echo "    - Bridge:        ${BRIDGE_IF}"
echo "    - Subnet:        ${SUBNET}"
echo "    - MITM Endpoint: http://${GATEWAY_IP}:${PROXY_PORT}"
