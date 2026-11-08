"""
EnergoPlus Client Portal - a realistic supplier portal for the Portal Courier demo.
"""
import os
import secrets
import logging
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Form, Request, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

# -------------------- config --------------------

REAL_USERNAME = os.getenv("REAL_USERNAME", "anna")
REAL_PASSWORD = os.getenv("REAL_PASSWORD", "real_secret_123")
# If true, the portal also accepts DUMMY_PASSWORD - useful for testing without proxy.
# In the demo, ALLOW_DUMMY is false: only the proxy knows how to turn VAULT_PASS into the real password.
ALLOW_DUMMY = os.getenv("ALLOW_DUMMY", "false").lower() == "true"
DUMMY_PASSWORD = os.getenv("DUMMY_PASSWORD", "VAULT_PASS")

SESSION_TTL_SECONDS = 3600

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("energoplus")

# -------------------- app --------------------

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="EnergoPlus Client Portal")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# -------------------- sessions --------------------

sessions: dict[str, dict] = {}


def new_session(username: str) -> str:
    sid = secrets.token_urlsafe(32)
    sessions[sid] = {
        "username": username,
        "created_at": datetime.utcnow(),
        "csrf": secrets.token_urlsafe(24),
    }
    return sid


def get_session(sid: str | None) -> dict | None:
    if not sid:
        return None
    s = sessions.get(sid)
    if not s:
        return None
    if datetime.utcnow() - s["created_at"] > timedelta(seconds=SESSION_TTL_SECONDS):
        sessions.pop(sid, None)
        return None
    return s


# -------------------- demo data --------------------

VENDOR = {
    "name": "EnergoPlus Sp. z o.o.",
    "address": "ul. Energetyczna 12, 00-950 Warszawa, Poland",
    "nip": "1234567890",
    "iban": "PL61 1090 1014 0000 0712 1981 2874",
    "email": "billing@energoplus.example",
    "phone": "+48 22 123 45 67",
}

CUSTOMER = {
    "name": "Kowalska & Partners Accounting Sp. z o.o.",
    "address": "ul. Ksiegowa 8, 00-123 Warszawa, Poland",
    "nip": "9876543210",
}

INVOICES = [
    {
        "id": "FV-2026-10-001",
        "period": "2026-10",
        "issue_date": "2026-10-31",
        "due_date": "2026-11-14",
        "currency": "EUR",
        "status": "Unpaid",
        "po": "PO-2026-10-001",
        "items": [
            {"description": "Electricity - day tariff", "quantity": 750, "unit": "kWh", "unit_price": 0.90, "net": 675.00},
            {"description": "Electricity - night tariff", "quantity": 200, "unit": "kWh", "unit_price": 0.50, "net": 100.00},
            {"description": "Distribution fee", "quantity": 1, "unit": "item", "unit_price": 75.00, "net": 75.00},
        ],
        "amount_net": 850.00,
        "amount_vat": 195.50,
        "amount_gross": 1045.50,
    },
    {
        "id": "FV-2026-09-002",
        "period": "2026-09",
        "issue_date": "2026-09-30",
        "due_date": "2026-10-14",
        "currency": "EUR",
        "status": "Paid",
        "po": "PO-2026-09-002",
        "items": [
            {"description": "Electricity - day tariff", "quantity": 700, "unit": "kWh", "unit_price": 0.90, "net": 630.00},
            {"description": "Electricity - night tariff", "quantity": 180, "unit": "kWh", "unit_price": 0.50, "net": 90.00},
            {"description": "Distribution fee", "quantity": 1, "unit": "item", "unit_price": 80.00, "net": 80.00},
        ],
        "amount_net": 800.00,
        "amount_vat": 184.00,
        "amount_gross": 984.00,
    },
    {
        "id": "FV-2026-08-003",
        "period": "2026-08",
        "issue_date": "2026-08-31",
        "due_date": "2026-09-14",
        "currency": "EUR",
        "status": "Paid",
        "po": "PO-2026-08-003",
        "items": [
            {"description": "Electricity - day tariff", "quantity": 950, "unit": "kWh", "unit_price": 0.90, "net": 855.00},
            {"description": "Electricity - night tariff", "quantity": 300, "unit": "kWh", "unit_price": 0.50, "net": 150.00},
            {"description": "Distribution fee", "quantity": 1, "unit": "item", "unit_price": 95.00, "net": 95.00},
        ],
        "amount_net": 1100.00,
        "amount_vat": 253.00,
        "amount_gross": 1353.00,
    },
    {
        "id": "FV-2026-07-004",
        "period": "2026-07",
        "issue_date": "2026-07-31",
        "due_date": "2026-08-14",
        "currency": "EUR",
        "status": "Paid",
        "po": "PO-2026-07-004",
        "items": [
            {"description": "Electricity - day tariff", "quantity": 600, "unit": "kWh", "unit_price": 0.90, "net": 540.00},
            {"description": "Electricity - night tariff", "quantity": 150, "unit": "kWh", "unit_price": 0.50, "net": 75.00},
            {"description": "Distribution fee", "quantity": 1, "unit": "item", "unit_price": 85.00, "net": 85.00},
        ],
        "amount_net": 700.00,
        "amount_vat": 161.00,
        "amount_gross": 861.00,
    },
    {
        "id": "FV-2026-06-005",
        "period": "2026-06",
        "issue_date": "2026-06-30",
        "due_date": "2026-07-14",
        "currency": "EUR",
        "status": "Paid",
        "po": "PO-2026-06-005",
        "items": [
            {"description": "Electricity - day tariff", "quantity": 650, "unit": "kWh", "unit_price": 0.90, "net": 585.00},
            {"description": "Electricity - night tariff", "quantity": 200, "unit": "kWh", "unit_price": 0.50, "net": 100.00},
            {"description": "Distribution fee", "quantity": 1, "unit": "item", "unit_price": 65.00, "net": 65.00},
        ],
        "amount_net": 750.00,
        "amount_vat": 172.50,
        "amount_gross": 922.50,
    },
]

INVOICES_BY_ID = {inv["id"]: inv for inv in INVOICES}


# -------------------- PDF styles --------------------

PDF_STYLES = getSampleStyleSheet()
PDF_STYLES.add(ParagraphStyle(name="InvH1", fontSize=18, leading=22, spaceAfter=8, textColor=colors.HexColor("#1a4d8f")))
PDF_STYLES.add(ParagraphStyle(name="InvH2", fontSize=11, leading=15, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1a4d8f")))
PDF_STYLES.add(ParagraphStyle(name="InvSmall", fontSize=8, leading=10, textColor=colors.grey))


def render_invoice_pdf(inv: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {inv['id']}",
        author=VENDOR["name"],
    )

    story = []

    story.append(Paragraph(VENDOR["name"], PDF_STYLES["InvH1"]))
    story.append(Paragraph(VENDOR["address"], PDF_STYLES["Normal"]))
    story.append(Paragraph(
        f"NIP: {VENDOR['nip']} &nbsp;&nbsp;|&nbsp;&nbsp; IBAN: {VENDOR['iban']}",
        PDF_STYLES["InvSmall"],
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(f"INVOICE {inv['id']}", PDF_STYLES["InvH2"]))

    meta_rows = [
        ["Issue date", inv["issue_date"], "Due date", inv["due_date"]],
        ["Billing period", inv["period"], "PO number", inv["po"]],
        ["Status", inv["status"], "Currency", inv["currency"]],
    ]
    meta = Table(meta_rows, colWidths=[30 * mm, 40 * mm, 30 * mm, 40 * mm])
    meta.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(meta)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Bill to", PDF_STYLES["InvH2"]))
    story.append(Paragraph(CUSTOMER["name"], PDF_STYLES["Normal"]))
    story.append(Paragraph(CUSTOMER["address"], PDF_STYLES["Normal"]))
    story.append(Paragraph(f"NIP: {CUSTOMER['nip']}", PDF_STYLES["InvSmall"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Line items", PDF_STYLES["InvH2"]))
    items_header = ["#", "Description", "Qty", "Unit", "Unit price", "Net"]
    items_rows = [items_header]
    for i, item in enumerate(inv["items"], start=1):
        items_rows.append([
            str(i),
            item["description"],
            str(item["quantity"]),
            item["unit"],
            f"{item['unit_price']:.2f}",
            f"{item['net']:.2f}",
        ])
    items_table = Table(items_rows, colWidths=[10 * mm, 70 * mm, 18 * mm, 15 * mm, 27 * mm, 27 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a4d8f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 6 * mm))

    totals_rows = [
        ["Net total", f"{inv['amount_net']:.2f} {inv['currency']}"],
        ["VAT (23%)", f"{inv['amount_vat']:.2f} {inv['currency']}"],
        ["Amount due", f"{inv['amount_gross']:.2f} {inv['currency']}"],
    ]
    totals = Table(totals_rows, colWidths=[120 * mm, 45 * mm])
    totals.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -2), "Helvetica", 10),
        ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 12),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, -1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(totals)
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph("Payment details", PDF_STYLES["InvH2"]))
    story.append(Paragraph(f"IBAN: {VENDOR['iban']}", PDF_STYLES["Normal"]))
    story.append(Paragraph(f"Reference: {inv['id']}", PDF_STYLES["Normal"]))
    story.append(Paragraph(f"Questions? {VENDOR['email']}", PDF_STYLES["InvSmall"]))

    doc.build(story)
    return buf.getvalue()


# -------------------- routes --------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "energoplus-portal"}


@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    session: str | None = Cookie(default=None),
    anon_csrf: str | None = Cookie(default=None),
):
    if get_session(session):
        return RedirectResponse("/dashboard", status_code=303)
    csrf = anon_csrf or secrets.token_urlsafe(24)
    resp = templates.TemplateResponse(
        "login.html",
        {"request": request, "csrf": csrf, "error": None, "vendor": VENDOR},
    )
    if not anon_csrf:
        resp.set_cookie(
            "anon_csrf", csrf,
            httponly=False, samesite="strict",
            max_age=SESSION_TTL_SECONDS, path="/",
        )
    return resp


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(...),
    anon_csrf: str | None = Cookie(default=None),
):
    if not anon_csrf or csrf != anon_csrf:
        log.warning("CSRF mismatch on login for user=%s", username)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf": anon_csrf or "", "error": "Session expired. Please try again.", "vendor": VENDOR},
            status_code=400,
        )

    password_ok = password == REAL_PASSWORD or (ALLOW_DUMMY and password == DUMMY_PASSWORD)
    if username != REAL_USERNAME or not password_ok:
        log.warning("Login failed for user=%s", username)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "csrf": anon_csrf, "error": "Invalid username or password.", "vendor": VENDOR},
            status_code=401,
        )

    sid = new_session(username)
    log.info("Login OK for user=%s", username)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie(
        "session", sid,
        httponly=True, samesite="strict",
        max_age=SESSION_TTL_SECONDS, path="/",
    )
    resp.delete_cookie("anon_csrf", path="/")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: str | None = Cookie(default=None),
    status_filter: str = "all",
    q: str = "",
):
    s = get_session(session)
    if not s:
        return RedirectResponse("/login", status_code=303)

    invoices = list(INVOICES)
    if status_filter in ("Paid", "Unpaid"):
        invoices = [i for i in invoices if i["status"] == status_filter]
    if q:
        needle = q.strip().lower()
        invoices = [
            i for i in invoices
            if needle in i["id"].lower() or needle in i["po"].lower()
        ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "vendor": VENDOR,
            "customer": CUSTOMER,
            "invoices": invoices,
            "username": s["username"],
            "status_filter": status_filter,
            "query": q,
            "total_count": len(INVOICES),
        },
    )


@app.get("/invoice/{invoice_id}", response_class=HTMLResponse)
async def invoice_detail(
    request: Request,
    invoice_id: str,
    session: str | None = Cookie(default=None),
):
    s = get_session(session)
    if not s:
        return RedirectResponse("/login", status_code=303)

    inv = INVOICES_BY_ID.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return templates.TemplateResponse(
        "invoice.html",
        {
            "request": request,
            "vendor": VENDOR,
            "customer": CUSTOMER,
            "invoice": inv,
            "username": s["username"],
        },
    )


@app.get("/invoice/{invoice_id}/download")
async def invoice_download(
    invoice_id: str,
    format: str | None = None,
    session: str | None = Cookie(default=None),
):
    s = get_session(session)
    if not s:
        raise HTTPException(status_code=401, detail="Not authenticated")

    inv = INVOICES_BY_ID.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    fmt = (format or "pdf").lower()
    clean_id = invoice_id.replace("/", "_")

    if fmt == "csv":
        csv_data = f"Invoice,Vendor,IssueDate,DueDate,Amount,Currency,Status\n{inv['id']},\"{VENDOR['name']}\",{inv['issue_date']},{inv['due_date']},{inv['amount_gross']},{inv['currency']},{inv['status']}\n"
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{clean_id}.csv"', "Cache-Control": "no-store"},
        )
    elif fmt == "txt":
        txt_data = f"INVOICE {inv['id']}\nVendor: {VENDOR['name']}\nDate: {inv['issue_date']}\nDue: {inv['due_date']}\nTotal: {inv['amount_gross']:.2f} {inv['currency']}\nStatus: {inv['status']}\n"
        return Response(
            content=txt_data,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{clean_id}.txt"', "Cache-Control": "no-store"},
        )
    elif fmt in ("html", "htm"):
        html_data = f"<!DOCTYPE html><html><body><h1>INVOICE {inv['id']}</h1><p>Vendor: {VENDOR['name']}</p><p>Total: {inv['amount_gross']:.2f} {inv['currency']}</p><p>Status: {inv['status']}</p></body></html>"
        return Response(
            content=html_data,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{clean_id}.html"', "Cache-Control": "no-store"},
        )
    else:
        pdf_bytes = render_invoice_pdf(inv)
        filename = clean_id + ".pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )


@app.get("/api/invoices")
async def api_invoices(session: str | None = Cookie(default=None)):
    s = get_session(session)
    if not s:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "invoices": [
            {
                "id": inv["id"],
                "period": inv["period"],
                "amount_net": inv["amount_net"],
                "amount_gross": inv["amount_gross"],
                "currency": inv["currency"],
                "status": inv["status"],
                "po": inv["po"],
                "download_url": f"/invoice/{inv['id']}/download",
            }
            for inv in INVOICES
        ]
    }


@app.get("/logout")
async def logout(session: str | None = Cookie(default=None)):
    if session:
        sessions.pop(session, None)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session", path="/")
    return resp