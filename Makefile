.PHONY: up down build restart logs ps clean nuke init-s3 s3-ls s3-upload s3-sync dynamo-init dynamo-init-aws

# ──────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose down && docker compose build --no-cache && docker compose up -d

restart:
	docker compose down && docker compose up -d

# ──────────────────────────────────────────────
# Bot Scaffolding
# ──────────────────────────────────────────────
scaffold:
	@test -n "$(bot)" || (echo "Usage: make scaffold bot=<bot_id>" && exit 1)
	python3 scripts/scaffold_bot.py $(bot) --endpoint-url http://localhost:4566

scaffold-prod:
	@@test -n "$(bot)" || (echo "Usage: make scaffold bot=<bot_id>" && exit 1)
	python3 scripts/scaffold_bot.py $(bot)

# ──────────────────────────────────────────────
# Logs & Status
# ──────────────────────────────────────────────
logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-web:
	docker compose logs -f web

logs-ls:
	docker compose logs -f localstack

ps:
	docker compose ps

# ──────────────────────────────────────────────
# S3 (Local)
# ──────────────────────────────────────────────
S3_ENDPOINT = --endpoint-url=http://localhost:4566
S3_BUCKET = s3://bot-factory-data
AWS_LOCAL = AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1

s3-ls:
	$(AWS_LOCAL) aws $(S3_ENDPOINT) s3 ls $(S3_BUCKET)/ --recursive

s3-upload:
	@test -n "$(file)" || (echo "Usage: make s3-upload file=path/to/file.yml prefix=knowledge-base/" && exit 1)
	$(AWS_LOCAL) aws $(S3_ENDPOINT) s3 cp $(file) $(S3_BUCKET)/$(prefix)

s3-sync:
	@test -n "$(dir)" || (echo "Usage: make s3-sync dir=./data/knowledge-base prefix=knowledge-base/" && exit 1)
	$(AWS_LOCAL) aws $(S3_ENDPOINT) s3 sync $(dir) $(S3_BUCKET)/$(prefix)

s3-mb:
	$(AWS_LOCAL) aws $(S3_ENDPOINT) s3 mb $(S3_BUCKET) 2>/dev/null || true

# ──────────────────────────────────────────────
# DynamoDB (Local)
# ──────────────────────────────────────────────
dynamo-init:
	$(AWS_LOCAL) bash scripts/init-dynamodb.sh

dynamo-init-aws:
	bash scripts/init-dynamodb.sh --aws

dynamo-ls:
	$(AWS_LOCAL) aws $(S3_ENDPOINT) dynamodb list-tables

dynamo-scan:
	@test -n "$(table)" || (echo "Usage: make dynamo-scan table=ChatbotRAG" && exit 1)
	$(AWS_LOCAL) aws $(S3_ENDPOINT) dynamodb scan --table-name $(table) --select COUNT

# ──────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────
clean:
	docker compose down -v

nuke:
	docker compose down -v --rmi all
	rm -rf ./localstack-data