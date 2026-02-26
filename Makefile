.PHONY: up down build rebuild restart logs logs-api logs-ls ps clean nuke \
        s3-ls s3-upload s3-sync s3-mb \
        dynamo-ls dynamo-scan dynamo-query dynamo-get dynamo-count dynamo-items \
        embed scaffold scaffold-prod

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
ENDPOINT    = http://localhost:4566
S3_BUCKET   = s3://bot-factory-data
AWS_FLAGS   = --endpoint-url=$(ENDPOINT)
AWS         = AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 aws $(AWS_FLAGS)
TABLE       ?= ChatbotRAG

# ─────────────────────────────────────────────────────────────
# Docker Compose
# ─────────────────────────────────────────────────────────────
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

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-ls:
	docker compose logs -f localstack

ps:
	docker compose ps

# ─────────────────────────────────────────────────────────────
# S3 (Local)
# ─────────────────────────────────────────────────────────────
s3-mb:
	$(AWS) s3 mb $(S3_BUCKET) 2>/dev/null || true

s3-ls:
	$(AWS) s3 ls $(S3_BUCKET)/ --recursive

## make s3-sync dir=bots/guitar/data prefix=guitar/data/
s3-sync:
	@test -n "$(dir)" || (echo "Usage: make s3-sync dir=bots/guitar/data prefix=guitar/data/" && exit 1)
	$(AWS) s3 sync $(dir) $(S3_BUCKET)/$(prefix)

## make s3-upload file=path/to/file.yml prefix=guitar/data/
s3-upload:
	@test -n "$(file)" || (echo "Usage: make s3-upload file=path/to/file.yml prefix=guitar/data/" && exit 1)
	$(AWS) s3 cp $(file) $(S3_BUCKET)/$(prefix)

## make s3-ls-bot bot=guitar
s3-ls-bot:
	@test -n "$(bot)" || (echo "Usage: make s3-ls-bot bot=guitar" && exit 1)
	$(AWS) s3 ls $(S3_BUCKET)/$(bot)/ --recursive

# ─────────────────────────────────────────────────────────────
# DynamoDB (Local)
# ─────────────────────────────────────────────────────────────

## List all tables
dynamo-ls:
	$(AWS) dynamodb list-tables

## Total item count for a table  (default: ChatbotRAG)
## make dynamo-count  OR  make dynamo-count TABLE=MyOtherTable
dynamo-count:
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --select COUNT \
	  --output json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Count: {d[\"Count\"]}')"

## Scan all items (returns first page, max 1 MB)
## make dynamo-scan  OR  make dynamo-scan TABLE=MyOtherTable
dynamo-scan:
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(json.dumps(i, indent=2)) for i in items]"

## Scan items for a specific bot (filtered)
## make dynamo-scan-bot bot=guitar
dynamo-scan-bot:
	@test -n "$(bot)" || (echo "Usage: make dynamo-scan-bot bot=guitar" && exit 1)
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --filter-expression "begins_with(pk, :prefix)" \
	  --expression-attribute-values '{":prefix": {"S": "$(bot)_"}}' \
	  --output json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Count: {d[\"Count\"]}'); [print(json.dumps(i,indent=2)) for i in d['Items']]"

## Get a single item by pk
## make dynamo-get pk=guitar_0
dynamo-get:
	@test -n "$(pk)" || (echo "Usage: make dynamo-get pk=guitar_0" && exit 1)
	$(AWS) dynamodb get-item \
	  --table-name $(TABLE) \
	  --key '{"pk": {"S": "$(pk)"}}' \
	  --output json

## Show keys (pks) only for a table
dynamo-keys:
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --projection-expression "pk" \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(i['pk']['S']) for i in items]"

## Show keys for a specific bot
## make dynamo-keys-bot bot=guitar
dynamo-keys-bot:
	@test -n "$(bot)" || (echo "Usage: make dynamo-keys-bot bot=guitar" && exit 1)
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --filter-expression "begins_with(pk, :prefix)" \
	  --expression-attribute-values '{":prefix": {"S": "$(bot)_"}}' \
	  --projection-expression "pk" \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(i['pk']['S']) for i in items]"

# ─────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────

## make embed bot=guitar
embed:
	@test -n "$(bot)" || (echo "Usage: make embed bot=guitar" && exit 1)
	python3 core/generate_embeddings.py $(bot) --endpoint-url $(ENDPOINT)

## Regenerate embeddings for all enabled bots
embed-all:
	python3 core/generate_embeddings.py --all --endpoint-url $(ENDPOINT)

# ─────────────────────────────────────────────────────────────
# Bot Scaffolding
# ─────────────────────────────────────────────────────────────

## make scaffold bot=<bot_id>
scaffold:
	@test -n "$(bot)" || (echo "Usage: make scaffold bot=<bot_id>" && exit 1)
	python3 scripts/scaffold_bot.py $(bot) --endpoint-url $(ENDPOINT)

## make scaffold-prod bot=<bot_id>
scaffold-prod:
	@test -n "$(bot)" || (echo "Usage: make scaffold-prod bot=<bot_id>" && exit 1)
	python3 scripts/scaffold_bot.py $(bot)

# ─────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────

## Stop containers and remove volumes
clean:
	docker compose down -v

## Full reset — removes containers, images, volumes, and persisted LocalStack data
nuke:
	docker compose down -v --rmi all
	rm -rf ./localstack-data
