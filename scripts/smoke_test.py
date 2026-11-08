"""Queue both demo portals, wait, print what happened.  python orchestrator/smoke_test.py [--approve-good --reject-hostile]"""
import sys, time, httpx

API = "http://127.0.0.1:8000"
c = httpx.Client(base_url=API, timeout=30)
jobs = c.post("/jobs", json={"portals": [{"portal_id": "good"}, {"portal_id": "hostile"}]}).json()
ids = [j["id"] for j in jobs]
print("queued:", ids)
while True:
    cur = [c.get(f"/jobs/{i}").json() for i in ids]
    print("  ", [(j["portal_id"], j["status"], j["phase"]) for j in cur])
    if all(j["status"] not in ("queued", "running") for j in cur):
        break
    time.sleep(2)
for j in cur:
    ev = {}
    for e in j["events"]:
        ev[e["type"]] = ev.get(e["type"], 0) + 1
    print(f"\n== {j['portal_id']}: status={j['status']} exit={j['exit_code']} invoice_id={j['invoice_id']}")
    print("   suspicious:", j["suspicious"], "| quote:", (j["quote"] or "")[:90])
    print("   fields:", j["fields"], "| extraction_failed:", j["extraction_failed"], "| inference:", j.get("inference"))
    print("   events:", ev)
if "--decide" in sys.argv:
    for j in cur:
        act = "reject" if j["suspicious"] else "approve"
        r = c.post(f"/jobs/{j['id']}/{act}", json={"comment": "smoke test"})
        print(act, j["portal_id"], "->", r.json()["status"])
