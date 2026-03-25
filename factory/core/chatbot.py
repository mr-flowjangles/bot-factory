"""
Chatbot Module (Parameterized)

Generates responses using Claude via AWS Bedrock with RAG context.
Loads the system prompt from S3 (bots/{bot_id}/prompt.yml) and
caches it per bot_id for warm Lambda reuse.
"""

import os
import time
import logging
import yaml
import boto3
from datetime import datetime
from .retrieval import retrieve_relevant_chunks, format_context_for_llm

logger = logging.getLogger(__name__)

# Cached resources — persist across warm Lambda invocations
_bedrock_client = None
_system_prompts = {}

S3_BUCKET = os.getenv("BOT_DATA_BUCKET", "bot-factory-data")


# ---------------------------------------------------------------------------
# Bedrock client
# ---------------------------------------------------------------------------


def get_bedrock_client():
    """Lazy-init Bedrock runtime client. Always uses real AWS."""
    global _bedrock_client
    if _bedrock_client is None:
        t_start = time.time()
        logger.info("[chatbot] Initializing Bedrock client...")
        _bedrock_client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        logger.info(f"[chatbot] Bedrock init — {time.time() - t_start:.3f}s")
    return _bedrock_client


# ---------------------------------------------------------------------------
# S3 client
# ---------------------------------------------------------------------------


def get_s3_client():
    if os.getenv("APP_ENV", "local") == "production":
        return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------


def load_system_prompt(bot_id: str) -> str:
    """
    Load and cache the system prompt for a bot from S3.
    Reads from s3://bot-factory-data/bots/{bot_id}/prompt.yml
    """
    if bot_id in _system_prompts:
        return _system_prompts[bot_id]

    s3_key = f"bots/{bot_id}/prompt.yml"
    logger.info(f"[chatbot:{bot_id}] Loading prompt from s3://{S3_BUCKET}/{s3_key}")

    s3 = get_s3_client()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
    data = yaml.safe_load(obj["Body"].read().decode("utf-8"))

    template = data.get("system_prompt", "")

    current_date = datetime.now().strftime("%B %d, %Y")
    try:
        prompt = template.format(current_date=current_date)
    except KeyError:
        prompt = template  # prompt has no format vars, use as-is

    _system_prompts[bot_id] = prompt
    logger.info(f"[chatbot:{bot_id}] Prompt loaded and cached ({len(prompt)} chars)")
    return prompt


# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------


def build_messages(user_message: str, context: str, conversation_history: list[dict]) -> list[dict]:
    """Build the messages array for Bedrock converse."""
    messages = []

    for msg in conversation_history:
        messages.append({"role": msg["role"], "content": [{"text": msg["content"]}]})

    user_content = f"""## Relevant Context:
{context}

## User Question:
{user_message}

Remember: Keep your response short and conversational. Write in PLAIN TEXT ONLY - do not use ** or any markdown. \
Use the context to answer even if the wording doesn't exactly match the question. \
Only say you can't answer if the context has nothing relevant."""

    messages.append({"role": "user", "content": [{"text": user_content}]})
    return messages


def _build_enriched_query(user_message: str, conversation_history: list[dict]) -> str:
    """Build a context-enriched query for better RAG retrieval on follow-ups.

    Uses the last exchange (user + assistant) to ground vague follow-ups like
    'what other chords are around there?' in the specific topic being discussed.
    Assistant text is truncated before tab diagrams to keep the embedding focused.
    """
    if not conversation_history:
        return user_message

    # Get the last user message and last assistant message
    last_user = None
    last_assistant = None
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant" and last_assistant is None:
            # Truncate at tab diagrams (lines with e|, B|, etc.) to remove noise
            text = msg["content"]
            for marker in ["\ne|", "\nB|", "\ne |", "\nB |"]:
                idx = text.find(marker)
                if idx > 0:
                    text = text[:idx]
                    break
            last_assistant = text[:200].strip()
        elif msg["role"] == "user" and last_user is None:
            last_user = msg["content"][:150].strip()
        if last_user and last_assistant:
            break

    parts = []
    if last_user:
        parts.append(last_user)
    if last_assistant:
        parts.append(last_assistant)
    parts.append(user_message)

    return " | ".join(parts)


def generate_response(
    bot_id: str,
    user_message: str,
    top_k: int,
    similarity_threshold: float,
    conversation_history: list[dict] = None,
) -> dict:
    if conversation_history is None:
        conversation_history = []

    t0 = time.time()

    enriched_query = _build_enriched_query(user_message, conversation_history)
    relevant_chunks = retrieve_relevant_chunks(
        bot_id=bot_id,
        query=enriched_query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
    t1 = time.time()

    context = format_context_for_llm(relevant_chunks)
    messages = build_messages(user_message, context, conversation_history)
    system_prompt = load_system_prompt(bot_id)
    t2 = time.time()

    client = get_bedrock_client()
    response = client.converse(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        inferenceConfig={"maxTokens": 1000},
        system=[{"text": system_prompt}, {"cachePoint": {"type": "default"}}],
        messages=messages,
    )
    t3 = time.time()

    usage = response.get("usage", {})
    cache_read = usage.get("cacheReadInputTokens", 0)
    cache_write = usage.get("cacheWriteInputTokens", 0)
    logger.info(
        f"[chatbot:{bot_id}] retrieval={t1-t0:.3f}s | prompt={t2-t1:.3f}s | bedrock={t3-t2:.3f}s | total={t3-t0:.3f}s"
        f" | cache_read={cache_read} cache_write={cache_write}"
    )

    return {
        "response": response["output"]["message"]["content"][0]["text"],
        "sources": [{"category": c["category"], "similarity": c["similarity"]} for c in relevant_chunks],
    }


def generate_response_stream(
    bot_id: str,
    user_message: str,
    top_k: int,
    similarity_threshold: float,
    conversation_history: list[dict] = None,
    metadata_out: dict = None,
):
    """Same as generate_response, but yields text chunks for streaming.

    Args:
        metadata_out: If provided, populated with retrieval metadata including
            'top_score' (highest similarity from RAG) for self-heal decisions.
    """
    logger.info(f"[chatbot:{bot_id}] stream start query='{user_message[:60]}'")

    if conversation_history is None:
        conversation_history = []
    if metadata_out is None:
        metadata_out = {}

    logger.info(f"[chatbot:{bot_id}] conversation_history={len(conversation_history)} messages")
    enriched_query = _build_enriched_query(user_message, conversation_history)
    logger.info(f"[chatbot:{bot_id}] enriched_query='{enriched_query[:120]}'")
    relevant_chunks = retrieve_relevant_chunks(
        bot_id=bot_id,
        query=enriched_query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )

    # Expose top similarity score for self-heal confidence check
    top_score = relevant_chunks[0]["similarity"] if relevant_chunks else 0.0
    metadata_out["top_score"] = top_score
    metadata_out["chunk_count"] = len(relevant_chunks)
    logger.info(f"[chatbot:{bot_id}] top_score={top_score:.3f} chunks={len(relevant_chunks)}")

    context = format_context_for_llm(relevant_chunks)
    messages = build_messages(user_message, context, conversation_history)
    system_prompt = load_system_prompt(bot_id)

    client = get_bedrock_client()
    response = client.converse_stream(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        inferenceConfig={"maxTokens": 1000},
        system=[{"text": system_prompt}, {"cachePoint": {"type": "default"}}],
        messages=messages,
    )

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            yield event["contentBlockDelta"]["delta"]["text"]
        elif "metadata" in event:
            usage = event["metadata"].get("usage", {})
            cache_read = usage.get("cacheReadInputTokens", 0)
            cache_write = usage.get("cacheWriteInputTokens", 0)
            total_in = usage.get("inputTokens", 0)
            print(
                f"  [chatbot:{bot_id}] cache_read={cache_read} cache_write={cache_write}"
                f" input={total_in} output={usage.get('outputTokens', 0)}"
            )
            logger.info(
                f"[chatbot:{bot_id}] stream done | cache_read={cache_read} cache_write={cache_write}"
            )
