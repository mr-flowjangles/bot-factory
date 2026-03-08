"""
Streaming Lambda handler for Function URL (RESPONSE_STREAM mode).
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
}


def handler(event, *args):
    """
    Lambda streaming handler.
    - Function URL with RESPONSE_STREAM: (event, response_stream, context)
    - Direct invocation: (event, context)
    """
    if len(args) == 2:
        response_stream, context = args
        is_streaming = True
    else:
        context = args[0]
        response_stream = None
        is_streaming = False

    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method", "POST")
    path = http.get("path", "/")

    if path == "/health" or path.endswith("/health"):
        response = {"status": "ok", "service": "bot-factory-stream"}
        if is_streaming:
            response_stream.write(json.dumps(response).encode())
            response_stream.close()
            return
        return {"statusCode": 200, "body": json.dumps(response)}

    if method == "OPTIONS":
        if is_streaming:
            response_stream.write(b"")
            response_stream.close()
            return
        return {"statusCode": 200, "headers": _CORS_HEADERS, "body": ""}

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, AttributeError):
        body = {}

    bot_id = body.get("bot_id")
    message = body.get("message")

    if not is_streaming:
        if not bot_id or not message:
            return {"statusCode": 400, "body": json.dumps({"error": "bot_id and message required"})}
        return {"statusCode": 501, "body": json.dumps({"error": "Use Function URL for streaming"})}

    if not bot_id:
        response_stream.write(b'data: {"error":"bot_id is required"}\n\n')
        response_stream.close()
        return

    if not message:
        response_stream.write(b'data: {"error":"message is required"}\n\n')
        response_stream.close()
        return

    try:
        from factory.core.chatbot import generate_response_stream

        logger.info(f"[stream:{bot_id}] query='{message[:60]}'")

        for token in generate_response_stream(
            bot_id=bot_id,
            user_message=message,
            top_k=5,
            similarity_threshold=0.3,
            conversation_history=[],
        ):
            chunk = f"data: {json.dumps({'token': token})}\n\n"
            response_stream.write(chunk.encode("utf-8"))

        response_stream.write(b"data: [DONE]\n\n")

    except Exception as e:
        logger.error(f"[stream:{bot_id}] error: {e}", exc_info=True)
        error_msg = f'data: {json.dumps({"error": str(e)})}\n\n'
        response_stream.write(error_msg.encode())

    response_stream.close()
