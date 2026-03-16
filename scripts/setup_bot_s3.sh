#!/bin/bash
# setup_bot_s3.sh
# Sets up S3 structure for all bots in scripts/bots/ in LocalStack.
# Usage: ./scripts/setup_bot_s3.sh

set -e

ENDPOINT="http://localhost:4566"
REGION="${AWS_REGION:-us-east-1}"
BUCKET="bot-factory-data"
AWS_CMD="aws --endpoint-url=$ENDPOINT --region $REGION"
BOTS_DIR="scripts/bots"

# Create bucket if it doesn't exist
echo "Ensuring bucket exists: $BUCKET"
$AWS_CMD s3 mb s3://$BUCKET 2>/dev/null || echo "  Bucket already exists"
echo ""

# Loop through all bot directories
for BOT_PATH in $BOTS_DIR/*/; do
    BOT_ID=$(basename "$BOT_PATH")
    echo "Setting up bot: $BOT_ID"

    # Create folder placeholders
    $AWS_CMD s3api put-object --bucket $BUCKET --key bots/$BOT_ID/ > /dev/null
    $AWS_CMD s3api put-object --bucket $BUCKET --key bots/$BOT_ID/data/ > /dev/null
    echo "  Created folder structure"

    # Upload config and prompt if they exist
    if [ -f "$BOT_PATH/config.yml" ]; then
        $AWS_CMD s3 cp $BOT_PATH/config.yml s3://$BUCKET/bots/$BOT_ID/config.yml
        echo "  Uploaded config.yml"
    else
        echo "  WARNING: no config.yml found"
    fi

    if [ -f "$BOT_PATH/prompt.yml" ]; then
        $AWS_CMD s3 cp $BOT_PATH/prompt.yml s3://$BUCKET/bots/$BOT_ID/prompt.yml
        echo "  Uploaded prompt.yml"
    else
        echo "  WARNING: no prompt.yml found"
    fi

    # Sync data files if any exist
    if [ "$(ls -A $BOT_PATH/data/ 2>/dev/null)" ]; then
        $AWS_CMD s3 sync $BOT_PATH/data/ s3://$BUCKET/bots/$BOT_ID/data/
        echo "  Synced data files"
    else
        echo "  No data files (add YAMLs to $BOT_PATH/data/)"
    fi

    echo ""
done

echo "All bots loaded. Verifying:"
$AWS_CMD s3 ls s3://$BUCKET/bots/ --recursive
