# Your Bot — Vision

## What it is

A custom AI chatbot for one business, deployed and run by Rob on the Bot Factory platform. Each customer gets a bot that knows *their* business — products, services, FAQs, hours, policies — embedded on their site as a chat widget.

The customer doesn't see Bot Factory. They see a working bot. Rob delivers, hosts, and maintains it.

## Who it's for

- Small / medium service businesses with a website, a clear set of repeat customer questions, and no dev team.
- Solo professionals and agencies (consultants, coaches, real estate, legal, dental, fitness) who want to answer "what are your hours / prices / services" without picking up the phone.
- Businesses that have tried "embed a generic chatbot" and watched it confidently make stuff up.

**Not for:** companies with developers who want to build their own. They should go DIY.

## What problem it solves

Three problems, in order:

1. **Repeat questions burn time.** Same five questions asked 30 times a week. A bot that knows the business handles them instantly.
2. **Generic chatbots hallucinate.** ChatGPT doesn't know the customer's hours. Intercom AI doesn't know their pricing. Your Bot is grounded in the customer's actual knowledge base.
3. **Building one is too much work.** RAG, embeddings, vector DBs, prompt engineering, hosting, monitoring — none of that is a service business's job.

## Why pay for this

| Alternative | Why Your Bot beats it |
|---|---|
| ChatGPT / Claude on their site | Doesn't know the business. Confidently wrong. No embed. |
| Intercom / Drift AI add-on | Hundreds to thousands per month, mostly for features they won't use. Setup is hostile to non-technical users. |
| DIY (hire a dev) | $10k+ to build, ongoing maintenance, has to be re-built every time the stack changes. |
| Doing nothing | Customer questions sit in inboxes. Phone keeps ringing. |

## Pricing model (initial — TBD with first customer)

- **Setup fee**: $500–$1,500 (one-time). Covers knowledge-base ingestion, prompt tuning, brand styling, embed deployment, first weeks of monitoring.
- **Monthly retainer**: $200–$500. Covers hosting, AWS infra, quarterly knowledge refresh, support, weekly activity reports.
- **Out of scope add-ons** (à la carte): rush refresh, custom integrations, multi-language support, custom branding beyond defaults.

Invoiced via Stripe Invoicing. No subscription self-serve.

## Product scope

**In:**
- One bot per customer, embedded on one domain.
- Knowledge base: text docs, FAQs, structured YAML, PDFs.
- Branded chat widget (color, name, persona).
- Weekly activity email to the customer (what your bot did, top topics, unanswered questions).
- Quarterly knowledge refresh.
- Best-effort support during business hours, 24-hour response.

**Out:**
- Self-serve account creation. Onboarding is a conversation with Rob.
- Customer-facing dashboard. The weekly email is the dashboard.
- Multi-tenant control plane. Bot Factory stays Rob's internal tooling.
- Per-customer AWS isolation. All bots share Rob's AWS account; budget alarms catch abuse.
- 24/7 support, four-nines SLA. This is small-business pricing.
- Integrations beyond the embed widget. No Slack, no Teams, no SMS — yet.

## Non-goals

These exist so the platform doesn't drift toward SaaS:

- **No customer-facing UI on Bot Factory.** If a customer wants to update their knowledge base, they email Rob a doc. Rob re-ingests.
- **No Stripe API integration.** Stripe Invoicing dashboard handles billing manually.
- **No accounts / auth / tenancy code.** Customers are rows in Rob's CRM (probably Notion), not records in a database.
- **No per-tenant cost isolation.** Rob eats Bedrock costs, prices the retainer to cover them, sets budget alarms to catch outliers.
- **No "let me try it free" landing flow.** This is sales-led. The website's job is to start a conversation, not to convert a signup.

If a request would push the platform toward any of those, it's a signal Rob has outgrown the managed-service model — not a signal to add the feature.
