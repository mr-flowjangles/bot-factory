#!/bin/bash
set -e

# ── Mode detection ─────────────────────────────────────────────────────────────
if [[ "$1" == "--aws" ]]; then
    ENDPOINT=""
    AWS_ARGS=""
    echo "Mode: AWS"
else
    ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localstack:4566}"
    AWS_ARGS="--endpoint-url=$ENDPOINT"
    echo "Mode: LOCAL (LocalStack @ $ENDPOINT)"
    echo "Waiting for LocalStack to be ready..."
    sleep 3
fi

REGION="us-east-1"

# ── Helper ─────────────────────────────────────────────────────────────────────
create_table() {
    local name=$1
    local extra_args=${@:2}

    echo "Creating $name table..."
    aws dynamodb create-table \
        --table-name "$name" \
        --region "$REGION" \
        $AWS_ARGS \
        $extra_args 2>/dev/null \
    && echo "  $name created" \
    || echo "  $name already exists"
}

# ── Tables ─────────────────────────────────────────────────────────────────────

# Stores embeddings for all bots (partitioned by bot_id field)
# Stores embeddings for all bots (GSI on bot_id for efficient per-bot queries)
create_table BotFactoryRAG \
    --attribute-definitions \
        AttributeName=pk,AttributeType=S \
        AttributeName=bot_id,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --global-secondary-indexes '[
        {
            "IndexName": "bot_id-index",
            "KeySchema": [{"AttributeName": "bot_id", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"}
        }
    ]' \
    --billing-mode PAY_PER_REQUEST


# Stores conversation history per session
create_table BotFactoryHistory \
    --attribute-definitions AttributeName=session_id,AttributeType=S \
    --key-schema AttributeName=session_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# Stores chat interaction logs
create_table BotFactoryLogs \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "DynamoDB initialization complete!"
