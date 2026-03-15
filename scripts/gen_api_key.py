#!/usr/bin/env python3
"""
Bot Factory — API Key Generator

Generates a random API key for a bot and stores it in DynamoDB.

Usage:
  python3 scripts/gen_api_key.py guitar --name dev-local
  python3 scripts/gen_api_key.py guitar --name dev-local --endpoint-url http://localhost:4566
"""

import argparse
import re
import secrets
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3


def get_dynamodb_table(table_name: str, endpoint_url: str = None):
    kwargs = {"region_name": os.getenv("AWS_REGION", "us-east-1")}
    if endpoint_url:
        kwargs.update({
            "endpoint_url": endpoint_url,
            "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "test"),
            "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        })
    dynamodb = boto3.resource("dynamodb", **kwargs)
    return dynamodb.Table(table_name)


def gen_key(bot_id: str, name: str, endpoint_url: str = None, table_name: str = "BotFactoryApiKeys"):
    api_key = f"bfk_{secrets.token_urlsafe(32)}"

    table = get_dynamodb_table(table_name, endpoint_url)
    table.put_item(Item={
        "api_key": api_key,
        "bot_id": bot_id,
        "name": name,
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    print(f"\n  API key generated for bot '{bot_id}'")
    print(f"  Name:    {name}")
    print(f"  Key:     {api_key}")
    print(f"  Table:   {table_name}")
    print(f"\n  Use this header in requests:")
    print(f"  X-API-Key: {api_key}")

    # Update .env if it exists
    env_path = Path(".env")
    if env_path.exists():
        env_text = env_path.read_text()
        if re.search(r"^API_KEY=.*$", env_text, re.MULTILINE):
            env_text = re.sub(r"^API_KEY=.*$", f"API_KEY={api_key}", env_text, flags=re.MULTILINE)
            env_path.write_text(env_text)
            print(f"\n  Updated API_KEY in .env")
        else:
            with open(env_path, "a") as f:
                f.write(f"\nAPI_KEY={api_key}\n")
            print(f"\n  Added API_KEY to .env")
    print()

    return api_key


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an API key for a Bot Factory bot")
    parser.add_argument("bot_id", help="Bot identifier (e.g. 'guitar')")
    parser.add_argument("--name", required=True, help="Key label (e.g. 'dev-local', 'prod-site')")
    parser.add_argument("--endpoint-url", default=None, help="LocalStack endpoint")
    parser.add_argument("--table", default="BotFactoryApiKeys", help="DynamoDB table name")

    args = parser.parse_args()

    if not all(c.isalnum() or c == '-' for c in args.bot_id) or args.bot_id.startswith('-') or args.bot_id.endswith('-'):
        print("bot_id must be alphanumeric with optional hyphens")
        sys.exit(1)

    gen_key(args.bot_id, args.name, args.endpoint_url, args.table)
