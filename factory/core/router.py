"""
Router Factory

Creates a FastAPI APIRouter for any bot given a bot_id.
Each bot gets:
  - POST /{bot_id}/chat       Send a message, get a response
  - GET  /{bot_id}/suggestions  Suggested starter questions
  - GET  /{bot_id}/warmup     Preload embedding cache

The chat endpoint invokes the chat Lambda (bot-factory-chat) via boto3.
Streaming is controlled by the bot's config.yml — the router handles
both cases transparently.

Usage in api/main.py:
    from factory.core.router import create_bot_router
    app.include_router(create_bot_router("guitar"))
"""
import os
import json
import uuid
import yaml
import boto3
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    sources: list[dict] = []


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_bot_config(bot_id: str) -> dict:
    """Load a bot's config.yml from the factory/bots directory."""
    config_path = Path(__file__).parent.parent / 'bots' / bot_id / 'config.yml'

    if not config_path.exists():
        raise FileNotFoundError(f"No config.yml found for bot '{bot_id}'")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Lambda invocation
# ---------------------------------------------------------------------------

def get_lambda_client():
    return boto3.client('lambda', region_name=os.getenv('AWS_REGION', 'us-east-1'))


def invoke_chat_lambda(bot_id: str, message: str, session_id: str) -> dict:
    """
    Invoke the bot-factory-chat Lambda synchronously.
    Returns the parsed response body.
    """
    function_name = os.getenv('CHAT_LAMBDA_NAME', 'bot-factory-chat')

    payload = {
        'bot_id':     bot_id,
        'message':    message,
        'session_id': session_id,
    }

    client = get_lambda_client()
    response = client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload),
    )

    raw = response['Payload'].read()
    result = json.loads(raw)

    if response.get('FunctionError'):
        raise RuntimeError(f"Lambda error: {result}")

    # Lambda returns {statusCode, body} — unwrap the body
    body = result.get('body', '{}')
    return json.loads(body)


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_bot_router(bot_id: str) -> APIRouter:
    """
    Create a FastAPI router for a specific bot.

    Args:
        bot_id: The bot folder name (e.g., 'guitar')

    Returns:
        APIRouter with /chat, /suggestions, /warmup endpoints
    """
    router = APIRouter(prefix=f"/{bot_id}", tags=[bot_id])

    @router.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Send a message to this bot and get a response."""
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        session_id = request.session_id or str(uuid.uuid4())

        try:
            result = invoke_chat_lambda(bot_id, request.message, session_id)

            return ChatResponse(
                response=result['response'],
                session_id=result['session_id'],
                sources=result.get('sources', []),
            )

        except Exception as e:
            print(f"Chat error ({bot_id}): {e}")
            raise HTTPException(status_code=500, detail="Error processing your message")

    @router.get("/suggestions")
    async def get_suggestions():
        """Return suggested starter questions from config."""
        try:
            config = load_bot_config(bot_id)
            return {"suggestions": config.get('suggestions', [])}
        except Exception:
            return {"suggestions": []}

    @router.get("/warmup")
    async def warmup():
        """
        Warm up the chat Lambda by sending a lightweight invoke.
        Preloads the embedding cache so the first real request is fast.
        """
        try:
            result = invoke_chat_lambda(bot_id, "__warmup__", str(uuid.uuid4()))
            return {"status": "warm"}
        except Exception as e:
            print(f"Warmup error ({bot_id}): {e}")
            return {"status": "error", "detail": str(e)}

    return router
