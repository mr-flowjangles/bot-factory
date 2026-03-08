# Clarity Suggestions (Current Repo)

This is a focused set of documentation/structure improvements that would make onboarding and day-to-day maintenance easier.

## 1) Consolidate docs and define a canonical entry point

Done

## 2) Normalize paths and command examples

Done

## 3) Add an explicit "local vs production" command matrix

Done

## 4) Add a short architecture map with ownership boundaries

Done — factory/README.md now has explicit "Edit freely / Edit with care / Don't edit" sections.

## 5) Clarify legacy vs current implementation status

Done — root README.md and factory/README.md updated to reflect current Lambda/Chalice architecture. Old FastAPI references removed.

## 6) Add a minimal "first successful run" checklist

Done — factory/README.md Step 1–8 guides the full workflow from scaffold to local test.

## 7) Tighten terminology consistency

Done — all docs now use consistent terms:
- **bot**: a configured chatbot instance (config + prompt + data in S3)
- **factory**: the shared Lambda code and RAG engine in `factory/`
- **embedding**: a 1024-dim Bedrock Titan V2 vector stored in DynamoDB
- **chunk**: a single embeddable text unit produced by the chunker from a YAML entry
- **bot_id**: the unique string identifier that drives S3 paths and DynamoDB partitioning

## 8) Link deep docs from the top-level README

Done — root README.md links to factory/README.md. factory/README.md links to CHAT_FLOW.md, EMBEDDING_FLOW.md, and LOCAL_DEVELOPMENT.md.
