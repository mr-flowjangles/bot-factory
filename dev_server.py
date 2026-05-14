"""
Local dev server for SSE streaming.

Usage: python3 dev_server.py
"""

import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

import flask
from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from factory.core.chatbot import generate_response_stream
from factory.core.retrieval import retrieve_relevant_chunks
from factory.core.bot_utils import load_bot_config, log_chat_interaction
from factory.core.auth import authorize_request
from factory.core.rate_limit import check_rate_limit
from factory.core.self_heal import invoke_self_heal_async, get_pending_result

logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__)

# Only enable Flask CORS locally — in prod, the Lambda Function URL handles CORS
if os.getenv("APP_ENV", "local") != "production":
    CORS(app)


@app.route("/")
def index():
    if os.getenv("APP_ENV", "local") == "production":
        return {"status": "ok", "service": "bot-factory-stream"}
    with open("app/chat_stream.html") as f:
        return Response(f.read(), content_type="text/html")


@app.route("/demo/<bot_id>")
def demo(bot_id):
    """Serve a bot's demo page (local dev only)."""
    if os.getenv("APP_ENV", "local") == "production":
        return {"error": "not available"}, 404
    demo_dir = os.path.join("scripts", "bots", bot_id)
    return flask.send_from_directory(demo_dir, "demo.html")


@app.route("/demo/<bot_id>/<path:filename>")
def demo_static(bot_id, filename):
    """Serve static assets for a bot's demo page."""
    if os.getenv("APP_ENV", "local") == "production":
        return {"error": "not available"}, 404
    demo_dir = os.path.join("scripts", "bots", bot_id)
    return flask.send_from_directory(demo_dir, filename)


@app.route("/bot_scripts/<path:filename>")
def bot_scripts(filename):
    """Serve shared bot scripts."""
    if os.getenv("APP_ENV", "local") == "production":
        return {"error": "not available"}, 404
    return flask.send_from_directory("app/bot_scripts", filename)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "bot-factory"}


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    bot_id = body.get("bot_id")
    message = body.get("message")
    conversation_history = body.get("conversation_history", [])

    if not bot_id or not message:
        return Response(
            f'data: {json.dumps({"error": "bot_id and message are required"})}\n\n',
            status=400,
            content_type="text/event-stream",
        )

    api_key = request.headers.get("X-Publishable-Key") or request.headers.get("X-API-Key", "")
    origin = request.headers.get("Origin", "")
    allowed, reason, key_record = authorize_request(api_key, bot_id, origin)
    if not allowed:
        return Response(
            f'data: {json.dumps({"error": f"unauthorized: {reason}"})}\n\n',
            status=401,
            content_type="text/event-stream",
        )

    client_ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                 or request.remote_addr or "")
    rate_limit = key_record.get("rate_limit_per_hour")
    rl_allowed, rl_count = check_rate_limit(api_key, client_ip, rate_limit)
    if not rl_allowed:
        app.logger.warning(f"[rate_limit] blocked bot_id={bot_id} ip={client_ip} count={rl_count}")
        return Response(
            f'data: {json.dumps({"error": "rate limit exceeded"})}\n\n',
            status=429,
            content_type="text/event-stream",
        )

    config = load_bot_config(bot_id)
    rag = config.get("bot", {}).get("rag", {})
    top_k = rag.get("top_k", 5)
    similarity_threshold = rag.get("similarity_threshold", 0.3)

    # Check for pending self-heal results from a previous request
    pending = get_pending_result(bot_id)

    # Self-heal config
    agentic = config.get("bot", {}).get("agentic", {})
    self_heal_enabled = agentic.get("self_heal", False)
    confidence_threshold = agentic.get("confidence_threshold", 0.5)

    def generate():
        try:
            # Piggyback: notify user about previously auto-learned content
            if pending:
                topic = pending.get("topic", "a new topic")
                heal_msg = f"I just learned about {topic}! Try asking me again."
                yield f"data: {json.dumps({'type': 'self_heal', 'message': heal_msg})}\n\n"

            # Emit sources for local debug UI
            chunks = retrieve_relevant_chunks(
                bot_id=bot_id,
                query=message,
                top_k=top_k,
                similarity_threshold=0.0,
            )
            sources = [
                {"heading": c.get("heading", ""), "category": c["category"], "similarity": round(c["similarity"], 4)}
                for c in chunks
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            metadata = {}
            full_response = []
            for token in generate_response_stream(
                bot_id=bot_id,
                user_message=message,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                conversation_history=conversation_history,
                metadata_out=metadata,
            ):
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"

            # Log the interaction
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
            log_chat_interaction(bot_id, message, "".join(full_response), sources, client_ip=client_ip)

            # Invoke self-heal BEFORE [DONE] — all tokens are already streamed,
            # but Lambda can freeze the container after [DONE] so we must fire first.
            top_score = metadata.get("top_score", 1.0)
            if self_heal_enabled and top_score < confidence_threshold:
                app.logger.info(
                    f"[self_heal:{bot_id}] low confidence ({top_score:.3f} < {confidence_threshold}) "
                    f"— spawning self-heal"
                )
                invoke_self_heal_async(bot_id, message, config)

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f'data: {json.dumps({"error": str(e)})}\n\n'

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    port = int(os.getenv("DEV_PORT", "8001"))
    print(f"🎸 Dev server (streaming) on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
