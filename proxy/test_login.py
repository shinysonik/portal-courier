"""Test the proxy's credential injection end-to-end."""
import re
import sys
import requests

PROXY = "http://127.0.0.1:8888"
PORTAL = "http://localhost:5001"
USERNAME = "anna"
DUMMY_PASSWORD = "VAULT_PASS"

proxies = {"http": PROXY, "https": PROXY}

session = requests.Session()
session.proxies.update(proxies)

# Step 1: open login page, get csrf from HTML and anon_csrf cookie from response.
r = session.get(f"{PORTAL}/login", proxies=proxies, timeout=10)
print(f"GET /login -> {r.status_code}")
if r.status_code != 200:
    print("FAIL: login page not reachable through proxy")
    sys.exit(1)

m = re.search(r'name="csrf"\s+value="([^"]+)"', r.text)
if not m:
    print("FAIL: csrf field not found in login page")
    sys.exit(1)
csrf = m.group(1)
print(f"csrf extracted: {csrf[:10]}...")

# Step 2: POST with dummy password. Proxy should swap VAULT_PASS -> real_secret_123.
r = session.post(
    f"{PORTAL}/login",
    data={"username": USERNAME, "password": DUMMY_PASSWORD, "csrf": csrf},
    proxies=proxies,
    timeout=10,
    allow_redirects=False,
)
print(f"POST /login -> {r.status_code}")
print(f"Location: {r.headers.get('Location', '(none)')}")

# Expected: 303 with Location=/dashboard. If 401, password swap failed.
if r.status_code == 303 and "/dashboard" in (r.headers.get("Location") or ""):
    print("PASS: credential injection works")
else:
    print("FAIL: expected 303 to /dashboard")
    print(f"Body: {r.text[:300]}")
    sys.exit(1)

# Step 3: follow redirect, verify dashboard is reachable.
r = session.get(f"{PORTAL}/dashboard", proxies=proxies, timeout=10)
print(f"GET /dashboard -> {r.status_code}")
if r.status_code == 200 and "Invoice" in r.text:
    print("PASS: session works via proxy (cookie stored on proxy side)")
else:
    print("FAIL: dashboard not reachable after login")
    sys.exit(1)