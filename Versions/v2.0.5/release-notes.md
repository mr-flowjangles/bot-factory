# v2.0.5 — Tuning Update (2026-03-24)

## Problem

v2.0.4 added a conversation history `cachePoint` that caused Bedrock cache writes on every turn with zero read hits — history changes each turn so the cache is never reused. This added latency to every request.

Additionally, `log_chat_interaction` and `log_visit` existed in `bot_utils.py` but were never called — the BotFactoryLogs table stayed empty.

## Solution

- Removed the conversation history `cachePoint`, keeping only the system prompt one
- Wired up chat and visit logging in `dev_server.py`

## New

- `/visit` POST endpoint in `dev_server.py` — logs site visits to BotFactoryLogs
- Chat interactions logged after stream completes (question, response, sources)

## Changed

- `build_messages()` no longer appends a `cachePoint` to conversation history
- Docstring updated to reflect removal

## Fixed

- Streaming latency regression from v2.0.4 conversation history cachePoint

## Files Changed

| File | Change |
|------|--------|
| factory/core/chatbot.py | Remove conversation history cachePoint |
| dev_server.py | Wire up `log_chat_interaction` + add `/visit` endpoint |
| factory/core/bot_utils.py | Add `log_visit` function |
| CLAUDE.md | Update caching docs |
