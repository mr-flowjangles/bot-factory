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
    "Access-Control-Allow-Headers": "content-type, x-api-key",
}


def handler(event, *args):
    """
    Lambda streaming handler.
    - Function URL with RESPONSE_STREAM: (event, response_stream, context)
    - Direct invocation: (event, context)
    """
    if len(args) == 2:
        response_stream = args[0]
        is_streaming = True
    else:
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
    conversation_history = body.get("conversation_history", [])

    if not is_streaming:
        if not bot_id or not message:
            return {"statusCode": 400, "body": json.dumps({"error": "bot_id and message required"})}
        return {"statusCode": 501, "body": json.dumps({"error": "Use Function URL for streaming"})}

    if not bot_id:
        response_stream.write(b'data: {"error":"bot_id is required"}\n\n')
        response_stream.close()
        return

    # Auth check
    headers = event.get("headers", {})
    api_key = headers.get("x-api-key", "")
    from factory.core.auth import validate_api_key

    if not validate_api_key(api_key, bot_id):
        response_stream.write(b'data: {"error":"unauthorized"}\n\n')
        response_stream.close()
        return

    if not message:
        response_stream.write(b'data: {"error":"message is required"}\n\n')
        response_stream.close()
        return

    try:
        from factory.core.chatbot import generate_response_stream
        from factory.core.bot_utils import load_bot_config
        from factory.core.self_heal import invoke_self_heal_async, get_pending_result

        config = load_bot_config(bot_id)
        rag = config.get("bot", {}).get("rag", {})
        top_k = rag.get("top_k", 5)
        similarity_threshold = rag.get("similarity_threshold", 0.3)

        # Self-heal config
        agentic = config.get("bot", {}).get("agentic", {})
        self_heal_enabled = agentic.get("self_heal", False)
        confidence_threshold = agentic.get("confidence_threshold", 0.5)

        logger.info(f"[stream:{bot_id}] query='{message[:60]}' top_k={top_k}")

        # Piggyback: notify about previously auto-learned content
        pending = get_pending_result(bot_id)
        if pending:
            topic = pending.get("topic", "a new topic")
            heal_msg = f"I just learned about {topic}! Try asking me again."
            msg = f"data: {json.dumps({'type': 'self_heal', 'message': heal_msg})}\n\n"
            response_stream.write(msg.encode("utf-8"))

        metadata = {}
        for token in generate_response_stream(
            bot_id=bot_id,
            user_message=message,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            conversation_history=conversation_history,
            metadata_out=metadata,
        ):
            chunk = f"data: {json.dumps({'token': token})}\n\n"
            response_stream.write(chunk.encode("utf-8"))

        response_stream.write(b"data: [DONE]\n\n")

        # Trigger self-heal if confidence is low
        top_score = metadata.get("top_score", 1.0)
        if self_heal_enabled and top_score < confidence_threshold:
            logger.info(
                f"[self_heal:{bot_id}] low confidence ({top_score:.3f} < {confidence_threshold}) "
                f"— invoking self-heal"
            )
            invoke_self_heal_async(bot_id, message, config)

    except Exception as e:
        logger.error(f"[stream:{bot_id}] error: {e}", exc_info=True)
        error_msg = f'data: {json.dumps({"error": str(e)})}\n\n'
        response_stream.write(error_msg.encode())

    response_stream.close()
