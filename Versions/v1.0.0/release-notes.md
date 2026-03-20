# v1.0.0 — Bot Factory Platform (2025–2026)

The foundation. A serverless RAG chatbot platform on AWS — deploy a bot by
providing a config + knowledge data files.

### Core Platform
- Multi-bot architecture — single Lambda deployment, bot_id scopes everything
- RAG pipeline: Titan V2 embeddings → cosine similarity → Claude response generation
- Two response modes: buffered (API Gateway) and streaming (Lambda Function URL + SSE)
- Local dev stack: LocalStack (S3 + DynamoDB) + Flask dev server + nginx
- Per-bot in-memory caching (embeddings, configs, prompts) for Lambda warm starts

### Bot Management
- YAML-based bot configuration (config.yml + prompt.yml + data/*.yml)
- Universal chunker supporting text and structured data formats
- Kill-and-fill embedding generation scoped per bot
- `make scaffold` to create new bot skeletons
- S3-based data storage with LocalStack parity

### Retrieval & Response
- Context-enriched follow-up queries (_build_enriched_query)
- Conversation history support for multi-turn awareness
- Configurable RAG parameters (top_k, similarity_threshold)
- Bot boundaries for domain-scoped responses

### Infrastructure
- Terraform-managed AWS infrastructure
- Lambda packaging and deployment (make deploy-streaming, make deploy-infra)
- API key authentication via DynamoDB (BotFactoryApiKeys)
- Chat interaction logging (BotFactoryLogs)
- SSE chat client for testing and demo

### Developer Experience
- Makefile-driven workflow (up, down, local, lint, format, load-bot, embed, etc.)
- flake8 + black code quality (line-length=120)
- Production deployment pipeline (deploy-bot-prod, deploy-streaming)
