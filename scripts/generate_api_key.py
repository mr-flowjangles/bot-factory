#!/usr/bin/env python3
"""
Generate and store Bot Factory API keys.

Usage:
    # Local (hits LocalStack)
    python3 -m scripts.generate_api_key guitar --name "fret-detective-prod"

    # Production (hits real AWS)
    APP_ENV=production python3 -m scripts.generate_api_key guitar --name "fret-detective-prod"

    # Wildcard key (access to all bots)
    python3 -m scripts.generate_api_key '*' --name "admin-key"

    # Revoke a key
    python3 -m scripts.generate_api_key --revoke bf_live_abc123...
"""

import argparse
import hashlib
import os
import secrets
import sys
import time

import boto3
from dotenv import load_dotenv

load_dotenv()

API_KEYS_TABLE = os.getenv("API_KEYS_TABLE", "BotFactoryApiKeys")
APP_ENV = os.getenv("APP_ENV", "local")
KEY_PREFIX = "bf_live_"


def get_table():
    if APP_ENV in ("local", ""):
        endpoint = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
        dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint, region_name="us-east-1")
    else:
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    return dynamodb.Table(API_KEYS_TABLE)


def generate_key():
    """Generate a random API key with prefix."""
    random_part = secrets.token_urlsafe(32)
    return f"{KEY_PREFIX}{random_part}"


def store_key(raw_key: str, bot_id: str, key_name: str):
    """Hash and store the key in DynamoDB."""
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    table = get_table()

    item = {
        "pk": key_hash,
        "bot_id": bot_id,
        "key_name": key_name,
        "created_at": int(time.time()),
        "key_prefix": raw_key[:12] + "...",  # Store prefix for identification
    }

    table.put_item(Item=item)
    return key_hash


def revoke_key(raw_key: str):
    """Mark a key as revoked."""
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    table = get_table()

    try:
        response = table.update_item(
            Key={"pk": key_hash},
            UpdateExpression="SET revoked_at = :t",
            ExpressionAttributeValues={":t": int(time.time())},
            ReturnValues="ALL_NEW",
        )
        item = response.get("Attributes", {})
        print(f"Revoked key for bot_id={item.get('bot_id')} ({item.get('key_name')})")
    except Exception as e:
        print(f"Error revoking key: {e}", file=sys.stderr)
        sys.exit(1)


def list_keys():
    """List all active keys (shows prefix only, not full key)."""
    table = get_table()
    response = table.scan()
    items = response.get("Items", [])

    if not items:
        print("No API keys found.")
        return

    print(f"{'Key Prefix':<20} {'Bot ID':<15} {'Name':<25} {'Status':<10}")
    print("-" * 70)
    for item in sorted(items, key=lambda x: x.get("created_at", 0)):
        status = "REVOKED" if item.get("revoked_at") else "ACTIVE"
        print(
            f"{item.get('key_prefix', '???'):<20} "
            f"{item.get('bot_id', '???'):<15} "
            f"{item.get('key_name', '???'):<25} "
            f"{status:<10}"
        )


def main():
    parser = argparse.ArgumentParser(description="Manage Bot Factory API keys")
    parser.add_argument("bot_id", nargs="?", help="Bot ID to create key for (use '*' for wildcard)")
    parser.add_argument("--name", default="default", help="Human-readable name for the key")
    parser.add_argument("--revoke", metavar="KEY", help="Revoke an existing key")
    parser.add_argument("--list", action="store_true", help="List all keys")

    args = parser.parse_args()

    if args.list:
        list_keys()
        return

    if args.revoke:
        revoke_key(args.revoke)
        return

    if not args.bot_id:
        parser.print_help()
        sys.exit(1)

    raw_key = generate_key()
    key_hash = store_key(raw_key, args.bot_id, args.name)

    print()
    print("=" * 60)
    print("  NEW API KEY GENERATED")
    print("=" * 60)
    print(f"  Bot ID:    {args.bot_id}")
    print(f"  Name:      {args.name}")
    print(f"  Key:       {raw_key}")
    print(f"  Hash:      {key_hash[:16]}...")
    print(f"  Env:       {APP_ENV}")
    print()
    print("  ⚠  SAVE THIS KEY NOW — it cannot be retrieved later.")
    print("=" * 60)


if __name__ == "__main__":
    main()
