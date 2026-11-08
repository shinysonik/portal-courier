# portal-courier-agent: disposable browser agent.
# Build from the repo root:  docker build -t portal-courier-agent -f agent/Dockerfile .
#
# Base image = official Playwright image, same version as requirements.txt (1.49.0), so the
# Chromium build matches the Python package and nothing is downloaded at build time.
# FALLBACK if this tag cannot be pulled: FROM python:3.11-slim-bookworm and replace the RUN below with
#   RUN pip install --no-cache-dir playwright==1.49.0 && playwright install --with-deps chromium
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir playwright==1.49.0

# Only the agent code goes into the image: no .env, no credentials, nothing else.
WORKDIR /app
COPY agent/agent.py /app/agent.py

# /out is bind-mounted by the orchestrator (OUT_ROOT/<job_id> -> /out). Runs as root inside the
# container (Chromium uses --no-sandbox); the container is destroyed after every run.
CMD ["python3", "/app/agent.py"]
