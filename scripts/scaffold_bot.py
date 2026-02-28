#!/usr/bin/env python3
"""
Bot Factory — Bot Scaffolder

Creates the full bot structure: local config + S3 data storage.

What it creates:
  Local:
    bots/{bot_id}/config.yml        (template with bot_id filled in)

  S3 (bot-factory-data bucket):
    {bot_id}/prompt.yml             (empty prompt template)
    {bot_id}/data/                  (ready for knowledge base files)

Usage:
  python3 scripts/scaffold_bot.py cat
  python3 scripts/scaffold_bot.py cat --endpoint-url http://localhost:4566
"""

import sys
import os
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
    provider: "anthropic"
    name: "claude-sonnet-4-20250514"
    max_tokens: 1024

  rag:
    embedding_model: "text-embedding-3-small"
    top_k: 5
    similarity_threshold: 0.3

  boundaries:
    discuss_unrelated: false

suggestions:
  - "<suggestion_1>"
  - "<suggestion_2>"
  - "<suggestion_3>"

frontend:
  subtitle: "<subtitle>"
  welcome: "<welcome_message>"
  placeholder: "Type a message..."
  badge: "Beta"
  nav:
    - icon: "💬"
      label: "Chat"
      section: "chat"
    - icon: "ℹ️"
      label: "About"
      section: "about"
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


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def get_s3_client(endpoint_url: str = None):
    """Create an S3 client, using local endpoint if provided."""
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
    """Create the bucket if it doesn't exist."""
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  ✓ S3 bucket '{bucket}' exists")
    except s3.exceptions.ClientError:
        s3.create_bucket(Bucket=bucket)
        print(f"  ✅ Created S3 bucket '{bucket}'")


def upload_text(s3, bucket: str, key: str, content: str):
    """Upload a text file to S3."""
    s3.put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"))
    print(f"  ✅ Uploaded s3://{bucket}/{key}")


def create_folder(s3, bucket: str, prefix: str):
    """Create an empty folder marker in S3."""
    s3.put_object(Bucket=bucket, Key=prefix, Body=b"")
    print(f"  ✅ Created s3://{bucket}/{prefix}")


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

def scaffold(bot_id: str, endpoint_url: str = None, bucket: str = "bot-factory-data"):
    """Create the full bot structure."""
    print(f"\n🔧 Scaffolding bot: {bot_id}\n")

    # --- Local: bots/{bot_id}/config.yml ---
    bot_dir = Path("bots") / bot_id

    if bot_dir.exists():
        print(f"  ⚠️  bots/{bot_id}/ already exists — skipping local config")
    else:
        bot_dir.mkdir(parents=True)
        config_content = CONFIG_TEMPLATE.format(bot_id=bot_id)
        config_path = bot_dir / "config.yml"
        config_path.write_text(config_content)
        print(f"  ✅ Created {config_path}")

    # --- S3: prompt + data folder ---
    s3 = get_s3_client(endpoint_url)
    ensure_bucket(s3, bucket)

    prompt_content = PROMPT_TEMPLATE.format(bot_id=bot_id)
    upload_text(s3, bucket, f"{bot_id}/prompt.yml", prompt_content)
    create_folder(s3, bucket, f"{bot_id}/data/")

    # --- Summary ---
    print(f"\n🎉 Bot '{bot_id}' scaffolded!\n")
    print(f"   Local:")
    print(f"     bots/{bot_id}/config.yml    ← edit bot settings")
    print(f"   S3 ({bucket}):")
    print(f"     {bot_id}/prompt.yml         ← edit system prompt")
    print(f"     {bot_id}/data/              ← add knowledge base YAML files")
    print(f"\n   Next steps:")
    print(f"   1. Edit bots/{bot_id}/config.yml with your bot's details")
    print(f"   2. Edit the prompt in S3: {bot_id}/prompt.yml")
    print(f"   3. Add data files to S3: {bot_id}/data/")
    print(f"   4. Run embeddings: python3 core/generate_embeddings.py {bot_id}")
    print(f"   5. Set enabled: true in config.yml and restart\n")


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

    if not args.bot_id.isalnum():
        print("❌ bot_id must be alphanumeric (e.g. 'cat', 'guitar', 'recipes')")
        sys.exit(1)

    scaffold(args.bot_id, args.endpoint_url, args.bucket)
