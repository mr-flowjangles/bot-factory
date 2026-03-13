
# Bot Factory Auth — Integration Guide
# =====================================
#
# 4 new files, 4 existing files to patch.
#


# ═══════════════════════════════════════════════════════════════
# NEW FILES (drop in as-is)
# ═══════════════════════════════════════════════════════════════
#
# factory/core/auth.py          ← auth middleware module
# scripts/generate_api_key.py   ← key generation CLI
# (terraform additions below)   ← DynamoDB table for keys
# (Makefile additions below)    ← gen-key, list-keys, revoke-key


# ═══════════════════════════════════════════════════════════════
# PATCH 1: dev_server.py — add auth to Flask routes
# ═══════════════════════════════════════════════════════════════
#
# At the top, add this import:
#
#   from factory.core.auth import require_auth, check_bot_access
#
# Then add @require_auth to /chat and /chat/stream routes:
#
# BEFORE:
#   @app.route("/chat/stream", methods=["POST"])
#   def chat_stream():
#       body = request.json
#       bot_id = body.get("bot_id")
#       ...
#
# AFTER:
#   @app.route("/chat/stream", methods=["POST"])
#   @require_auth
#   def chat_stream():
#       body = request.json
#       bot_id = body.get("bot_id")
#
#       # Verify key has access to this bot
#       if not check_bot_access(request.auth_info, bot_id):
#           return jsonify({"error": f"Key does not have access to bot '{bot_id}'"}), 403
#       ...
#
# Same pattern for /chat route.
# Do NOT add @require_auth to /health or /test (test page itself).


# ═══════════════════════════════════════════════════════════════
# PATCH 2: streaming_handler.py — add auth to Lambda handler
# ═══════════════════════════════════════════════════════════════
#
# After parsing the body and before streaming tokens, add:
#
#   from factory.core.auth import extract_api_key, validate_api_key, check_bot_access
#
#   raw_key = extract_api_key(event)
#   if not raw_key:
#       if is_streaming:
#           response_stream.write(b'data: {"error":"Missing API key"}\n\n')
#           response_stream.close()
#           return
#       return {"statusCode": 401, "body": json.dumps({"error": "Missing API key"})}
#
#   auth_info = validate_api_key(raw_key)
#   if not auth_info:
#       if is_streaming:
#           response_stream.write(b'data: {"error":"Invalid API key"}\n\n')
#           response_stream.close()
#           return
#       return {"statusCode": 403, "body": json.dumps({"error": "Invalid API key"})}
#
#   if not check_bot_access(auth_info, bot_id):
#       if is_streaming:
#           response_stream.write(b'data: {"error":"Key has no access to this bot"}\n\n')
#           response_stream.close()
#           return
#       return {"statusCode": 403, "body": json.dumps({"error": "Key has no access to this bot"})}


# ═══════════════════════════════════════════════════════════════
# PATCH 3: init-dynamodb.sh — add API keys table
# ═══════════════════════════════════════════════════════════════
#
# Add alongside the other create_table calls:
#
#   create_table BotFactoryApiKeys \
#       --attribute-definitions \
#           AttributeName=pk,AttributeType=S \
#       --key-schema AttributeName=pk,KeyType=HASH \
#       --billing-mode PAY_PER_REQUEST
#
# Also add it to the drop section if you have --drop support:
#
#   drop_table BotFactoryApiKeys


# ═══════════════════════════════════════════════════════════════
# PATCH 4: terraform/main.tf — add DynamoDB table + Lambda env var
# ═══════════════════════════════════════════════════════════════
#
# A) Add the table resource (see terraform_api_keys.tf)
#
# B) Add API_KEYS_TABLE to the streaming Lambda environment block:
#
#   environment {
#     variables = {
#       ...existing vars...
#       API_KEYS_TABLE = aws_dynamodb_table.api_keys.name
#     }
#   }


# ═══════════════════════════════════════════════════════════════
# TEST SEQUENCE (local)
# ═══════════════════════════════════════════════════════════════
#
# 1. Recreate tables with the new ApiKeys table:
#    make up reset=1
#
# 2. Load embeddings:
#    make embed BOT=guitar
#
# 3. Generate a local key:
#    make gen-key bot=guitar name=test-local
#    (SAVE the key output)
#
# 4. Start dev server:
#    python3 dev_server.py
#
# 5. Test WITHOUT key (should get 401):
#    curl -X POST http://localhost:8001/chat/stream \
#      -H "Content-Type: application/json" \
#      -d '{"bot_id":"guitar","message":"hello"}'
#
# 6. Test WITH key (should stream):
#    curl -X POST http://localhost:8001/chat/stream \
#      -H "Content-Type: application/json" \
#      -H "Authorization: Bearer bf_live_YOUR_KEY_HERE" \
#      -d '{"bot_id":"guitar","message":"hello"}'
#
# 7. Test web page at http://localhost:8001/test
#    (page should have API key input field)
