# Cost Optimization TODO

| Opportunity | Impact | Status |
|---|---|---|
| **Conversation history cap** — limit to last N turns instead of unbounded history growing every request | High | Done — server-side cap of 6 messages in build_messages() |
| **Model tiering** — Haiku for simple questions, Sonnet for complex ones | High | Not started |
| **Prompt caching strategy** — make cachePoint conditional on traffic, or extend cached prefix | Medium | In place (system prompt only) |
| **RAG context trimming** — fewer/shorter chunks for high-confidence matches | Medium | Not started |
| **System prompt trimming** — prompt is ~100 lines, could be tighter | Low | Not started |
