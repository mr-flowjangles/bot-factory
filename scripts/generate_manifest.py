#!/usr/bin/env python3
"""
Knowledge Base Manifest Generator

Reads all YAML data files for a bot, extracts metadata (id, heading, search_terms),
and uploads a manifest to S3. The manifest serves as a table of contents that the
self-heal agent reads before deciding whether to generate new content.

Usage:
    python3 scripts/generate_manifest.py the-fret-detective          # local
    python3 scripts/generate_manifest.py the-fret-detective --prod   # production
    make manifest bot=the-fret-detective                             # Makefile target
"""

import os
import sys
import yaml
from datetime import datetime, timezone

# Add project root to path so we can import factory modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Set APP_ENV before importing factory modules
if "--prod" in sys.argv:
    os.environ["APP_ENV"] = "production"
    os.environ.pop("AWS_ACCESS_KEY_ID", None)
    os.environ.pop("AWS_SECRET_ACCESS_KEY", None)

from factory.core.chunker import load_yaml_files, get_s3_client, S3_BUCKET  # noqa: E402


def generate_manifest(bot_id: str) -> dict:
    """Build a manifest dict from all data entries for a bot."""
    entries = load_yaml_files(bot_id)

    if not entries:
        print(f"  No entries found for bot '{bot_id}'")
        return {}

    # Group by category
    categories = {}
    for entry in entries:
        category = entry.get("category", "General")
        if category not in categories:
            categories[category] = []

        categories[category].append({
            "id": entry.get("id", ""),
            "heading": entry.get("heading", ""),
            "search_terms": entry.get("search_terms", ""),
        })

    manifest = {
        "bot_id": bot_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "entry_count": len(entries),
        "categories": categories,
    }

    return manifest


def upload_manifest(bot_id: str, manifest: dict):
    """Upload manifest to s3://bucket/bots/{bot_id}/manifest.yml"""
    s3 = get_s3_client()
    s3_key = f"bots/{bot_id}/manifest.yml"
    yml_text = yaml.dump(manifest, default_flow_style=False, sort_keys=False, width=200)

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=yml_text.encode("utf-8"),
        ContentType="text/yaml",
    )
    print(f"  Uploaded manifest to s3://{S3_BUCKET}/{s3_key}")


def main():
    # Parse args
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("Usage: python3 scripts/generate_manifest.py <bot_id> [--prod]")
        sys.exit(1)

    bot_id = args[0]
    is_prod = "--prod" in sys.argv
    env_label = "PROD" if is_prod else "LOCAL"

    print(f"\n  Generating manifest for '{bot_id}' ({env_label})")
    print(f"  {'=' * 50}")

    manifest = generate_manifest(bot_id)
    if not manifest:
        sys.exit(1)

    upload_manifest(bot_id, manifest)

    print(f"\n  Manifest: {manifest['entry_count']} entries across {len(manifest['categories'])} categories")
    for cat, items in manifest["categories"].items():
        print(f"    {cat}: {len(items)} entries")
    print()


if __name__ == "__main__":
    main()
