"""
Portal Courier - browser agent.

Runs inside a disposable Docker container (but can be developed on the host).
It may: open the portal page, fill a form, click, wait for navigation, save a download.
It may NOT: run shell commands, read other env vars, write outside OUT_DIR,
open links from the PDF, open any URL other than PORTAL_URL, store the password.

Environment (the only variables this file reads):
    PORTAL_URL        login page URL
    USERNAME          portal username
    DUMMY_PASSWORD    always the literal VAULT_PASS (the proxy swaps it for the real one)
    VAT_ID            optional, only used if the login form has a "nip" field
    OUT_DIR           folder where the PDF is written
    HTTP_PROXY / HTTPS_PROXY   optional proxy address
    PORTAL_KIND       optional, "good" or "hostile" (informational only, never used for logic)

Output:
    OUT_DIR/invoice.pdf   (fixed filename)
    optional one JSON line on stdout: {"invoice_id": "..."}   (all logs go to stderr)

Exit codes: 0 success, 1 login failed, 2 download failed, 3 timeout, 10 unknown.
"""

import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# ---- exit codes -------------------------------------------------------------
EXIT_OK = 0
EXIT_LOGIN_FAILED = 1
EXIT_DOWNLOAD_FAILED = 2
EXIT_TIMEOUT = 3
EXIT_UNKNOWN = 10

# ---- constants --------------------------------------------------------------
TOTAL_TIMEOUT_S = 60          # hard cap for the whole run
LOGIN_SIGNAL_TIMEOUT_S = 15   # wait for the post-login success signal
DEFAULT_INVOICE_NAME = "invoice.pdf"
PDF_NAME = DEFAULT_INVOICE_NAME  # alias for backward compatibility
INVOICE_YEAR = "2026"         # period-picker portals (hostile): fixed per the brief
INVOICE_MONTH = "10"

_START = time.monotonic()


class AgentError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def log(msg: str) -> None:
    # stderr only: stdout is reserved for the single optional JSON line.
    print(f"[agent {time.monotonic() - _START:5.1f}s] {msg}", file=sys.stderr, flush=True)


def remaining_ms(cap_s: float | None = None) -> int:
    """Milliseconds left in the global budget (optionally capped for one step)."""
    left = TOTAL_TIMEOUT_S - (time.monotonic() - _START)
    if left <= 0:
        raise AgentError(EXIT_TIMEOUT, "global 60s timeout reached")
    if cap_s is not None:
        left = min(left, cap_s)
    return int(left * 1000)


# ---- config -----------------------------------------------------------------
def read_config() -> dict:
    portal_url = os.environ.get("PORTAL_URL", "").strip()
    out_dir = os.environ.get("OUT_DIR", "").strip()
    username = os.environ.get("USERNAME", "")
    password = os.environ.get("DUMMY_PASSWORD", "")
    if not portal_url or not out_dir or not username or not password:
        raise AgentError(EXIT_UNKNOWN, "PORTAL_URL, OUT_DIR, USERNAME and DUMMY_PASSWORD are required")
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
             or os.environ.get("https_proxy") or os.environ.get("http_proxy") or "").strip()
    return {
        "portal_url": portal_url,
        "out_dir": Path(out_dir),
        "username": username,
        "password": password,                       # used once, never logged or stored
        "vat_id": os.environ.get("VAT_ID", "").strip(),
        "proxy": proxy,
        "kind": os.environ.get("PORTAL_KIND", "").strip(),
    }


def check_proxy_reachable(proxy_url: str) -> None:
    u = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    host, port = u.hostname, u.port or 8080
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        raise AgentError(EXIT_TIMEOUT, f"proxy {host}:{port} is unreachable ({exc})")


# ---- helpers ----------------------------------------------------------------
def save_debug(page, out_dir: Path) -> None:
    try:
        page.screenshot(path=str(out_dir / "debug.png"), timeout=3000)
    except Exception:
        pass


def password_visible(page) -> bool:
    return page.locator('input[type="password"]:visible').count() > 0


def alert_visible(page) -> bool:
    return page.locator(".alert:visible").count() > 0


def has_invoice_or_download_link(page) -> bool:
    return page.locator("a, button").filter(
        has_text=re.compile(r"invoice|download", re.I)
    ).count() > 0


def login_succeeded(page) -> bool:
    if "/login" not in page.url:
        return True
    return (not password_visible(page)) and has_invoice_or_download_link(page)


# ---- steps ------------------------------------------------------------------
def do_login(page, cfg: dict) -> None:
    log("opening portal login page")
    page.goto(cfg["portal_url"], wait_until="domcontentloaded", timeout=remaining_ms(20))

    if login_succeeded(page):
        log(f"already logged in (url: {page.url})")
        return

    pw_field = page.locator('input[type="password"]').first
    if pw_field.count() == 0:
        raise AgentError(EXIT_LOGIN_FAILED, "no password field on the login page")

    user_field = page.locator('input[name="username"]')
    if user_field.count() == 0:
        user_field = page.locator('input[type="text"], input:not([type])').first
    user_field.first.fill(cfg["username"], timeout=remaining_ms(10))
    pw_field.fill(cfg["password"], timeout=remaining_ms(10))

    # Optional third field (hostile portal): fill only if present AND we have a value.
    nip = page.locator('input[name="nip"]')
    if nip.count() > 0:
        if cfg["vat_id"]:
            nip.first.fill(cfg["vat_id"], timeout=remaining_ms(10))
        else:
            log("login form has a VAT field but VAT_ID is not set - skipping it")
            if nip.first.get_attribute("required") is not None:
                raise AgentError(EXIT_LOGIN_FAILED, "login form requires a VAT ID but VAT_ID is not set")

    submit = page.locator('button[type="submit"], input[type="submit"]').first
    if submit.count() == 0:
        submit = page.get_by_role("button", name=re.compile(r"sign in|log ?in", re.I)).first
    log("submitting login form")
    submit.click(timeout=remaining_ms(10))

    # Success signal (15s). Early exit on an explicit failure.
    deadline = time.monotonic() + LOGIN_SIGNAL_TIMEOUT_S
    while time.monotonic() < deadline:
        remaining_ms()  # raises AgentError(3) if the global budget is gone
        try:
            if login_succeeded(page):
                log(f"login ok (url: {page.url})")
                return
            if "/login" in page.url and alert_visible(page) and password_visible(page):
                raise AgentError(EXIT_LOGIN_FAILED, "portal rejected the login (alert shown)")
        except PlaywrightError as exc:
            # page is mid-navigation; check again
            if "Execution context was destroyed" not in str(exc) and "navigat" not in str(exc).lower():
                raise
        page.wait_for_timeout(250)
    raise AgentError(EXIT_LOGIN_FAILED, "no success signal within 15s after login")


def find_download_trigger(page):
    """First link/button/clickable element whose text contains download, pdf, or file extensions."""
    pattern = re.compile(r"download|pdf|\.csv|\.txt|\.html|\.json", re.I)
    for sel in ("a", "button", "[onclick]", "span"):
        loc = page.locator(sel).filter(has_text=pattern)
        if loc.count() > 0:
            return loc.first
    return None


def click_and_capture(page, trigger, out_dir: Path) -> dict:
    """Click inside expect_download (never poll the filesystem). Returns invoice metadata."""
    with page.expect_download(timeout=remaining_ms(30)) as dl_info:
        trigger.click(timeout=remaining_ms(10))
    download = dl_info.value

    # Universal file handling: determine filename from suggested_filename or URL
    suggested = download.suggested_filename
    if suggested:
        filename = Path(suggested).name
    else:
        url_part = Path(download.url.split("?")[0].rstrip("/")).name
        if "." in url_part and len(url_part.rsplit(".", 1)[1]) <= 5:
            filename = url_part
        else:
            filename = DEFAULT_INVOICE_NAME

    if not filename or filename == ".":
        filename = DEFAULT_INVOICE_NAME

    target = out_dir / filename
    download.save_as(str(target))

    # Backward compatibility: if it is a PDF not named invoice.pdf, also copy as invoice.pdf
    if target.suffix.lower() == ".pdf" and target.name != DEFAULT_INVOICE_NAME:
        try:
            import shutil
            shutil.copyfile(target, out_dir / DEFAULT_INVOICE_NAME)
        except Exception:
            pass

    # Ensure file is not 0 bytes
    if not target.exists() or target.stat().st_size == 0:
        raise AgentError(EXIT_DOWNLOAD_FAILED, f"downloaded file '{filename}' is empty")

    # If it is explicitly a .pdf, verify valid %PDF magic bytes
    if target.suffix.lower() == ".pdf":
        with open(target, "rb") as f:
            if f.read(4) != b"%PDF":
                raise AgentError(EXIT_DOWNLOAD_FAILED, f"downloaded file '{filename}' lacks %PDF header")

    m = re.search(r"/invoice/(.+?)(?:/download)?$", download.url)
    invoice_id = m.group(1) if m else None
    log(f"captured universal invoice download: {filename} ({target.stat().st_size} bytes)")
    return {"invoice_id": invoice_id, "filename": filename}


def do_download(page, cfg: dict) -> dict | None:
    # Register BEFORE any click that may trigger a confirm() (hostile portal).
    page.on("dialog", lambda d: d.accept())

    # Period-picker portals (hostile): select year + month, show invoices, then download.
    year_sel = page.locator('select[name="year"]')
    month_sel = page.locator('select[name="month"]')
    if year_sel.count() > 0 and month_sel.count() > 0:
        log(f"selecting period {INVOICE_YEAR}/{INVOICE_MONTH}")
        year_sel.first.select_option(INVOICE_YEAR, timeout=remaining_ms(10))
        month_sel.first.select_option(INVOICE_MONTH, timeout=remaining_ms(10))
        page.get_by_role("button", name=re.compile(r"show invoices", re.I)).first.click(timeout=remaining_ms(10))

        # Do NOT wait for network idle: this page fires slow requests (the exfil attempts).
        # Wait for the download link itself.
        pattern = re.compile(r"download|pdf|\.csv|\.txt|\.html|\.json", re.I)
        link = page.locator("a, button, [onclick], span").filter(has_text=pattern).first
        try:
            link.wait_for(state="visible", timeout=remaining_ms(20))
        except PlaywrightTimeout:
            raise AgentError(EXIT_DOWNLOAD_FAILED, "no invoice download link appeared for the period")
        log("download link visible, clicking (confirm dialog will be accepted)")
        return click_and_capture(page, link, cfg["out_dir"])

    # Flat portals (good): a download trigger is already on the post-login page.
    trigger = find_download_trigger(page)
    if trigger is not None:
        log("download trigger found on landing page")
        return click_and_capture(page, trigger, cfg["out_dir"])

    raise AgentError(EXIT_DOWNLOAD_FAILED, "no download link and no period picker found")


# ---- main -------------------------------------------------------------------
def run() -> int:
    cfg = read_config()
    cfg["out_dir"].mkdir(parents=True, exist_ok=True)

    launch_args = ["--no-sandbox"]
    if cfg["proxy"]:
        check_proxy_reachable(cfg["proxy"])
        launch_args += [
            f"--proxy-server={cfg['proxy']}",
            "--proxy-bypass-list=<-loopback>",   # route localhost through the proxy too
            "--ignore-certificate-errors",
        ]
        log("routing browser traffic through the proxy")

    dl_meta = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch_args)
        page = None
        try:
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            do_login(page, cfg)
            dl_meta = do_download(page, cfg)
        except PlaywrightTimeout as exc:
            if page:
                save_debug(page, cfg["out_dir"])
            raise AgentError(EXIT_DOWNLOAD_FAILED, f"playwright timeout: {str(exc).splitlines()[0]}")
        except AgentError:
            if page:
                save_debug(page, cfg["out_dir"])
            raise
        finally:
            try:
                browser.close()
            except Exception:
                pass

    if isinstance(dl_meta, dict):
        out_payload = {k: v for k, v in dl_meta.items() if v is not None}
        if out_payload:
            print(json.dumps(out_payload), flush=True)
    elif dl_meta:
        print(json.dumps({"invoice_id": str(dl_meta)}), flush=True)
    log("done")
    return EXIT_OK


def _watchdog() -> None:
    # Backstop if something hangs inside Playwright itself: the container gets destroyed anyway.
    time.sleep(TOTAL_TIMEOUT_S + 3)
    print("[agent] watchdog: hard timeout", file=sys.stderr, flush=True)
    os._exit(EXIT_TIMEOUT)


def main() -> None:
    threading.Thread(target=_watchdog, daemon=True).start()
    try:
        code = run()
    except AgentError as exc:
        log(f"ERROR ({exc.code}): {exc.message}")
        code = exc.code
    except Exception as exc:  # noqa: BLE001
        log(f"UNEXPECTED: {type(exc).__name__}: {exc}")
        code = EXIT_UNKNOWN
    sys.exit(code)


if __name__ == "__main__":
    main()
