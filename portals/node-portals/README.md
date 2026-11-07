# Node.js Publisher Press Demo Portals & Agent Dashboard

This folder contains **6 mock supplier portals** built with Node.js and Express, simulating diverse literary publisher presses. They run independently on `http://localhost:3000/` and demonstrate universal multi-format invoice extraction alongside client-side zero-trust egress containment.

---

## 1. What's Inside

- **`server.js`** — Single-file Express server simulating 6 distinct publisher supplier portals with multi-format invoice generation (`.txt`, `.csv`, `.html`, `.pdf`), live HTTP request logging, dual-stack `::` listening, and malicious egress simulation.
- **`dashboard.html`** — Single-file AI Agent Hackathon Dashboard built with Tailwind CSS following Emil Kowalski's "Taste" design system. Features real-time state machine simulation, 2x3 portal grid, dynamic ingestion popups, live telemetry metrics, and a left slide-over drawer with the Team Dossier.
- **`start.bat`** — Automated one-click Windows launcher. Resolves WinGet Node.js LTS installations, launches default browser tabs for both `http://localhost:3000/` and `dashboard.html`, and runs the server with error pause protection.
- **`package.json` & `package-lock.json`** — Lightweight npm configuration with zero external dependencies beyond `express`.

---

## 2. The 6 Publisher Portals

| Portal ID | Publisher Press Name | Code | File Format | Safety Profile | Egress Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`portal1`** | **Tiny Fox Press** | `TFP-01` | `.txt` (Plain Text) | Clean / Safe | Normal invoice download |
| **`portal2`** | **Featherproof Books** | `FPB-02` | `.txt` (Plain Text) | Clean / Safe | Normal invoice download |
| **`portal3`** | **Melville House** | `MVH-03` | `.csv` (Spreadsheet) | Clean / Safe | Normal invoice download |
| **`portal4`** | **Dalkey Archive Press** | `DAP-04` | `.csv` (Spreadsheet) | Compromised | Exfiltration `fetch()` to `185.23.50.50:80` (Blocked) |
| **`portal5`** | **Smith, Elder & Co** | `SEC-05` | `.html` (DOM Document) | Compromised | Exfiltration `fetch()` to `185.23.50.50:80` (Blocked) |
| **`portal6`** | **Chronicle Books** | `CHB-06` | `.pdf` (Portable Doc) | Clean / Safe | Normal invoice download |

---

## 3. How to Run

### Quick Start (Windows)
Double-click **`start.bat`**. It will automatically:
1. Detect Node.js (including WinGet paths).
2. Open your default browser to `http://localhost:3000/` (Supplier Portal Directory) and `dashboard.html` (AI Agent Dashboard).
3. Start the Express server on port 3000 with real-time terminal request logging.

### Manual Start (Cross-Platform)
```bash
cd portals/node-portals
npm install
npm start
```

---

## 4. Proxy & Zero-Trust Integration

- Port `3000` is pre-configured in the MITM forward proxy's `ALLOWED_HOSTS` (`localhost:5001,localhost:5002,localhost:3000`).
- Portals 4 and 5 fire client-side exfiltration attempts to external IP `185.23.50.50:80`. When running behind the zero-trust bridge (`playwright-net` and iptables rules), all egress packets are dropped with 0 bytes leaked.
