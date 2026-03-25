# v2.0.6 — Performance Tuning (2026-03-24)

## Problem

After v2.0.4 deployment, The Fret Detective response times jumped to ~7s (from ~3s). Two causes:
1. Bedrock prompt caching on conversation history added write overhead every turn with zero read hits
2. DynamoDB embedding scan (164 items with 1024-dim vectors) taking 1.7s per request, worsened by self-heal growing the KB

## Solution

- Cache embeddings in Lambda memory for container lifetime — eliminates 1.7s DynamoDB round-trip on warm requests
- System prompt cachePoint restored (stable prefix, gets read hits in a session)
- Conversation history cachePoint removed (changes every turn, write-only overhead)
- Added observability: print(flush=True) timing breakdowns visible in CloudWatch through Lambda Web Adapter

## New

- Embedding cache (`_embeddings_cache` in retrieval.py)
- Retrieval timing breakdown in CloudWatch: embed / dynamo / cosine
- Streaming timing breakdown in CloudWatch: retrieval / prompt / bedrock
- Performance baseline documented in CLAUDE.md (~3s target)

## Changed

- `get_embeddings()` — caches results per bot_id for Lambda container lifetime
- System prompt cachePoint restored on `converse` and `converse_stream`
- Root logger set to INFO in dev_server.py

## Fixed

- ~7s response times reduced to ~1.5s on warm Lambda

## Files Changed

| File | Change |
|------|--------|
| factory/core/retrieval.py | Embedding cache + granular timing |
| factory/core/chatbot.py | Streaming timing + system prompt cachePoint restored |
| dev_server.py | Root logger set to INFO |
| CLAUDE.md | Updated caching docs + performance baseline |
