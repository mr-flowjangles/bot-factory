# v2.0.7 — Debug Timing Guard (2026-03-24)

## Problem

v2.0.6 added `print(flush=True)` timing breakdowns to retrieval and chatbot modules for CloudWatch observability. These always print on every request, adding noise to production logs when not actively debugging.

## Solution

- Gated all timing `print()` calls behind a `DEBUG_TIMING` env var
- Reads the env var on each call (not at module load) so it can be toggled in the Lambda console without redeploying code

## Changed

- `retrieval.py` — 3 print calls gated behind `_debug_timing()`
- `chatbot.py` — 4 print calls gated behind `_debug_timing()`

## Files Changed

| File | Change |
|------|--------|
| factory/core/retrieval.py | Gate timing prints behind `DEBUG_TIMING` env var |
| factory/core/chatbot.py | Gate timing prints behind `DEBUG_TIMING` env var |
