# v2.0.3 — Prompt Tuning for Retrieval Utilization (2026-03-19)

Coverage testing revealed the bot was saying "I don't have that" even when relevant
context was retrieved — the prompt was too strict about exact-match answering.

### Fixed
- System prompt and RAG instructions updated to reason about retrieved context
  rather than requiring exact wording matches
- Bot no longer rejects questions when relevant context is present but phrased
  differently (e.g., "where can I anchor to solo in D" now uses triad position data)

### Changed
- `factory/core/chatbot.py` — RAG instruction: "use context even if wording doesn't
  exactly match" replaces strict "if you can't answer, say so"
- `scripts/bots/the-fret-detective/prompt.yml` — prompt rules updated to encourage
  reasoning about context instead of pattern-matching exact wording
- `Makefile` — `test-coverage-local` renamed to `test-coverage-prod`
- `scripts/test_knowledge_coverage.py` — test script refactored
- Self-heal diagram updated for V2.0.2 accuracy (removed cache busting, fixed
  duplicate check threshold)
