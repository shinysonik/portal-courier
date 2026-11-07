#!/usr/bin/env bash
# ==============================================================================
# Universal Ephemeral Playwright Disposable Container Runner
# Zero-trust sandbox bound to local MITM forward proxy.
# Supports: Interactive TTY, Non-TTY (CI/CD, cron, background tasks), Docker, Podman
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# Configurable Parameters (Overridable via Environment)
# ------------------------------------------------------------------------------
PROXY_URL="${PROXY_URL:-http://172.28.0.1:8888}"
NETWORK_NAME="${NETWORK_NAME:-playwright-net}"
IMAGE_NAME="${1:-mcr.microsoft.com/playwright:v1.49.0-noble}"

# Shift first argument (image) if provided, leaving command arguments in $@
if [[ $# -ge 1 ]]; then
    shift
fi

# ------------------------------------------------------------------------------
# Container Runtime Detection
# ------------------------------------------------------------------------------
RUNTIME=""
if command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
elif command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
else
    echo "[!] Error: Neither 'docker' nor 'podman' was found in PATH." >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# TTY & Interactive Execution Mode Detection
# Prevents "the input device is not a TTY" failures in CI/CD, headless, or background jobs
# ------------------------------------------------------------------------------
INTERACTIVE_FLAGS=()
if [[ -t 0 ]] && [[ -t 1 ]]; then
    INTERACTIVE_FLAGS=("-it")
elif [[ -t 0 ]]; then
    INTERACTIVE_FLAGS=("-i")
fi

echo "[+] Spawning ephemeral Playwright sandbox attached to '${NETWORK_NAME}' via ${RUNTIME}..."
echo "    - Proxy: ${PROXY_URL}"
echo "    - Interactive flags: ${INTERACTIVE_FLAGS[*]:-none (headless/non-tty mode)}"
echo "    - Command: python /agent/agent.py"

# ------------------------------------------------------------------------------
# Launch Hardened Disposable Container
# 1. --rm: permanent self-destruction on exit
# 2. --network: bound strictly to the zero-trust bridge
# 3. --dns 127.0.0.1: dead-end DNS to block standard resolver leaks
# 4. Proxy envs: directs HTTP/HTTPS/Node/Playwright traffic to the MITM proxy
# 5. Kernel hardening: cap-drop=ALL, no-new-privileges
# 6. Memory: --ipc=host + --shm-size=1gb for stable browser rendering
# 7. Volume mounts: agent code and output directory shared with host
# ------------------------------------------------------------------------------
exec "${RUNTIME}" run --rm "${INTERACTIVE_FLAGS[@]}"   --network "${NETWORK_NAME}"   --dns 127.0.0.1   -v "$(pwd)/agent:/agent"   -v "$(pwd)/out:/out"   --env HTTP_PROXY="${PROXY_URL}"   --env HTTPS_PROXY="${PROXY_URL}"   --env http_proxy="${PROXY_URL}"   --env https_proxy="${PROXY_URL}"   --env ALL_PROXY="${PROXY_URL}"   --env all_proxy="${PROXY_URL}"   --env NO_PROXY=""   --env no_proxy=""   --env NODE_TLS_REJECT_UNAUTHORIZED="${NODE_TLS_REJECT_UNAUTHORIZED:-0}"   --security-opt=no-new-privileges:true   --cap-drop=ALL   --shm-size=1gb   --ipc=host   "${IMAGE_NAME}"   python /agent/agent.py
