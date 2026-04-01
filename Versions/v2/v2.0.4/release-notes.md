# v2.0.4 — Knowledge Base Manifest (2026-03-19)

Self-heal now uses an LLM-read knowledge manifest instead of cosine similarity to
detect duplicate topics, eliminating the ~135 duplicate files caused by retrieval
misses in v2.0.2.

## Problem

Self-heal decided whether to generate new content by checking embedding similarity
(cosine score). A low score didn't necessarily mean the knowledge was missing — it
could mean retrieval failed (bad search terms, abbreviation mismatch, etc). This
caused duplicate content generation for topics the bot already knew about.

## Solution

Generate a **knowledge manifest** — a YAML table of contents listing every entry's
id, heading, and search_terms grouped by category. The self-heal agent reads the
manifest via an LLM call before deciding to generate. An LLM reading a topic list
reasons about semantic overlap far better than cosine similarity.

## New

- `scripts/generate_manifest.py` — Generates a manifest from all bot data files
  and uploads to `s3://bucket/bots/{bot_id}/manifest.yml`
- `MANIFEST_CHECK_PROMPT` in `self_heal_prompts.py` — Prompt for LLM to determine
  if a question is already covered by existing knowledge
- `make manifest bot={bot_id}` / `make manifest-prod bot={bot_id}` — Standalone targets
- Manifest auto-generates after `make embed`, `make embed-prod`, and `make deploy-bot-prod`

## Changed

- `factory/core/self_heal.py` — Step 2 of pipeline changed from `_duplicate_check`
  (cosine similarity) to `_manifest_check` (LLM reads manifest TOC)
- Backward compatible: falls back to cosine duplicate check if no manifest exists
- Pipeline now has 4 LLM calls: boundary → manifest → generate → validate

## Files Changed

| File | Change |
|------|--------|
| `scripts/generate_manifest.py` | **New** — manifest generation script |
| `factory/core/self_heal.py` | Add `_load_manifest`, `_manifest_check`; replace `_duplicate_check` in pipeline |
| `factory/core/self_heal_prompts.py` | Add `MANIFEST_CHECK_PROMPT` |
| `Makefile` | Add `manifest`/`manifest-prod`; hook into embed + deploy targets |
| `CLAUDE.md` | Add v2.0.4 to versions, add manifest design pattern |
