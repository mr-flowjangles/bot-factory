#!/bin/bash
# =============================================================================
# s3_data.sh
#
# Manages bot YAML data files in S3.
# Works with both LocalStack (local dev) and real AWS.
#
# Commands:
#   ./s3_data.sh create-bucket          # create the bucket (first time only)
#   ./s3_data.sh sync <bot_id>          # upload one bot's data files
#   ./s3_data.sh sync-all               # upload all bots' data files
#   ./s3_data.sh list <bot_id>          # list files in S3 for a bot
#   ./s3_data.sh diff <bot_id>          # show what would change (dry run)
#
# Env vars:
#   AWS_ENDPOINT_URL   set to http://localhost:4566 for LocalStack, unset for AWS
#   AWS_REGION         default: us-east-1
#
# Bucket name is derived automatically from your AWS account ID + region
# so it is guaranteed unique. It is saved to .env.bucket for reuse.
# =============================================================================

set -e

REGION="${AWS_REGION:-us-east-1}"
BOTS_DIR="factory/bots"
ENV_FILE=".env.bucket"

# ── Detect local vs AWS ────────────────────────────────────────────────────────

if [[ -n "$AWS_ENDPOINT_URL" ]]; then
    MODE="local"
    AWS_ARGS="--endpoint-url $AWS_ENDPOINT_URL"
    echo "Mode: LOCAL (LocalStack @ $AWS_ENDPOINT_URL)"
else
    MODE="aws"
    AWS_ARGS=""
    echo "Mode: AWS"
fi

# ── Derive or load bucket name ─────────────────────────────────────────────────

get_bucket_name() {
    # Check if already resolved and saved
    if [[ -f "$ENV_FILE" ]]; then
        source "$ENV_FILE"
        if [[ -n "$BOT_DATA_BUCKET" ]]; then
            echo "$BOT_DATA_BUCKET"
            return
        fi
    fi

    if [[ "$MODE" == "local" ]]; then
        BUCKET="bot-factory-data-local"
    else
        # Use account ID for guaranteed global uniqueness
        ACCOUNT_ID=$(aws sts get-caller-identity $AWS_ARGS --query Account --output text)
        BUCKET="bot-factory-data-${ACCOUNT_ID}-${REGION}"
    fi

    # Save for reuse and for other scripts (generate_embeddings, build_lambda)
    echo "BOT_DATA_BUCKET=$BUCKET" > "$ENV_FILE"
    echo "$BUCKET"
}

BUCKET=$(get_bucket_name)
echo "Bucket: $BUCKET"
echo ""

# ── Commands ───────────────────────────────────────────────────────────────────

cmd_create_bucket() {
    echo "Creating bucket: $BUCKET"

    # Check if it already exists
    if aws s3api head-bucket --bucket "$BUCKET" $AWS_ARGS 2>/dev/null; then
        echo "  Bucket already exists — nothing to do."
        return
    fi

    if [[ "$REGION" == "us-east-1" ]]; then
        # us-east-1 does not accept a LocationConstraint
        aws s3api create-bucket \
            --bucket "$BUCKET" \
            --region "$REGION" \
            $AWS_ARGS
    else
        aws s3api create-bucket \
            --bucket "$BUCKET" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION" \
            $AWS_ARGS
    fi

    # Block all public access (good default for data buckets)
    if [[ "$MODE" == "aws" ]]; then
        aws s3api put-public-access-block \
            --bucket "$BUCKET" \
            --public-access-block-configuration \
              BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
            $AWS_ARGS
        echo "  Public access blocked."
    fi

    echo "  Done — bucket ready."
    echo ""
    echo "  Add this to your Lambda env vars and shell profile:"
    echo "    export BOT_DATA_BUCKET=$BUCKET"
    echo ""
    echo "  Or source it directly:"
    echo "    source $ENV_FILE"
}

cmd_sync() {
    local bot_id="$1"
    if [[ -z "$bot_id" ]]; then
        echo "Usage: ./s3_data.sh sync <bot_id>"
        exit 1
    fi

    local local_path="$BOTS_DIR/$bot_id/data"
    local s3_path="s3://$BUCKET/bots/$bot_id/data/"

    if [[ ! -d "$local_path" ]]; then
        echo "Error: $local_path not found"
        exit 1
    fi

    echo "Syncing bot '$bot_id'..."
    echo "  $local_path → $s3_path"
    echo ""

    aws s3 sync "$local_path" "$s3_path" \
        --exclude "*" \
        --include "*.yml" \
        --include "*.yaml" \
        $AWS_ARGS

    echo ""
    echo "  Done."
}

cmd_sync_all() {
    echo "Syncing all bots in $BOTS_DIR..."
    echo ""

    if [[ ! -d "$BOTS_DIR" ]]; then
        echo "Error: $BOTS_DIR not found"
        exit 1
    fi

    for bot_dir in "$BOTS_DIR"/*/; do
        bot_id=$(basename "$bot_dir")
        data_dir="$bot_dir/data"
        if [[ -d "$data_dir" ]]; then
            cmd_sync "$bot_id"
        else
            echo "  Skipping '$bot_id' — no data/ folder"
        fi
    done
}

cmd_list() {
    local bot_id="$1"
    if [[ -z "$bot_id" ]]; then
        echo "Usage: ./s3_data.sh list <bot_id>"
        exit 1
    fi
    echo "Files in S3 for bot '$bot_id':"
    aws s3 ls "s3://$BUCKET/bots/$bot_id/data/" $AWS_ARGS
}

cmd_diff() {
    local bot_id="$1"
    if [[ -z "$bot_id" ]]; then
        echo "Usage: ./s3_data.sh diff <bot_id>"
        exit 1
    fi

    local local_path="$BOTS_DIR/$bot_id/data"
    local s3_path="s3://$BUCKET/bots/$bot_id/data/"

    echo "Dry run — what would change for bot '$bot_id':"
    echo ""

    aws s3 sync "$local_path" "$s3_path" \
        --exclude "*" \
        --include "*.yml" \
        --include "*.yaml" \
        --dryrun \
        $AWS_ARGS
}

# ── Dispatch ───────────────────────────────────────────────────────────────────

case "$1" in
    create-bucket) cmd_create_bucket ;;
    sync)          cmd_sync "$2" ;;
    sync-all)      cmd_sync_all ;;
    list)          cmd_list "$2" ;;
    diff)          cmd_diff "$2" ;;
    *)
        echo "Usage: ./s3_data.sh <command> [bot_id]"
        echo ""
        echo "Commands:"
        echo "  create-bucket       Create the S3 bucket (first time only)"
        echo "  sync <bot_id>       Upload one bot's YAML files to S3"
        echo "  sync-all            Upload all bots' YAML files to S3"
        echo "  list <bot_id>       List files currently in S3 for a bot"
        echo "  diff <bot_id>       Show what would change without uploading"
        echo ""
        echo "Local dev:  export AWS_ENDPOINT_URL=http://localhost:4566"
        echo "AWS:        unset AWS_ENDPOINT_URL"
        exit 1
        ;;
esac
