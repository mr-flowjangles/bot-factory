"""
Responder

Loads the system prompt from S3, builds the message array,
and calls Claude via Bedrock. Supports both standard and streaming responses.

Prompt location: s3://{BOT_DATA_BUCKET}/bots/{bot_id}/prompt.txt
"""
import os
from datetime import datetime
from .connections import get_bedrock_client, get_s3_client

MODEL_ID   = "us.anthropic.claude-sonnet-4-20250514-v1:0"
MAX_TOKENS = 1000

# ---------------------------------------------------------------------------
# Prompt loading — cached per bot for warm Lambda reuse
# ---------------------------------------------------------------------------

_prompt_cache: dict[str, str] = {}


def load_system_prompt(bot_id: str) -> str:
    """
    Load and cache the system prompt for a bot from S3.
    Injects current date into the prompt template.

    Expects: s3://{BOT_DATA_BUCKET}/bots/{bot_id}/prompt.txt
    """
    if bot_id in _prompt_cache:
        return _prompt_cache[bot_id]

    bucket = os.getenv('BOT_DATA_BUCKET')
    if not bucket:
        raise EnvironmentError("BOT_DATA_BUCKET environment variable not set")

    key = f"bots/{bot_id}/prompt.txt"
    print(f"Loading prompt for '{bot_id}' from s3://{bucket}/{key}")

    s3 = get_s3_client()
    response = s3.get_object(Bucket=bucket, Key=key)
    template = response['Body'].read().decode('utf-8')

    current_date = datetime.now().strftime('%B %d, %Y')
    prompt = template.replace('{current_date}', current_date)

    _prompt_cache[bot_id] = prompt
    return prompt


def invalidate_prompt_cache(bot_id: str):
    """Force prompt reload on next request — useful after updating prompt.txt in S3."""
    _prompt_cache.pop(bot_id, None)


# ---------------------------------------------------------------------------
# Message building
# ---------------------------------------------------------------------------

def build_messages(
    user_message: str,
    context: str,
    conversation_history: list[dict],
) -> list[dict]:
    """
    Build the Bedrock messages array.
    Injects RAG context into the current user message.
    """
    messages = []

    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}],
        })

    user_content = (
        f"## Relevant Context:\n{context}\n\n"
        f"## User Question:\n{user_message}\n\n"
        f"Remember: Keep your response short and conversational. "
        f"Write in plain text only — no markdown or bullet points unless essential."
    )

    messages.append({"role": "user", "content": [{"text": user_content}]})
    return messages


# ---------------------------------------------------------------------------
# Bedrock calls
# ---------------------------------------------------------------------------

def generate_response(
    bot_id: str,
    user_message: str,
    context: str,
    conversation_history: list[dict],
) -> str:
    """
    Call Claude via Bedrock and return the full response text.
    """
    system_prompt = load_system_prompt(bot_id)
    messages = build_messages(user_message, context, conversation_history)
    client = get_bedrock_client()

    response = client.converse(
        modelId=MODEL_ID,
        inferenceConfig={"maxTokens": MAX_TOKENS},
        system=[{"text": system_prompt}],
        messages=messages,
    )

    return response["output"]["message"]["content"][0]["text"]


def generate_response_stream(
    bot_id: str,
    user_message: str,
    context: str,
    conversation_history: list[dict],
):
    """
    Call Claude via Bedrock and yield text chunks as they arrive.
    """
    system_prompt = load_system_prompt(bot_id)
    messages = build_messages(user_message, context, conversation_history)
    client = get_bedrock_client()

    response = client.converse_stream(
        modelId=MODEL_ID,
        inferenceConfig={"maxTokens": MAX_TOKENS},
        system=[{"text": system_prompt}],
        messages=messages,
    )

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            yield event["contentBlockDelta"]["delta"]["text"]
