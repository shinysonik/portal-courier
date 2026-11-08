"""Fake Vultr Serverless Inference for local testing (no key needed).
Run:  uvicorn scripts.mock_vultr:app --port 9000
Then: VULTR_BASE_URL=http://127.0.0.1:9000/v1  VULTR_API_KEY=x  VULTR_MODEL=mock
Set MOCK_FAIL=1 to make it return HTTP 500 (tests the retry + extraction_failed path)."""
import json, os, re
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()


@app.get("/v1/models")
def models():
    return {"data": [{"id": "mock"}]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    if os.getenv("MOCK_FAIL") == "1":
        raise HTTPException(500, "mock failure")
    body = await req.json()
    text = body["messages"][-1]["content"]
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("Invoice text")]
    amount = re.search(r"(\d[\d ,.]*\d)\s*(EUR|PLN|USD)", text)
    number = re.search(r"INVOICE\s+(\S+)", text)
    out = {"vendor": lines[0] if lines else None,
           "amount": f"{amount.group(1)} {amount.group(2)}" if amount else None,
           "invoice_number": number.group(1) if number else None}
    return {"choices": [{"message": {"role": "assistant", "content": "```json\n" + json.dumps(out) + "\n```"}}]}
