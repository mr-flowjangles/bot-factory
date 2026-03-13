# Chalice References in the Repository

This document lists every tracked-file occurrence of the term `Chalice`/`chalice` in the codebase (via `git grep -ni "chalice"`).

## README.md
- **Line 30**: "Local development uses Docker Compose (nginx + LocalStack) and Chalice local server."
- **Line 54**: "sync_tf_config.py      ← Sync Terraform outputs → .chalice/config.json"
- **Line 60**: "app.py                     ← Chalice app (local dev API server)"
- **Line 64**: ".chalice/                  ← Chalice config + deployment state"
- **Line 83**: "... starts the Chalice API server on port 8000."
- **Line 100**: "# 1. Build and apply Terraform, then deploy Chalice API"

## app/chat.html
- **Line 265**: `title="Chalice API (health check)"`
- **Line 350**: "Otherwise → fall back to Chalice /chat/stream (buffered)"

## dev_server.py
- **Line 3**: "Bypasses Chalice's Werkzeug buffering."

## factory/README.md
- **Line 24**: "**Chalice** — `pip install chalice` ..."
- **Line 55**: "app.py                         # Chalice app (local dev only)"
- **Line 228**: "# First time: provision infrastructure + deploy Chalice API"
- **Line 328**: "... Chalice API :8000 ..."
- **Line 334**: "... Terraform + Chalice deploy"

## factory/core/docs/LOCAL_DEVELOPMENT.md
- **Line 18**: "Starts the Chalice local API server on :8000"
- **Line 56**: "# Or hit the Chalice API directly"
- **Line 70**: "Chalice's local server (port 8000) buffers the full response..."
- **Line 96**: "For the Chalice server, credentials are passed through..."
