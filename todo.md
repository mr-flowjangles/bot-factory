# Bot Factory Roadmap

## v2.2.0 — PDF Ingestion (next)

| Item | Impact | Status |
|---|---|---|
| **PDF to knowledge base** — scrape PDF, Claude analyzes content, generates structured YAML (category, heading, search_terms, text) ready for embedding | High | Not started |

## v3.0.0 — Production Ready (Demo Version)

| Item | Impact | Status |
|---|---|---|
| **Analytics dashboard** — chat volume by day, unique visitors by IP, top questions, source hit rates | High | Not started |
| **Triad retrieval fix** — 48 near-identical embeddings crowd each other out; wrong key/type ranks higher | High | Not started — options: keyword pre-filter, boost key name in embedding text, increase top_k |
| **Multi-query retrieval** — decompose complex questions into sub-queries, retrieve for each, merge context | High | Not started — enables "triads for a 12-bar blues in G" style questions |
| **Migrate to Pinecone serverless** — replace DynamoDB+cosine with real vector DB; metadata filtering, native similarity search (free tier covers our scale) | High | Research done — go |
| **Model tiering** — Haiku for simple questions, Sonnet for complex ones | High | Not started |
| **Search term auto-enrichment** — bot reads coverage results and proposes search_terms additions | Medium | Not started — depends on manual enrichment validation |

## v3.1.0 — Recommendation Agent

| Item | Impact | Status |
|---|---|---|
| **Topic recommendation agent** — after a response, suggest related topics the user might want to explore (e.g., asked about G chord → suggest G major scale, modes in G) | High | Not started — platform-level feature driven by knowledge category relationships in bot config |

## Backlog

| Item | Impact | Status |
|---|---|---|
| **Prompt caching strategy** — make cachePoint conditional on traffic, or extend cached prefix | Medium | In place (system prompt only) |
| **RAG context trimming** — fewer/shorter chunks for high-confidence matches | Medium | Not started |
| **System prompt trimming** — prompt is ~100 lines, could be tighter | Low | Not started |
| **Real-time self-heal push** — hold SSE connection open after [DONE], push self-heal result to user | Medium | Not started |
| **Self-heal notification in chat** — show user when new knowledge is generated from their question | Medium | Blocked by real-time self-heal push |
