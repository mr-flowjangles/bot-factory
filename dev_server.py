"""
Local dev server for SSE streaming.

Usage: python3 dev_server.py
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from factory.core.chatbot import generate_response_stream
from factory.core.retrieval import retrieve_relevant_chunks
from factory.core.bot_utils import load_bot_config
from factory.core.auth import validate_api_key

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



@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "bot-factory"}


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id or not message:
        return Response(
            f'data: {json.dumps({"error": "bot_id and message are required"})}\n\n',
            status=400,
            content_type="text/event-stream",
        )

    api_key = request.headers.get("X-API-Key", "")
    if not validate_api_key(api_key, bot_id):
        return Response(
            f'data: {json.dumps({"error": "unauthorized"})}\n\n',
            status=401,
            content_type="text/event-stream",
        )

    config = load_bot_config(bot_id)
    rag = config.get("bot", {}).get("rag", {})
    top_k = rag.get("top_k", 5)
    similarity_threshold = rag.get("similarity_threshold", 0.3)

    def generate():
        try:
            # Emit sources for local debug UI
            chunks = retrieve_relevant_chunks(
                bot_id=bot_id, query=message, top_k=top_k, similarity_threshold=0.0,
            )
            sources = [
                {"heading": c.get("heading", ""), "category": c["category"], "similarity": round(c["similarity"], 4)}
                for c in chunks
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            for token in generate_response_stream(
                bot_id=bot_id,
                user_message=message,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                conversation_history=[],
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
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
