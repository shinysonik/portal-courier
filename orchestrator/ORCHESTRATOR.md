# Orchestrator Architecture

The orchestrator (`orchestrator/app/main.py`) provides the core job scheduler, human-in-the-loop review interface, and Vultr Serverless Inference integration.

## Architecture
- **Job Queue:** Sequential in-memory FIFO queue with atomic state persistence (`jobs/<job_id>/result.json`).
- **Container Lifecycle:** Spawns ephemeral Docker containers on `playwright-net` and destroys them forcefully in a `finally` block after invoice extraction.
- **Vultr AI Extraction:** Dispatches extracted invoice text to Vultr Serverless Inference (`/v1/chat/completions`) using prompt defense guards against prompt injections.
- **Human-in-the-Loop Review:** Serves static frontend dashboard at `GET /` and exposes REST endpoints for manual invoice approvals and rejections with operator remarks.
