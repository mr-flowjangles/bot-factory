"""
Lambda Handler

Entrypoint for AWS Lambda. Replaces FastAPI/Mangum with a thin
HTTP dispatcher. All business logic lives in core/.

Routes:
  POST /chat        Send a message, get a response
  GET  /bots        List all available bots
  GET  /health      Health check
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ok(body: dict) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def err(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def parse_body(event: dict) -> dict:
    body = event.get("body") or "{}"
    if isinstance(body, str):
        return json.loads(body)
    return body


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def handle_chat(event: dict) -> dict:
    body = parse_body(event)
    bot_id  = body.get("bot_id")
    message = body.get("message", "").strip()
    conversation_history = body.get("conversation_history", [])

    if not bot_id:
        return err(400, "bot_id is required")
    if not message:
        return err(400, "message cannot be empty")

    try:
        from factory.core.bot_utils import load_bot_config, log_chat_interaction
        from factory.core.chatbot import generate_response

        config     = load_bot_config(bot_id)
        rag_config = config.get("bot", {}).get("rag", {})

        result = generate_response(
            bot_id=bot_id,
            user_message=message,
            conversation_history=conversation_history,
            top_k=rag_config.get("top_k", 5),
            similarity_threshold=rag_config.get("similarity_threshold", 0.3),
        )

        log_chat_interaction(
            bot_id=bot_id,
            question=message,
            response=result["response"],
            sources=result["sources"],
        )

        return ok({"response": result["response"], "sources": result["sources"]})

    except Exception as e:
        logger.error(f"Chat error ({bot_id}): {e}", exc_info=True)
        return err(500, "Error processing your message")


def handle_list_bots(event: dict) -> dict:
    try:
        bots_path = Path(__file__).parent.parent / "scripts" / "bots"
        EXCLUDED  = {"TEMPLATE", "testbot"}

        bots = []
        if bots_path.exists():
            for path in sorted(bots_path.iterdir()):
                if path.is_dir() and (path / "config.yml").exists() and path.name not in EXCLUDED:
                    bots.append(path.name)

        return ok({"bots": bots})

    except Exception as e:
        logger.error(f"List bots error: {e}", exc_info=True)
        return err(500, "Error listing bots")


def handle_health(event: dict) -> dict:
    return ok({"status": "ok", "service": "bot-factory"})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

ROUTES = {
    ("POST", "/chat"):   handle_chat,
    ("GET",  "/bots"):   handle_list_bots,
    ("GET",  "/health"): handle_health,
}


def lambda_handler(event: dict, context) -> dict:
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path   = event.get("rawPath", "")

    logger.info(f"[lambda] {method} {path}")

    handler = ROUTES.get((method, path))
    if not handler:
        return err(404, f"No route for {method} {path}")

    return handler(event)