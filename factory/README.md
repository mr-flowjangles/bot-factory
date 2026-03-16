# Bot Factory

A reusable RAG chatbot framework. Write a config, add knowledge data, run one command — get a working chatbot with semantic search and Claude-powered responses.

## How It Works

Each bot has three things stored in S3: a `config.yml`, a `prompt.yml`, and knowledge data files. The factory's core modules handle everything else — chunking data into text, generating embeddings via AWS Bedrock Titan V2, storing them in DynamoDB, retrieving relevant context via cosine similarity, and generating Claude responses via Bedrock.

```
User question
  → Bedrock Titan V2 embedding (convert question to vector)
  → DynamoDB GSI query (load bot's embeddings, cached on warm Lambda)
  → Cosine similarity search (find top_k relevant chunks)
  → Bedrock Claude Sonnet (generate response with context)
  → User gets answer
```

For a detailed trace of every file and function called during a chat request, see [docs/CHAT_FLOW.md](core/docs/CHAT_FLOW.md).

## Prerequisites

- **Docker** — for local development (`make up`)
- **AWS CLI** — configured with credentials for DynamoDB, S3, and Bedrock
- **Flask** — `pip install flask flask-cors` (for local dev server)

**AWS Bedrock access** — request model access in the AWS Console → Bedrock → Model catalog:
- `amazon.titan-embed-text-v2:0` (embeddings)
- `claude-sonnet-4` (responses)

## Where to Edit

### Edit freely — this is your bot
```
scripts/bots/<bot_id>/config.yml       # Bot settings, model params, RAG config
scripts/bots/<bot_id>/prompt.yml       # System prompt for Claude
scripts/bots/<bot_id>/data/*.yml       # Knowledge base files (upload to S3 before embedding)
```

### Edit with care — shared framework
```
factory/core/
  chatbot.py                   # Orchestrator (chat pipeline + Bedrock calls)
  retrieval.py                 # Semantic search / DynamoDB GSI query
  chunker.py                   # S3 YAML → text chunks
  generate_embeddings.py       # Embedding pipeline (offline, dev-run)
  bot_utils.py                 # Config loader + chat logger
  auth.py                      # API key validation
```

Changes here affect **all bots**. Test against multiple bots before committing.

### Don't edit — entry points and infra
```
factory/streaming_handler.py   # Streaming Lambda entry point (Lambda Function URL)
terraform/                     # Infrastructure as code
```

## Creating a New Bot

### Step 1: Scaffold the bot structure

```bash
make scaffold bot={bot_id}
```

This creates local files and ensures the S3 bucket exists:
```
scripts/bots/{bot_id}/config.yml     ← edit bot settings
scripts/bots/{bot_id}/prompt.yml     ← edit system prompt
scripts/bots/{bot_id}/data/          ← drop knowledge base YAMLs here
```

### Step 2: Write config.yml

This is the single source of truth for your bot. The `bot.id` drives everything — S3 paths, DynamoDB partitioning, API routing.

```yaml
bot:
  id: "cooking"
  enabled: true
  name: "ChefBot"
  personality: "friendly"

  response_style:
    tone: "conversational"
    length: "concise"
    suggestions: true

  model:
    provider: "bedrock"
    name: "us.anthropic.claude-sonnet-4-20250514-v1:0"
    max_tokens: 1000

  rag:
    top_k: 5
    similarity_threshold: 0.3

  boundaries:
    discuss_cooking: true
    discuss_unrelated: false

suggestions:
  - "How do I make pasta from scratch?"
  - "What temp for a medium-rare steak?"
  - "Best way to dice an onion?"
```

See [Config Reference](#config-reference) for all fields.

### Step 3: Write prompt.yml

System prompt sent to Claude with every request. The `system_prompt` field supports `{current_date}` as a placeholder injected at runtime.

```yaml
system_prompt: |
  You are ChefBot, a friendly cooking assistant.

  Today's date is {current_date}.

  Rules:
  - Keep responses to 2-3 sentences
  - Always mention food safety when relevant
  - If asked about something outside cooking, politely redirect
```

### Step 4: Add knowledge data

Create YAML files in `scripts/bots/{bot_id}/data/`, then upload them to S3. The embedding pipeline reads from S3, not the local filesystem.

Two entry types are supported:

**String entries** — content is embedded as-is:

```yaml
entries:
  - id: knife_basics
    format: string
    category: "Techniques"
    heading: "Knife Skills"
    content: "The three essential cuts are dice, julienne, and chiffonade..."
```

**Object entries** — a template applied to each item:

```yaml
entries:
  - id: cooking_temps
    format: object
    category: "Temperatures"
    heading: "Protein Cooking Temperatures"
    template: "{protein} cooked to {doneness}: internal temp {temp}F. {notes}"
    items:
      - protein: "Chicken breast"
        doneness: "done"
        temp: "165"
        notes: "No pink remaining."
      - protein: "Beef steak"
        doneness: "medium-rare"
        temp: "130"
        notes: "Warm red center."
```

The chunker flattens object entries so each item becomes a standalone text chunk for embedding. Add a `search_terms` field to any entry to improve semantic search recall.

**Upload data to S3:**

```bash
# Local (LocalStack)
make load-bot bot={bot_id}

# Production
make deploy-bot-prod bot={bot_id}
```

### Step 5: Deploy and test locally

```bash
# One command does it all: deploy config + load data + embed + API key
make setup-bot bot={bot_id}

# Test it
make test-chat BOT={bot_id} MSG="your test question"
```

Or start the full local stack and use the chat UI at `http://localhost:8080`.

### Step 6: Deploy to production

```bash
# First time: provision infrastructure
make deploy-infra
make deploy-streaming

# Deploy bot (config + data + embeddings + API key)
make setup-bot-prod bot={bot_id}
```

## Project Structure

```
/
├── factory/
│   ├── README.md                  ← you are here
│   ├── streaming_handler.py       ← Lambda entry point (streaming, Function URL)
│   └── core/
│       ├── chatbot.py             ← Orchestrator: retrieval → build messages → Bedrock Claude
│       ├── retrieval.py           ← DynamoDB GSI query + cosine similarity
│       ├── chunker.py             ← S3 YAML → text chunks
│       ├── generate_embeddings.py ← chunks → Bedrock Titan V2 → DynamoDB
│       ├── bot_utils.py           ← Config loader (S3) + chat logger (DynamoDB)
│       ├── auth.py                ← API key validation (DynamoDB)
│       └── docs/
│           ├── CHAT_FLOW.md       ← full trace of a chat request
│           ├── EMBEDDING_FLOW.md  ← full trace of embedding generation
│           └── LOCAL_DEVELOPMENT.md ← local dev commands and troubleshooting
│
└── scripts/bots/                  ← bot source files (one folder per bot)
    ├── RobbAI/                    ← resume AI assistant
    └── the-fret-detective/        ← guitar learning bot
```

## Config Reference

### bot (required)

| Field         | Type    | Description                                                |
| ------------- | ------- | ---------------------------------------------------------- |
| `id`          | string  | Bot identifier. Drives S3 paths and DynamoDB partitioning. |
| `enabled`     | boolean | Set `false` to disable without deleting.                   |
| `name`        | string  | Display name (shown in UI labels).                         |
| `personality` | string  | Personality hint passed to the system prompt context.      |

### bot.response_style

| Field         | Type    | Description                                   |
| ------------- | ------- | --------------------------------------------- |
| `tone`        | string  | `"conversational"`, `"formal"`, `"technical"` |
| `length`      | string  | `"concise"`, `"detailed"`                     |
| `suggestions` | boolean | Show suggestion chips in the UI.              |

### bot.model

| Field        | Type    | Description                                                            |
| ------------ | ------- | ---------------------------------------------------------------------- |
| `provider`   | string  | `"bedrock"`                                                            |
| `name`       | string  | Bedrock model ID, e.g., `"us.anthropic.claude-sonnet-4-20250514-v1:0"` |
| `max_tokens` | integer | Max response length in tokens.                                         |

### bot.rag

| Field                  | Type    | Description                                                             |
| ---------------------- | ------- | ----------------------------------------------------------------------- |
| `top_k`                | integer | Number of chunks to retrieve. Use 10+ if data has many similar entries. |
| `similarity_threshold` | float   | Minimum cosine similarity (0.0-1.0). Start at 0.3, tune up if noisy.   |

### bot.boundaries

Free-form key-value pairs. The keys and values are passed to the system prompt to define what the bot will and won't discuss.

### suggestions (required)

List of starter questions shown as chips in the chat UI.

## Embedding Notes

All bot embeddings share one DynamoDB table (`BotFactoryRAG`), partitioned by `bot_id`. Each record's primary key is `{bot_id}_{entry_id}`. A GSI on `bot_id` allows efficient per-bot queries without scanning the entire table.

Embeddings use **Bedrock Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`) at 1024 dimensions. Knowledge data files live in S3 (`s3://<bucket>/bots/{bot_id}/data/`) — the chunker reads from S3 at embedding time, keeping data files out of the Lambda package.

If your bot has many similar entries (like The Fret Detective's chord voicings across 12 keys), increase `top_k` to 10 or higher so the right result isn't crowded out by near-duplicates.

## Command Reference

| Task | Command | Notes |
| ---- | ------- | ----- |
| Start local stack | `make up` | nginx :8080, Flask :8001, LocalStack :4566 |
| Stop everything | `make down` | |
| Full local setup | `make setup-bot bot={id}` | Deploy + load + embed + API key |
| Full prod setup | `make setup-bot-prod bot={id}` | Deploy + embed + API key |
| Deploy bot data (local) | `make load-bot bot={id}` | Upload data to LocalStack S3 |
| Deploy config+prompt (local) | `make deploy-bot bot={id}` | Upload config+prompt to LocalStack S3 |
| Generate embeddings (local) | `make embed bot={id}` | Reads LocalStack S3, writes LocalStack DynamoDB |
| Generate API key (local) | `make gen-key bot={id} name=dev-local` | Scoped to bot, writes to .env |
| Send test message | `make test-chat BOT={id} MSG="..."` | Calls lambda_handler directly |
| Deploy infra (prod) | `make deploy-infra` | Terraform deploy |
| Deploy streaming (prod) | `make deploy-streaming` | Streaming Lambda + Function URL |
| Deploy bot (prod) | `make deploy-bot-prod bot={id}` | Upload to prod S3 + generate prod embeddings |
| Scaffold new bot | `make scaffold bot={id}` | Creates local file structure |
| See all commands | `make help` | |
