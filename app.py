from chalice import Chalice, Response
from factory.core.chatbot import generate_response

app = Chalice(app_name="bot-factory")

import os

@app.route("/", methods=["GET"])
def index():
    html_path = "app/chat.html"
    with open(html_path) as f:
        return Response(body=f.read(), status_code=200, headers={"Content-Type": "text/html"})


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "bot-factory"}


@app.route("/chat", methods=["POST"])
def chat():
    request = app.current_request
    body = request.json_body

    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id:
        return Response(body={"error": "bot_id is required"}, status_code=400)
    if not message:
        return Response(body={"error": "message is required"}, status_code=400)

    try:
        result = generate_response(
            bot_id=bot_id,
            user_message=message,
            top_k=5,
            similarity_threshold=0.3,
            conversation_history=[],
        )
        return {
            "response": result["response"],
            "sources": result["sources"],
        }
    except Exception as e:
        return Response(body={"error": str(e)}, status_code=500)
