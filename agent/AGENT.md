# Agent Specification & Isolation Protocol

The Portal Courier agent (`agent/agent.py`) is an autonomous Playwright browser automation agent designed to execute inside disposable Docker sandboxes.

## Capabilities & Constraints
- **Allowed Actions:** Open configured login URL, submit authentication form, navigate to billing period, trigger PDF download, save to `/out/invoice.pdf`.
- **Forbidden Actions:** No local shell execution, no environment reading outside configuration keys, no file writes outside `/out`, no navigation to external domains.
- **Credential Hygiene:** Uses dummy credential `VAULT_PASS`. Real passwords and session cookies are swapped and managed externally by the forward proxy.
- **Magic Byte Validation:** Enforces `%PDF` header validation on all downloaded artifacts.

## Docker Packaging
Packaged via `agent/Dockerfile` using `mcr.microsoft.com/playwright/python:v1.49.0-noble`.
Isolated via `agent/docker-infrastructure/deploy-zerotrust-network.sh` with dropped Linux capabilities (`--cap-drop ALL`), `no-new-privileges:true`, and zero external WAN routing.
