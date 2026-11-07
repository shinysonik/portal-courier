Here is the complete, polished `proxy/README.md`. It is designed to be read by someone who just cloned the repo and needs to understand exactly what this component does, how to run it, and how to prove it works.

Copy this into your `proxy/README.md` file.

---

# Portal Courier: MITM Proxy

This proxy is the security boundary of the entire system. It sits between the disposable Docker container (where the Playwright agent runs) and the supplier portals.

Its job is to ensure the agent **never** sees real credentials, **never** holds a real session, and **cannot** exfiltrate data to an attacker. It also writes a verifiable audit log of everything that happens.

## What it does

1. **Domain Allowlist.** Blocks all requests except those going to the allowed portals (default: `localhost:5001` and `localhost:5002`). Everything else gets a `403 Forbidden`. This is the core of the network containment.
2. **Credential Injection.** The agent only knows the dummy password `VAULT_PASS`. The proxy intercepts the login request and swaps it for the real password (default: `real_secret_123`) before it reaches the portal.
3. **Session Isolation (Cookie Stripping).** When the portal sends a session cookie via `Set-Cookie`, the proxy intercepts it, stores it in its own memory, and removes it from the response. The browser inside the container never receives it. On subsequent requests, the proxy attaches the stored cookie.
4. **Event Logging.** Writes every action to `events.jsonl`. This file is the audit trail used by the orchestrator and the demo dashboard.

## Prerequisites

You need `mitmproxy` to run the proxy.

**Do not install it in the local `.venv` you created for the project.** `mitmproxy` has heavy dependencies that can conflict with FastAPI, Playwright, and `reportlab` which are used by the portals and the orchestrator.
*(Note: The `.venv` folder is not tracked by Git; every developer creates their own local `.venv` after cloning the repo).*

Install `mitmproxy` globally using `pipx` so it lives in its own isolated environment:

```powershell
pip install --user pipx
python -m pipx ensurepath
pipx install mitmproxy
```
*Restart your terminal after installation so the `mitmdump` command becomes available.*

## Configuration

The proxy uses environment variables. Defaults are set inside `addon.py`, but you can override them in your terminal before starting the proxy.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ALLOWED_HOSTS` | `localhost:5001,localhost:5002` | Comma-separated list of allowed `host:port` combinations. |
| `REAL_PASSWORD` | `real_secret_123` | The actual password the proxy swaps in. |
| `DUMMY_PASSWORD` | `VAULT_PASS` | The placeholder password the agent uses. |
| `EVENTS_PATH` | `events.jsonl` | Where to write the audit log. |

## How to run

1. Make sure both demo portals are running in separate terminals from the project root:
   ```powershell
   uvicorn portals.good.app:app --port 5001 --reload
   uvicorn portals.hostile.app:app --port 5002 --reload
   ```

2. Start the proxy from the project root. We use port `8888` because port `8080` is often occupied by other local services.
   ```powershell
   mitmdump -s proxy/addon.py --listen-port 8888
   ```
   *(Do not pipe the output to a file using `>`. The terminal buffers it, so you won't see events in real time. Just watch the terminal window).*

## How to test the proxy

Because the portals use CSRF tokens, you cannot test the proxy with simple `curl` commands. We have provided Python scripts for this. Run these from the project root while the proxy is running.

### Test 1: Credential Injection and Cookie Stripping
```powershell
python proxy/test_login.py
```
*   **Expect:** The proxy terminal logs `[CREDENTIAL_INJECTED]` and `[COOKIE_STRIPPED]`.
*   **Expect:** The script prints `PASS: credential injection works`.

### Test 2: The Containment Moment (Hostile Portal)
```powershell
python proxy/test_hostile.py
```
*   **Expect:** The script downloads the PDF successfully (`PASS: PDF downloaded through proxy`).
*   **Expect:** If you open the downloaded PDF with `pdfplumber`, you will find the hidden prompt injection.

### Proving the 5 Exfiltration Blocks (The Demo Moment)
The hostile portal's invoice list page contains malicious JavaScript that tries to steal the session in 5 different ways (`fetch`, `Image().src`, `POST`, direct IP, `sendBeacon`).

Standard Python `requests` does not execute JavaScript, so it won't trigger these attacks. To see the containment moment, you must use a browser that executes JS and routes through the proxy.

**Important Note on Browsers:**
Chrome, Edge, and Firefox **by default** ignore system proxies for `localhost` traffic. Even if you set the proxy to `127.0.0.1:8888` and clear all bypass lists, the browser will connect to `localhost:5002` directly, bypassing the proxy.

To test this manually, you must launch a browser with the `--proxy-bypass-list=<-loopback>` flag, or use our Playwright test script. We recommend the script:

```powershell
python proxy/test_browser.py
```
This script launches a headless Chromium, logs into the hostile portal, navigates to the invoice list, and triggers the attacks.

**What you should see in the `mitmdump` terminal:**
```text
[BLOCKED] {'host': 'attacker.example:443', 'method': 'GET', 'path': '/steal?...', 'reason': 'host_not_in_allowlist'}
[BLOCKED] {'host': 'attacker.example:443', 'method': 'GET', 'path': '/pixel?...', 'reason': 'host_not_in_allowlist'}
[BLOCKED] {'host': 'attacker.example:443', 'method': 'POST', 'path': '/submit', 'reason': 'host_not_in_allowlist'}
[BLOCKED] {'host': '185.23.45.67:443', 'method': 'GET', 'path': '/exfil?...', 'reason': 'host_not_in_allowlist'}
[BLOCKED] {'host': 'attacker.example:443', 'method': 'POST', 'path': '/beacon', 'reason': 'host_not_in_allowlist'}
```
If you see these 5 lines, network containment is proven. Zero bytes left the sandbox.

## Docker Integration

When running the actual agent inside a Docker container, it will not be able to reach the host's proxy using `localhost`. You must use `host.docker.internal`.

When launching the agent container, pass these environment variables to it:
```text
HTTP_PROXY=http://host.docker.internal:8888
HTTPS_PROXY=http://host.docker.internal:8888
```
And add this flag to the `docker run` command (required on Linux, harmless on Windows/Mac):
```text
--add-host=host.docker.internal:host-gateway
```

## The Event Log (`events.jsonl`)

Every event is appended to `events.jsonl` in the project root as a single-line JSON object. The orchestrator reads this file to show the audit trail in the UI. Because it's a simple text file, you can tail it during debugging:

```powershell
Get-Content events.jsonl -Wait
```

Example events:
```json
{"ts": "2026-11-06T23:20:50Z", "type": "REQUEST_ALLOWED", "host": "localhost:5002", "method": "GET", "path": "/login"}
{"ts": "2026-11-06T23:20:50Z", "type": "COOKIE_PASSED", "host": "localhost:5002", "cookie_name": "anon_csrf"}
{"ts": "2026-11-06T23:20:50Z", "type": "CREDENTIAL_INJECTED", "host": "localhost:5002", "username": "anna"}
{"ts": "2026-11-06T23:20:50Z", "type": "COOKIE_STRIPPED", "host": "localhost:5002", "cookie_name": "session"}
{"ts": "2026-11-06T23:20:50Z", "type": "BLOCKED", "host": "attacker.example:443", "method": "GET", "path": "/steal?...", "reason": "host_not_in_allowlist"}
```