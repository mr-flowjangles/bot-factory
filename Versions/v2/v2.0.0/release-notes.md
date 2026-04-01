# v2.0.0 — Self-Healing Knowledge Base (2026-03-18)

The bot goes from static to self-improving. When a bot can't answer a question,
it now detects the gap and autonomously generates new knowledge — no manual
data entry required.

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
  │     If similarity >= confidence_threshold → skip │
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
  │  9. Send notification email (SES)                │
  │         |                                        │
  │  10. Store result for piggyback notification     │
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

## Duplicate Prevention

Four layers prevent redundant content:
1. **Short message filter** — messages under 10 chars skipped
2. **Boundary + coherence check** — LLM rejects gibberish, greetings, off-topic
3. **Embedding similarity** — if top score >= confidence_threshold against existing embeddings, the knowledge exists
4. **S3 key check** — slug-based filename means the same topic won't regenerate

## Notification Strategy

**Phase 1 (shipped):** Piggyback on next message.
- Self-heal stores result in `_pending_results` dict keyed by bot_id
- On next `/chat` request, check for pending results
- Emit SSE event: `{"type": "self_heal", "message": "I just learned about {topic}!"}`

**Phase 2 (future):** Keep SSE connection open with timeout for real-time push.

## New
- Self-healing knowledge base pipeline (factory/core/self_heal.py)
- Bot config: `bot.agentic` block (self_heal, boundary_check, confidence_threshold, notify_email)
- `embed_and_store_single()` in generate_embeddings.py for additive writes
- `metadata_out` parameter on `generate_response_stream()` exposing RAG confidence scores

## Changed
- dev_server.py — spawns background self-heal thread on low-confidence responses
- streaming_handler.py — same self-heal trigger for production Lambda

## Files Changed

| Component | Location |
|-----------|----------|
| Confidence check | `factory/core/chatbot.py` |
| Self-heal orchestrator | `factory/core/self_heal.py` |
| LLM prompts | `factory/core/self_heal_prompts.py` |
| SES notifier | `factory/core/ses_notifier.py` |
| Single-entry embedding | `factory/core/generate_embeddings.py` |
| Self-heal Lambda | `factory/core/self_heal.py` |
| Dev server trigger | `dev_server.py` |
| Terraform | `terraform/lambdas.tf` |
