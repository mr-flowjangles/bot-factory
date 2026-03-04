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

Remember: Keep your response short and conversational. Write in PLAIN TEXT ONLY - do not use ** or any markdown. If you can't answer from the context, say so politely."""

    messages.append({"role": "user", "content": [{"text": user_content}]})
    return messages


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

    relevant_chunks = retrieve_relevant_chunks(
        bot_id=bot_id,
        query=user_message,
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
        system=[{"text": system_prompt}],
        messages=messages,
    )
    t3 = time.time()

    logger.info(f"[chatbot:{bot_id}] retrieval={t1-t0:.3f}s | prompt={t2-t1:.3f}s | bedrock={t3-t2:.3f}s | total={t3-t0:.3f}s")

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
):
    """Same as generate_response, but yields text chunks for streaming."""
    logger.info(f"[chatbot:{bot_id}] stream start query='{user_message[:60]}'")

    if conversation_history is None:
        conversation_history = []

    relevant_chunks = retrieve_relevant_chunks(
        bot_id=bot_id,
        query=user_message,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )

    context = format_context_for_llm(relevant_chunks)
    messages = build_messages(user_message, context, conversation_history)
    system_prompt = load_system_prompt(bot_id)

    client = get_bedrock_client()
    response = client.converse_stream(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        inferenceConfig={"maxTokens": 1000},
        system=[{"text": system_prompt}],
        messages=messages,
    )

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            yield event["contentBlockDelta"]["delta"]["text"]
