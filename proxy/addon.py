"""
Portal Courier MITM proxy addon.

Responsibilities:
1. Allowlist: only requests to the configured portal host are allowed.
2. Credential injection: replace VAULT_PASS in the login form with the real password.
3. Cookie stripping: strip the session cookie from responses, keep it on the proxy side.
   Non-auth cookies (like CSRF tokens) pass through to the browser.
4. Event log: append one JSON line per event to events.jsonl.

The proxy never stores the real password in memory longer than needed,
and the browser inside the container never sees the real session cookie.
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from mitmproxy import http, ctx


# --- Configuration

ALLOWED_HOSTS = {
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "localhost:5001,localhost:5002").split(",")
    if h.strip()
}

REAL_USERNAME = os.getenv("REAL_USERNAME", "anna")
REAL_PASSWORD = os.getenv("REAL_PASSWORD", "real_secret_123")
DUMMY_PASSWORD = os.getenv("DUMMY_PASSWORD", "VAULT_PASS")

# Cookies that must never reach the browser. Names only, exact match.
STRIPPED_COOKIES = {"session"}

EVENTS_PATH = Path(os.getenv("EVENTS_PATH", "events.jsonl"))

# Session storage on the proxy side. Host -> cookie string.
SESSION_COOKIES: dict[str, str] = {}


# --- Helpers

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_event(event_type: str, **fields) -> None:
    record = {"ts": now_iso(), "type": event_type, **fields}
    try:
        with EVENTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        ctx.log.warn(f"Failed to write event log: {exc}")
    ctx.log.info(f"[{event_type}] {fields}")


def host_of(flow: http.HTTPFlow) -> str:
    return f"{flow.request.host}:{flow.request.port}"


def is_allowed(flow: http.HTTPFlow) -> bool:
    return host_of(flow) in ALLOWED_HOSTS


def request_path_only(flow: http.HTTPFlow) -> str:
    """Path without query string, e.g. '/login' even if '/login?next=x'."""
    return flow.request.path.split("?", 1)[0]


# --- Addon

class PortalCourierProxy:
    def request(self, flow: http.HTTPFlow) -> None:
        host = host_of(flow)

        # 1. Allowlist check.
        if not is_allowed(flow):
            log_event(
                "BLOCKED",
                host=host,
                method=flow.request.method,
                path=flow.request.path,
                reason="host_not_in_allowlist",
            )
            flow.response = http.Response.make(
                403,
                b"Blocked by Portal Courier proxy: host not in allowlist\n",
                {"Content-Type": "text/plain"},
            )
            return

        log_event(
            "REQUEST_ALLOWED",
            host=host,
            method=flow.request.method,
            path=flow.request.path,
        )

        # 2. Inject real credentials into the login form.
        content_type = flow.request.headers.get("content-type", "")
        if (
            flow.request.method == "POST"
            and request_path_only(flow) == "/login"
            and content_type.startswith("application/x-www-form-urlencoded")
        ):
            try:
                body = flow.request.get_text()
                params = parse_qs(body, keep_blank_values=True)
                if params.get("password", [None])[0] == DUMMY_PASSWORD:
                    params["password"] = [REAL_PASSWORD]
                    flow.request.set_text(urlencode(params, doseq=True))
                    log_event(
                        "CREDENTIAL_INJECTED",
                        host=host,
                        username=params.get("username", [""])[0],
                    )
                else:
                    log_event(
                        "CREDENTIAL_NOT_INJECTED",
                        host=host,
                        reason="dummy_password_not_found",
                    )
            except Exception as exc:
                ctx.log.warn(f"Failed to inject credentials: {exc}")

        # 3. Re-attach the session cookie stored on the proxy side.
        #    Do not override cookies the browser already has (like anon_csrf).
        if host in SESSION_COOKIES:
            existing = flow.request.headers.get("Cookie", "")
            if existing:
                # Merge: keep browser cookies, add/replace the session cookie.
                browser_pairs = [
                    p.strip() for p in existing.split(";") if p.strip()
                ]
                session_pair = SESSION_COOKIES[host]
                session_name = session_pair.split("=", 1)[0]
                filtered = [
                    p for p in browser_pairs
                    if p.split("=", 1)[0] != session_name
                ]
                filtered.append(session_pair)
                flow.request.headers["Cookie"] = "; ".join(filtered)
            else:
                flow.request.headers["Cookie"] = SESSION_COOKIES[host]
            log_event("COOKIE_REATTACHED", host=host)

    def response(self, flow: http.HTTPFlow) -> None:
        host = host_of(flow)

        # 4. Strip only auth cookies from the response, keep the rest.
        #    mitmproxy exposes multi-value headers via get_all; handle each.
        set_cookie_values = flow.response.headers.get_all("Set-Cookie")
        if not set_cookie_values:
            return

        kept: list[str] = []
        for raw in set_cookie_values:
            cookie_pair = raw.split(";", 1)[0].strip()
            cookie_name = cookie_pair.split("=", 1)[0].strip()
            if cookie_name in STRIPPED_COOKIES:
                SESSION_COOKIES[host] = cookie_pair
                log_event(
                    "COOKIE_STRIPPED",
                    host=host,
                    cookie_name=cookie_name,
                )
            else:
                kept.append(raw)
                log_event(
                    "COOKIE_PASSED",
                    host=host,
                    cookie_name=cookie_name,
                )

        # Rewrite the header: replace all Set-Cookie with the kept ones.
        del flow.response.headers["Set-Cookie"]
        for value in kept:
            flow.response.headers.add("Set-Cookie", value)
addons = [PortalCourierProxy()]
