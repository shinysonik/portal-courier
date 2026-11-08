# Portal Courier — Docker + Zero-Trust deployment runbook (Vultr VM)

Target: one Ubuntu 24.04 Vultr Cloud Compute instance running everything:
portals (demo suppliers) · MITM proxy · orchestrator (FastAPI + dashboard) · disposable agent containers on an isolated, firewalled Docker network.

> **Status of this runbook.** The agent, orchestrator, proxy fix and dashboard were tested locally (agent as a subprocess).
> Everything *Docker-, iptables- and systemd-related below has not been run yet* — each phase therefore ends with a **Check**.
> Do not move to the next phase until the check passes. Anything that fails: see Troubleshooting at the end.

```
Internet ──(8000 only)──▶ orchestrator ──docker──▶ [ agent container ]  on  playwright-net (172.28.0.0/16)
                              │                          │  only reachable endpoint: 172.28.0.1:8888
                              │ reads events.jsonl       ▼
                              └─────────────────── MITM proxy (172.28.0.1:8888)
                                                         │  allowlist · VAULT_PASS → real password · Set-Cookie stripped
                                                         ▼
                                              portals on 127.0.0.1:5001 / 5002
```

Why the portals are at `127.0.0.1`: the container resolves nothing itself (DNS is a dead end) and its browser is forced to send
*every* request, loopback included, to the proxy. The proxy runs on the host, so for it `127.0.0.1:5001` is the real portal.

---

## 0. Before you start

* Vultr account with the $200 hackathon credit applied (Billing → Gift Code).
* **Serverless Inference** subscription (Products → Serverless → Inference) → copy its API key. This is *not* the cloud API key.
* A model id: `curl -s https://api.vultrinference.com/v1/models -H "Authorization: Bearer $KEY"`. Choose a plain **instruct** model
  (reasoning models can spend the 400-token limit thinking and never emit the JSON).
* The repo URL, and your public SSH key.

## 1. Create the VM

1. Vultr console → **Deploy** → *Cloud Compute* (shared CPU; **not** GPU — GPUs are unavailable for this event).
2. Ubuntu **24.04 LTS x64**, at least **2 vCPU / 4 GB RAM** (Chromium alone is capped at 1 GB), 50 GB+ disk. Add your SSH key.
3. **Firewall group** (Products → Firewall), attach it to the instance:

   | Port | Source | Why |
   |---|---|---|
   | 22/tcp | your IP only | SSH |
   | 8000/tcp | anywhere | the public demo URL |
   | *(nothing else)* | | **never** expose 8888 (proxy) or 5001/5002 (portals) |

> The dashboard/API has **no authentication**: anyone with the URL can queue jobs and approve invoices. Acceptable for a
> demo with fake data; if you don't want that, put Caddy with basic auth in front and open 80/443 instead of 8000.

**Check:** `ssh root@<VM_IP>` works.

## 2. Install the base system

```bash
apt update && apt -y upgrade
apt -y install docker.io git python3-venv python3-pip iptables curl
systemctl enable --now docker
DEBIAN_FRONTEND=noninteractive apt -y install iptables-persistent     # lets the firewall rules survive a reboot

useradd -m -s /bin/bash courier
usermod -aG docker courier          # NOTE: docker group == root-equivalent on this box. Fine for a hackathon VM.
mkdir -p /opt/portal-courier /etc/portal-courier
chown courier:courier /opt/portal-courier
python3 -m venv /opt/mitm && /opt/mitm/bin/pip install mitmproxy       # separate venv: mitmproxy conflicts with the app's deps
```

**Check:** `docker version` shows Client *and* Server. `/opt/mitm/bin/mitmdump --version` prints a version.

## 3. Get the code, build the agent image

```bash
sudo -iu courier
git clone <REPO_URL> /opt/portal-courier        # the directory is empty, so this works
cd /opt/portal-courier
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
docker build -t portal-courier-agent -f agent/Dockerfile .
```

If `FROM mcr.microsoft.com/playwright/python:v1.49.0-noble` cannot be pulled, use the fallback written in the Dockerfile's header comment.

**Check:**
```bash
docker run --rm --shm-size=512m portal-courier-agent python3 -c \
 "from playwright.sync_api import sync_playwright as s; p=s().start(); b=p.chromium.launch(args=['--no-sandbox']); print('chromium ok', b.version); b.close(); p.stop()"
```
→ `chromium ok …`. (Exit with `exit` to leave the courier shell when done.)

## 4. Create the zero-trust network + firewall (as root)

```bash
cd /opt/portal-courier/agent/docker-infrastructure
chmod +x *.sh
./deploy-zerotrust-network.sh
```

It creates `playwright-net` (bridge `br-playwright`, 172.28.0.0/16, gateway 172.28.0.1), drops everything from that bridge to the host
except `172.28.0.1:8888`, drops all forwarded (internet) traffic from the bridge, and blocks port 53.

**Check:**
```bash
docker network inspect playwright-net --format '{{(index .IPAM.Config 0).Subnet}}'   # 172.28.0.0/16
ip -br addr show br-playwright                                                        # has 172.28.0.1
iptables -S PLAYWRIGHT-HOST ; iptables -S PLAYWRIGHT-EGRESS ; iptables -S DOCKER-USER | grep PLAYWRIGHT
```
If `br-playwright` does not exist until a container is attached, run one throw-away container on the network first:
`docker run --rm --network playwright-net alpine true`, then re-check.

## 5. Services (systemd)

Demo "supplier side" secrets — read **only** by the portals and the proxy, never by the orchestrator or the agent:

```bash
cat > /etc/portal-courier/demo.env <<'EOT'
REAL_USERNAME=anna
REAL_PASSWORD=real_secret_123
ALLOWED_HOSTS=127.0.0.1:5001,127.0.0.1:5002
EOT
chmod 600 /etc/portal-courier/demo.env
```

Orchestrator settings (this file does **not** contain the demo password):

```bash
cat > /opt/portal-courier/.env <<'EOT'
RUNNER=docker
DOCKER_NETWORK=playwright-net
PROXY_URL=http://172.28.0.1:8888
VULTR_API_KEY=<serverless inference key>
VULTR_BASE_URL=https://api.vultrinference.com/v1
VULTR_MODEL=<instruct model id>
EOT
chown courier:courier /opt/portal-courier/.env && chmod 600 /opt/portal-courier/.env
```

Units:

```bash
cd /etc/systemd/system

for spec in "good:5001" "hostile:5002"; do
  name=${spec%%:*}; port=${spec##*:}
  cat > portal-$name.service <<EOT
[Unit]
Description=Demo supplier portal ($name)
After=network.target
[Service]
User=courier
WorkingDirectory=/opt/portal-courier
EnvironmentFile=/etc/portal-courier/demo.env
ExecStart=/opt/portal-courier/.venv/bin/uvicorn portals.$name.app:app --host 127.0.0.1 --port $port
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOT
done

cat > courier-proxy.service <<'EOT'
[Unit]
Description=Portal Courier MITM proxy
After=docker.service
Requires=docker.service
[Service]
User=courier
WorkingDirectory=/opt/portal-courier
EnvironmentFile=/etc/portal-courier/demo.env
# wait (max 30s) for the isolated bridge, then listen ONLY on it - never on the public interface
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do ip -4 addr show br-playwright | grep -q 172.28.0.1 && exit 0; sleep 1; done; exit 1'
ExecStart=/opt/mitm/bin/mitmdump -s proxy/addon.py --listen-host 172.28.0.1 --listen-port 8888
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOT

cat > courier-orchestrator.service <<'EOT'
[Unit]
Description=Portal Courier orchestrator + dashboard
After=docker.service courier-proxy.service
Requires=docker.service
[Service]
User=courier
WorkingDirectory=/opt/portal-courier
ExecStart=/opt/portal-courier/.venv/bin/uvicorn orchestrator.app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOT

systemctl daemon-reload
systemctl enable --now portal-good portal-hostile courier-proxy courier-orchestrator
```

The proxy writes `events.jsonl` into its working directory and the orchestrator reads it from the repo root — both are `/opt/portal-courier`, so keep them identical.

**Check:**
```bash
systemctl --no-pager status portal-good portal-hostile courier-proxy courier-orchestrator | grep -E "●|Active"
curl -s localhost:8000/health        # {"status":"ok","runner":"docker",...,"vultr_configured":true}
journalctl -u courier-orchestrator -n 5 --no-pager   # runner=docker network=playwright-net ... portal_host=127.0.0.1 proxy=http://172.28.0.1:8888
```

## 6. Verify the containment, in this order

**6.1 The firewall holds** (this is a strong video moment — keep the output):
```bash
docker run --rm --network playwright-net --dns 127.0.0.1 --cap-drop ALL --security-opt no-new-privileges:true \
  -e HTTP_PROXY=http://172.28.0.1:8888 -e HTTPS_PROXY=http://172.28.0.1:8888 \
  -v /opt/portal-courier/agent/docker-infrastructure/verify-zerotrust.sh:/verify.sh:ro \
  portal-courier-agent bash /verify.sh
```
Expect 4/4: WAN egress blocked, port 53 blocked, host SSH blocked, proxy reachable.

**6.2 One agent container by hand, good and hostile:**
```bash
for k in good hostile; do
  [ $k = good ] && url=http://127.0.0.1:5001/login vat="" || { url=http://127.0.0.1:5002/login; vat=9876543210; }
  mkdir -p /tmp/out_$k && chmod 777 /tmp/out_$k
  docker run --rm --network playwright-net --dns 127.0.0.1 --cap-drop ALL --security-opt no-new-privileges:true \
    --shm-size 512m --memory 1g --pids-limit 256 \
    -e PORTAL_URL=$url -e USERNAME=anna -e DUMMY_PASSWORD=VAULT_PASS -e VAT_ID=$vat -e OUT_DIR=/out \
    -e HTTP_PROXY=http://172.28.0.1:8888 -e HTTPS_PROXY=http://172.28.0.1:8888 \
    -v /tmp/out_$k:/out portal-courier-agent
  echo "$k exit=$?"; ls /tmp/out_$k
done
grep -c BLOCKED /opt/portal-courier/events.jsonl      # expect 5 after the hostile run
```

**6.3 The whole pipeline through the API:**
```bash
sudo -iu courier
cd /opt/portal-courier && .venv/bin/python scripts/smoke_test.py --decide
```
Good job: clean, fields from Vultr, approved. Hostile job: suspicious with the `SYSTEM OVERRIDE` quote, `BLOCKED: 5`, rejected.

**6.4 From your laptop:** open `http://<VM_IP>:8000/`, press **Start**, review both cards, Approve one, Reject the other with a comment, open the **Event log** tab.

**6.5 Release checklist**
```bash
docker ps -a --filter name=pc-                                  # empty: containers are destroyed after every run
grep -rl real_secret_123 /opt/portal-courier/jobs || echo "no password in job output"
grep -rl "$(grep ^VULTR_API_KEY /opt/portal-courier/.env | cut -d= -f2)" /opt/portal-courier/jobs || echo "no API key in job output"
python3 - <<'PY'
import json,glob
for f in sorted(glob.glob('/opt/portal-courier/jobs/*/result.json')):
    r=json.load(open(f)); print(r['portal']['id'], round(r['agent_finished_at']-r['agent_started_at']-1.2,1),'s agent run', r.get('inference'))
PY
```
Brief targets: cold start < 10 s, < 30 s per portal. If slower, tell the agent owner before adding retries.

**6.6 Reboot test** (do it once, before recording): `reboot`, wait, then `systemctl status courier-proxy` and repeat 6.4.
If the proxy failed at boot because `br-playwright` was not up yet, `systemctl restart courier-proxy courier-orchestrator`; to make it permanent run the one-container command from section 4 in a `ExecStartPre` of the proxy.

## 7. Hackathon submission mapping (Challenge 1 · Blast Radius Zero)

| Requirement | Where it is satisfied | How to show it |
|---|---|---|
| Vultr VM backend, web app on Vultr | this VM runs proxy, orchestrator, dashboard, containers | public URL `http://<VM_IP>:8000/` |
| Vultr Serverless Inference in the agent path | `orchestrator/app/main.py` → `extract_fields()` (`/chat/completions`) | every result card shows `Vultr · <model> · <ms>` |
| Process isolation | one disposable container per portal, isolated bridge, caps dropped | 6.1 output, `docker ps -a` empty |
| Secret hygiene | agent only knows `VAULT_PASS`; real password only in the proxy's env; cookies kept in the proxy | `grep` in 6.5, `CREDENTIAL_INJECTED` / `COOKIE_STRIPPED` in the event log |
| Resource limits | 60 s agent limit, 70 s hard kill, 1 GB RAM, 1 CPU, 256 pids | `main.py` `run_agent_docker` |
| Lifecycle discipline | container removed after every run | `docker ps -a` empty |
| **Containment moment (video)** | hostile portal → 5 BLOCKED events → next job continues → card flagged | Event log tab + the red card with the quoted `SYSTEM OVERRIDE` line |
| Human approval | nothing is "processed" until Approve (`awaiting_review` → `approved`/`rejected`) | click Approve / Reject with a comment |

README must state honestly: the proxy is the allowlist; the iptables rules are the second, independent barrier (6.1 proves it);
the dashboard has no auth; the demo credentials are fake.

## 8. Troubleshooting (first stop: `jobs/<id>/agent.log` and `jobs/<id>/events.json`)

| Symptom | Likely cause → fix |
|---|---|
| Agent exit 3, "proxy 172.28.0.1:8888 unreachable" | proxy not listening on the bridge IP → `systemctl status courier-proxy`, `ss -ltn | grep 8888`; or the INPUT rule's `PROXY_PORT` differs from 8888 |
| Agent exit 1, "no password field" | proxy answered 403: allowlist mismatch → `ALLOWED_HOSTS` must contain `127.0.0.1:5001,127.0.0.1:5002`; look for BLOCKED hosts in `events.json` |
| Container fails to start, "operation not permitted" | hardening conflict → set `DOCKER_HARDEN=0` in `.env`, restart the orchestrator, retry; report which flag it was |
| Only 1 BLOCKED event | `proxy/addon.py` lacks the `http_connect` method (see git history) |
| `extraction_failed: true` | read `inference.error`: 401 wrong key · 404/400 wrong model id · parse error → try another instruct model |
| Dashboard says "orchestrator unreachable" | service down or port 8000 not open in the Vultr firewall group |
| Dashboard unstyled | the page loads Tailwind and fonts from public CDNs: the *viewer's browser* needs internet, the VM does not |
| `verify-zerotrust.sh` test 1 FAILED | the egress rule is not active on the bridge → re-run section 4, re-check `iptables -S DOCKER-USER` |

## 9. Cost and cleanup

Credits drain while the VM exists (stopping is not enough — destroy it when the hackathon is over). Snapshot first if you want to keep the setup.
