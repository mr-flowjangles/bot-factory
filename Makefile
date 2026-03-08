.PHONY: up down build rebuild restart logs logs-ls ps clean nuke \
        s3-ls s3-upload s3-sync s3-mb \
        dynamo-ls dynamo-scan dynamo-query dynamo-get dynamo-count dynamo-items dynamo-init dynamo-reset \
        embed embed-all scaffold scaffold-prod deploy-bot deploy-bot-prod deploy-infra \
        package-streaming deploy-streaming \
        init server server-stop test-chat help

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
ENDPOINT    = http://localhost:4566
S3_BUCKET   = s3://bot-factory-data
AWS_FLAGS   = --endpoint-url=$(ENDPOINT)
AWS         = AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 aws $(AWS_FLAGS)
TABLE       ?= BotFactoryRAG
TABLES      = BotFactoryRAG BotFactoryHistory BotFactoryLogs

# ─────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Bot Factory — Available Commands"
	@echo "════════════════════════════════════════════════════════════"
	@echo "  Docker"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "up [reset=1]"                 "Start all containers + Flask (reset=1 drops DynamoDB tables)"
	@printf "  %-38s %s\n" "init"                         "Re-run S3 + DynamoDB init (after bounce)"
	@printf "  %-38s %s\n" "down"                         "Stop all containers + Flask"
	@printf "  %-38s %s\n" "build"                        "Build containers"
	@printf "  %-38s %s\n" "rebuild"                      "Full rebuild from scratch"
	@printf "  %-38s %s\n" "restart"                      "Restart all containers"
	@printf "  %-38s %s\n" "logs"                         "Tail all logs"
	@printf "  %-38s %s\n" "logs-ls"                      "Tail LocalStack logs"
	@printf "  %-38s %s\n" "ps"                           "Show container status"
	@printf "  %-38s %s\n" "server"                       "Start Flask dev server"
	@printf "  %-38s %s\n" "server-stop"                  "Stop Flask dev server"
	@echo ""
	@echo "  Testing"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "test-chat BOT={id} [MSG=\"..\"]" "Send a test message (default: hi)"
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
	@printf "  %-38s %s\n" "dynamo-init"                  "Create DynamoDB tables (skip existing)"
	@printf "  %-38s %s\n" "dynamo-reset"                 "Drop and recreate all DynamoDB tables"
	@printf "  %-38s %s\n" "dynamo-ls"                    "List all tables"
	@printf "  %-38s %s\n" "dynamo-count"                 "Item count (default: BotFactoryRAG)"
	@printf "  %-38s %s\n" "dynamo-scan"                  "Scan all items in a table"
	@printf "  %-38s %s\n" "dynamo-scan-bot bot={bot_id}" "Scan items for a specific bot"
	@printf "  %-38s %s\n" "dynamo-get pk={bot_id}_0"     "Get a single item by pk"
	@printf "  %-38s %s\n" "dynamo-keys"                  "Show all keys in a table"
	@printf "  %-38s %s\n" "dynamo-keys-bot bot={bot_id}" "Show keys for a specific bot"
	@echo ""
	@echo "  Data Loading (Local)"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "load-bot bot={bot_id}"        "Sync scripts/bots/{bot_id}/data/ to S3"
	@printf "  %-38s %s\n" "deploy-bot bot={bot_id}"      "Upload config.yml + prompt.yml to S3 (local)"
	@echo ""
	@echo "  Embeddings"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "embed BOT={bot_id}"           "Generate embeddings (local)"
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
	@echo "  Production Deployment"
	@echo "  ──────────────────────────────────────────────────────────"
	@printf "  %-38s %s\n" "deploy-infra"                 "Package Lambdas + deploy via Terraform"
	@printf "  %-38s %s\n" "deploy-streaming"             "Deploy streaming Lambda + Function URL"
	@printf "  %-38s %s\n" "deploy-bot-prod bot={bot_id}" "Deploy a bot to prod (S3 + embeddings)"
	@echo ""


# ─────────────────────────────────────────────────────────────
# Docker Compose
# ─────────────────────────────────────────────────────────────

up:
	docker compose up -d
	@echo "Waiting for LocalStack to be ready..."
	@sleep 5
ifeq ($(reset),1)
	$(MAKE) dynamo-reset
else
	$(MAKE) dynamo-init
endif
	$(MAKE) s3-init
	-$(MAKE) server-stop
	$(MAKE) server

down:
	docker compose down
	-$(MAKE) server-stop

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

server:
	LOCALSTACK_ENDPOINT=http://localhost:4566 python3 app.py & echo $$! > .flask.pid
	@sleep 1
	@echo "Flask running on http://localhost:8000 (PID: $$(cat .flask.pid))"

server-stop:
	@if [ -f .flask.pid ]; then \
		kill $$(cat .flask.pid) 2>/dev/null || true; \
		rm -f .flask.pid; \
	fi
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@echo "Flask stopped"

# ─────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────

test-chat:
	@test -n "$(BOT)" || (echo "Usage: make test-chat BOT={bot_id}" && exit 1)
	@curl -s -X POST http://localhost:8000/chat \
		-H "Content-Type: application/json" \
		-d '{"bot_id": "$(BOT)", "message": "$(or $(MSG),hi)"}' | python3 -m json.tool

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

dynamo-drop:
	@echo "Dropping DynamoDB tables..."
	@for table in $(TABLES); do \
		$(AWS) dynamodb delete-table --table-name $$table 2>/dev/null && echo "  ✓ $$table dropped" || echo "  - $$table not found"; \
	done
	@sleep 1

dynamo-create:
	@echo "Creating BotFactoryRAG..."
	@$(AWS) dynamodb create-table \
		--table-name BotFactoryRAG \
		--attribute-definitions \
			AttributeName=pk,AttributeType=S \
			AttributeName=bot_id,AttributeType=S \
		--key-schema AttributeName=pk,KeyType=HASH \
		--global-secondary-indexes '[{"IndexName":"bot_id-index","KeySchema":[{"AttributeName":"bot_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
		--billing-mode PAY_PER_REQUEST \
		>/dev/null 2>&1 && echo "  ✓ BotFactoryRAG created" || echo "  - BotFactoryRAG already exists"
	@echo "Creating BotFactoryHistory..."
	@$(AWS) dynamodb create-table \
		--table-name BotFactoryHistory \
		--attribute-definitions AttributeName=session_id,AttributeType=S \
		--key-schema AttributeName=session_id,KeyType=HASH \
		--billing-mode PAY_PER_REQUEST \
		>/dev/null 2>&1 && echo "  ✓ BotFactoryHistory created" || echo "  - BotFactoryHistory already exists"
	@echo "Creating BotFactoryLogs..."
	@$(AWS) dynamodb create-table \
		--table-name BotFactoryLogs \
		--attribute-definitions AttributeName=id,AttributeType=S \
		--key-schema AttributeName=id,KeyType=HASH \
		--billing-mode PAY_PER_REQUEST \
		>/dev/null 2>&1 && echo "  ✓ BotFactoryLogs created" || echo "  - BotFactoryLogs already exists"

dynamo-verify:
	@echo "Verifying tables..."
	@for table in $(TABLES); do \
		$(AWS) dynamodb describe-table --table-name $$table >/dev/null 2>&1 && echo "  ✓ $$table exists" || (echo "  ✗ $$table MISSING" && exit 1); \
	done

dynamo-init: dynamo-create dynamo-verify

dynamo-reset: dynamo-drop dynamo-create dynamo-verify

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
	  --expression-attribute-values '":prefix": {"S": "$(bot)_"}' \
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
	  --expression-attribute-values '":prefix": {"S": "$(bot)_"}' \
	  --projection-expression "pk" \
	  --output json | python3 -c "import sys,json; items=json.load(sys.stdin)['Items']; [print(i['pk']['S']) for i in items]"

# ─────────────────────────────────────────────────────────────
# Production Deployment
# ─────────────────────────────────────────────────────────────
PROD_BUCKET = $(shell terraform -chdir=terraform output -raw bucket_name 2>/dev/null)

## Deploy infra via Terraform (Lambda + API Gateway + S3 + DynamoDB)
deploy-infra:
	@echo "═══ Packaging Lambdas ═══"
	bash scripts/package_lambda.sh
	bash scripts/package_streaming.sh
	@echo ""
	@echo "═══ Terraform Init ═══"
	terraform -chdir=terraform init
	@echo ""
	@echo "═══ Terraform Apply ═══"
	terraform -chdir=terraform apply
	@echo ""
	@echo "═══ Done ═══"
	@terraform -chdir=terraform output

## Package streaming Lambda zip
package-streaming:
	bash scripts/package_streaming.sh

## Deploy streaming Lambda + Function URL
deploy-streaming: package-streaming
	@echo "═══ Deploying streaming Lambda ═══"
	terraform -chdir=terraform init
	terraform -chdir=terraform apply -target=aws_lambda_function.streaming -target=aws_lambda_function_url.streaming
	@echo ""
	@echo "═══ Stream URL ═══"
	@terraform -chdir=terraform output -raw streaming_url
	@echo ""

## Deploy a bot to prod (run per bot, re-run on data changes)
## Uploads config, prompt, data to S3 then generates embeddings
deploy-bot-prod:
	@test -n "$(bot)" || (echo "Usage: make deploy-bot-prod bot={bot_id}" && exit 1)
	@test -n "$(PROD_BUCKET)" || (echo "Error: Run 'make deploy-infra' first (no TF bucket found)" && exit 1)
	@echo "═══ Deploying bot: $(bot) → s3://$(PROD_BUCKET) ═══"
	@echo "→ Uploading config + prompt..."
	aws s3 cp scripts/bots/$(bot)/config.yml s3://$(PROD_BUCKET)/bots/$(bot)/config.yml
	aws s3 cp scripts/bots/$(bot)/prompt.yml s3://$(PROD_BUCKET)/bots/$(bot)/prompt.yml
	@echo "→ Syncing data..."
	aws s3 sync scripts/bots/$(bot)/data/ s3://$(PROD_BUCKET)/bots/$(bot)/data/
	@echo "→ Generating embeddings..."
	APP_ENV=production BOT_DATA_BUCKET=$(PROD_BUCKET) python3 -m factory.core.generate_embeddings $(bot) --force
	@echo "═══ Bot $(bot) deployed ═══"

# ─────────────────────────────────────────────────────────────
# Data Loading (Local)
# ─────────────────────────────────────────────────────────────

load-bot:
	@test -n "$(bot)" || (echo "Usage: make load-bot bot={bot_id}" && exit 1)
	$(AWS) s3 sync scripts/bots/$(bot)/data/ $(S3_BUCKET)/bots/$(bot)/data/

deploy-bot:
	@test -n "$(bot)" || (echo "Usage: make deploy-bot bot={bot_id}" && exit 1)
	$(AWS) s3 cp scripts/bots/$(bot)/config.yml $(S3_BUCKET)/bots/$(bot)/config.yml
	$(AWS) s3 cp scripts/bots/$(bot)/prompt.yml $(S3_BUCKET)/bots/$(bot)/prompt.yml

# ─────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────

embed:
	@test -n "$(BOT)" || (echo "Usage: make embed BOT={bot_id}" && exit 1)
	PYTHONDONTWRITEBYTECODE=1 python3 -m factory.core.generate_embeddings $(BOT) --force

embed-force:
	@test -n "$(bot)" || (echo "Usage: make embed-force bot={bot_id}" && exit 1)
	python3 -m factory.core.generate_embeddings $(bot) --force

embed-prod:
	@test -n "$(bot)" || (echo "Usage: make embed-prod bot={bot_id}" && exit 1)
	@test -n "$(PROD_BUCKET)" || (echo "Error: Run 'make deploy-infra' first" && exit 1)
	APP_ENV=production BOT_DATA_BUCKET=$(PROD_BUCKET) python3 -m factory.core.generate_embeddings $(bot) --force

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
