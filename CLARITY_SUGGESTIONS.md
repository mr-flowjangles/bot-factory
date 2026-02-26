# Clarity Suggestions (Current Repo)

This is a focused set of documentation/structure improvements that would make onboarding and day-to-day maintenance easier.

## 1) Consolidate docs and define a canonical entry point

Done

## 2) Normalize paths and command examples

Done

## 3) Add an explicit “local vs production” command matrix

done

## 4) Add a short architecture map with ownership boundaries

- Core concepts exist, but ownership boundaries (what to edit per bot vs framework) are easy to miss.
- Suggestion: add a 10-line “edit here vs don’t edit here” section (e.g., `factory/bots/<id>/` vs `factory/core/`).
- Benefit: prevents accidental edits in shared internals.

## 5) Clarify legacy vs current implementation status

- There are references to legacy components and migrated factory components.
- Suggestion: add a small “Current status” section that states what is legacy, what is active, and migration intent.
- Benefit: avoids ambiguity about where new work should go.

## 6) Add a minimal “first successful run” checklist

- Suggestion: add a short checklist for first-time setup:
  1. `docker compose up -d`
  2. create bot from template
  3. upload data
  4. generate embeddings
  5. hit `/api/{bot_id}/chat`
- Benefit: gives contributors a confidence-building happy path.

## 7) Tighten terminology consistency

- Terms like “factory”, “bot”, “chatbot”, and provider names are used in slightly different ways across docs.
- Suggestion: add a tiny glossary section (5–8 terms).
- Benefit: reduces confusion in discussions and PR reviews.

## 8) Link deep docs from the top-level README

- Existing deep docs under `factory/core/docs/` are useful but easy to miss.
- Suggestion: add a “Further reading” block linking chat flow, embedding flow, and local development docs.
- Benefit: helps advanced contributors self-serve quickly.
