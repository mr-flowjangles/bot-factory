"""
Self-Healing Knowledge Base — Orchestrator

When a bot can't answer a question (low RAG confidence), this module:
1. Checks if the question is within the bot's domain (boundary check)
2. Checks for duplicate content (embedding similarity)
3. Generates a YML data file via LLM
4. Validates the generated content via a second LLM call
5. Uploads the YML to S3
6. Generates an embedding and stores it in DynamoDB (additive)
7. Invalidates the in-memory embedding cache
8. Sends a notification email via SES

Runs as a background thread locally, or as a separate Lambda in production.
"""

import json
import os
import re
import time
import logging
import yaml
import boto3

from .self_heal_prompts import BOUNDARY_CHECK_PROMPT, YML_GENERATION_PROMPT, VALIDATION_PROMPT
from .retrieval import (
    generate_query_embedding,
    get_cached_embeddings,
    cosine_similarity,
    invalidate_bot_cache,
)
from .generate_embeddings import embed_and_store_single
from .ses_notifier import send_self_heal_email

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("BOT_DATA_BUCKET", "bot-factory-data")

# In-memory store for pending self-heal results (keyed by bot_id)
# Checked on next /chat request to piggyback a notification
_pending_results = {}


def get_pending_result(bot_id: str) -> dict | None:
    """Pop and return a pending self-heal result for a bot, if any."""
    return _pending_results.pop(bot_id, None)


# ---------------------------------------------------------------------------
# S3 + Bedrock clients
# ---------------------------------------------------------------------------


def _get_s3_client():
    if os.getenv("APP_ENV", "local") == "production":
        return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def _get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))


def _llm_call(prompt: str) -> str:
    """Make a single LLM call to Bedrock Claude and return the text response."""
    client = _get_bedrock_client()
    response = client.converse(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        inferenceConfig={"maxTokens": 2000},
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
    return response["output"]["message"]["content"][0]["text"]


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to a URL/filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60].strip("-")


def _boundary_check(question: str, config: dict) -> bool:
    """Check if the question is within the bot's domain. Returns True if in-bounds."""
    bot = config.get("bot", {})
    boundaries = bot.get("boundaries", {})
    if not boundaries:
        return True  # No boundaries defined = everything is in scope

    agentic = bot.get("agentic", {})
    if not agentic.get("boundary_check", True):
        return True  # Boundary checking disabled

    bot_name = bot.get("name", bot.get("id", "unknown"))
    personality = bot.get("personality", "helpful")

    boundary_desc = "\n".join(f"  - {k}: {v}" for k, v in boundaries.items())

    prompt = BOUNDARY_CHECK_PROMPT.format(
        bot_name=bot_name,
        boundaries=boundary_desc,
        personality=personality,
        question=question,
    )

    response = _llm_call(prompt).strip().lower()
    in_bounds = response.startswith("yes")
    status = "IN" if in_bounds else "OUT"
    print(f"  [self_heal] boundary_check: {status} — {response[:100]}")
    logger.info(f"[self_heal] boundary_check: {status} — {response[:100]}")
    return in_bounds


def _duplicate_check(bot_id: str, question: str, threshold: float = 0.7) -> bool:
    """Check if similar content already exists. Returns True if duplicate found."""
    try:
        query_embedding = generate_query_embedding(question)
        items = get_cached_embeddings(bot_id)

        for item in items:
            stored_embedding = [float(x) for x in item["embedding"]]
            similarity = cosine_similarity(query_embedding, stored_embedding)
            if similarity >= threshold:
                logger.info(
                    f"[self_heal:{bot_id}] duplicate found — similarity={similarity:.3f} "
                    f"(threshold={threshold}) item={item.get('pk', 'unknown')}"
                )
                return True
    except Exception as e:
        logger.warning(f"[self_heal:{bot_id}] duplicate check failed: {e}")

    return False


def _s3_key_exists(s3_key: str) -> bool:
    """Check if an S3 key already exists."""
    try:
        s3 = _get_s3_client()
        s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except Exception:
        return False


def _generate_knowledge_yml(question: str, config: dict, slug: str) -> tuple[str, dict] | None:
    """Generate YML data content via LLM. Returns (yml_string, parsed_entry) or None."""
    bot = config.get("bot", {})
    bot_name = bot.get("name", bot.get("id", "unknown"))
    entry_id = f"self-heal-{slug}"

    # Gather existing categories from boundaries/config
    categories = [k.replace("discuss_", "").replace("_", " ").title() for k in bot.get("boundaries", {})]
    if not categories:
        categories = ["General"]

    prompt = YML_GENERATION_PROMPT.format(
        bot_name=bot_name,
        question=question,
        entry_id=entry_id,
        category=categories[0] if len(categories) == 1 else f"one of: {', '.join(categories)}",
        heading="[a clear, descriptive title for this topic]",
        search_terms=f"keywords related to: {question}",
        categories=", ".join(categories),
    )

    yml_text = _llm_call(prompt).strip()

    # Strip markdown code fences if present
    if yml_text.startswith("```"):
        lines = yml_text.split("\n")
        # Remove first line (```yaml) and last line (```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        yml_text = "\n".join(lines)

    try:
        parsed = yaml.safe_load(yml_text)
        entries = parsed.get("entries", [])
        if not entries:
            logger.error("[self_heal] generated YML has no entries")
            return None
        entry = entries[0]
        # Ensure the id matches what we want
        entry["id"] = entry_id
        return yml_text, entry
    except yaml.YAMLError as e:
        logger.error(f"[self_heal] failed to parse generated YML: {e}")
        return None


def _validate_content(question: str, content: str, config: dict) -> bool:
    """Validate generated content via a second LLM call. Returns True if valid."""
    bot = config.get("bot", {})
    bot_name = bot.get("name", bot.get("id", "unknown"))

    prompt = VALIDATION_PROMPT.format(
        bot_name=bot_name,
        question=question,
        content=content,
    )

    response = _llm_call(prompt).strip().lower()
    passed = response.startswith("pass")
    logger.info(f"[self_heal] validation: {'PASS' if passed else 'FAIL'} — {response[:100]}")
    return passed


def _upload_to_s3(bot_id: str, slug: str, yml_text: str) -> str:
    """Upload YML file to S3. Returns the S3 key."""
    s3_key = f"bots/{bot_id}/data/self-heal-{slug}.yml"
    s3 = _get_s3_client()
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=yml_text.encode("utf-8"),
        ContentType="text/yaml",
    )
    logger.info(f"[self_heal:{bot_id}] uploaded to s3://{S3_BUCKET}/{s3_key}")
    return s3_key


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_self_heal(bot_id: str, question: str, config: dict, on_complete_callback=None):
    """Run the full self-heal pipeline. Intended to be called in a background thread.

    Args:
        bot_id: The bot that couldn't answer.
        question: The user's original question.
        config: The bot's loaded config dict.
        on_complete_callback: Optional callback(result_dict) when done.
    """
    t_start = time.time()
    print(f"  [self_heal:{bot_id}] starting pipeline for: {question[:80]}")

    # Skip trivially short messages (greetings, "hi", "thanks", etc.)
    MIN_QUESTION_LENGTH = 10
    if len(question.strip()) < MIN_QUESTION_LENGTH:
        print(f"  [self_heal:{bot_id}] skipping — question too short ({len(question.strip())} chars)")
        return

    slug = _slugify(question)
    if not slug:
        logger.error(f"[self_heal:{bot_id}] could not generate slug from question")
        return

    # 1. Boundary check
    if not _boundary_check(question, config):
        print(f"  [self_heal:{bot_id}] question out of bounds, skipping")
        return

    # 2. Duplicate check
    if _duplicate_check(bot_id, question):
        print(f"  [self_heal:{bot_id}] similar content exists, skipping")
        return

    # 3. Check if S3 file already exists
    s3_key = f"bots/{bot_id}/data/self-heal-{slug}.yml"
    if _s3_key_exists(s3_key):
        print(f"  [self_heal:{bot_id}] S3 key already exists: {s3_key}, skipping")
        return

    # 4. Generate knowledge YML
    print(f"  [self_heal:{bot_id}] generating knowledge YML...")
    result = _generate_knowledge_yml(question, config, slug)
    if result is None:
        print(f"  [self_heal:{bot_id}] YML generation failed")
        return
    yml_text, entry = result

    # 5. Validate content
    print(f"  [self_heal:{bot_id}] validating content...")
    content_for_validation = entry.get("content", "") or entry.get("heading", "")
    if not _validate_content(question, content_for_validation, config):
        print(f"  [self_heal:{bot_id}] content failed validation, skipping")
        return

    # 6. Upload to S3
    _upload_to_s3(bot_id, slug, yml_text)

    # 7. Generate embedding + store in DynamoDB (additive)
    # Build the text the same way the chunker does
    heading = entry.get("heading", "")
    content = entry.get("content", "")
    search_terms = entry.get("search_terms", "")
    text = f"{heading}\n\n{content}" if heading and content else content or heading
    if search_terms:
        text = f"Search terms: {search_terms}\n\n{text}"

    embed_entry = {
        "id": entry["id"],
        "category": entry.get("category", "General"),
        "heading": heading,
        "text": text,
    }
    embed_and_store_single(bot_id, embed_entry)

    # 8. Invalidate cache so next request picks up the new embedding
    invalidate_bot_cache(bot_id)

    # 9. Send notification email
    agentic = config.get("bot", {}).get("agentic", {})
    notify_email = agentic.get("notify_email")
    if notify_email:
        send_self_heal_email(bot_id, question, yml_text, notify_email)

    elapsed = time.time() - t_start
    print(f"  [self_heal:{bot_id}] pipeline complete in {elapsed:.1f}s — topic: {slug}")

    # 10. Store result for piggyback notification
    heal_result = {
        "topic": heading or slug,
        "question": question,
        "entry_id": entry["id"],
    }
    _pending_results[bot_id] = heal_result

    if on_complete_callback:
        on_complete_callback(heal_result)


# ---------------------------------------------------------------------------
# Lambda entry point (production)
# ---------------------------------------------------------------------------


def lambda_handler(event, context):
    """AWS Lambda handler for async self-heal invocation.

    Expected event payload:
        {"bot_id": "...", "question": "...", "config": {...}}
    """
    bot_id = event.get("bot_id")
    question = event.get("question")
    config = event.get("config")

    if not bot_id or not question or not config:
        print(f"  [self_heal] lambda_handler missing required fields: {list(event.keys())}")
        return {"status": "error", "message": "missing bot_id, question, or config"}

    print(f"  [self_heal] lambda_handler invoked for {bot_id}: {question[:80]}")
    run_self_heal(bot_id, question, config)
    return {"status": "ok", "bot_id": bot_id}


def invoke_self_heal_async(bot_id: str, question: str, config: dict):
    """Invoke the self-heal Lambda asynchronously (fire-and-forget).

    In local dev, falls back to a background thread.
    """
    if os.getenv("APP_ENV", "local") != "production":
        # Local dev — use background thread
        import threading
        thread = threading.Thread(
            target=run_self_heal,
            args=(bot_id, question, config),
            daemon=True,
        )
        thread.start()
        return

    # Production — invoke Lambda async
    function_name = os.getenv("SELF_HEAL_FUNCTION_NAME", "bot-factory-self-heal")
    payload = json.dumps({"bot_id": bot_id, "question": question, "config": config})

    try:
        client = boto3.client("lambda", region_name=os.getenv("AWS_REGION", "us-east-1"))
        client.invoke(
            FunctionName=function_name,
            InvocationType="Event",  # async, fire-and-forget
            Payload=payload.encode("utf-8"),
        )
        print(f"  [self_heal:{bot_id}] async Lambda invoked: {function_name}")
    except Exception as e:
        print(f"  [self_heal:{bot_id}] failed to invoke Lambda: {e}")
