#!/usr/bin/env python3
"""
Bot Factory — Bot Scaffolder

Creates the local bot structure and ensures the S3 bucket exists.
Uploading prompt/data to S3 is a separate step (make deploy-bot).

What it creates:
  Local:
    scripts/bots/{bot_id}/config.yml    (bot settings template)
    scripts/bots/{bot_id}/prompt.yml    (system prompt template)
    scripts/bots/{bot_id}/data/         (drop YAML knowledge base files here)

  S3 (bot-factory-data bucket):
    Creates the bucket if it doesn't exist

Usage:
  python3 scripts/scaffold_bot.py cat
  python3 scripts/scaffold_bot.py cat --endpoint-url http://localhost:4566
"""

import sys
import argparse
import boto3
from pathlib import Path


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

CONFIG_TEMPLATE = """bot:
  id: "{bot_id}"
  enabled: false
  name: "<bot_name>"
  personality: "<bot_personality>"

  response_style:
    tone: "<response_tone>"
    length: "<response_length>"
    suggestions: true

  model:
    provider: "bedrock"
    name: "anthropic.claude-sonnet-4-20250514-v1:0"
    max_tokens: 1024

  rag:
    top_k: 5
    similarity_threshold: 0.3

  boundaries:
    discuss_unrelated: false
"""

PROMPT_TEMPLATE = """system_prompt: |
  You are {bot_id}, a helpful assistant.

  ## Your Role
  <describe the bot's role here>

  ## Guidelines
  - Only answer questions using retrieved context
  - If you don't have information, say so honestly
  - NEVER invent or fabricate information

  ## Boundaries
  - Stay on topic
  - Be helpful and concise
"""

LOAD_README = """# {bot_id} — Knowledge Base Source Files

Drop YAML knowledge base files here, then run:

  make load-bot bot={bot_id}

This syncs files to s3://bot-factory-data/bots/{bot_id}/data/

Then generate embeddings:

  make embed BOT={bot_id}
"""


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def get_s3_client(endpoint_url: str = None):
    kwargs = {}
    if endpoint_url:
        kwargs = {
            "endpoint_url": endpoint_url,
            "aws_access_key_id": "test",
            "aws_secret_access_key": "test",
            "region_name": "us-east-1",
        }
    return boto3.client("s3", **kwargs)


def ensure_bucket(s3, bucket: str):
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  ✓ S3 bucket '{bucket}' exists")
    except Exception:
        s3.create_bucket(Bucket=bucket)
        print(f"  ✅ Created S3 bucket '{bucket}'")


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

def scaffold(bot_id: str, endpoint_url: str = None, bucket: str = "bot-factory-data"):
    print(f"\n🔧 Scaffolding bot: {bot_id}\n")

    # --- Local: scripts/bots/{bot_id}/ (config + prompt + data/) ---
    bot_dir = Path("scripts") / "bots" / bot_id
    if bot_dir.exists():
        print(f"  ⚠️  scripts/bots/{bot_id}/ already exists — skipping")
    else:
        bot_dir.mkdir(parents=True)
        config_path = bot_dir / "config.yml"
        config_path.write_text(CONFIG_TEMPLATE.format(bot_id=bot_id))
        print(f"  ✅ Created {config_path}")

        prompt_path = bot_dir / "prompt.yml"
        prompt_path.write_text(PROMPT_TEMPLATE.format(bot_id=bot_id))
        print(f"  ✅ Created {prompt_path}")

        data_dir = bot_dir / "data"
        data_dir.mkdir()
        readme_path = data_dir / "README.md"
        readme_path.write_text(LOAD_README.format(bot_id=bot_id))
        print(f"  ✅ Created scripts/bots/{bot_id}/data/")

    # --- S3: ensure bucket exists ---
    s3 = get_s3_client(endpoint_url)
    ensure_bucket(s3, bucket)

    # --- Summary ---
    print(f"\n🎉 Bot '{bot_id}' scaffolded!\n")
    print(f"   Local files created:")
    print(f"     scripts/bots/{bot_id}/config.yml     ← edit bot settings")
    print(f"     scripts/bots/{bot_id}/prompt.yml     ← edit system prompt")
    print(f"     scripts/bots/{bot_id}/data/           ← drop knowledge base YAMLs here")
    print(f"\n   Next steps:")
    print(f"   1. Edit scripts/bots/{bot_id}/config.yml")
    print(f"   2. Edit scripts/bots/{bot_id}/prompt.yml")
    print(f"   3. Run: make deploy-bot bot={bot_id}   ← uploads config + prompt to S3")
    print(f"   4. Add YAMLs to scripts/bots/{bot_id}/data/ and run: make load-bot bot={bot_id}")
    print(f"   5. Generate embeddings: make embed BOT={bot_id}")
    print(f"   6. Set enabled: true in config.yml and restart\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold a new Bot Factory bot")
    parser.add_argument("bot_id", help="Unique bot identifier (e.g. 'cat')")
    parser.add_argument("--endpoint-url", default=None,
                        help="LocalStack endpoint (e.g. http://localhost:4566)")
    parser.add_argument("--bucket", default="bot-factory-data",
                        help="S3 bucket name (default: bot-factory-data)")

    args = parser.parse_args()

    if not all(c.isalnum() or c == '-' for c in args.bot_id):
        print("❌ bot_id must be alphanumeric or hyphens (e.g. 'guitar', 'the-fret-detective')")
        sys.exit(1)

    scaffold(args.bot_id, args.endpoint_url, args.bucket)