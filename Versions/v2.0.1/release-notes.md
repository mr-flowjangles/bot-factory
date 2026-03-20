# v2.0.1 — Production Self-Heal + Chat UX (2026-03-18)

Fixes self-heal in production and polishes the chat experience.

## Problem

V2.0.0 shipped self-heal with background threads. Two production issues surfaced:

1. **Lambda kills background threads** — Lambda freezes the container after the response
   stream closes. Any background thread spawned during the request dies before completing
   the self-heal pipeline. The bot would say "I'm logging it" but never actually learn.

2. **Response felt slow** — The initial fix (inline `invoke_self_heal_async()` after
   `[DONE]`) blocked the response stream closure while creating a boto3 client and making
   the Lambda invoke call. Users saw a ~20s delay after the last token.

3. **Chat UX jank** — Typing indicator appeared as an orphan bubble, then disappeared,
   then the bot header appeared, then tokens streamed in. Three visual state changes
   instead of a smooth transition.

## Solution

### Async Self-Heal Lambda

Created a dedicated `bot-factory-self-heal` Lambda invoked via `InvocationType="Event"`
(fire-and-forget, returns 202 immediately).

- **Handler:** `factory.core.self_heal.lambda_handler`
- **Timeout:** 300s (plenty for 3 LLM calls + embedding + S3 upload)
- **Memory:** 512MB
- **IAM:** `lambda:InvokeFunction` on `bot-factory-self-heal` + `ses:SendEmail`

The invoke fires **before** `[DONE]` is yielded — all tokens are already streamed so
the user has the full answer. Lambda can't freeze the container before the invoke happens.

### Cached boto3 Client

Module-level `_get_lambda_client()` caches the boto3 Lambda client. First call creates
it (~500ms), subsequent calls reuse it (<10ms). Keeps the delay before `[DONE]`
imperceptible.

### Local Dev Fallback

`invoke_self_heal_async()` detects `APP_ENV` and uses a daemon thread locally (no Lambda
container lifecycle to worry about).

### Chat UX

Bot label and typing indicator now render as a single unit from the start. When tokens
arrive, the typing dots are removed and tokens stream into the same div. One smooth
transition instead of three visual jumps.

## Fixed
- Self-heal now runs as a dedicated async Lambda instead of background threads
- Self-heal invocation moved before `[DONE]` marker
- Cached boto3 Lambda client eliminates cold-start overhead
- SES sender address updated to verified email
- Chat client endpoint fixed: `/chat/stream` → `/chat`

## Improved
- Chat UX: bot label and typing dots appear together as one unit

## Infrastructure
- New Lambda: `bot-factory-self-heal` (300s timeout, 512MB)
- IAM: `lambda:InvokeFunction` for self-heal Lambda + `ses:SendEmail`
- Streaming Lambda gets `SELF_HEAL_FUNCTION_NAME` env var

## Files Changed

| File | Change |
|------|--------|
| `factory/core/self_heal.py` | Added `lambda_handler()`, `invoke_self_heal_async()`, `_get_lambda_client()` |
| `dev_server.py` | Uses `invoke_self_heal_async()`, fires before `[DONE]` |
| `factory/streaming_handler.py` | Same pattern |
| `factory/core/ses_notifier.py` | SES sender updated to verified address |
| `terraform/lambdas.tf` | New `bot-factory-self-heal` Lambda + `SELF_HEAL_FUNCTION_NAME` env var |
| `terraform/main.tf` | IAM: `lambda:InvokeFunction` + `ses:SendEmail` permissions |
| `app/bot_scripts/chat.js` | Bot label + typing dots appear together; `/chat/stream` → `/chat` |

## Verification

| Question | Boundary | Duplicate | Result |
|----------|----------|-----------|--------|
| "how do guitar pots work" | OUT (gear) | — | Rejected correctly |
| "6 vs 7 string guitar" | IN | No | New knowledge generated + embedded |
| "6 vs 7 string guitar" (2nd) | IN | Yes | Skipped (duplicate detected) |
| "A blues scale" | IN | No | Generated but failed validation — skipped |
| "jumbo frets" | IN | No | New knowledge generated + embedded |
