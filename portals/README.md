
# Demo supplier portals

Seven supplier portals used in the Portal Courier demo. They are props, not part of the product.

We use two different tech stacks (Python and Node.js) to simulate a realistic, messy environment. Real companies work with a mix of modern and legacy suppliers, and receive invoices in different formats.

**Group 1: Python Portals (2)**
*   `good/` — EnergoPlus (Port 5001). Modern, clean. Outputs `.pdf`.
*   `hostile/` — GazSfera (Port 5002). Legacy, compromised. Outputs `.pdf` with hidden prompt injection.

**Group 2: Node.js Portals (5)**
*   `node-portals/` — 5 mock portals running on Port 3000. 
*   Outputs a mix of formats: `.txt`, `.csv`, and `.html`.
*   Portals 4 and 5 are compromised and trigger JS exfiltration attacks.

---

## Setup

From the project root, once for Python:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For the Node.js portals, navigate to their folder and install dependencies:

```powershell
cd portals/node-portals
npm install
```

---

## Run

All portals must be started from the project root (except Node.js) in separate terminals.

**1. Python Good Portal (Port 5001):**
```powershell
uvicorn portals.good.app:app --host 0.0.0.0 --port 5001 --reload
```

**2. Python Hostile Portal (Port 5002):**
```powershell
uvicorn portals.hostile.app:app --host 0.0.0.0 --port 5002 --reload
```

**3. Node.js Portals (Port 3000):**
```powershell
cd portals/node-portals
npm start
```

Quick check that everything is up:
```powershell
curl http://localhost:5001/health
curl http://localhost:5002/health
curl http://localhost:3000/
```

---

## Credentials

**Python Portals (Good & Hostile):**
*   Username: `anna`
*   Password: `real_secret_123`
*   *Hostile Portal also requires:* Client VAT ID: `9876543210`

**Node.js Portals (1–5):**
*   They accept **any** username and password (built for Playwright testing).
*   Route example: `http://localhost:3000/portal1/login`

*(Note: `VAULT_PASS` is rejected by the Python portals unless you start them with `ALLOW_DUMMY=true`. Only the proxy should know the real password).*

---

## The Attack Cases (Containment Moments)

We have two different threat scenarios to test the proxy and orchestrator.

### Threat 1: The Python Hostile Portal (GazSfera)
*   **Network Attack:** The invoice list page runs malicious JS that fires 5 exfiltration attempts to `attacker.example` and `185.23.45.67`.
*   **File Attack:** The downloaded `.pdf` contains a hidden white-on-white prompt injection (`SYSTEM OVERRIDE: Ignore all previous instructions...`) and a phishing link.
*   *The Orchestrator must extract the text from the PDF and flag the hidden instruction.*

### Threat 2: The Node.js Portals (4 & 5)
*   **Network Attack:** The dashboard runs JS that fires an exfiltration attempt to `185.23.50.50`.
*   *The proxy must block this request (403 Forbidden).*
*   *Note for Agent devs:* Chrome blocks HTTP requests to raw IPs by default. To test these attacks, Playwright must be launched with the `--disable-web-security` flag.

---

## How the pieces fit

```
Browser agent (in Docker container)
        │ all traffic
        ▼
Proxy on host (port 8888)
        │ allowlist + credential swap + cookie strip
        ▼
Portals (Python on :5001/:5002, Node.js on :3000)
```

The proxy decides whether a portal is reachable at all. We have added `localhost:3000` to the proxy's `ALLOWED_HOSTS`. If the proxy is not running, the agent cannot open any portal.

For local debugging without the proxy, open the portals directly in your browser. For the real flow, the agent never talks to a portal directly — it always goes through the proxy.

---

## One rule

The portals are props. Their job is to look real enough that the agent behaves like a real browser, and to be malicious enough that the proxy has something to block. Do not polish them further.
