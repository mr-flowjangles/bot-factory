# Your Bot — Build Plan

Live checkbox tracker. Tick boxes as we ship them. Start date: **2026-05-14**. Target: **first paying customer by 2026-05-31**.

Three milestones, smallest-first. M0 makes Rob faster. M1 makes Rob discoverable. M2 makes Rob paid.

---

## M0 — Platform readiness for managed delivery

Goal: cut Rob's per-customer onboarding from "a day of clicking" to "30 minutes of script". Pure internal tooling. Customer never sees any of this.

- [ ] **Repeatable onboarding script** — `scripts/onboard_customer.sh` that takes `--bot-id`, `--customer-name`, `--allowed-origins`, `--data-dir`. Runs: scaffold → sync data → embed → gen publishable key → deploy. End state: one command per new customer.
- [ ] **Weekly activity email** — new Lambda on a CloudWatch schedule. Reads `BotFactoryLogs`, groups by bot_id over the last 7 days, sends one email per customer via SES with: total messages, top 10 topics, top 5 unanswered questions, week-over-week delta. Subscriber email lives on the bot's config.
- [ ] **Decommission workflow** — `scripts/offboard_customer.sh`: disable keys (`enabled=false`), export their data to a tarball, optionally delete their embeddings + logs. For churn or contract end.
- [ ] **Fix the `make deploy-streaming` Makefile bug** (carried over from v2.3.0). It builds the wrong zip. Either delete the target or repoint it at `build_lambda.sh`.
- [ ] **Onboarding playbook doc** — `docs/your-bot/03-onboarding-playbook.md`. The exact runbook Rob follows for each new customer, with checklist + sample customer questionnaire + brand-config template.

## M1 — Customer-facing surface

Goal: a website that a stranger could land on and understand what Rob sells in 30 seconds, then start a conversation.

- [ ] **Brand decision** — name (confirm "Your Bot" or pick alt), color palette, voice. One paragraph.
- [ ] **Domain registered** — candidate names: `yourbot.dev`, `yourbot.studio`, `getyourbot.com`. Pick one, register, point at Route 53.
- [ ] **Landing page** — single page, no nav. Sections:
  - [ ] Hero — value prop in one sentence + a working demo (embed RobbAI on the landing page)
  - [ ] How it works — 3 steps: send us your docs, we build the bot, embed it on your site
  - [ ] Pricing — setup fee + monthly retainer + what's included
  - [ ] FAQ — "is my data private?", "what if my bot is wrong?", "what does the weekly report look like?"
  - [ ] Contact form — name, email, business, what would the bot do? (reuse the FastAPI contact endpoint pattern from aws-serverless-resume)
- [ ] **Deploy landing page** — own serverless stack (Lambda + CloudFront + S3 + Terraform). Could literally fork aws-serverless-resume.
- [ ] **SOW / contract template** — lawyer-reviewed one-pager. Scope, payment terms, IP ownership (customer owns their content + bot output; Rob owns the platform), support level, cancellation, data-deletion rights.
- [ ] **Stripe Invoicing account** — connect to Rob's business entity. Create invoice templates for setup fee and monthly retainer.
- [ ] **Privacy policy + terms of service** — generated from a template (Termly, Iubenda). Linked from landing page.

## M2 — First paying customer

Goal: prove someone will pay for it. End-to-end validation of M0 tooling and M1 surface.

- [ ] **Target prospect list** — 5–10 warm-network candidates. Service businesses Rob already knows. Write each name and what their bot would do.
- [ ] **Demo flow** — what does a sales call look like? Probably: live demo of RobbAI → "imagine this for your business" → questionnaire → quote.
- [ ] **First sales conversation** — book a call, walk through demo, send proposal.
- [ ] **First signed SOW** — close the deal.
- [ ] **Onboard end-to-end** — actually run `onboard_customer.sh` against a real customer. *This is the M0 stress test*. Capture every rough edge.
- [ ] **First invoice sent + paid** — Stripe Invoicing, setup fee + first month.
- [ ] **First weekly activity email delivered** — confirm M0's report Lambda fires.
- [ ] **Post-mortem** — update the playbook doc with lessons learned. What surprised us? What took longer than expected? What did the customer ask for that we didn't have?

---

## How we work this plan

- Tick boxes inline as work ships. Don't wait for a separate tracker.
- M0 → M1 → M2 ideally in that order. M1 can run in parallel with M0 if Rob has the energy.
- Each ticked task that produces code follows the version flow (`new-version.sh`).
- Each milestone completion gets its own retro in this doc — a 5-line note on what we learned before moving on.

## Out of scope for this plan

Things that show up later, not now:

- Multi-tenant control plane / customer dashboard. (Vision doc explicitly rules this out.)
- Stripe API integration / metered billing.
- Multi-bot per customer.
- Voice / phone / SMS interfaces.
- Self-serve signup.

If any of these become unavoidable, that's the signal Bot Factory has outgrown the managed-service model — start a new plan, don't bolt onto this one.
