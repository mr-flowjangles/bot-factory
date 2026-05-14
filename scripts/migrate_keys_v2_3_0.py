#!/usr/bin/env python3
"""
v2.3.0 migration — backfill `allowed_origins` and `rate_limit_per_hour` on existing keys.

Run BEFORE deploying v2.3.0 code. Old code ignores the new fields, so this is safe
to run against production while v2.2.x is still serving traffic.

Usage:
  # Production:
  python3 scripts/migrate_keys_v2_3_0.py \\
      --bot-id RobbAI --origins https://robrose.info --rate-limit 30
  python3 scripts/migrate_keys_v2_3_0.py \\
      --bot-id the-fret-detective --origins https://thefretdetective.com --rate-limit 30

  # Local:
  python3 scripts/migrate_keys_v2_3_0.py --bot-id guitar \\
      --origins http://localhost:8080 --endpoint-url http://localhost:4566
"""

import argparse
import os
import sys

import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-id", required=True)
    parser.add_argument("--origins", required=True, help="Comma-separated allowed origins")
    parser.add_argument("--rate-limit", type=int, default=30)
    parser.add_argument("--endpoint-url", default=None)
    parser.add_argument("--table", default="BotFactoryApiKeys")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    origins = [o.strip() for o in args.origins.split(",") if o.strip()]
    if not origins:
        print("--origins must contain at least one origin")
        sys.exit(1)

    kwargs = {"region_name": os.getenv("AWS_REGION", "us-east-1")}
    if args.endpoint_url:
        kwargs.update({
            "endpoint_url": args.endpoint_url,
            "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "test"),
            "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        })
    table = boto3.resource("dynamodb", **kwargs).Table(args.table)

    response = table.scan()
    matched = [item for item in response.get("Items", []) if item.get("bot_id") == args.bot_id]

    if not matched:
        print(f"No keys found for bot_id={args.bot_id}")
        sys.exit(1)

    print(f"Found {len(matched)} key(s) for bot_id={args.bot_id}")
    for item in matched:
        key = item["api_key"]
        print(f"  {key[:12]}…  name={item.get('name', '?')}")
        if args.dry_run:
            continue
        table.update_item(
            Key={"api_key": key},
            UpdateExpression="SET allowed_origins = :o, rate_limit_per_hour = :r",
            ExpressionAttributeValues={":o": origins, ":r": args.rate_limit},
        )
        print(f"    → set allowed_origins={origins}, rate_limit={args.rate_limit}/hr")

    if args.dry_run:
        print("\nDry run — nothing written.")
    else:
        print("\nDone.")


if __name__ == "__main__":
    main()
