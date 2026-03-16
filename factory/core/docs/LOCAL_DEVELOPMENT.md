# Local Development Guide

How to generate embeddings and test the chatbot from your local machine.

---

## Starting the Stack

```bash
make up
```

This does everything in order:
1. Starts Docker Compose (nginx on :8080, LocalStack on :4566)
2. Waits for LocalStack to be ready
3. Creates DynamoDB tables in LocalStack (`BotFactoryRAG`, `BotFactoryHistory`, `BotFactoryLogs`, `BotFactoryApiKeys`)
4. Creates the S3 bucket and uploads all bots from `scripts/bots/` to LocalStack S3
5. Starts the Flask dev server on :8001

Frontend: `http://localhost:8080`
API: `http://localhost:8001`

---

## Generating Embeddings

```bash
# 1. Make sure your stack is running
make up

# 2. If you changed data files, sync them to LocalStack S3 first
make load-bot bot={bot_id}

# 3. Generate embeddings (reads LocalStack S3, writes LocalStack DynamoDB)
make embed bot={bot_id}
```

Replace `{bot_id}` with `RobbAI`, `the-fret-detective`, or whatever bot you're working on.

> **Note:** Bedrock always hits real AWS — LocalStack does not emulate Bedrock. You need real AWS credentials available in your shell environment when running the embeddings command.

---

## Testing the Chatbot Locally

```bash
# Send a test message via the Makefile (calls lambda_handler directly)
make test-chat BOT=RobbAI MSG="What does Rob do?"

# Or hit the Flask dev server streaming endpoint
curl -N -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key_here" \
  -d '{"bot_id": "RobbAI", "message": "What does Rob do?"}'
```

Or open the browser at `http://localhost:8080` and chat through the UI.

> **Note on streaming:** The Flask dev server (`dev_server.py`, port 8001) supports real SSE streaming locally. In production, streaming works via the Lambda Function URL.

---

## Adding or Changing Bot Data

```bash
# 1. Edit YAML files in scripts/bots/{bot_id}/data/

# 2. Sync data to LocalStack S3
make load-bot bot={bot_id}

# 3. Regenerate embeddings
make embed bot={bot_id}
```

The S3 sync in step 2 is required any time you change your YAML data files — the chunker reads from LocalStack S3, not your local filesystem.

---

## Troubleshooting Bedrock Credentials

If Bedrock calls are failing, the most common cause is AWS credentials not being available.

The embeddings command and `make test-chat` run directly on your host machine, so they use your host shell's AWS credentials. Make sure `~/.aws/credentials` is configured or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are exported in your shell.

Note: The `.env` file has `AWS_ACCESS_KEY_ID=test` for LocalStack. Production commands in the Makefile clear these so your AWS profile is used instead.

---

## Useful Commands

```bash
make help            # Full command reference
make ps              # Show Docker container status
make logs            # Tail all container logs
make dynamo-count    # Count embeddings in BotFactoryRAG
make dynamo-scan-bot bot=RobbAI      # Inspect stored embeddings for a bot
make s3-ls-bot bot=RobbAI            # List files in S3 for a bot
```
