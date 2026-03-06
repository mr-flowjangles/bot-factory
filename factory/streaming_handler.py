"""
Streaming Lambda handler for Function URL (RESPONSE_STREAM mode).
Invoked directly by Lambda Function URL — bypasses API Gateway.
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, response_stream):
    """
    Lambda streaming handler. Function URL with RESPONSE_STREAM invoke mode
    passes a writable response_stream instead of expecting a return value.
    """
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, AttributeError):
        body = {}

    bot_id = body.get("bot_id")
    message = body.get("message")

    # --- Validation ---
    if not bot_id:
        response_stream.write(b'data: {"error":"bot_id is required"}\n\n')
        response_stream.close()
        return

    if not message:
        response_stream.write(b'data: {"error":"message is required"}\n\n')
        response_stream.close()
        return

    # --- Stream tokens from Bedrock ---
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
        response_stream.write(
            f'data: {json.dumps({"error": str(e)})}\n\n'.encode("utf-8")
        )

    response_stream.close()
