# v2.3.0 — Security Hardening for Public Embed (2026-05-14)

## Problem

Bot Factory's chat keys (`bfk_...`) live in client-side JavaScript — anyone viewing source on a site that embeds a bot can copy the key. The platform was designed to be embeddable (like Stripe's `pk_` keys), but the protection layer that makes that design safe wasn't actually in place:

- The `X-API-Key` header was the only check. A stolen key worked from any origin, with no rate limit and no spend cap.
- A leaked key could be used to drive arbitrary Bedrock costs from any browser or script in the world.

## Solution

Treat `bfk_` keys as **publishable identifiers**, not secrets, and enforce three checks hard server-side: bot scoping (already in place), origin allowlist (new), and per-IP rate limiting (new). Backstop the whole thing with an AWS Budgets alarm on Bedrock spend.

## New

- **Origin allowlist** — every key now carries `allowed_origins`. Requests whose `Origin` header isn't in the list are rejected. Keys with no `allowed_origins` are rejected (no permissive fallback).
- **Per-(key, IP) rate limit** — new `BotFactoryRateLimit` DynamoDB table with TTL-based sliding windows. Each key declares `rate_limit_per_hour` (default 30). Fail-open if the table is unavailable so rate-limit outages can't take chat down.
- **`X-Publishable-Key` header** — preferred header name, signals the key is safe to expose. `X-API-Key` still accepted indefinitely for legacy clients.
- **Bedrock budget alarm** — `aws_budgets_budget` on Amazon Bedrock spend with email notifications at 80% / 100% actual and 100% forecasted. Caps configurable via `bedrock_monthly_budget_usd` (default $20). Requires a new `budget_notification_email` tfvar.
- **Migration script** — `scripts/migrate_keys_v2_3_0.py` backfills `allowed_origins` and `rate_limit_per_hour` on existing keys. Safe to run before deploying v2.3.0 code (old code ignores the new fields).

## Changed

- **`factory/core/auth.py`** — `validate_api_key(key, bot_id) -> bool` replaced with `authorize_request(key, bot_id, origin) -> (allowed, reason, record)` and `lookup_api_key(key) -> record | None`. The in-memory cache now stores the full record (origins, rate limit) instead of just the bot_id.
- **`factory/streaming_handler.py` and `dev_server.py`** — both accept `X-Publishable-Key` (preferred) and `X-API-Key` (legacy). Both now check Origin and rate limit before invoking the model.
- **`scripts/gen_api_key.py`** — `--allowed-origins` is now required (comma-separated list). `--rate-limit` accepted (default 30/hr).
- **Docs** — `CHAT_FLOW.md` and `LOCAL_DEVELOPMENT.md` updated to document the publishable-key model and new headers/origin requirement.

## Fixed

- Closed the API-key-leak abuse path on the streaming Lambda Function URL.

## Files Changed

| File | Change |
|------|--------|
| `factory/core/auth.py` | Replaced `validate_api_key` with `lookup_api_key` + `authorize_request`; hard-enforced origin allowlist; cache holds full record |
| `factory/core/rate_limit.py` | **New** — DynamoDB-backed per-(key, IP) rate limiter with TTL-based windows |
| `factory/streaming_handler.py` | Origin + rate-limit checks; accepts both headers |
| `dev_server.py` | Origin + rate-limit checks; accepts both headers |
| `terraform/main.tf` | New `BotFactoryRateLimit` table with TTL; IAM updated to include it |
| `terraform/lambdas.tf` | `RATE_LIMIT_TABLE_NAME` env var on api + streaming Lambdas |
| `terraform/variables.tf` | `dynamo_rate_limit_table_name`, `budget_notification_email`, `bedrock_monthly_budget_usd` |
| `terraform/budgets.tf` | **New** — `aws_budgets_budget` on Amazon Bedrock with 80% / 100% / forecast notifications |
| `scripts/gen_api_key.py` | `--allowed-origins` required, `--rate-limit` optional; writes new fields |
| `scripts/migrate_keys_v2_3_0.py` | **New** — backfill existing keys before deploy |
| `scripts/init-dynamodb.sh` | Creates `BotFactoryRateLimit` table for local dev, enables TTL |
| `app/bot_scripts/chat.js` | `publishableKey` config field (accepts `apiKey` as alias); sends `X-Publishable-Key` |
| `factory/core/docs/CHAT_FLOW.md` | Documented publishable-key model + new auth flow |
| `factory/core/docs/LOCAL_DEVELOPMENT.md` | Curl example uses `X-Publishable-Key` + `Origin` |

## Deploy sequence

This is a hard cutover. Existing keys must be backfilled with `allowed_origins` and `rate_limit_per_hour` **before** the new code is deployed, or live bots will break.

1. Confirm `budget_notification_email` is set in `terraform/terraform.tfvars`.
2. `terraform apply` to create `BotFactoryRateLimit` and the budget alarm. (Safe — new resources only.)
3. Backfill all three live keys:
   ```bash
   python3 scripts/migrate_keys_v2_3_0.py --bot-id RobbAI \
     --origins https://robrose.info,http://localhost:8080 --rate-limit 30
   python3 scripts/migrate_keys_v2_3_0.py --bot-id the-fret-detective \
     --origins https://thefretdetective.com,http://localhost:8080 --rate-limit 30
   python3 scripts/migrate_keys_v2_3_0.py --bot-id bellese-atlas \
     --origins http://localhost:8080 --rate-limit 30
   ```
4. `make deploy-streaming` to roll out the new code.
5. Smoke-test all three bots from their respective origins.
