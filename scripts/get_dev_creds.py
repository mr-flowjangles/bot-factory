#!/usr/bin/env python3
"""
Fetch short-lived AWS credentials from the Bot Factory Lambda execution role
and write them into the local .env file.

Usage:
    python3 scripts/get_dev_creds.py

Required env vars (already in .env or exported):
    LAMBDA_API_URL  — e.g. https://abc123.execute-api.us-east-1.amazonaws.com
    DEV_TOKEN       — secret token matching the Lambda's DEV_TOKEN env var
"""

import os
import sys
import re
import urllib.request
import urllib.error
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ENV_FILE = Path(__file__).parent.parent / ".env"

LAMBDA_API_URL = os.getenv("LAMBDA_API_URL", "").rstrip("/")
DEV_TOKEN = os.getenv("DEV_TOKEN", "")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return ""


def upsert_var(content: str, key: str, value: str) -> str:
    """Update an existing KEY=value line, or append it if absent."""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(new_line, content)
    # Append with newline
    if content and not content.endswith("\n"):
        content += "\n"
    return content + new_line + "\n"


def write_env_file(path: Path, content: str):
    path.write_text(content)
    print(f"  ✓ wrote {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not LAMBDA_API_URL:
        print("ERROR: LAMBDA_API_URL is not set.")
        print("  Add it to your .env:  LAMBDA_API_URL=https://<api-gw-id>.execute-api.us-east-1.amazonaws.com")
        sys.exit(1)

    if not DEV_TOKEN:
        print("ERROR: DEV_TOKEN is not set.")
        print("  Add it to your .env:  DEV_TOKEN=<your-secret-token>")
        sys.exit(1)

    url = f"{LAMBDA_API_URL}/dev-creds"
    print(f"Fetching creds from {url} ...")

    req = urllib.request.Request(url, headers={"x-dev-token": DEV_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"ERROR: HTTP {e.code} — {body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Could not reach {url} — {e.reason}")
        sys.exit(1)

    content = load_env_file(ENV_FILE)

    content = upsert_var(content, "APP_ENV", "production")
    content = upsert_var(content, "AWS_ACCESS_KEY_ID", data["aws_access_key_id"])
    content = upsert_var(content, "AWS_SECRET_ACCESS_KEY", data["aws_secret_access_key"])
    content = upsert_var(content, "AWS_SESSION_TOKEN", data["aws_session_token"])
    content = upsert_var(content, "AWS_REGION", data["region"])

    write_env_file(ENV_FILE, content)
    print("Done. Restart 'chalice local' to pick up new credentials.")
    print("Creds are valid for ~1 hour — re-run 'make dev-creds' to refresh.")


if __name__ == "__main__":
    main()
