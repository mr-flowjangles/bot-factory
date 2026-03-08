import os
import json
from flask import Flask, request, jsonify, send_file, Response
from factory.core.chatbot import generate_response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return send_file("app/chat.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "bot-factory"})


@app.route("/chat", methods=["POST"])
def chat():
    body = request.json
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id:
        return jsonify({"error": "bot_id is required"}), 400
    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        result = generate_response(
            bot_id=bot_id,
            user_message=message,
            top_k=5,
            similarity_threshold=0.3,
            conversation_history=[],
        )
        return jsonify({"response": result["response"], "sources": result["sources"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    body = request.json
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id:
        return Response(
            'data: {"error":"bot_id is required"}\n\n',
            status=400,
            content_type="text/event-stream",
        )
    if not message:
        return Response(
            'data: {"error":"message is required"}\n\n',
            status=400,
            content_type="text/event-stream",
        )

    def generate():
        try:
            from factory.core.chatbot import generate_response_stream

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

    return Response(generate(), content_type="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
