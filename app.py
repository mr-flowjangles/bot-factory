import os
from chalice import Chalice, Response
from factory.core.chatbot import generate_response
from dotenv import load_dotenv

load_dotenv()

app = Chalice(app_name="bot-factory")

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
    

# ─── Replace the existing /chat/stream route in app.py with this ───

@app.route("/chat/stream", methods=["POST"], cors=True)
def chat_stream():
    """
    SSE endpoint using real Bedrock streaming.
    Note: chalice local buffers the full response (Werkzeug limitation).
    Real token-by-token streaming happens via the Lambda Function URL.
    """
    import json
    request = app.current_request
    body = request.json_body
    bot_id = body.get("bot_id")
    message = body.get("message")

    if not bot_id:
        return Response(
            body='data: {"error":"bot_id is required"}\n\n',
            status_code=400,
            headers={"Content-Type": "text/event-stream"},
        )
    if not message:
        return Response(
            body='data: {"error":"message is required"}\n\n',
            status_code=400,
            headers={"Content-Type": "text/event-stream"},
        )

    try:
        from factory.core.chatbot import generate_response_stream

        chunks = []
        for token in generate_response_stream(
            bot_id=bot_id,
            user_message=message,
            top_k=5,
            similarity_threshold=0.3,
            conversation_history=[],
        ):
            chunks.append(f"data: {json.dumps({'token': token})}\n\n")

        chunks.append("data: [DONE]\n\n")
        return Response(
            body="".join(chunks),
            status_code=200,
            headers={"Content-Type": "text/event-stream"},
        )
    except Exception as e:
        return Response(
            body=f'data: {json.dumps({"error": str(e)})}\n\n',
            status_code=500,
            headers={"Content-Type": "text/event-stream"},
        )
