#!/bin/bash
set -e

# ── Flags ──────────────────────────────────────────────────────────────────────
DROP_TABLES=false
USE_AWS=false

for arg in "$@"; do
    case $arg in
        --aws) USE_AWS=true ;;
        --drop) DROP_TABLES=true ;;
    esac
done

# ── Mode detection ─────────────────────────────────────────────────────────────
if [[ "$USE_AWS" == "true" ]]; then
    AWS_ARGS=""
    echo "Mode: AWS"
else
    ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost:4566}"
    AWS_ARGS="--endpoint-url=$ENDPOINT"
    echo "Mode: LOCAL (LocalStack @ $ENDPOINT)"
    sleep 2
fi

REGION="us-east-1"

# ── Helpers ────────────────────────────────────────────────────────────────────
drop_table() {
    local name=$1
    echo "Dropping $name..."
    if aws dynamodb delete-table --table-name "$name" --region "$REGION" $AWS_ARGS 2>/dev/null; then
        echo "  ✓ $name dropped"
        sleep 1  # Give LocalStack a moment
    else
        echo "  - $name didn't exist"
    fi
}

create_table() {
    local name=$1
    shift
    local extra_args="$@"

    echo "Creating $name..."
    
    # Run create and capture both stdout and stderr
    local output
    if output=$(aws dynamodb create-table \
        --table-name "$name" \
        --region "$REGION" \
        $AWS_ARGS \
        $extra_args 2>&1); then
        echo "  ✓ $name created"
    else
        if echo "$output" | grep -q "ResourceInUseException"; then
            echo "  - $name already exists"
        else
            echo "  ✗ $name FAILED:"
            echo "$output"
            exit 1
        fi
    fi
}

# ── Drop tables if requested ───────────────────────────────────────────────────
if [[ "$DROP_TABLES" == "true" ]]; then
    echo ""
    echo "═══ Dropping existing tables ═══"
    drop_table BotFactoryRAG
    drop_table BotFactoryHistory
    drop_table BotFactoryLogs
    echo ""
fi

# ── Create tables ──────────────────────────────────────────────────────────────
echo "═══ Creating tables ═══"

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

create_table BotFactoryHistory \
    --attribute-definitions AttributeName=session_id,AttributeType=S \
    --key-schema AttributeName=session_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

create_table BotFactoryLogs \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# ── Verify ─────────────────────────────────────────────────────────────────────
echo ""
echo "═══ Verifying tables ═══"
TABLES=$(aws dynamodb list-tables --region "$REGION" $AWS_ARGS --query 'TableNames' --output text)
echo "Tables: $TABLES"

for required in BotFactoryRAG BotFactoryHistory BotFactoryLogs; do
    if echo "$TABLES" | grep -q "$required"; then
        echo "  ✓ $required exists"
    else
        echo "  ✗ $required MISSING"
        exit 1
    fi
done

echo ""
echo "DynamoDB initialization complete!"
