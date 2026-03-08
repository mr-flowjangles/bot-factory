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
3. Creates DynamoDB tables in LocalStack (`BotFactoryRAG`, `BotFactoryHistory`, `BotFactoryLogs`)
4. Creates the S3 bucket and uploads all bots from `scripts/bots/` to LocalStack S3
5. Starts the Chalice local API server on :8000

Frontend: `http://localhost:8080`
API: `http://localhost:8000`

---

## Generating Embeddings

```bash
# 1. Make sure your stack is running
make up

# 2. If you changed data files, sync them to LocalStack S3 first
make load-bot bot={bot_id}

# 3. Generate embeddings (reads LocalStack S3, writes LocalStack DynamoDB)
python3 -m factory.core.generate_embeddings {bot_id}

# Or skip the confirmation prompt
python3 -m factory.core.generate_embeddings {bot_id} --force

# Or use the Makefile shortcut
make embed bot={bot_id}
```

Replace `{bot_id}` with `guitar` or whatever bot you're working on.

> **Note:** Bedrock always hits real AWS — LocalStack does not emulate Bedrock. You need real AWS credentials available in your shell environment when running the embeddings command.

---

## Testing the Chatbot Locally

```bash
# Send a test message via the Makefile (calls lambda_handler directly)
make test-chat BOT=guitar MSG="What is standard tuning?"

# Or hit the Chalice API directly
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"bot_id": "guitar", "message": "What is standard tuning?"}'

# Test the streaming endpoint via dev_server.py
python3 dev_server.py
curl -X POST http://localhost:8001/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"bot_id": "guitar", "message": "What is standard tuning?"}'
```

Or open the browser at `http://localhost:8080/{bot_id}.html` and chat directly.

> **Note on streaming locally:** Chalice's local server (port 8000) buffers the full response before sending — you won't see token-by-token streaming. For real SSE streaming during local dev, run `python3 dev_server.py` (Flask, port 8001 by default). Real streaming only works end-to-end via the Lambda Function URL in production.

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

For the Chalice server, credentials are passed through from the host environment automatically.

---

## Useful Commands

```bash
make help            # Full command reference
make ps              # Show Docker container status
make logs            # Tail all container logs
make dynamo-count    # Count embeddings in BotFactoryRAG
make dynamo-scan-bot bot=guitar   # Inspect stored embeddings for a bot
make s3-ls-bot bot=guitar         # List files in S3 for a bot
```
