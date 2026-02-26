# aws-serverless-resume

A serverless portfolio site with an embedded AI chatbot platform. The frontend is static HTML/CSS/JS hosted on S3 and served via CloudFront. The backend is a FastAPI app running in AWS Lambda, connected to DynamoDB and S3, with AI powered by AWS Bedrock.

## Architecture

```
Browser
  → CloudFront
    → S3 (static frontend: HTML, JS, CSS, assets)
    → API Gateway → Lambda (FastAPI backend)
                      → DynamoDB (embeddings, session data)
                      → S3 (bot knowledge data)
                      → Bedrock (embeddings + Claude responses)
```

Local development mirrors production using Docker Compose + LocalStack.

## Project Structure

```
/
├── ai/
│   ├── factory/               ← Bot Factory (see ai/factory/README.md)
│   │   ├── core/              ← Shared RAG engine
│   │   ├── bots/              ← One folder per bot
│   │   └── scaffold_bot.py    ← Frontend generator
│   ├── scripts/               ← Export/import embedding utilities
│   └── ...                    ← Legacy RobbAI resume assistant
│
├── app/                       ← Frontend (generated + hand-authored)
│   ├── bot_scripts/           ← Shared and bot-specific JS/CSS
│   └── assets/                ← Bot-specific images
│
├── terraform/                 ← Infrastructure as code
├── docker-compose.yml         ← Local dev environment
├── build-lambda.sh            ← Package Lambda for deployment
└── main.py                    ← FastAPI entrypoint
```

## Bot Factory

The Bot Factory (`ai/factory/`) is a reusable RAG chatbot framework built on top of this infrastructure. Write a config, add knowledge data, run one command — get a working chatbot with semantic search and Claude-powered responses.

→ **[Full documentation: ai/factory/README.md](ai/factory/README.md)**

## Bots

| Bot                | ID       | Endpoint           | Description                                           |
| ------------------ | -------- | ------------------ | ----------------------------------------------------- |
| RobbAI             | —        | `/api/ai/chat`     | Resume assistant. Legacy code, not yet on the factory. |
| The Fret Detective | `guitar` | `/api/guitar/chat` | Electric guitar instruction. First factory bot.       |

## Local Development

```bash
docker compose up -d
```

The API runs at `http://localhost:8000`, frontend at `http://localhost:8080`. LocalStack simulates DynamoDB, S3, and Bedrock locally.

## Deploy

```bash
# Backend (Lambda)
./build-lambda.sh
aws s3 cp terraform/builds/fastapi-app.zip s3://aws-serverless-resume-prod/lambda/fastapi-app.zip
aws lambda update-function-code --function-name aws-serverless-resume-api --s3-bucket aws-serverless-resume-prod --s3-key lambda/fastapi-app.zip

# Frontend (S3 + CloudFront)
aws s3 sync app/ s3://aws-serverless-resume-prod/ --cache-control "no-cache"
aws cloudfront create-invalidation --distribution-id <your_id> --paths "/*"
```

For bot-specific deploy steps (data changes, embeddings) see the factory docs.
