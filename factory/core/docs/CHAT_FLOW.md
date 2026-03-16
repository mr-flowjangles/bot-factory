# Chat Endpoint Flow

A trace of every file and function called when a user sends a message to a bot.

---

## Entry Point

**Streaming:** `POST /chat` via Lambda Function URL → `factory/streaming_handler.py`

Request body:
```json
{
  "bot_id": "RobbAI",
  "message": "What does Rob do?"
}
```

Header: `X-API-Key: bfk_...`

---

## Flow — Streaming (`streaming_handler.py`)

Uses Lambda Response Streaming (invoked by a Lambda Function URL with `RESPONSE_STREAM` mode), which bypasses API Gateway and allows token-by-token delivery via SSE.

### 1. `streaming_handler.py` — `handler(event, response_stream)`

AWS Lambda invokes this function with the HTTP event and a writable `response_stream` object.

- Parses `bot_id` and `message` from the request body
- Validates API key via `auth.validate_api_key()`
- Loads bot config via `bot_utils.load_bot_config(bot_id)` — reads `top_k` and `similarity_threshold` from `bot.rag`
- Calls `generate_response_stream()` from `core/chatbot.py`

### 2. `core/chatbot.py` — `generate_response_stream()`

Orchestrates the full RAG pipeline.

**Step A — Retrieve context:**
```python
relevant_chunks = retrieve_relevant_chunks(
    bot_id, user_message, top_k, similarity_threshold
)
```
→ delegates to `core/retrieval.py` (see section 3 below)

**Step B — Format context:**
```python
context = format_context_for_llm(relevant_chunks)
```
→ joins chunks into `[CATEGORY]\ntext` blocks separated by `---`

**Step C — Build messages array:**
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

**Step E — Stream response from Bedrock:**
- Uses `client.converse_stream()` instead of `client.converse()`
- Yields each text chunk as it arrives:
  ```python
  for event in response["stream"]:
      if "contentBlockDelta" in event:
          yield event["contentBlockDelta"]["delta"]["text"]
  ```

---

### 3. `core/retrieval.py` — `retrieve_relevant_chunks()`

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

### 4. Back in `streaming_handler.py` — SSE output

For each yielded token:
```python
chunk = f"data: {json.dumps({'token': token})}\n\n"
response_stream.write(chunk.encode("utf-8"))
```

Closes with `data: [DONE]\n\n` and `response_stream.close()`.

---

## Summary Diagram

```
POST via Function URL (SSE)
        │
        ▼
streaming_handler.py
  handler()
  │  validate_api_key() → DynamoDB BotFactoryApiKeys
  │  load_bot_config() → S3 (top_k, similarity_threshold)
  │
  ▼
chatbot.py
  generate_response_stream()
  │
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
        converse_stream() → streamed token chunks
```

---

## Bedrock Calls at a Glance

| # | Where | Function | Model | Purpose |
|---|-------|----------|-------|---------|
| 1 | `retrieval.py` | `generate_query_embedding()` | `amazon.titan-embed-text-v2:0` | Convert user question to 1024-dim vector |
| 2 | `chatbot.py` | `generate_response_stream()` | `claude-sonnet-4-20250514` | Generate response with RAG context injected |

---

## AWS Resources Used

| Resource | Name | Purpose |
|----------|------|---------|
| DynamoDB table | `BotFactoryRAG` | Stores embeddings (pk: `{bot_id}_{chunk_id}`, GSI: `bot_id-index`) |
| DynamoDB table | `BotFactoryLogs` | Chat interaction logs |
| DynamoDB table | `BotFactoryApiKeys` | API key validation |
| S3 bucket | `<BOT_DATA_BUCKET>` | Bot configs, prompts, data files |
| Bedrock model | `amazon.titan-embed-text-v2:0` | Query embedding |
| Bedrock model | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Response generation |

---

## Warm vs Cold Lambda

On a **cold start**, the Bedrock client initializes, the DynamoDB GSI query runs, and the system prompt is fetched from S3. Everything is then cached in module-level globals.

On a **warm invocation**, all three caches are already populated — the only external calls are the two Bedrock API calls.
