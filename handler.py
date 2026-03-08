"""
Bot Factory — Main Lambda handler (API Gateway / Function URL).
Replaces Chalice. Plain Lambda, no framework.
"""

import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Route requests to the appropriate function."""
    # Function URL puts path in rawPath; API Gateway v1 uses path
    path = event.get("rawPath") or event.get("path", "/")
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod", "GET")
    )

    logger.info(f"[{method}] {path}")

    try:
        if path == "/health" and method == "GET":
            return _response(200, {"status": "ok", "service": "bot-factory"})

        if path == "/chat" and method == "POST":
            return _handle_chat(event)

        if path == "/" and method == "GET":
            return _serve_html()

        # CORS preflight
        if method == "OPTIONS":
            return _response(200, "")

        return _response(404, {"error": "not found"})

    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return _response(500, {"error": str(e)})


def _handle_chat(event):
    body = json.loads(event.get("body", "{}"))
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id:
        return _response(400, {"error": "bot_id is required"})
    if not message:
        return _response(400, {"error": "message is required"})

    from factory.core.chatbot import generate_response

    result = generate_response(
        bot_id=bot_id,
        user_message=message,
        top_k=5,
        similarity_threshold=0.3,
        conversation_history=[],
    )
    return _response(200, {
        "response": result["response"],
        "sources": result["sources"],
    })


def _serve_html():
    # chat.html is packaged alongside this file
    html_path = os.path.join(os.path.dirname(__file__), "app", "chat.html")
    try:
        with open(html_path) as f:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": f.read(),
            }
    except FileNotFoundError:
        return _response(404, {"error": "chat.html not found"})


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body) if isinstance(body, dict) else body,
    }
