#!/bin/bash
# sync_s3_data.sh
# Pulls new data files from production S3 that don't exist locally.
# Designed for self-heal generated files that only live in S3.
#
# Usage:
#   ./scripts/sync_s3_data.sh                  # sync all bots
#   ./scripts/sync_s3_data.sh the-fret-detective  # sync one bot

set -e

REGION="${AWS_REGION:-us-east-1}"
BOTS_DIR="scripts/bots"

# Get prod bucket from Terraform output
PROD_BUCKET=$(terraform -chdir=terraform output -raw bucket_name 2>/dev/null || true)

if [ -z "$PROD_BUCKET" ]; then
    echo "⚠️  No production bucket found (terraform output missing). Skipping S3 sync."
    exit 0
fi

echo "═══ Syncing data from s3://$PROD_BUCKET ═══"
echo ""

sync_bot() {
    local BOT_ID=$1
    local LOCAL_DIR="$BOTS_DIR/$BOT_ID/data"
    local S3_PREFIX="bots/$BOT_ID/data/"

    # Ensure local data dir exists
    mkdir -p "$LOCAL_DIR"

    # List S3 files (just filenames)
    S3_FILES=$(aws s3 ls "s3://$PROD_BUCKET/$S3_PREFIX" --region "$REGION" 2>/dev/null | awk '{print $NF}' | grep '\.yml$' || true)

    if [ -z "$S3_FILES" ]; then
        echo "  $BOT_ID: no data files in S3"
        return
    fi

    S3_COUNT=$(echo "$S3_FILES" | wc -l | tr -d ' ')
    LOCAL_COUNT=$(ls "$LOCAL_DIR"/*.yml 2>/dev/null | wc -l | tr -d ' ')

    if [ "$S3_COUNT" -eq "$LOCAL_COUNT" ]; then
        echo "  $BOT_ID: in sync ($S3_COUNT files)"
        return
    fi

    echo "  $BOT_ID: S3 has $S3_COUNT files, local has $LOCAL_COUNT"

    # Find and pull files that exist in S3 but not locally
    PULLED=0
    for FILE in $S3_FILES; do
        if [ ! -f "$LOCAL_DIR/$FILE" ]; then
            echo "    ↓ pulling $FILE"
            aws s3 cp "s3://$PROD_BUCKET/$S3_PREFIX$FILE" "$LOCAL_DIR/$FILE" --region "$REGION" > /dev/null
            PULLED=$((PULLED + 1))
        fi
    done

    if [ "$PULLED" -gt 0 ]; then
        echo "  $BOT_ID: pulled $PULLED new file(s)"
    fi
}

# Sync specific bot or all bots
if [ -n "$1" ]; then
    sync_bot "$1"
else
    for BOT_PATH in $BOTS_DIR/*/; do
        BOT_ID=$(basename "$BOT_PATH")
        sync_bot "$BOT_ID"
    done
fi

echo ""
echo "═══ Sync complete ═══"
