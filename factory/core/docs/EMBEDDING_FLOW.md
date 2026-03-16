# Embedding Generation Flow

A trace of every file and function called when generating embeddings for a bot.

This is an **offline, developer-run process** — not part of the live chat pipeline. Run it after adding or changing a bot's knowledge data.

---

## Entry Point

```bash
python3 -m factory.core.generate_embeddings {bot_id} --force

# Or via Makefile
make embed bot={bot_id}
```

---

## Full Call Chain

### 1. `core/generate_embeddings.py` — `main()`

CLI entry point. Parses `bot_id` from `sys.argv` and the optional `--force` flag, then calls `generate_bot_embeddings()`.

---

### 2. `core/generate_embeddings.py` — `generate_bot_embeddings(bot_id, force)`

Orchestrates the full pipeline across 6 steps.

**Step 1 — Connect to DynamoDB:**
```python
dynamodb = get_dynamodb_connection()
table = dynamodb.Table('BotFactoryRAG')
```
- Checks `APP_ENV` env var
- If `local`: connects to LocalStack via `LOCALSTACK_ENDPOINT`
- If `production`: connects to real AWS DynamoDB

**Step 2 — Check if embeddings already exist:**
- Scans `BotFactoryRAG` for rows matching `bot_id`
- If embeddings exist and `--force` was not passed: prompts `"Regenerate? (y/n)"`
- If `--force`: skips the prompt and proceeds

**Step 3 — Load and chunk the bot's data:**
```python
chunks = load_bot_data(bot_id)
```
→ delegates to `core/chunker.py` (see section 3 below)

**Step 4 — Generate embeddings:**
```python
bedrock_client = get_bedrock_client()
chunks = generate_all_embeddings(bedrock_client, chunks)
```
→ see section 4 below

**Step 5 — Clear old embeddings (kill-and-fill):**
- Scans `BotFactoryRAG` for all rows where `bot_id` matches
- Batch deletes those rows only — other bots are untouched

**Step 6 — Store new embeddings:**
- Batch writes all chunks to `BotFactoryRAG`
- Each row stored with key `{bot_id}_{chunk_id}` and fields: `id`, `bot_id`, `category`, `heading`, `text`, `embedding`
- Embedding values stored as `Decimal` (DynamoDB requirement)

---

### 3. `core/chunker.py` — `load_bot_data(bot_id)`

Reads knowledge files from S3 and produces text chunks ready for embedding.

**`load_yaml_files(bot_id)`**

- Initializes S3 client via `get_s3_client()`
  - Checks `APP_ENV` — LocalStack or real AWS
- Lists all `.yml` / `.yaml` files at `s3://<bucket>/bots/{bot_id}/data/`
- For each file: calls `s3.get_object()` and parses YAML
- Returns combined list of all `entries` across all files

**For each entry — `chunk_entry(entry)`**

Routes to the correct handler based on `entry.format`:

- `format: text` or `format: string` → **`chunk_text_entry()`**
  - Combines `heading` + `content` into a single text block

- `format: structured` or `format: object` → **`chunk_structured_entry()`**
  - Applies `template` string to each item in `items[]` using `.format(**item)`
  - Each item becomes its own line of text under the heading

- If `search_terms` is present on the entry, prepends `"Search terms: {search_terms}\n\n"` to the final text

Returns a list of dicts: `{id, bot_id, category, heading, text}`

---

### 4. `core/generate_embeddings.py` — `generate_all_embeddings(client, chunks)`

Loops through every chunk and embeds it one at a time.

**For each chunk — `generate_embedding(client, text)`**

> **BEDROCK CALL** — `client.invoke_model()`
> - Model: `amazon.titan-embed-text-v2:0`
> - Input: chunk's `text` field as plain text
> - Config: `dimensions=1024`, `normalize=True`
> - Output: 1024-dimension float vector

The vector is added to the chunk dict as `chunk['embedding']`.

If any single embedding call fails, the script exits immediately with an error — no partial writes.

---

## Summary Diagram

```
CLI: python3 -m factory.core.generate_embeddings {bot_id}
        │
        ▼
generate_embeddings.py — generate_bot_embeddings()
  │
  ├─► DynamoDB — BotFactoryRAG scan
  │     check if embeddings already exist for bot_id
  │     prompt to confirm regeneration (unless --force)
  │
  ├─► chunker.py — load_bot_data()
  │     │
  │     ├─► S3 — list_objects_v2()
  │     │     s3://<bucket>/bots/{bot_id}/data/
  │     │
  │     ├─► S3 — get_object() × N files
  │     │     parse YAML, extract entries[]
  │     │
  │     └─► chunk_entry() × N entries
  │           string entries → chunk_text_entry()
  │           object entries → chunk_structured_entry()
  │           → list of {id, bot_id, category, heading, text}
  │
  ├─► generate_all_embeddings()
  │     │
  │     └─► BEDROCK — Titan V2 × N chunks
  │               amazon.titan-embed-text-v2:0
  │               input: chunk text
  │               → 1024-dim float vector per chunk
  │
  ├─► DynamoDB — batch_delete (kill)
  │     remove all existing rows for bot_id
  │
  └─► DynamoDB — batch_write (fill)
        write all new chunks + embeddings to BotFactoryRAG
        key: {bot_id}_{chunk_id}
```

---

## Local vs Production

The same script runs in both environments. The difference is the `APP_ENV` env var:

| `APP_ENV` | Target |
|-----------|--------|
| `local` (default) | LocalStack (DynamoDB + S3 via `LOCALSTACK_ENDPOINT`) |
| `production` | Real AWS |

Note: Bedrock is **always real AWS** — LocalStack does not emulate Bedrock.
