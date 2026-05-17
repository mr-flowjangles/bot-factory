# v2.4.0 — Your Bot Vision and Build Plan (2026-05-14)

## Problem

Bot Factory is a working platform with three production bots, hardened auth (v2.3.0), and proven RAG behavior — but no commercial plan. Without an explicit vision and roadmap, future work would drift toward "what's interesting to build" instead of "what makes managed-service delivery possible." Worse, it would drift toward SaaS plumbing (control planes, tenancy, billing APIs) that doesn't pay off until customers exist.

## Solution

Lock in the commercialization frame as a **managed service** ("Your Bot") and capture it in two design docs that anchor every future decision. The build plan is a live checkbox tracker — we ship through it, we don't write more docs.

## New

- **`docs/your-bot/01-vision.md`** — what Your Bot is, ICP, why someone pays for it instead of ChatGPT / Intercom / DIY, pricing model, and explicit non-goals (no self-serve, no control plane, no per-tenant cost isolation).
- **`docs/your-bot/02-build-plan.md`** — three milestones (M0 platform readiness, M1 customer-facing surface, M2 first paying customer) as checkbox tasks. Target: first paying customer by 2026-05-31.

## Changed

None — docs-only version.

## Fixed

None.

## Files Changed

| File | Change |
|------|--------|
| `docs/your-bot/01-vision.md` | **New** — vision + ICP + pricing model + non-goals |
| `docs/your-bot/02-build-plan.md` | **New** — M0/M1/M2 checkbox tracker, 2-week target |
