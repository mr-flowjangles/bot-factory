# Self-Healing Knowledge Base

> **Phase 1 Shipped** — 2026-03-18

## Overview

When a bot can't answer a question (low RAG confidence), it automatically generates new knowledge, embeds it, and backfills the knowledge base — so the next user gets an instant answer. No manual data entry required.

## Flow

```
User asks question
        |
        v
  RAG Retrieval
        |
        v
  Confidence check ──── HIGH ──── Respond normally (no change)
        |
       LOW (top_score < confidence_threshold)
        |
        v
  Respond immediately with low-confidence context
        |
        v
  ┌──────────────────────────────────────────────────┐
  │  ASYNC LAMBDA (non-blocking)                     │
  │                                                  │
  │  1. Short message filter                         │
  │     Skip if < 10 chars (greetings, "hi", etc.)   │
  │         |                                        │
  │  2. Boundary + coherence check (LLM)             │
  │     "Is this a clear, in-domain question?"       │
  │     Rejects: gibberish, incomplete, off-topic    │
  │         |                                        │
  │     NO ──> Log & discard                         │
  │         |                                        │
  │        YES                                       │
  │         |                                        │
  │  3. Duplicate check                              │
  │     Embed question → compare vs existing         │
  │     If similarity > 0.7 → skip (already have it) │
  │         |                                        │
  │  4. S3 key check                                 │
  │     If self-heal-{slug}.yml exists → skip        │
  │         |                                        │
  │  5. Generate YML data file (LLM)                 │
  │     Claude produces: id, category, heading,      │
  │     search_terms, content — matching existing     │
  │     data file format                             │
  │         |                                        │
  │  6. Validate content (second LLM call)           │
  │     Fact-check for accuracy and completeness     │
  │         |                                        │
  │     FAIL ──> Log & discard                       │
  │         |                                        │
  │     PASS                                         │
  │         |                                        │
  │  7. Upload YML to S3                             │
  │     bots/{bot_id}/data/self-heal-{slug}.yml      │
  │         |                                        │
  │  8. Generate embedding + store in DynamoDB       │
  │     Additive (no kill-and-fill)                  │
  │         |                                        │
  │  9. Invalidate in-memory embedding cache         │
  │         |                                        │
  │  10. Send notification email (SES)               │
  │         |                                        │
  │  11. Store result for piggyback notification     │
  └──────────────────────────────────────────────────┘
        |
        v
  Next /chat request:
  "I just learned about {topic}! Try asking me again."
        |
        v
  Future users get instant answers from RAG
```

## Config

Any bot opts in via `config.yml`:

```yaml
bot:
  agentic:
    self_heal: true              # enable self-healing knowledge base
    boundary_check: true         # LLM gate — rejects off-topic, gibberish, incomplete
    confidence_threshold: 0.5    # RAG score below this triggers background job
    notify_email: "you@example.com"
```

Bots without `self_heal: true` behave exactly as they do today.

## Notification Strategy

**Phase 1 (shipped):** Piggyback on next message.
- Self-heal stores result in `_pending_results` dict keyed by bot_id
- On next `/chat` request, check for pending results
- Emit SSE event: `{"type": "self_heal", "message": "I just learned about {topic}!"}`

**Phase 2 (future):** Keep SSE connection open with timeout for real-time push.

## Duplicate Prevention

Four layers prevent redundant content:
1. **Short message filter** — messages under 10 chars skipped
2. **Boundary + coherence check** — LLM rejects gibberish, greetings, off-topic
3. **Embedding similarity** — if top score > 0.7 against existing embeddings, the knowledge exists (retrieval quality issue, not missing data)
4. **S3 key check** — slug-based filename means the same topic won't regenerate

## Implementation Components

| Component | Location | Description |
|-----------|----------|-------------|
| Confidence check | `factory/core/chatbot.py` | `metadata_out["top_score"]` from `generate_response_stream()` |
| Self-heal orchestrator | `factory/core/self_heal.py` | Full pipeline: filter → boundary → duplicate → generate → validate → embed → notify |
| LLM prompts | `factory/core/self_heal_prompts.py` | Boundary check, YML generation, validation |
| SES notifier | `factory/core/ses_notifier.py` | Email via SES (logs in local dev) |
| Single-entry embedding | `factory/core/generate_embeddings.py` | `embed_and_store_single()` — additive, no kill-and-fill |
| Cache invalidation | `factory/core/retrieval.py` | `invalidate_bot_cache()` |
| Self-heal Lambda | `factory/core/self_heal.py` | `lambda_handler()` — dedicated async Lambda in production |
| Async invoker | `factory/core/self_heal.py` | `invoke_self_heal_async()` — threads locally, async Lambda in prod |
| Dev server trigger | `dev_server.py` | Invokes self-heal before `[DONE]` via `invoke_self_heal_async()` |
| Prod streaming trigger | `dev_server.py` (via Lambda Web Adapter) | Same code path — Flask runs in Lambda |
| Terraform | `terraform/lambdas.tf` | `bot-factory-self-heal` Lambda (300s timeout, 512MB) |

## What This Solves

**Before:**
1. User asks about "sweep picking"
2. Bot: "I don't have that"
3. Developer manually writes data file, embeds, deploys
4. Days/weeks later, the answer exists

**After:**
1. User asks about "sweep picking"
2. Bot responds with what it can (low-confidence context)
3. Background: LLM generates YML → validates → embeds → stores (seconds)
4. Same session or next user: full answer from knowledge base

## Production Architecture

In production, self-heal runs as a **separate Lambda** (`bot-factory-self-heal`) invoked
asynchronously (`InvocationType=Event`) by the streaming Lambda. This solves a critical
issue: Lambda freezes/kills the container after the response stream closes, which killed
background threads before they could complete.

```
Streaming Lambda (bot-factory-stream)
  → Flask via Lambda Web Adapter
    → Stream tokens to user
    → invoke_self_heal_async() fires before [DONE]
      → boto3 lambda.invoke(InvocationType="Event") — returns 202 immediately
    → yield [DONE], close stream

Self-Heal Lambda (bot-factory-self-heal)  ← async, fire-and-forget
  → lambda_handler() receives {bot_id, question, config}
  → run_self_heal() — full pipeline (boundary → generate → validate → embed)
  → 300s timeout, 512MB — plenty of room for LLM calls
```

**Locally**, `invoke_self_heal_async()` falls back to a daemon thread since there's no
Lambda container lifecycle to worry about.

The boto3 Lambda client is cached at module level (`_get_lambda_client()`) to avoid
cold-start overhead on every invoke — keeps the delay before `[DONE]` under 500ms.

## Future (v2.1+)

- Real-time SSE push notification (keep connection open with timeout)
- Web search integration for factual content augmentation
- Gap analytics dashboard (what are users asking that bots can't answer?)
- Content review UI for approving/rejecting auto-generated entries
- Content versioning and audit trail
