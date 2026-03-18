# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bot Factory is a serverless RAG chatbot platform on AWS. Deploy a bot by providing a config + knowledge data files — the platform handles embedding generation, retrieval, and Claude-powered responses via AWS Bedrock.

## Common Commands

```bash
# Local development
make up                          # Start Docker (LocalStack + nginx) + init S3/DynamoDB + Flask dev server
make down                        # Stop everything
make local                       # Start Flask SSE dev server (port 8001)
make init                        # Re-init S3 + DynamoDB after a bounce

# Code quality
make lint                        # flake8 (max-line-length=120)
make format                      # black (line-length=120)
make format-check                # Check formatting without applying

# Testing (manual — no automated test suite)
make test-chat BOT={bot_id} MSG="your question"   # Invoke lambda_handler directly

# Bot data management
make load-bot bot={bot_id}       # Sync bot data/ to LocalStack S3
make deploy-bot bot={bot_id}     # Upload config.yml + prompt.yml to LocalStack S3
make embed bot={bot_id}          # Generate embeddings (uses real Bedrock, local DynamoDB)

# Production deployment
make deploy-infra                # Terraform + Lambda packaging
make deploy-streaming            # Streaming Lambda + Function URL
make deploy-bot-prod bot={bot_id}  # Upload bot data + generate prod embeddings
make scaffold bot={bot_id}       # Create new bot skeleton
```

## Architecture

```
Browser → nginx (localhost:8080)
                ↓
       ┌────────┴────────┐
       │ Buffered         │ Streaming
       │ lambda_handler   │ streaming_handler / dev_server.py (Flask SSE)
       └────────┬────────┘
                ↓
         factory/core/chatbot.py  ← orchestrator
                ↓
    ┌───────────┼───────────┐
    │           │           │
 retrieval.py  │     bot_utils.py (config, prompt, logging)
 (embed query  │
  → cosine     │
  similarity)  │
    ↓          ↓
 DynamoDB    Bedrock Claude (response generation)
 (embeddings)
```

**Key data flow:** User message → Titan V2 embedding → cosine similarity against DynamoDB embeddings → top_k chunks → Claude generates response with retrieved context.

**Two Lambda handlers:**
- `factory/lambda_handler.py` — Buffered responses via API Gateway
- `factory/streaming_handler.py` — SSE streaming via Lambda Function URL

**Local dev uses:**
- LocalStack (port 4566) for S3 and DynamoDB
- Real AWS Bedrock (LocalStack doesn't emulate it)
- Flask `dev_server.py` (port 8001) for local streaming
- nginx (port 8080) for serving static frontend

## Bot Structure

Each bot lives in `scripts/bots/{bot_id}/` with three components:
- `config.yml` — All bot settings (model, RAG params, personality, frontend config)
- `prompt.yml` — System prompt template (supports `{current_date}` placeholder)
- `data/*.yml` — Knowledge base files (text or structured format with optional `search_terms`)

## Code Style

- Python 3.12
- Line length: 120 (both flake8 and black)
- No automated test suite — testing is manual via `make test-chat` or browser

## Key Design Patterns

- **Per-bot in-memory caching:** Embeddings, configs, and prompts cached per bot_id in Lambda warm starts
- **Kill-and-fill embeddings:** Regeneration deletes only the target bot's embeddings, leaving others untouched
- **Environment abstraction:** `APP_ENV` env var switches between LocalStack endpoints (local) and real AWS (production)
- **Multi-bot single deployment:** All bots share the same Lambda/infra; bot_id scopes everything (S3 paths, DynamoDB queries, caches)
- **Context-aware RAG retrieval:** Follow-up queries are enriched with the last exchange (user + assistant) so vague references like "around there" resolve correctly via `_build_enriched_query()` in `chatbot.py`
- **Conversation history:** The client sends `conversation_history` in each request; both handlers pass it through to Claude for multi-turn awareness

## Enhancements

Enhancement docs live in `Docs/Enhancements/{version}/` (date-prefixed):
- **V2.0.0 — Self-Healing Knowledge Base** (`V2.0.0/2026-03-18-self-healing-knowledge-base.md`) — When a bot can't answer a question (low RAG confidence), a background thread generates a YML data file via LLM, validates it, embeds it, and backfills the knowledge base. Config-driven (`bot.agentic.self_heal`). Phase 1 shipped.

## Production Deployment Notes

- The streaming Lambda runs Flask `dev_server.py` via Lambda Web Adapter (not `streaming_handler.py` directly)
- Deploy Lambda code: `make deploy-streaming` (may need `-auto-approve` for non-interactive terraform)
- After deploying bot data + re-embedding, force a Lambda cold start to clear the in-memory embedding cache
- To force a cold start: `aws lambda update-function-configuration --function-name bot-factory-stream --region us-east-1 --description "cache-bust-$(date +%s)"`
