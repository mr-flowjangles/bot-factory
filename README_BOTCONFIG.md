# Creating a New Bot

## TL;DR

```bash
make scaffold bot={bot_id}
# edit config.yml, prompt.yml, add data YAMLs
make deploy-bot bot={bot_id}
make load-bot bot={bot_id}
make embed bot={bot_id}
make gen-key bot={bot_id} name=dev-local
make test-chat bot={bot_id}
```

---

Step-by-step guide for adding a new bot to Bot Factory.

## Prerequisites

- Docker running (`make up` or `make up reset=1`)
- AWS credentials configured (for Bedrock embeddings)
- `.env` file with `BOT_DATA_BUCKET=bot-factory-data`

## Step 1: Scaffold

```bash
make scaffold bot={bot_id}
```

This creates:

```
scripts/bots/{bot_id}/
├── config.yml      ← bot settings (model, RAG, frontend)
├── prompt.yml      ← system prompt sent to Claude
└── data/
    └── README.md   ← instructions for knowledge base files
```

The bot ID must be alphanumeric, lowercase. It drives everything — folder names, S3 keys, API routing.

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

frontend:
  subtitle: "Bot subtitle"
  welcome: "Welcome message shown on load"
  placeholder: "Type a message..."
  badge: "Beta"
  nav:
    - icon: "💬"
      label: "Chat"
      section: "chat"
    - icon: "ℹ️"
      label: "About"
      section: "about"
```

## Step 3: Edit prompt.yml

`scripts/bots/{bot_id}/prompt.yml` defines the system prompt. Supports `{current_date}` placeholder injected at runtime.

```yaml
prompt: |
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
- id: unique_id
  format: string
  category: "Category Name"
  heading: "Entry Heading"
  content: "The actual knowledge content that gets embedded..."
```

**Object entries** — a template applied to each item:

```yaml
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

The chunker flattens object entries using the template, so each item becomes a standalone text chunk for embedding.

## Step 5: Deploy Config + Prompt to S3

```bash
make deploy-bot bot={bot_id}
```

Uploads `config.yml` and `prompt.yml` to `s3://bot-factory-data/bots/{bot_id}/`.

## Step 6: Load Data to S3

```bash
make load-bot bot={bot_id}
```

Syncs `scripts/bots/{bot_id}/data/` to `s3://bot-factory-data/bots/{bot_id}/data/`.

## Step 7: Generate Embeddings

```bash
make embed bot={bot_id}
```

Reads data from S3, generates Titan V2 embeddings, and writes vectors to the `BotFactoryRAG` DynamoDB table.

Use `make embed-force bot={bot_id}` to skip the confirmation prompt.

## Step 8: Generate API Key

```bash
make gen-key bot={bot_id} name=dev-local
```

Save the key it prints — you'll need it for every request. Keys are stored in the `BotFactoryApiKeys` DynamoDB table and scoped to specific bots.

Useful commands:

```bash
make list-keys              # show all keys
make revoke-key key=bf_...  # revoke a key
```

## Step 9: Test

```bash
make test-chat bot={bot_id}
```

Or hit the local dev server directly:

```bash
curl -N -X POST http://localhost:8001/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer bf_live_YOUR_KEY_HERE" \
  -d '{"bot_id":"{bot_id}","message":"hello","session_id":"test123"}'
```

Without the `Authorization` header you'll get a 401. Wrong bot scope gets a 403.

---

## Quick Reference

| Step | Command | What it does |
|------|---------|-------------|
| Scaffold | `make scaffold bot={bot_id}` | Creates local file structure |
| Deploy config | `make deploy-bot bot={bot_id}` | Uploads config + prompt to S3 |
| Load data | `make load-bot bot={bot_id}` | Syncs data YAMLs to S3 |
| Embed | `make embed bot={bot_id}` | Generates vectors in DynamoDB |
| API key | `make gen-key bot={bot_id} name=dev` | Creates scoped API key |
| Test | `make test-chat bot={bot_id}` | Quick smoke test |

## Production

For production deploys, use the `-prod` variants:

```bash
make deploy-bot-prod bot={bot_id}
make embed-prod bot={bot_id}
```

These hit real AWS instead of LocalStack.

## S3 Structure

After a full deploy, your bot's S3 layout looks like:

```
s3://bot-factory-data/
└── bots/
    └── {bot_id}/
        ├── config.yml
        ├── prompt.yml
        └── data/
            ├── knowledge_file_1.yml
            └── knowledge_file_2.yml
```

## Security

Two layers protect the chat endpoint in production.

### Layer 1: Origin Verification (protects the door)

CloudFront and Lambda share a secret. CloudFront injects it as a custom header on every request it forwards. Lambda checks for it. If the header is missing or wrong, Lambda returns 403.

The browser never sees this header — it's added server-to-server, behind the scenes.

**How it works:**

```
User's browser
  → thefretdetective.com/chat/stream (HTTPS)
    → CloudFront adds "X-Origin-Verify: <secret>" automatically
      → Lambda checks header, matches env var → allowed

Someone hitting Lambda URL directly
  → No X-Origin-Verify header
    → Lambda returns 403
```

**Setup (Terraform):**

CloudFront side — tell it to add the header:

```hcl
resource "aws_cloudfront_distribution" "bot" {
  origin {
    custom_header {
      name  = "X-Origin-Verify"
      value = "your-random-secret-here"
    }
  }
}
```

Lambda side — give it the same secret to check against:

```hcl
resource "aws_lambda_function" "streaming" {
  environment {
    variables = {
      ORIGIN_SECRET = "your-random-secret-here"
    }
  }
}
```

Lambda code:

```python
origin_secret = event["headers"].get("x-origin-verify", "")
if origin_secret != os.environ["ORIGIN_SECRET"]:
    return {"statusCode": 403, "body": "Forbidden"}
```

Same random string in two Terraform blocks. Generate it once, deploy, done.

### Layer 2: API Keys (protects the bot)

Each bot has its own API keys stored in the `BotFactoryApiKeys` DynamoDB table. Keys are scoped — a key generated for `guitar` can't access `the-fret-detective`.

```bash
make gen-key bot={bot_id} name=dev-local    # create
make list-keys                               # view all
make revoke-key key=bf_live_...              # revoke
```

Keys are sent via `Authorization: Bearer bf_live_...` header.

### When to use which

For a **public-facing bot** (like thefretdetective.com), origin verification alone is enough. Users don't need API keys — the site itself is the trusted caller. The origin header proves the request came through your CloudFront, and HTTPS encrypts everything in transit.

For **direct API access** (third-party integrations, testing, CI), use API keys. These let you grant and revoke access per bot without touching infrastructure.

Both layers together: the origin header proves *where* the request came from, the API key proves *who* is making it.
