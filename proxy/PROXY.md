# Portal Courier: MITM Proxy

This proxy is the security boundary of the entire system. It sits between the disposable Docker container (where the Playwright agent runs) and the supplier portals.

Its job is to ensure the agent **never** sees real credentials, **never** holds a real session, and **cannot** exfiltrate data to an attacker. It also writes a verifiable audit log of everything that happens.

## What it does

1. **Domain Allowlist.** Blocks all requests except those going to the allowed portals. Everything else gets a `403 Forbidden`. This is the core of the network containment.
2. **Credential Injection.** The agent only knows the dummy password `VAULT_PASS`. The proxy intercepts the login request and swaps it for the real password (`real_secret_123`) before it reaches the portal.
3. **Session Isolation (Cookie Stripping).** When the portal sends a session cookie via `Set-Cookie`, the proxy intercepts it, stores it in its own memory, and removes it from the response. The browser inside the container never receives it.
4. **Event Logging.** Writes every action to `events.jsonl`. This file is the audit trail used by the orchestrator and the demo dashboard.

## Prerequisites

You need `mitmproxy` to run the proxy. **Do not install it in the local `.venv`**. Install it globally using `pipx`:

```powershell
pip install --user pipx
python -m pipx ensurepath
pipx install mitmproxy
```
*Restart your terminal after installation so the `mitmdump` command becomes available.*

## Configuration

Defaults are set inside `addon.py`, but you can override them in your terminal.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ALLOWED_HOSTS` | `localhost:5001,localhost:5002,localhost:3000` | Allowed host:port combinations. |
| `REAL_PASSWORD` | `real_secret_123` | The actual password the proxy swaps in. |
| `DUMMY_PASSWORD` | `VAULT_PASS` | The placeholder password the agent uses. |
| `EVENTS_PATH` | `events.jsonl` | Where to write the audit log. |

## How to run

1. Make sure all demo portals are running in separate terminals:
   ```powershell
   # Python portals (5001, 5002)
   uvicorn portals.good.app:app --port 5001 --reload
   uvicorn portals.hostile.app:app --port 5002 --reload
   
   # Node.js portals (3000)
   cd portals/node-portals
   npm start
   ```

2. Start the proxy from the project root on port `8888`:
   ```powershell
   mitmdump -s proxy/addon.py --listen-port 8888
   ```
   *(Do not pipe the output to a file using `>`. The terminal buffers it, so you won't see events in real time).*

## How to test the proxy

Because the portals use CSRF tokens and JavaScript, you cannot test the proxy with simple `curl` commands. Use the provided Python scripts.

### Test 1: Credential Injection and Cookie Stripping (Python Portal)
```powershell
python proxy/test_login.py
```
*   **Expect:** The proxy logs `[CREDENTIAL_INJECTED]` and `[COOKIE_STRIPPED]`.

### Test 2: The Containment Moment (Python Hostile Portal)
```powershell
python proxy/test_hostile.py
```
*   **Expect:** The script downloads the PDF successfully. The proxy logs 5 `[BLOCKED]` events for `attacker.example` and `185.23.45.67`.

### Test 3: The Node.js Attack (Requires Browser)
Standard Python `requests` does not execute JavaScript. To trigger the attack on the Node.js portals (Portal 4), we use Playwright.

```powershell
python proxy/test_node_browser.py
```
*   **Expect:** A browser opens, logs into Portal 4, and triggers the exfiltration attempt. The proxy logs `[BLOCKED] {'host': '185.23.50.50:80'}`.

*(Note on Chrome/Edge: Browsers by default bypass proxies for `localhost`. The Playwright script bypasses this restriction using the `--proxy-bypass-list=<-loopback>` flag).*

## Docker Integration

When running the Agent inside a Docker container, it will not be able to reach the host's proxy using `localhost`. 

When launching the container, pass these environment variables:
```text
HTTP_PROXY=http://host.docker.internal:8888
HTTPS_PROXY=http://host.docker.internal:8888
```
And add this flag to the `docker run` command (required on Linux):
```text
--add-host=host.docker.internal:host-gateway
```

## The Event Log (`events.jsonl`)

Every event is appended to `events.jsonl` in the project root. The orchestrator reads this file to show the audit trail in the UI. You can tail it during debugging:

```powershell
Get-Content events.jsonl -Wait
```