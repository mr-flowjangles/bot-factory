# v2.4.2 — Migrate Sonnet 4 to Sonnet 4.6 (2026-05-17)

## Problem

AWS notified us that **`anthropic.claude-sonnet-4-20250514-v1:0` is now Legacy** (effective Apr 14, 2026). Timeline:

- **Apr 14, 2026** — Legacy state (no new quota increases)
- **Jul 14, 2026** — Extended access
- **Oct 14, 2026** — End-of-life; requests to this model ID fail

Bot Factory hardcodes the Sonnet 4 model ID in five places across the runtime and the PDF ingestion script. We need to migrate well ahead of the EOL date — and the Legacy quota freeze is itself a reason not to wait.

## Solution

Swap every hardcoded `us.anthropic.claude-sonnet-4-20250514-v1:0` reference to `us.anthropic.claude-sonnet-4-6` (the US cross-region inference profile for Claude Sonnet 4.6). The new ID drops the date and `-v1:0` suffixes — that's the convention AWS uses for the 4.6 family inference profiles.

The Sonnet 4.6 model card lists prompt caching support with the same constraints we already rely on (1024 min tokens, 4 max checkpoints, system/messages/tools fields), so the existing `cachePoint` on the system prompt continues to work unchanged.

## Changed

- **`factory/core/chatbot.py`** — `converse` (non-stream) and `converse_stream` calls now target Sonnet 4.6.
- **`factory/core/self_heal.py`** — `MODEL_SONNET` constant points at Sonnet 4.6. (`MODEL_HAIKU` already on Haiku 4.5 — unaffected.)
- **`scripts/pdf_ingest.py`** — both ingestion-time LLM calls (chunk processing + entry enrichment) on Sonnet 4.6.
- **`scripts/scaffold_bot.py`** — scaffold template default updated for cosmetic consistency. (The scaffolded `config.yml`'s `model.name` field is descriptive only; the runtime reads the hardcoded constant, not the bot config.)

## Verification

- `grep -rn "claude-sonnet-4-20250514"` returns zero hits outside `Versions/` history.
- Direct Bedrock smoke test from the local repo (`boto3 client.converse` to `us.anthropic.claude-sonnet-4-6` in `us-east-1`) returned a 200 with expected output and usage metrics — model access is already enabled on the account.

## Files Changed

| File | Change |
|------|--------|
| `factory/core/chatbot.py` | Sonnet 4 → Sonnet 4.6 in both `converse` and `converse_stream` calls |
| `factory/core/self_heal.py` | `MODEL_SONNET` constant → Sonnet 4.6 |
| `scripts/pdf_ingest.py` | Both ingestion `converse` calls → Sonnet 4.6 |
| `scripts/scaffold_bot.py` | Scaffold template default → Sonnet 4.6 |

## Known issues / notes

- **Production deploy required:** Lambda code still runs the old model ID until `make deploy-streaming` is run. The legacy model will keep working until Oct 14, 2026, so this isn't urgent — but it should ship before the next customer goes live.
- **End-to-end browser test deferred:** `make test-chat` requires a valid publishable key from DynamoDB; the direct Bedrock smoke test covers the same risk (model access + ID validity). Worth a quick browser run before deploying to prod, just to confirm streaming behavior on a warm Lambda.
- **Performance baseline:** the v2.0.6 notes establish Fret Detective at ~3s on Sonnet 4. If Sonnet 4.6 changes that materially (faster or slower), it's worth a follow-up note on `DEBUG_TIMING` output before adjusting any caching settings.
