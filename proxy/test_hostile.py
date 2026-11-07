"""Test the hostile portal through the proxy. Expect 5 BLOCKED events."""
import re
import sys
import requests

PROXY = "http://127.0.0.1:8888"
PORTAL = "http://localhost:5002"
USERNAME = "anna"
DUMMY_PASSWORD = "VAULT_PASS"
VAT_ID = "9876543210"

proxies = {"http": PROXY, "https": PROXY}
session = requests.Session()
session.proxies.update(proxies)

# Step 1: open login page.
r = session.get(f"{PORTAL}/login", proxies=proxies, timeout=10)
print(f"GET /login -> {r.status_code}")
m = re.search(r'name="csrf"\s+value="([^"]+)"', r.text)
if not m:
    print("FAIL: no csrf field")
    sys.exit(1)
csrf = m.group(1)

# Step 2: login with 3 fields.
r = session.post(
    f"{PORTAL}/login",
    data={
        "username": USERNAME,
        "password": DUMMY_PASSWORD,
        "nip": VAT_ID,
        "csrf": csrf,
    },
    proxies=proxies,
    timeout=10,
    allow_redirects=False,
)
print(f"POST /login -> {r.status_code}, Location: {r.headers.get('Location')}")
if r.status_code != 303:
    print(f"FAIL: login returned {r.status_code}")
    sys.exit(1)

# Step 3: open /invoices. This is the page that fires the 5 attacks.
# We expect the page to load (200) AND the proxy to block 5 outbound requests.
r = session.get(
    f"{PORTAL}/invoices?year=2026&month=10",
    proxies=proxies,
    timeout=30,  # attacks will hang for a bit before proxy blocks them
)
print(f"GET /invoices -> {r.status_code}")
if r.status_code == 200 and "GS/2026/10/041" in r.text:
    print("PASS: hostile invoice list loaded")
else:
    print("FAIL: invoice list did not load")
    sys.exit(1)

# Step 4: download the invoice PDF through the proxy.
r = session.get(
    f"{PORTAL}/invoice/GS/2026/10/041/download?year=2026&month=10",
    proxies=proxies,
    timeout=10,
)
print(f"GET /invoice/.../download -> {r.status_code}, {len(r.content)} bytes")
if r.status_code == 200 and r.content[:4] == b"%PDF":
    print("PASS: PDF downloaded through proxy")
    with open("hostile_invoice.pdf", "wb") as f:
        f.write(r.content)
    print("Saved to hostile_invoice.pdf")
else:
    print("FAIL: PDF not downloaded correctly")
    sys.exit(1)

print("\nDone. Now check mitmdump output for 5 BLOCKED events on attacker.example and 185.23.45.67.")