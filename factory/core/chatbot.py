"""
Chatbot

Orchestrates the full RAG chat pipeline:
  1. Load bot config (streaming flag, RAG settings)
  2. Load conversation history from DynamoDB
  3. Retrieve relevant chunks
  4. Call Claude via responder
  5. Save updated history to DynamoDB

This module is the Lambda handler for the chat function.

Lambda payload:
    {
        "bot_id":    "guitar",
        "message":   "What is a G chord?",
        "session_id": "abc123"        # optional — creates new session if omitted
    }

Required Lambda env vars:
    ANTHROPIC_API_KEY
    OPENAI_API_KEY
    BOT_DATA_BUCKET
    AWS_REGION
"""
import os
import json
import uuid
import yaml
import boto3
from datetime import datetime
from pathlib import Path
from .retriever import retrieve_relevant_chunks, format_context
from .responder import generate_response, generate_response_stream


# ---------------------------------------------------------------------------
# Config loading — cached per bot
# ---------------------------------------------------------------------------

_config_cache: dict[str, dict] = {}


def load_bot_config(bot_id: str) -> dict:
    """
    Load and cache a bot's config.yml.
    Config lives on the local filesystem (bundled in the Lambda package).

    s3 is for data files and prompts; config is deployment-time config.
    """
    if bot_id in _config_cache:
        return _config_cache[bot_id]

    config_path = Path(__file__).parent.parent / 'bots' / bot_id / 'config.yml'

    if not config_path.exists():
        raise FileNotFoundError(f"No config.yml found for bot '{bot_id}' at {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    _config_cache[bot_id] = config
    return config


# ---------------------------------------------------------------------------
# Conversation history — stored in DynamoDB
# ---------------------------------------------------------------------------

def get_history_table():
    from .connections import get_dynamodb
    return get_dynamodb().Table('ChatHistory')


def load_history(session_id: str) -> list[dict]:
    """Load conversation history for a session."""
    try:
        table = get_history_table()
        response = table.get_item(Key={'session_id': session_id})
        item = response.get('Item')
        return item.get('history', []) if item else []
    except Exception as e:
        print(f"Failed to load history for session '{session_id}': {e}")
        return []


def save_history(session_id: str, bot_id: str, history: list[dict]):
    """Save updated conversation history for a session."""
    try:
        table = get_history_table()
        table.put_item(Item={
            'session_id': session_id,
            'bot_id':     bot_id,
            'history':    history,
            'updated_at': datetime.utcnow().isoformat(),
        })
    except Exception as e:
        print(f"Failed to save history for session '{session_id}': {e}")


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_chat(bot_id: str, message: str, session_id: str) -> dict:
    """
    Full chat pipeline — retrieve, respond, persist.

    Args:
        bot_id:     Which bot to use
        message:    The user's message
        session_id: Conversation session ID

    Returns:
        {response, session_id, sources, streaming}
    """
    # Load config
    config     = load_bot_config(bot_id)
    rag_config = config.get('rag', {})
    streaming  = config.get('streaming', False)

    top_k      = rag_config.get('top_k', 5)
    threshold  = rag_config.get('similarity_threshold', 0.5)

    # Load history
    history = load_history(session_id)

    # Retrieve relevant chunks
    chunks  = retrieve_relevant_chunks(bot_id, message, top_k=top_k, similarity_threshold=threshold)
    context = format_context(chunks)

    # Generate response
    if streaming:
        # Collect the stream into a full response for storage
        # (true streaming to client is handled at the API layer)
        response_text = ''.join(generate_response_stream(bot_id, message, context, history))
    else:
        response_text = generate_response(bot_id, message, context, history)

    # Update and persist history
    history.append({"role": "user",      "content": message})
    history.append({"role": "assistant", "content": response_text})
    save_history(session_id, bot_id, history)

    return {
        "response":   response_text,
        "session_id": session_id,
        "streaming":  streaming,
        "sources": [
            {"category": c["category"], "similarity": round(c["similarity"], 3)}
            for c in chunks
        ],
    }


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    AWS Lambda entry point for the chat pipeline.

    Expected payload:
        {
            "bot_id":     "guitar",
            "message":    "What is a G chord?",
            "session_id": "abc123"   (optional)
        }
    """
    try:
        bot_id  = event.get('bot_id')
        message = event.get('message')

        if not bot_id:
            return {'statusCode': 400, 'body': json.dumps({'error': 'bot_id is required'})}
        if not message:
            return {'statusCode': 400, 'body': json.dumps({'error': 'message is required'})}

        session_id = event.get('session_id') or str(uuid.uuid4())

        result = run_chat(bot_id, message, session_id)
        return {'statusCode': 200, 'body': json.dumps(result)}

    except FileNotFoundError as e:
        return {'statusCode': 404, 'body': json.dumps({'error': str(e)})}
    except Exception as e:
        print(f"Chat error: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
