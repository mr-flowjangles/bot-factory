.PHONY: up down build rebuild restart logs logs-ls ps clean nuke \
        s3-ls s3-upload s3-sync s3-mb \
        dynamo-ls dynamo-scan dynamo-query dynamo-get dynamo-count dynamo-items dynamo-init \
        embed embed-all scaffold scaffold-prod deploy-bot deploy-bot-prod \
        init chalice chalice-stop help

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
ENDPOINT    = http://localhost:4566
S3_BUCKET   = s3://bot-factory-data
AWS_FLAGS   = --endpoint-url=$(ENDPOINT)
AWS         = AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 aws $(AWS_FLAGS)
TABLE       ?= BotFactoryRAG

# ─────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Bot Factory — Available Commands"
	@echo "════════════════════════════════════════════════════════════"
	@echo "  Docker"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "up"                           "Start all containers + run init"
	@printf "  %-38s %s\n" "init"                         "Re-run S3 + DynamoDB init (after bounce)"
	@printf "  %-38s %s\n" "down"                         "Stop all containers + Chalice"
	@printf "  %-38s %s\n" "build"                        "Build containers"
	@printf "  %-38s %s\n" "rebuild"                      "Full rebuild from scratch"
	@printf "  %-38s %s\n" "restart"                      "Restart all containers"
	@printf "  %-38s %s\n" "logs"                         "Tail all logs"
	@printf "  %-38s %s\n" "logs-ls"                      "Tail LocalStack logs"
	@printf "  %-38s %s\n" "ps"                           "Show container status"
	@printf "  %-38s %s\n" "chalice"                      "Start Chalice local dev server"
	@printf "  %-38s %s\n" "chalice-stop"                 "Stop Chalice local dev server"
	@echo ""
	@echo "  Code Quality"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "lint"                         "Run flake8 linter"
	@printf "  %-38s %s\n" "format"                       "Auto-format with black"
	@printf "  %-38s %s\n" "format-check"                 "Check formatting without applying"
	@echo ""
	@echo "  S3 (Local)"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "s3-mb"                        "Create the S3 bucket in LocalStack"
	@printf "  %-38s %s\n" "s3-ls"                        "List all files in the bucket"
	@printf "  %-38s %s\n" "s3-ls-bot bot={bot_id}"       "List files for a specific bot"
	@printf "  %-38s %s\n" "s3-sync dir=path prefix=path/" "Sync a local dir to S3"
	@printf "  %-38s %s\n" "s3-upload file=path prefix=path/" "Upload a single file to S3"
	@printf "  %-38s %s\n" "s3-init"                      "Create bucket and upload all bots from scripts/bots/ to S3"
	@echo ""
	@echo "  DynamoDB (Local)"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "dynamo-init"                  "Create DynamoDB tables in LocalStack"
	@printf "  %-38s %s\n" "dynamo-ls"                    "List all tables"
	@printf "  %-38s %s\n" "dynamo-count"                 "Item count (default: BotFactoryRAG)"
	@printf "  %-38s %s\n" "dynamo-scan"                  "Scan all items in a table"
	@printf "  %-38s %s\n" "dynamo-scan-bot bot={bot_id}" "Scan items for a specific bot"
	@printf "  %-38s %s\n" "dynamo-get pk={bot_id}_0"     "Get a single item by pk"
	@printf "  %-38s %s\n" "dynamo-keys"                  "Show all keys in a table"
	@printf "  %-38s %s\n" "dynamo-keys-bot bot={bot_id}" "Show keys for a specific bot"
	@echo ""
	@echo "  Data Loading"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "load-bot bot={bot_id}"        "Sync scripts/bots/{bot_id}/data/ to S3"
	@printf "  %-38s %s\n" "deploy-bot bot={bot_id}"      "Upload config.yml + prompt.yml to S3 (local)"
	@printf "  %-38s %s\n" "deploy-bot-prod bot={bot_id}" "Upload config.yml + prompt.yml to S3 (prod)"
	@echo ""
	@echo "  Embeddings"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "embed bot={bot_id}"           "Generate embeddings (local)"
	@printf "  %-38s %s\n" "embed-force bot={bot_id}"     "Regenerate without prompt"
	@printf "  %-38s %s\n" "embed-prod bot={bot_id}"      "Generate embeddings (production)"
	@echo ""
	@echo "  Scaffolding"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "scaffold bot={bot_id}"        "Create a new bot (local)"
	@printf "  %-38s %s\n" "scaffold-prod bot={bot_id}"   "Create a new bot (production)"
	@echo ""
	@echo "  Cleanup"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "clean"                        "Stop containers and remove volumes"
	@printf "  %-38s %s\n" "nuke"                         "Full reset — removes everything including LocalStack data"
	@echo ""


# ─────────────────────────────────────────────────────────────
# Docker Compose
# ─────────────────────────────────────────────────────────────

up:
	docker compose up -d
	@echo "Waiting for LocalStack to be ready..."
	@sleep 5
	$(MAKE) dynamo-init
	$(MAKE) s3-init
	$(MAKE) chalice

down:
	docker compose down
	$(MAKE) chalice-stop

init:
	$(MAKE) dynamo-init
	$(MAKE) s3-init

build:
	docker compose build

rebuild:
	docker compose down && docker compose build --no-cache && docker compose up -d

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f

logs-ls:
	docker compose logs -f localstack

ps:
	docker compose ps

chalice:
	LOCALSTACK_ENDPOINT=http://localhost:4566 chalice local --port 8000 & echo $$! > .chalice/server.pid
	@echo "Chalice running on http://localhost:8000 (PID: $$(cat .chalice/server.pid))"

chalice-stop:
	@if [ -f .chalice/server.pid ]; then \
		kill $$(cat .chalice/server.pid) 2>/dev/null && rm .chalice/server.pid && echo "Chalice stopped"; \
	else \
		lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "Chalice stopped"; \
	fi

# ─────────────────────────────────────────────────────────────
# Code Quality
# ─────────────────────────────────────────────────────────────

lint:
	pip install -q -r requirements-dev.txt
	flake8 factory/ --max-line-length=120 --exclude=__pycache__,localstack-data

format:
	pip install -q -r requirements-dev.txt
	black factory/ --line-length 120

format-check:
	black factory/ --line-length 120 --check

# ─────────────────────────────────────────────────────────────
# S3 (Local)
# ─────────────────────────────────────────────────────────────

s3-mb:
	$(AWS) s3 mb $(S3_BUCKET) 2>/dev/null || true

s3-ls:
	$(AWS) s3 ls $(S3_BUCKET)/ --recursive

s3-ls-bot:
	@test -n "$(bot)" || (echo "Usage: make s3-ls-bot bot={bot_id}" && exit 1)
	$(AWS) s3 ls $(S3_BUCKET)/bots/$(bot)/ --recursive

s3-sync:
	@test -n "$(dir)" || (echo "Usage: make s3-sync dir=bots/guitar/data prefix=guitar/data/" && exit 1)
	$(AWS) s3 sync $(dir) $(S3_BUCKET)/$(prefix)

s3-upload:
	@test -n "$(file)" || (echo "Usage: make s3-upload file=path/to/file.yml prefix=guitar/data/" && exit 1)
	$(AWS) s3 cp $(file) $(S3_BUCKET)/$(prefix)

s3-init:
	bash scripts/setup_bot_s3.sh

# ─────────────────────────────────────────────────────────────
# DynamoDB (Local)
# ─────────────────────────────────────────────────────────────

dynamo-init:
	LOCALSTACK_ENDPOINT=http://localhost:4566 bash scripts/init-dynamodb.sh

dynamo-ls:
	$(AWS) dynamodb list-tables

dynamo-count:
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --select COUNT \
	  --output json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Count: {d[\"Count\"]}')"

dynamo-scan:
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(json.dumps(i, indent=2)) for i in items]"

dynamo-scan-bot:
	@test -n "$(bot)" || (echo "Usage: make dynamo-scan-bot bot={bot_id}" && exit 1)
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --filter-expression "begins_with(pk, :prefix)" \
	  --expression-attribute-values '{":prefix": {"S": "$(bot)_"}}' \
	  --output json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Count: {d[\"Count\"]}'); [print(json.dumps(i,indent=2)) for i in d['Items']]"

dynamo-get:
	@test -n "$(pk)" || (echo "Usage: make dynamo-get pk={bot_id}_0" && exit 1)
	$(AWS) dynamodb get-item \
	  --table-name $(TABLE) \
	  --key '{"pk": {"S": "$(pk)"}}' \
	  --output json

dynamo-keys:
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --projection-expression "pk" \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(i['pk']['S']) for i in items]"

dynamo-keys-bot:
	@test -n "$(bot)" || (echo "Usage: make dynamo-keys-bot bot={bot_id}" && exit 1)
	$(AWS) dynamodb scan \
	  --table-name $(TABLE) \
	  --filter-expression "begins_with(pk, :prefix)" \
	  --expression-attribute-values '{":prefix": {"S": "$(bot)_"}}' \
	  --projection-expression "pk" \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(i['pk']['S']) for i in items]"

# ─────────────────────────────────────────────────────────────
# Data Loading
# ─────────────────────────────────────────────────────────────

load-bot:
	@test -n "$(bot)" || (echo "Usage: make load-bot bot={bot_id}" && exit 1)
	$(AWS) s3 sync scripts/bots/$(bot)/data/ $(S3_BUCKET)/bots/$(bot)/data/

deploy-bot:
	@test -n "$(bot)" || (echo "Usage: make deploy-bot bot={bot_id}" && exit 1)
	$(AWS) s3 cp scripts/bots/$(bot)/config.yml $(S3_BUCKET)/bots/$(bot)/config.yml
	$(AWS) s3 cp scripts/bots/$(bot)/prompt.yml $(S3_BUCKET)/bots/$(bot)/prompt.yml

deploy-bot-prod:
	@test -n "$(bot)" || (echo "Usage: make deploy-bot-prod bot={bot_id}" && exit 1)
	APP_ENV=production aws s3 cp scripts/bots/$(bot)/config.yml s3://bot-factory-data/bots/$(bot)/config.yml
	APP_ENV=production aws s3 cp scripts/bots/$(bot)/prompt.yml s3://bot-factory-data/bots/$(bot)/prompt.yml

# ─────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────

embed:
	@test -n "$(bot)" || (echo "Usage: make embed bot={bot_id}" && exit 1)
	python3 -m factory.core.generate_embeddings $(bot)

embed-force:
	@test -n "$(bot)" || (echo "Usage: make embed-force bot={bot_id}" && exit 1)
	python3 -m factory.core.generate_embeddings $(bot) --force

embed-prod:
	@test -n "$(bot)" || (echo "Usage: make embed-prod bot={bot_id}" && exit 1)
	APP_ENV=production python3 -m factory.core.generate_embeddings $(bot) --force

# ─────────────────────────────────────────────────────────────
# Bot Scaffolding
# ─────────────────────────────────────────────────────────────

scaffold:
	@test -n "$(bot)" || (echo "Usage: make scaffold bot={bot_id}" && exit 1)
	python3 scripts/scaffold_bot.py $(bot) --endpoint-url $(ENDPOINT)

scaffold-prod:
	@test -n "$(bot)" || (echo "Usage: make scaffold-prod bot={bot_id}" && exit 1)
	APP_ENV=production python3 scripts/scaffold_bot.py $(bot)

# ─────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────

clean:
	docker compose down -v

nuke:
	docker compose down -v --rmi all
	rm -rf ./localstack-data