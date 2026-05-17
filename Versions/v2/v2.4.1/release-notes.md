# v2.4.1 — Customer Onboarding Script (2026-05-14)

## Problem

Onboarding a new managed-service customer required Rob to remember and run a sequence of `make` targets and Python scripts by hand: scaffold the bot, copy config/prompt/data files, deploy to S3, generate embeddings, generate a publishable key with the correct origin allowlist. Easy to forget a step. Easy to ship a key with no rate limit. The build plan flagged this as M0 task #1 — make Rob faster before Rob talks to a customer.

## Solution

A single bash wrapper, `scripts/onboard_customer.sh`, that takes a "brief dir" (customer's config + prompt + knowledge files) and does the rest end-to-end. Prints an onboarding receipt with the embed snippet so Rob can copy-paste it into the customer email.

## New

- **`scripts/onboard_customer.sh`** — one-command onboarding:
  1. Scaffolds the bot (idempotent — skips if the dir exists)
  2. Imports `config.yml`, `prompt.yml`, and `data/` from the customer's brief dir
  3. Runs `make deploy-bot-prod` (uploads to S3, generates embeddings, generates manifest)
  4. Calls `gen_api_key.py` with the customer's allowed origins and rate limit
  5. Prints an onboarding receipt: publishable key, allowed origins, stream URL, embed snippet

  Run without `--brief-dir` to scaffold an empty bot and stop, so Rob can hand-edit the templates first before re-running.

## Changed

- **`docs/your-bot/02-build-plan.md`** — M0 task #1 checkbox ticked.

## Fixed

None.

## Files Changed

| File | Change |
|------|--------|
| `scripts/onboard_customer.sh` | **New** — one-command customer onboarding |
| `docs/your-bot/02-build-plan.md` | M0 task #1 ticked |

## Usage

```bash
scripts/onboard_customer.sh \
  --bot-id acme-cleaning \
  --customer-name "Acme Cleaning" \
  --allowed-origins https://acmecleaning.com \
  --brief-dir ~/customers/acme-cleaning \
  --rate-limit 30
```

The brief dir must contain `config.yml`, `prompt.yml`, and a `data/` subdirectory.

## Open follow-ups

- The embed snippet in the receipt references `<chat.js host TBD>`. **Decision made**: option 3 — hosted `embed.js` + a `/config` endpoint on bot-factory that the script self-loads from. Added as a new task in M1 of the build plan. Resolved when M1 lands.
- A customer-brief template (`docs/your-bot/customer-brief-template/`) will land with the onboarding playbook doc (M0 task #5).
