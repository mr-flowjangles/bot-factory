# Chat Endpoint Flow

A trace of every file and function called when a user sends a message to a bot.

---

## Entry Points

There are two Lambda entry points — one for buffered responses, one for streaming:

**Buffered:** `POST /chat` via API Gateway → `factory/lambda_handler.py`

**Streaming:** `POST` via Lambda Function URL → `factory/streaming_handler.py`

Request body (both):
```json
{
  "bot_id": "guitar",
  "message": "What chord shapes work at fret 7?",
  "conversation_history": []
}
```

---

## Path A — Buffered (`lambda_handler.py`)

### 1. `lambda_handler.py` — `lambda_handler()`

AWS Lambda invokes this function with the API Gateway event.

- Extracts `method` and `path` from `event["requestContext"]["http"]` and `event["rawPath"]`
- Routes `POST /chat` → `handle_chat()`
- Routes `GET /bots` → `handle_list_bots()`
- Routes `GET /health` → `handle_health()`

---

### 2. `lambda_handler.py` — `handle_chat()`

- Parses `bot_id`, `message`, `conversation_history` from the request body
- Calls `load_bot_config(bot_id)` from `core/bot_utils.py`
  - Fetches `s3://<bucket>/bots/{bot_id}/config.yml` from S3, cached per bot
  - Reads `bot.rag.top_k` and `bot.rag.similarity_threshold`
- Calls `generate_response()` from `core/chatbot.py` (see section 3)
- Calls `log_chat_interaction()` from `core/bot_utils.py`
  - Writes question, response, and source categories to `BotFactoryLogs` DynamoDB table
- Returns `{"response": "...", "sources": [...]}`

---

### 3. `core/chatbot.py` — `generate_response()`

Orchestrates the full RAG pipeline.

**Step A — Retrieve context:**
```python
relevant_chunks = retrieve_relevant_chunks(
    bot_id, user_message, top_k, similarity_threshold
)
```
→ delegates to `core/retrieval.py` (see section 4 below)

**Step B — Format context:**
```python
context = format_context_for_llm(relevant_chunks)
```
→ joins chunks into `[CATEGORY]\ntext` blocks separated by `---`

**Step C — Build messages array:**
- Loops over `conversation_history`, appending each as `{"role": ..., "content": [{"text": ...}]}`
- Appends current user message with context injected:
  ```
  ## Relevant Context:
  {context}

  ## User Question:
  {user_message}
  ```

**Step D — Load system prompt:**
```python
system_prompt = load_system_prompt(bot_id)
```
- Checks `_system_prompts` cache (dict, persists on warm Lambda)
- On miss: fetches `s3://<bucket>/bots/{bot_id}/prompt.yml` from S3
- Injects `{current_date}` into the template
- Caches result for subsequent requests

**Step E — Initialize Bedrock client:**
```python
client = get_bedrock_client()
```
- Checks `_bedrock_client` global (lazy-init, persists on warm Lambda)
- On cold start: creates `boto3.client("bedrock-runtime")` using IAM role

---

### 4. `core/retrieval.py` — `retrieve_relevant_chunks()`

**Step A — Embed the query:**
```python
query_embedding = generate_query_embedding(query)
```

> **BEDROCK CALL #1** — `client.invoke_model()`
> - Model: `amazon.titan-embed-text-v2:0`
> - Input: user's question as plain text
> - Config: `dimensions=1024`, `normalize=True`
> - Output: 1024-dimension float vector

**Step B — Load bot embeddings:**
```python
items = get_cached_embeddings(bot_id)
```
- Checks `_embeddings_cache[bot_id]` (dict keyed by bot_id, warm Lambda cache)
- On cache **HIT**: returns immediately, no DynamoDB call
- On cache **MISS**:
  - Queries `BotFactoryRAG` DynamoDB table using the `bot_id-index` GSI
  - Only fetches rows for this bot — no full-table scan
  - Paginates until all items are loaded
  - Stores in `_embeddings_cache[bot_id]`

**Step C — Cosine similarity search (in memory):**
- Converts each stored embedding from `Decimal` to `float`
- Computes `cosine_similarity(query_embedding, stored_embedding)` using numpy
- Filters to items above `similarity_threshold`
- Sorts descending by score
- Returns top `top_k` results

Each result: `{id, category, heading, text, similarity}`

---

### 5. Back in `core/chatbot.py` — Bedrock Claude call

With context formatted and messages built:

> **BEDROCK CALL #2** — `client.converse()`
> - Model: `us.anthropic.claude-sonnet-4-20250514-v1:0`
> - System: bot's system prompt (from `prompt.yml` in S3)
> - Messages: conversation history + current user message with injected context
> - Config: `maxTokens=1000`
> - Output: complete response text

Returns `{"response": "...", "sources": [...]}` to `handle_chat()`.

---

## Path B — Streaming (`streaming_handler.py`)

Uses Lambda Response Streaming (invoked by a Lambda Function URL with `RESPONSE_STREAM` mode), which bypasses API Gateway and allows token-by-token delivery.

### 1. `streaming_handler.py` — `handler(event, response_stream)`

AWS Lambda invokes this function with the HTTP event and a writable `response_stream` object.

- Parses `bot_id` and `message` from the request body
- Validates both are present; writes error and closes stream on failure
- Calls `generate_response_stream()` from `core/chatbot.py`

### 2. `core/chatbot.py` — `generate_response_stream()`

Same pipeline as `generate_response()` through steps A–E above, but:
- Uses `client.converse_stream()` instead of `client.converse()`
- Yields each text chunk as it arrives:
  ```python
  for event in response["stream"]:
      if "contentBlockDelta" in event:
          yield event["contentBlockDelta"]["delta"]["text"]
  ```

### 3. Back in `streaming_handler.py`

For each yielded token:
```python
chunk = f"data: {json.dumps({'token': token})}\n\n"
response_stream.write(chunk.encode("utf-8"))
```

Closes with `data: [DONE]\n\n` and `response_stream.close()`.

---

## Summary Diagram

```
POST /chat (API Gateway)                POST via Function URL (SSE)
        │                                       │
        ▼                                       ▼
lambda_handler.py                   streaming_handler.py
  handle_chat()                        handler()
  │  load_bot_config() → S3            │
  │                                    │
  ▼                                    ▼
chatbot.py                          chatbot.py
  generate_response()                 generate_response_stream()
  │                                   │
  ├─► retrieval.py — retrieve_relevant_chunks()
  │     │
  │     ├─► BEDROCK #1 — Titan V2 (embed query)
  │     │     amazon.titan-embed-text-v2:0
  │     │     → 1024-dim vector
  │     │
  │     ├─► DynamoDB — BotFactoryRAG (GSI query, cache miss only)
  │     │     filtered by bot_id via bot_id-index
  │     │
  │     └─► cosine similarity (numpy, in memory)
  │           → top_k chunks above threshold
  │
  ├─► retrieval.py — format_context_for_llm()
  │
  ├─► load_system_prompt() → S3 (prompt.yml)
  │
  └─► BEDROCK #2 — Claude Sonnet
        us.anthropic.claude-sonnet-4-20250514-v1:0
        converse()           →  full response text
        converse_stream()    →  streamed token chunks
```

---

## Bedrock Calls at a Glance

| # | Where | Function | Model | Purpose |
|---|-------|----------|-------|---------|
| 1 | `retrieval.py` | `generate_query_embedding()` | `amazon.titan-embed-text-v2:0` | Convert user question to 1024-dim vector |
| 2 | `chatbot.py` | `generate_response()` / `generate_response_stream()` | `claude-sonnet-4-20250514` | Generate response with RAG context injected |

---

## AWS Resources Used

| Resource | Name | Purpose |
|----------|------|---------|
| DynamoDB table | `BotFactoryRAG` | Stores embeddings (pk: `{bot_id}_{chunk_id}`, GSI: `bot_id-index`) |
| DynamoDB table | `BotFactoryLogs` | Chat interaction logs (buffered path only) |
| S3 bucket | `<BOT_DATA_BUCKET>` | Bot configs, prompts, data files |
| Bedrock model | `amazon.titan-embed-text-v2:0` | Query embedding |
| Bedrock model | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Response generation |

---

## Warm vs Cold Lambda

On a **cold start**, the Bedrock client initializes, the DynamoDB GSI query runs, and the system prompt is fetched from S3. Everything is then cached in module-level globals.

On a **warm invocation**, all three caches are already populated — the only external calls are the two Bedrock API calls.
