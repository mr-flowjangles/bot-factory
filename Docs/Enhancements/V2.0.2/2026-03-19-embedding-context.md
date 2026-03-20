# V2.0.2 — Embedding Context + Search Term Enrichment

> **Shipped** — 2026-03-19

## Problem

The Fret Detective bot had poor retrieval scores for domain-specific queries. Root causes:

1. **Embedding model misinterprets domain abbreviations** — Titan V2 reads "Am" as the
   English verb "am" rather than the guitar chord "A minor." Similarly, "EADGBE" is
   meaningless to the model. This caused cosine similarity to tank for the most common
   chord queries.

2. **Self-heal duplicates** — Low retrieval scores (0.4–0.6) triggered self-heal for
   queries that already had knowledge base entries, creating ~135 duplicate files on prod
   that diluted retrieval for other queries.

3. **Embedding cache masked stale content** — V2.0.1 cached embeddings per-bot for the
   Lambda lifetime. Self-healed content wasn't available until the next cold start.

## Solution

### Embedding Context (generic, config-driven)

New `embedding_context` field under `bot.rag` in config.yml. A domain preamble that gets
prepended to:

- **Every document chunk** at embed time (in `chunker.py`)
- **Every user query** at retrieval time (in `retrieval.py`)

This ensures both sides of the cosine similarity calculation share the same domain context,
so the embedding model correctly interprets abbreviations and jargon.

The feature is generic — any bot can define its own `embedding_context` with no code changes.

```yaml
# Example: the-fret-detective/config.yml
rag:
  embedding_context: "Guitar knowledge base. Common abbreviations: Am = A minor chord..."
```

### Remove Embedding Cache

Embeddings are now queried fresh from DynamoDB on every request via the bot_id GSI.
Self-healed content is immediately available without waiting for a cold start.

### Search Term Enrichment

Added `search_terms` to 30+ entries across 13 data files to improve retrieval for
colloquial phrasings (e.g., "best pick for beginner" matching `gear_picks`).

### Self-Heal Duplicate Cleanup

Deleted 119 duplicate self-heal files from prod S3, kept 16 with genuinely new content.
Re-embedded prod from 260 down to 164 chunks.

## Results

Coverage test (294 queries):

| Metric | Before | After |
|--------|--------|-------|
| Pass rate | ~85% | 99.3% (292/294) |
| Minimum score | 0.32 | 0.745 |
| Topics below 0.6 | 16 | 0 |
| Self-heal triggers | Frequent | None (all scores > 0.6 threshold) |

The 2 remaining FAILs are false positives — high retrieval scores (>0.9) but the response
doesn't use the retrieved context. This is a prompt issue, not retrieval.

## Files Changed

| File | Change |
|------|--------|
| `factory/core/chunker.py` | Added `load_embedding_context()`, prepend context to chunks |
| `factory/core/retrieval.py` | Added `_load_embedding_context()`, prepend context to queries, removed embedding cache |
| `scripts/bots/the-fret-detective/config.yml` | Added `embedding_context` glossary |
| `scripts/bots/the-fret-detective/data/*.yml` | Enriched `search_terms` on 30+ entries across 13 files |
| `scripts/test_knowledge_coverage.py` | New coverage test script (294 queries) |
| `Makefile` | Added `test-coverage` and `test-coverage-local` targets |
