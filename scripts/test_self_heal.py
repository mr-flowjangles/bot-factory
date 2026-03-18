#!/usr/bin/env python3
"""
Self-Heal Pipeline — Automated Tests

Runs test questions from test_questions.yml against the local dev server,
tracks whether self-heal triggered, and writes results to test_results.yml.

Usage:
    python3 scripts/test_self_heal.py
    make test-self-heal

Requires: BOT_API_KEY env var (or reads from .env)
"""

import json
import os
import sys
import time
from datetime import datetime

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8001"
BOT_ID = "the-fret-detective"
API_KEY = os.getenv("BOT_API_KEY", os.getenv("THE_FRET_DETECTIVE_API_KEY", os.getenv("API_KEY", "")))

QUESTIONS_FILE = "scripts/test_questions.yml"
RESULTS_FILE = "scripts/test_results.yml"

# LocalStack
S3_ENDPOINT = "http://localhost:4566"
S3_BUCKET = "bot-factory-data"

# How long to wait for self-heal pipeline to complete (seconds)
HEAL_WAIT = 25
REJECT_WAIT = 10


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def send_chat(message):
    """Send a chat message and collect the full SSE response + metadata."""
    resp = requests.post(
        f"{BASE_URL}/chat",
        json={"bot_id": BOT_ID, "message": message, "conversation_history": []},
        headers={"X-API-Key": API_KEY},
        stream=True,
    )
    tokens = []
    sources = []
    self_heal_event = None

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            parsed = json.loads(data)
            if "token" in parsed:
                tokens.append(parsed["token"])
            elif parsed.get("type") == "sources":
                sources = parsed.get("sources", [])
            elif parsed.get("type") == "self_heal":
                self_heal_event = parsed.get("message", "")
        except json.JSONDecodeError:
            pass

    top_score = sources[0]["similarity"] if sources else 0.0
    return {
        "response": "".join(tokens),
        "top_score": top_score,
        "source_count": len(sources),
        "top_source": sources[0] if sources else None,
        "self_heal_notification": self_heal_event,
    }


def slugify(text):
    """Match the slugify logic in self_heal.py."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def s3_file_exists(key):
    """Check if a file exists in LocalStack S3."""
    try:
        import boto3
        s3 = boto3.client(
            "s3", endpoint_url=S3_ENDPOINT, region_name="us-east-1",
            aws_access_key_id="test", aws_secret_access_key="test",
        )
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except Exception:
        return False


def s3_delete(key):
    """Delete a file from LocalStack S3."""
    try:
        import boto3
        s3 = boto3.client(
            "s3", endpoint_url=S3_ENDPOINT, region_name="us-east-1",
            aws_access_key_id="test", aws_secret_access_key="test",
        )
        s3.delete_object(Bucket=S3_BUCKET, Key=key)
    except Exception:
        pass


def dynamo_delete(pk):
    """Delete an item from LocalStack DynamoDB."""
    try:
        import boto3
        dynamodb = boto3.resource(
            "dynamodb", endpoint_url=S3_ENDPOINT, region_name="us-east-1",
            aws_access_key_id="test", aws_secret_access_key="test",
        )
        table = dynamodb.Table("BotFactoryRAG")
        table.delete_item(Key={"pk": pk})
    except Exception:
        pass


def cleanup_test_entry(slug):
    """Remove self-heal S3 file and DynamoDB entry for a test slug."""
    s3_key = f"bots/{BOT_ID}/data/self-heal-{slug}.yml"
    s3_delete(s3_key)
    dynamo_delete(f"{BOT_ID}_self-heal-{slug}")


# ─────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────


def run_question(q):
    """Run a single test question and return the result dict."""
    text = q["text"]
    expect = q["expect"]
    slug = slugify(text)
    s3_key = f"bots/{BOT_ID}/data/self-heal-{slug}.yml"

    # Clean up any leftover from previous runs
    cleanup_test_entry(slug)

    result = {
        "question": text,
        "expect": expect,
        "slug": slug,
    }

    # Send the question
    chat = send_chat(text)
    result["response"] = chat["response"][:300]
    result["top_score"] = round(chat["top_score"], 4)
    result["self_heal_notification"] = chat["self_heal_notification"]

    # Determine if self-heal ran
    if expect == "should_heal":
        # Wait for pipeline to complete
        print(f"        waiting for self-heal (~{HEAL_WAIT}s)...", flush=True)
        healed = False
        for _ in range(HEAL_WAIT):
            time.sleep(1)
            if s3_file_exists(s3_key):
                healed = True
                break
        result["self_healed"] = healed
        result["passed"] = healed

    elif expect == "should_skip":
        # High confidence — self-heal should NOT trigger
        time.sleep(2)
        result["self_healed"] = s3_file_exists(s3_key)
        result["passed"] = not result["self_healed"] and chat["top_score"] >= 0.5

    elif expect == "should_reject":
        # Out of domain — boundary check should block
        time.sleep(REJECT_WAIT)
        result["self_healed"] = s3_file_exists(s3_key)
        result["passed"] = not result["self_healed"]

    elif expect == "should_filter":
        # Too short — filtered before pipeline
        time.sleep(2)
        result["self_healed"] = s3_file_exists(s3_key)
        result["passed"] = not result["self_healed"]

    return result


def main():
    if not API_KEY:
        print("ERROR: Set BOT_API_KEY or API_KEY in .env")
        sys.exit(1)

    # Health check
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=3)
        assert resp.status_code == 200
    except Exception:
        print(f"ERROR: Dev server not running at {BASE_URL}")
        print("       Start it with: make local")
        sys.exit(1)

    # Load questions
    with open(QUESTIONS_FILE) as f:
        data = yaml.safe_load(f)
    questions = data["questions"]

    print()
    print("=" * 60)
    print("  Self-Heal Pipeline Tests")
    print(f"  Server: {BASE_URL}  Bot: {BOT_ID}")
    print(f"  Questions: {len(questions)}")
    print("=" * 60)
    print()

    results = []
    passed = 0
    failed = 0
    slugs_to_clean = []

    for i, q in enumerate(questions, 1):
        label = "HEAL" if q["expect"] == "should_heal" else q["expect"].replace("should_", "").upper()
        print(f"  [{i}/{len(questions)}] ({label}) {q['text'][:60]}")

        result = run_question(q)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        score_str = f"score={result['top_score']}"
        heal_str = "healed" if result.get("self_healed") else "no heal"
        print(f"        {status}  {score_str}  {heal_str}")
        print()

        if result["passed"]:
            passed += 1
        else:
            failed += 1

        # Track slugs for cleanup
        if result.get("self_healed"):
            slugs_to_clean.append(result["slug"])

    # Write results file
    output = {
        "run_date": datetime.now().isoformat(),
        "bot_id": BOT_ID,
        "total": len(questions),
        "passed": passed,
        "failed": failed,
        "results": results,
    }

    with open(RESULTS_FILE, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, width=120)

    print("=" * 60)
    print(f"  {passed} passed, {failed} failed out of {len(questions)}")
    print(f"  Results written to: {RESULTS_FILE}")
    print("=" * 60)

    # Cleanup self-healed test entries
    if slugs_to_clean:
        print()
        print(f"  Cleaning up {len(slugs_to_clean)} test entries...")
        for slug in slugs_to_clean:
            cleanup_test_entry(slug)
        print("  Done")

    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
