"""
Local dev server for SSE streaming.
Bypasses Chalice's Werkzeug buffering.

Usage: python3 dev_server.py
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
from factory.core.chatbot import generate_response, generate_response_stream

app = Flask(__name__)
CORS(app)


@app.route("/")
def index():
    with open("app/chat_stream.html") as f:
        return Response(f.read(), content_type="text/html")


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "bot-factory"}


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    body = request.get_json()
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id or not message:
        return Response(
            f'data: {json.dumps({"error": "bot_id and message are required"})}\n\n',
            status=400,
            content_type="text/event-stream",
        )

    def generate():
        try:
            for token in generate_response_stream(
                bot_id=bot_id,
                user_message=message,
                top_k=5,
                similarity_threshold=0.3,
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


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id or not message:
        return {"error": "bot_id and message are required"}, 400

    try:
        result = generate_response(
            bot_id=bot_id,
            user_message=message,
            top_k=5,
            similarity_threshold=0.3,
            conversation_history=[],
        )
        return {"response": result["response"], "sources": result["sources"]}
    except Exception as e:
        return {"error": str(e)}, 500


if __name__ == "__main__":
    port = int(os.getenv("DEV_PORT", "8001"))
    print(f"🎸 Dev server (streaming) on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)