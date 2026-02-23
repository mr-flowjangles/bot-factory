#!/bin/bash
# =============================================================================
# init-dynamodb.sh
#
# Creates required DynamoDB tables.
# Works with both LocalStack (local dev) and real AWS.
#
# Local dev:  run automatically via docker-compose
# AWS:        run once manually: ./scripts/init-dynamodb.sh --aws
# =============================================================================

set -e

# ── Mode detection ─────────────────────────────────────────────────────────────
if [[ "$1" == "--aws" ]]; then
    ENDPOINT=""
    AWS_ARGS=""
    echo "Mode: AWS"
else
    ENDPOINT="http://localstack:4566"
    AWS_ARGS="--endpoint-url=$ENDPOINT"
    echo "Mode: LOCAL (LocalStack @ $ENDPOINT)"
    echo "Waiting for LocalStack to be ready..."
    sleep 5
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
create_table ChatbotRAG \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# Stores conversation history per session
create_table ChatHistory \
    --attribute-definitions AttributeName=session_id,AttributeType=S \
    --key-schema AttributeName=session_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "DynamoDB initialization complete!"
