# Creating a New Bot

## TL;DR

```bash
make scaffold bot={bot_id}
# edit config.yml, prompt.yml, add data YAMLs
make setup-bot bot={bot_id}
```

---

Step-by-step guide for adding a new bot to Bot Factory.

## Prerequisites

- Docker running (`make up`)
- AWS credentials configured (for Bedrock embeddings)

## Step 1: Scaffold

```bash
make scaffold bot={bot_id}
```

This creates:

```
scripts/bots/{bot_id}/
├── config.yml      ← bot settings (model, RAG, boundaries)
├── prompt.yml      ← system prompt sent to Claude
└── data/
    └── 00-template.yml   ← example data file with both entry formats
```

The bot ID must be alphanumeric with optional hyphens. It drives everything — folder names, S3 keys, DynamoDB partitioning.

## Step 2: Edit config.yml

`scripts/bots/{bot_id}/config.yml` is the single source of truth for your bot.

```yaml
bot:
  id: "{bot_id}"
  enabled: true
  name: "Display Name"
  personality: "friendly"

  response_style:
    tone: "conversational"
    length: "concise"
    suggestions: true

  model:
    provider: "bedrock"
    name: "us.anthropic.claude-sonnet-4-20250514-v1:0"
    max_tokens: 1024

  rag:
    top_k: 5
    similarity_threshold: 0.3

  boundaries:
    discuss_unrelated: false

suggestions:
  - "Suggestion 1"
  - "Suggestion 2"
  - "Suggestion 3"
```

## Step 3: Edit prompt.yml

`scripts/bots/{bot_id}/prompt.yml` defines the system prompt. Supports `{current_date}` placeholder injected at runtime.

```yaml
system_prompt: |
  You are {bot_name}, a helpful assistant specialized in {topic}.

  Today's date is {current_date}.

  Rules:
  - Keep responses concise
  - Stay on topic
  - If asked about something outside your domain, politely redirect
```

## Step 4: Add Knowledge Data

Drop YAML files into `scripts/bots/{bot_id}/data/`. Two entry formats are supported:

**String entries** — content embedded as-is:

```yaml
entries:
  - id: unique_id
    format: string
    category: "Category Name"
    heading: "Entry Heading"
    search_terms: "keywords that help retrieval"
    content: "The actual knowledge content that gets embedded..."
```

**Object entries** — a template applied to each item:

```yaml
entries:
  - id: unique_id
    format: object
    category: "Category Name"
    heading: "Entry Heading"
    template: "{field_a} — {field_b}: {field_c}"
    items:
      - field_a: "Value"
        field_b: "Value"
        field_c: "Value"
```

The chunker flattens object entries using the template, so each item becomes a standalone text chunk for embedding. Add a `search_terms` field to any entry to improve semantic search recall.

## Step 5: Deploy and Test Locally

```bash
# One command: deploy config + load data + embed + generate API key
make setup-bot bot={bot_id}

# Test it
make test-chat BOT={bot_id} MSG="your test question"
```

Or open `http://localhost:8080` and chat through the UI.

## Step 6: Deploy to Production

```bash
# First time: provision infrastructure
make deploy-infra
make deploy-streaming

# Deploy bot (config + data + embeddings + API key)
make setup-bot-prod bot={bot_id}
```

---

## Quick Reference

| Step | Command | What it does |
|------|---------|-------------|
| Scaffold | `make scaffold bot={bot_id}` | Creates local file structure |
| Full local setup | `make setup-bot bot={bot_id}` | Deploy + load + embed + API key |
| Full prod setup | `make setup-bot-prod bot={bot_id}` | Deploy + embed + API key |
| Deploy config | `make deploy-bot bot={bot_id}` | Uploads config + prompt to S3 |
| Load data | `make load-bot bot={bot_id}` | Syncs data YAMLs to S3 |
| Embed | `make embed bot={bot_id}` | Generates vectors in DynamoDB |
| API key | `make gen-key bot={bot_id} name=dev-local` | Creates scoped API key |
| Test | `make test-chat BOT={bot_id}` | Quick smoke test |

## S3 Structure

After a full deploy, your bot's S3 layout looks like:

```
s3://bot-factory-data/
└── bots/
    └── {bot_id}/
        ├── config.yml
        ├── prompt.yml
        └── data/
            ├── 00-basics.yml
            └── 01-details.yml
```

## Security

API keys are stored in the `BotFactoryApiKeys` DynamoDB table. Keys are scoped per bot — a key generated for `RobbAI` can't access `the-fret-detective`.

```bash
make gen-key bot={bot_id} name=dev-local       # local key
make gen-key-prod bot={bot_id} name=prod        # production key
```

Keys are sent via the `X-API-Key` header:

```bash
curl -X POST https://your-lambda-url/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bfk_your_key_here" \
  -d '{"bot_id": "{bot_id}", "message": "hello"}'
```
